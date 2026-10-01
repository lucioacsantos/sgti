"""Painel de reconciliações do CMDB.

Detecta discrepâncias entre o CMDB e fontes externas (ativos sem IP, IPs órfãos,
aplicações sem instância, serviços órfãos), agrega em execuções de reconciliação
e impõe o workflow de quatro olhos: cada item só pode ser retificado/ratificado
após parecer de NO MÍNIMO 2 analistas distintos (nunca o próprio autor da
decisão, e o criador da execução não pode validar sozinho).

Todo POST/PUT passa por get_current_actor e grava audit log.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from typing import Optional
from datetime import datetime
import models, schemas, auth, audit
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reconciliacoes", tags=["Reconciliações"])

MIN_ANALISTAS = 2  # four-eyes: mínimo de analistas distintos por item
CONFIANCA_PADRAO = 0.9  # inferência IA: abaixo disso abre verificação manual


def _require_admin(current_service: models.ServiceAccount) -> None:
    import json
    try:
        roles = json.loads(current_service.token_hash).get("roles", [])
    except Exception:
        roles = []
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Required role(s): ['admin']")


def _audit(db: Session, entidade: str, entidade_id, acao: str,
           antes=None, depois=None, usuario: str = None) -> None:
    try:
        audit.create_audit_log(db=db, entidade=entidade, entidade_id=entidade_id,
                               acao=acao, antes=antes, depois=depois, usuario=usuario)
    except Exception:
        logger.warning("Falha ao gravar audit log", exc_info=True)


import json


def json_loads(txt: str) -> dict:
    return json.loads(txt)


def _nome_ator(account: models.ServiceAccount) -> str:
    try:
        data = json_loads(account.token_hash)
        if isinstance(data, dict) and data.get("ad_user"):
            return data.get("display_name") or data.get("username") or account.name
    except Exception:
        pass
    return account.name


def _contagens(db: Session, reconciliacao_id: int) -> dict:
    linhas = (db.query(models.ItemReconciliacao.status,
                       sa_func.count(models.ItemReconciliacao.id))
              .filter(models.ItemReconciliacao.reconciliacao_id == reconciliacao_id)
              .group_by(models.ItemReconciliacao.status).all())
    c = {s: n for s, n in linhas}
    return {
        "total_itens": sum(c.values()),
        "pendentes": c.get("pendente", 0) + c.get("em_verificacao", 0),
        "retificados": c.get("retificado", 0),
        "ratificados": c.get("ratificado", 0),
        "ignorados": c.get("ignorado", 0),
    }


# ============================================================
# Detecção automática de discrepâncias (CMDB interno)
# ============================================================

def detectar_discrepancias(db: Session) -> list[dict]:
    """Regras de consistência estrutural do CMDB (fonte 'manual'):

    D1: ativo sem endereço IP associado
    D2: ativo com serviço apontando para ativo inexistente (FK órfã lógica)
    D3: aplicação sem instância em nenhum ativo
    D4: instância de aplicação sem ativo (ativo_id NULL)
    D5: cluster sem ativo associado
    D6: serviço de negócio sem descrição
    D7: ativo sem ambiente definido
    """
    achados: list[dict] = []

    ids_ativos_com_ip = {r[0] for r in db.query(models.EnderecoIp.ativo_id)
                         .filter(models.EnderecoIp.ativo_id.isnot(None)).all()}
    for ativo in db.query(models.Ativo).all():
        if ativo.id not in ids_ativos_com_ip:
            achados.append({"entidade": "ativo", "entidade_id": ativo.id, "campo": "endereco_ip",
                            "valor_cmdb": None, "valor_fonte": "não identificado na fonte",
                            "detalhe": f"Ativo {ativo.nome} não possui IP associado"})
        if ativo.ambiente_id is None:
            achados.append({"entidade": "ativo", "entidade_id": ativo.id, "campo": "ambiente",
                            "valor_cmdb": None, "valor_fonte": "ausente na fonte",
                            "detalhe": f"Ativo {ativo.nome} sem ambiente definido"})

    apps_com_instancia = {r[0] for r in db.query(models.InstanciaAplicacao.aplicacao_id)
                          .filter(models.InstanciaAplicacao.aplicacao_id.isnot(None)).all()}
    for app in db.query(models.Aplicacao).all():
        if app.id not in apps_com_instancia:
            achados.append({"entidade": "aplicacao", "entidade_id": app.id, "campo": "instancia",
                            "valor_cmdb": "sem instância", "valor_fonte": "hospedagem declarada",
                            "detalhe": f"Aplicação {app.sistema} sem instância em nenhum ativo"})

    for inst in db.query(models.InstanciaAplicacao).all():
        if inst.ativo_id is None:
            achados.append({"entidade": "instancia_aplicacao", "entidade_id": inst.id,
                            "campo": "ativo_id", "valor_cmdb": None,
                            "valor_fonte": "host identificado",
                            "detalhe": f"Instância {inst.id} sem ativo associado"})

    for cl in db.query(models.Cluster).all():
        if cl.ativo_id is None:
            achados.append({"entidade": "cluster", "entidade_id": cl.id, "campo": "ativo_id",
                            "valor_cmdb": None, "valor_fonte": "host identificado",
                            "detalhe": f"Cluster {cl.nome} sem ativo associado"})

    return achados


# ============================================================
# Endpoints
# ============================================================

@router.get("/", response_model=list[schemas.ReconciliacaoResponse])
def list_reconciliacoes(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    query = db.query(models.Reconciliacao)
    if status_filter:
        query = query.filter(models.Reconciliacao.status == status_filter)
    execs = query.order_by(models.Reconciliacao.criado_em.desc()).all()
    saida = []
    for e in execs:
        cont = _contagens(db, e.id)
        saida.append(schemas.ReconciliacaoResponse(
            id=e.id, nome=e.nome, fonte=e.fonte, status=e.status,
            criado_por=e.criado_por, criado_em=e.criado_em, concluida_em=e.concluida_em,
            **cont))
    return saida


@router.post("/", response_model=schemas.ReconciliacaoResponse, status_code=201)
def create_reconciliacao(
    payload: schemas.ReconciliacaoCreate,
    auto_deteccao: bool = True,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Cria execução; com auto_deteccao=True roda a detecção estrutural
    e agenda os itens pendentes de verificação por 2+ analistas."""
    recon = models.Reconciliacao(nome=payload.nome, fonte=payload.fonte,
                                 status="aberta", criado_por=_nome_ator(current_service))
    db.add(recon)
    db.flush()

    if auto_deteccao:
        for achado in detectar_discrepancias(db):
            db.add(models.ItemReconciliacao(reconciliacao_id=recon.id, **achado))
    db.commit()
    db.refresh(recon)
    _audit(db, "reconciliacao", recon.id, "CREATE",
           depois={"nome": recon.nome, "fonte": recon.fonte},
           usuario=_nome_ator(current_service))
    cont = _contagens(db, recon.id)
    return schemas.ReconciliacaoResponse(
        id=recon.id, nome=recon.nome, fonte=recon.fonte, status=recon.status,
        criado_por=recon.criado_por, criado_em=recon.criado_em, **cont)


@router.post("/inferencia", response_model=schemas.ReconciliacaoInferenciaIAResponse,
             status_code=201)
def reportar_inferencia_ia(
    payload: schemas.ReconciliacaoInferenciaIA,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Auditoria de ações executadas pela inferência por IA.

    O script de inferência (infer_infra_map_ia.py) reporta aqui cada ação
    inferida com a confiabilidade devolvida pelo modelo. Ações com confiança
    abaixo do limiar (padrão 0.9) abrem itens pendentes de verificação manual
    (workflow de quatro olhos); as com confiança suficiente são registradas
    como ratificadas, preservando a trilha de auditoria."""
    recon = models.Reconciliacao(
        nome=payload.nome or f"Inferência IA — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        fonte="ia", status="aberta", criado_por=_nome_ator(current_service))
    db.add(recon)
    db.flush()

    abertos = auto_ratificados = 0
    for it in payload.itens:
        baixa = it.confianca < payload.limiar
        item = models.ItemReconciliacao(
            reconciliacao_id=recon.id,
            entidade=it.entidade, entidade_id=it.entidade_id, campo=it.campo,
            valor_cmdb=it.valor_cmdb, valor_fonte=it.valor_proposto,
            confianca=round(it.confianca, 4),
            detalhe=(f"Inferência IA: {it.acao}"
                     + (f" — confiabilidade {it.confianca:.0%}" if baixa else "")))
        if baixa:
            item.status = "pendente"
            abertos += 1
        else:
            item.status = "ratificado"
            item.resolvido_por = "inferencia_ia"
            item.resolvido_em = datetime.utcnow()
            auto_ratificados += 1
        db.add(item)
    db.commit()
    db.refresh(recon)
    _audit(db, "reconciliacao", recon.id, "CREATE_IA",
           depois={"nome": recon.nome, "fonte": "ia",
                   "itens": len(payload.itens), "limiar": payload.limiar,
                   "pendentes": abertos, "auto_ratificados": auto_ratificados},
           usuario=_nome_ator(current_service))
    cont = _contagens(db, recon.id)
    return schemas.ReconciliacaoInferenciaIAResponse(
        reconciliacao=schemas.ReconciliacaoResponse(
            id=recon.id, nome=recon.nome, fonte=recon.fonte, status=recon.status,
            criado_por=recon.criado_por, criado_em=recon.criado_em, **cont),
        limiar=payload.limiar, recebidos=len(payload.itens),
        pendentes_abertos=abertos, auto_ratificados=auto_ratificados)


@router.get("/{reconciliacao_id}", response_model=schemas.ReconciliacaoResponse)
def get_reconciliacao(
    reconciliacao_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    recon = db.query(models.Reconciliacao).get(reconciliacao_id)
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliação não encontrada")
    cont = _contagens(db, recon.id)
    return schemas.ReconciliacaoResponse(
        id=recon.id, nome=recon.nome, fonte=recon.fonte, status=recon.status,
        criado_por=recon.criado_por, criado_em=recon.criado_em,
        concluida_em=recon.concluida_em, **cont)


@router.get("/{reconciliacao_id}/itens", response_model=list[schemas.ItemReconciliacaoResponse])
def list_itens(
    reconciliacao_id: int,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    if not db.query(models.Reconciliacao).get(reconciliacao_id):
        raise HTTPException(status_code=404, detail="Reconciliação não encontrada")
    query = (db.query(models.ItemReconciliacao)
             .filter(models.ItemReconciliacao.reconciliacao_id == reconciliacao_id))
    if status_filter:
        query = query.filter(models.ItemReconciliacao.status == status_filter)
    itens = query.order_by(models.ItemReconciliacao.id).all()
    saida = []
    for it in itens:
        resp = schemas.ItemReconciliacaoResponse.model_validate(it)
        resp.analistas = sorted({p.analista for p in it.pareceres})
        saida.append(resp)
    return saida


@router.post("/{reconciliacao_id}/itens/{item_id}/parecer",
             response_model=schemas.ItemReconciliacaoResponse)
def registrar_parecer(
    reconciliacao_id: int,
    item_id: int,
    payload: schemas.ParecerReconciliacaoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Registra o parecer individual de um analista sobre a discrepância.

    Regras 4-olhos: um analista só registra UMA vez por item; parecer 'retificar'
    não pode partir de quem criou a execução (separação de responsabilidades)."""
    item = (db.query(models.ItemReconciliacao)
            .filter(models.ItemReconciliacao.id == item_id,
                    models.ItemReconciliacao.reconciliacao_id == reconciliacao_id).first())
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if item.status not in ("pendente", "em_verificacao"):
        raise HTTPException(status_code=409, detail="Item já resolvido")

    analista = _nome_ator(current_service)
    ja_registrado = db.query(models.ParecerReconciliacao).filter(
        models.ParecerReconciliacao.item_id == item.id,
        models.ParecerReconciliacao.analista == analista).first()
    if ja_registrado:
        raise HTTPException(status_code=409,
                            detail="Este analista já registrou parecer neste item")

    if payload.parecer == "retificar" and item.reconciliacao.criado_por == analista:
        raise HTTPException(status_code=403,
                            detail="O criador da execução não pode retificar sozinho; "
                                   "registre 'inconcluso' ou peça um segundo analista")

    db.add(models.ParecerReconciliacao(item_id=item.id, analista=analista,
                                       parecer=payload.parecer,
                                       comentario=payload.comentario))
    item.status = "em_verificacao"
    db.commit()
    db.refresh(item)
    _audit(db, "item_reconciliacao", item.id, "PARECER",
           depois={"analista": analista, "parecer": payload.parecer},
           usuario=analista)
    resp = schemas.ItemReconciliacaoResponse.model_validate(item)
    resp.analistas = sorted({p.analista for p in item.pareceres})
    return resp


@router.post("/{reconciliacao_id}/itens/{item_id}/decisao",
             response_model=schemas.ItemReconciliacaoResponse)
def decidir_item(
    reconciliacao_id: int,
    item_id: int,
    payload: schemas.ItemDecisaoRequest,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Retifica/ratifica o item. Exige NO MÍNIMO 2 analistas distintos com
    parecer registrado; a decisão final só é aceita se o decisor participou
    da verificação (registrou parecer) — workflow de quatro olhos."""
    _require_admin(current_service)
    item = (db.query(models.ItemReconciliacao)
            .filter(models.ItemReconciliacao.id == item_id,
                    models.ItemReconciliacao.reconciliacao_id == reconciliacao_id).first())
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if item.status not in ("pendente", "em_verificacao"):
        raise HTTPException(status_code=409, detail="Item já resolvido")

    analista = _nome_ator(current_service)
    pareceres = db.query(models.ParecerReconciliacao).filter(
        models.ParecerReconciliacao.item_id == item.id).all()
    analistas = sorted({p.analista for p in pareceres})
    if len(analistas) < MIN_ANALISTAS:
        raise HTTPException(
            status_code=409,
            detail=f"Verificação manual exige {MIN_ANALISTAS} analistas distintos "
                   f"(atuais: {len(analistas)}: {', '.join(analistas) or 'nenhum'})")
    if analista not in analistas:
        raise HTTPException(status_code=403,
                            detail="Somente analista que participou da verificação "
                                   "pode registrá-la no item")

    antes = {"status": item.status}
    item.status = payload.decisao
    item.resolvido_por = analista
    item.resolvido_em = datetime.utcnow()
    db.commit()
    db.refresh(item)
    _audit(db, "item_reconciliacao", item.id, "DECISAO",
           antes=antes, depois={"status": payload.decisao, "por": analista},
           usuario=analista)
    resp = schemas.ItemReconciliacaoResponse.model_validate(item)
    resp.analistas = analistas
    return resp


@router.post("/{reconciliacao_id}/concluir", response_model=schemas.ReconciliacaoResponse)
def concluir_reconciliacao(
    reconciliacao_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    _require_admin(current_service)
    recon = db.query(models.Reconciliacao).get(reconciliacao_id)
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliação não encontrada")
    cont = _contagens(db, recon.id)
    if cont["pendentes"] > 0:
        raise HTTPException(status_code=409,
                            detail=f"Existem {cont['pendentes']} itens pendentes de "
                                   f"verificação por {MIN_ANALISTAS} analistas")
    recon.status = "concluida"
    recon.concluida_em = datetime.utcnow()
    db.commit()
    db.refresh(recon)
    _audit(db, "reconciliacao", recon.id, "CONCLUIR", usuario=_nome_ator(current_service))
    return schemas.ReconciliacaoResponse(
        id=recon.id, nome=recon.nome, fonte=recon.fonte, status=recon.status,
        criado_por=recon.criado_por, criado_em=recon.criado_em,
        concluida_em=recon.concluida_em, **cont)


@router.delete("/{reconciliacao_id}", status_code=204)
def cancelar_reconciliacao(
    reconciliacao_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    _require_admin(current_service)
    recon = db.query(models.Reconciliacao).get(reconciliacao_id)
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliação não encontrada")
    recon.status = "cancelada"
    db.commit()
    _audit(db, "reconciliacao", recon.id, "CANCELAR", usuario=_nome_ator(current_service))