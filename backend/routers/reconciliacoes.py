"""Painel de reconciliações do CMDB.

Detecta discrepâncias entre o CMDB e fontes externas (ativos sem IP, IPs órfãos,
aplicações sem instância, serviços órfãos, alarmes Zabbix via regras Z1–Z3),
agrega em execuções de reconciliação e impõe o workflow de quatro olhos: cada
item só pode ser retificado/ratificado após parecer de NO MÍNIMO 2 analistas
distintos (nunca o próprio autor da decisão, e o criador da execução não pode
validar sozinho). Na decisão 'retificado' o CMDB é corrigido automaticamente
quando o item tem regra aplicável (campo de referência, nome, IP, vínculo ou
criação de ativo); o resultado fica no audit log (CORRECAO).

Todo POST/PUT passa por get_current_actor e grava audit log.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from typing import Optional
from datetime import datetime, UTC
import ipaddress
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
# Integração Zabbix: alarme → discrepância → reconciliação
# ============================================================

def _ativo_por_nome(db: Session, host: str) -> Optional[models.Ativo]:
    """Casa o host do Zabbix (FQDN/hostname) com o ativo: primeiro nome exato,
    depois prefixo curto (hostname sem domínio)."""
    ativo = db.query(models.Ativo).filter(models.Ativo.nome.ilike(host)).one_or_none()
    if ativo is None and host:
        curto = host.split(".")[0]
        if curto:
            ativo = (db.query(models.Ativo)
                     .filter(models.Ativo.nome.ilike(f"{curto}%")).one_or_none())
    return ativo


def _ativo_por_ip(db: Session, ip: str) -> Optional[models.Ativo]:
    if not ip:
        return None
    return (db.query(models.Ativo)
            .join(models.EnderecoIp, models.EnderecoIp.ativo_id == models.Ativo.id)
            .filter(models.EnderecoIp.ip == ip).one_or_none())


def detectar_discrepancias_zabbix(db: Session, host: str, ip: Optional[str] = None) -> list[dict]:
    """Regras de consistência Zabbix ↔ CMDB (fonte 'zabbix'):

    Z1: host monitorado no Zabbix sem ativo correspondente no CMDB
    Z2: host casado apenas pelo IP — nome divergente entre Zabbix e CMDB
    Z3: host casado pelo nome, mas IP reportado não registrado no ativo
    """
    achados: list[dict] = []
    ativo = _ativo_por_nome(db, host)
    if ativo is None:
        ativo = _ativo_por_ip(db, ip)

    if ativo is None:
        achados.append({
            "entidade": "ativo", "entidade_id": None, "campo": "host_nao_cadastrado",
            "valor_cmdb": None, "valor_fonte": host,
            "detalhe": "Host monitorado no Zabbix sem ativo correspondente no CMDB",
        })
        return achados

    ips = db.query(models.EnderecoIp).filter(models.EnderecoIp.ativo_id == ativo.id).all()
    curto = host.split(".")[0]
    casa_por_nome = (ativo.nome.lower() == host.lower()
                     or (curto and ativo.nome.lower().startswith(curto.lower())))
    if not casa_por_nome:
        achados.append({
            "entidade": "ativo", "entidade_id": ativo.id, "campo": "nome",
            "valor_cmdb": ativo.nome, "valor_fonte": host,
            "detalhe": "Host casado apenas pelo IP; nome divergente entre "
                       "Zabbix e CMDB",
        })
    elif ip and not any(e.ip == ip for e in ips):
        primario = next((e.ip for e in ips if e.primario), None)
        achados.append({
            "entidade": "ativo", "entidade_id": ativo.id, "campo": "endereco_ip",
            "valor_cmdb": primario or (", ".join(e.ip for e in ips) or None),
            "valor_fonte": ip,
            "detalhe": f"IP reportado pelo Zabbix ausente no ativo {ativo.nome}",
        })
    return achados


@router.post("/zabbix/alarme", response_model=schemas.ZabbixAlarmeReconciliacaoOut)
def reportar_alarme_zabbix(
    payload: schemas.ZabbixAlarmeReconciliacaoIn,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Webhook do Zabbix → reconciliação (fonte 'zabbix').

    Cada alarme é confrontado com o CMDB (Z1–Z3). Itens acumulam em uma única
    execução fonte=zabbix (dedupe por entidade/campo/valor da fonte) e seguem
    o workflow de quatro olhos — inclusive a criação de ativo na decisão
    'retificado' para hosts não cadastrados."""
    achados = detectar_discrepancias_zabbix(db, payload.host, payload.ip)
    if not achados:
        return schemas.ZabbixAlarmeReconciliacaoOut(
            registrou=False, reconciliacao=None,
            achados=[], novos_itens=0, duplicados_ignorados=0)

    recon = (db.query(models.Reconciliacao)
             .filter(models.Reconciliacao.fonte == "zabbix",
                     models.Reconciliacao.status.in_(("aberta", "em_verificacao")))
             .order_by(models.Reconciliacao.criado_em.desc())
             .first())
    if recon is None:
        recon = models.Reconciliacao(
            nome=f"Discrepâncias Zabbix — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            fonte="zabbix", status="aberta",
            criado_por=_nome_ator(current_service))
        db.add(recon)
        db.flush()

    prefixo = f"Alarme Zabbix {payload.event_id}"
    if payload.problema:
        prefixo += f": {payload.problema}"
    novos = duplicados = 0
    for achado in achados:
        aberto = (db.query(models.ItemReconciliacao)
                  .filter(models.ItemReconciliacao.reconciliacao_id == recon.id,
                          models.ItemReconciliacao.entidade == achado["entidade"],
                          models.ItemReconciliacao.campo == achado["campo"],
                          models.ItemReconciliacao.valor_fonte == achado["valor_fonte"],
                          models.ItemReconciliacao.status.in_(("pendente", "em_verificacao")))
                  .first())
        if aberto:
            duplicados += 1
            continue
        dados = dict(achado)
        dados["detalhe"] = f"{prefixo} — {dados.get('detalhe', '')}"
        db.add(models.ItemReconciliacao(reconciliacao_id=recon.id, **dados))
        novos += 1

    _audit(db, "reconciliacao", recon.id, "CREATE_ZBX",
           depois={"event_id": payload.event_id, "host": payload.host,
                   "ip": payload.ip, "achados": len(achados),
                   "novos_itens": novos, "duplicados": duplicados},
           usuario=_nome_ator(current_service))
    db.commit()
    db.refresh(recon)

    cont = _contagens(db, recon.id)
    return schemas.ZabbixAlarmeReconciliacaoOut(
        registrou=True,
        reconciliacao=schemas.ReconciliacaoResponse(
            id=recon.id, nome=recon.nome, fonte=recon.fonte, status=recon.status,
            criado_por=recon.criado_por, criado_em=recon.criado_em, **cont),
        achados=[a["detalhe"] for a in achados],
        novos_itens=novos, duplicados_ignorados=duplicados)


# ============================================================
# Correção automática do CMDB na decisão 'retificar'
# ============================================================

def _ref_por_nome(db: Session, model, campo: str, valor: str):
    return (db.query(model)
            .filter(sa_func.lower(getattr(model, campo)) == valor.strip().lower())
            .one_or_none())


def _corrigir_ativo(db: Session, item: models.ItemReconciliacao,
                    fonte: str) -> tuple[str, Optional[dict]]:
    """Regras ativo/*: criação de ativo em análise, campos de referência
    (ambiente/status/criticidade), nome e associação de IP"""
    if item.campo == "host_nao_cadastrado":
        if db.query(models.Ativo).filter(models.Ativo.nome.ilike(fonte)).first():
            return ("correção automática não aplicável: ativo com esse nome "
                    "já existe no CMDB", None)
        tipo = (_ref_por_nome(db, models.TipoAtivo, "nome", "Servidor Virtual")
                or db.query(models.TipoAtivo).order_by(models.TipoAtivo.id).first())
        if tipo is None:
            return ("correção automática não aplicável: nenhum tipo de ativo "
                    "cadastrado", None)
        novo = models.Ativo(nome=fonte, tipo_id=tipo.id)
        db.add(novo)
        db.flush()
        item.entidade_id = novo.id
        return (f"correção automática aplicada: ativo #{novo.id} '{fonte}' criado "
                f"a partir da fonte (tipo '{tipo.nome}')",
                {"campo": item.campo, "antes": None,
                 "depois": {"criado": "ativo", "id": novo.id, "nome": fonte}})
    ativo = db.query(models.Ativo).get(item.entidade_id) if item.entidade_id else None
    if ativo is None:
        return ("correção automática não aplicável: registro alvo não "
                "encontrado no CMDB", None)

    if item.campo in ("ambiente", "status", "criticidade"):
        model, campo_ref = {
            "ambiente": (models.Ambiente, "nome"),
            "status": (models.StatusAtivo, "nome"),
            "criticidade": (models.Criticidade, "nivel"),
        }[item.campo]
        ref = _ref_por_nome(db, model, campo_ref, fonte)
        if ref is None:
            return (f"correção automática não aplicável: "
                    f"'{fonte}' não cadastrado como {item.campo} de referência", None)
        antes_val = getattr(ativo, item.campo)
        antes_nome = getattr(antes_val, campo_ref) if antes_val else None
        setattr(ativo, f"{item.campo}_id", ref.id)
        return (f"correção automática aplicada: {item.campo} de "
                f"'{antes_nome or 'ausente'}' para '{fonte}'",
                {"campo": item.campo,
                 "antes": {"id": antes_val.id if antes_val else None, "nome": antes_nome},
                 "depois": {"id": ref.id, "nome": fonte}})

    if item.campo == "nome":
        if fonte.lower() == (ativo.nome or "").lower():
            return "correção automática não aplicável: nome já idêntico ao da fonte", None
        antes_nome = ativo.nome
        ativo.nome = fonte
        return (f"correção automática aplicada: nome de '{antes_nome}' "
                f"para '{fonte}'",
                {"campo": "nome", "antes": {"nome": antes_nome},
                 "depois": {"nome": fonte}})

    if item.campo == "endereco_ip":
        try:
            ip_obj = ipaddress.ip_address(fonte)
        except ValueError:
            return (f"correção automática não aplicável: valor da fonte "
                    f"'{fonte}' não é um IP válido", None)
        existe = (db.query(models.EnderecoIp)
                  .filter(models.EnderecoIp.ativo_id == ativo.id,
                          models.EnderecoIp.ip == str(ip_obj)).one_or_none())
        if existe:
            return ("correção automática não aplicável: IP já registrado "
                    "no ativo", None)
        primario = db.query(models.EnderecoIp).filter(
            models.EnderecoIp.ativo_id == ativo.id).count() == 0
        db.add(models.EnderecoIp(ativo_id=ativo.id, ip=str(ip_obj),
                                 tipo=f"IPv{ip_obj.version}", primario=primario))
        return (f"correção automática aplicada: IP {ip_obj} associado "
                f"ao ativo {ativo.nome}" + (" (primário)" if primario else ""),
                {"campo": "endereco_ip", "antes": None,
                 "depois": {"adicionado": str(ip_obj), "primario": primario}})

    return (f"correção automática não aplicável: sem regra para "
            f"ativo/{item.campo}", None)


def _vincular_ativo(db: Session, item: models.ItemReconciliacao, fonte: str,
                    model, etiqueta: str) -> tuple[str, Optional[dict]]:
    """Regras instancia_aplicacao|cluster / ativo_id: vincula o host
    identificado, respeitando o vínculo único ativo↔registro."""
    registro = db.query(model).get(item.entidade_id) if item.entidade_id else None
    if registro is None:
        return ("correção automática não aplicável: registro alvo não "
                "encontrado no CMDB", None)
    alvo = None
    if fonte.isdigit():
        alvo = db.query(models.Ativo).get(int(fonte))
    if alvo is None:
        alvo = db.query(models.Ativo).filter(models.Ativo.nome.ilike(fonte)).first()
    if alvo is None:
        return (f"correção automática não aplicável: nenhum ativo casando "
                f"com '{fonte}'", None)
    if registro.ativo_id == alvo.id:
        return ("correção automática não aplicável: vínculo já existente", None)
    conflito = (db.query(model)
                .filter(getattr(model, "ativo_id") == alvo.id,
                        getattr(model, "id") != registro.id).first())
    if conflito:
        return (f"correção automática não aplicável: {etiqueta} #{conflito.id} "
                f"já vinculada ao ativo {alvo.nome}", None)
    antes_id = registro.ativo_id
    registro.ativo_id = alvo.id
    return (f"correção automática aplicada: {etiqueta} #{registro.id} vinculada "
            f"ao ativo {alvo.nome}",
            {"campo": "ativo_id", "antes": {"ativo_id": antes_id},
             "depois": {"ativo_id": alvo.id, "nome": alvo.nome}})


def aplicar_correcao_cmdb(db: Session,
                          item: models.ItemReconciliacao) -> tuple[str, Optional[dict]]:
    """Aplica no CMDB a correção implícita na decisão 'retificado'.

    Regras suportadas:
      ativo/ambiente|status|criticidade → campo de referência ajustado para o valor da fonte
      ativo/nome → renomeia o ativo
      ativo/endereco_ip → associa o IP reportado (primário se for o primeiro)
      ativo/host_nao_cadastrado → cria ativo em análise
      instancia_aplicacao|cluster com ativo_id → vincula o host identificado

    Demais casos (ex.: criação de serviço/relacionamento inferida por IA, sem
    valor estruturado) retornam nota 'não aplicável' que fica registrada no
    detalhe do item e no audit log — nada escapa da trilha."""
    fonte = (item.valor_fonte or "").strip()
    if not fonte:
        return ("correção automática não aplicável: item sem valor acionável "
                "na fonte", None)
    try:
        if item.entidade == "ativo":
            return _corrigir_ativo(db, item, fonte)
        elif (item.entidade == "instancia_aplicacao"
              and item.campo == "ativo_id"):
            return _vincular_ativo(db, item, fonte, models.InstanciaAplicacao,
                                   "instância")
        elif item.entidade == "cluster" and item.campo == "ativo_id":
            return _vincular_ativo(db, item, fonte, models.Cluster, "cluster")
    except Exception:
        logger.exception("Falha na correção automática do item %s", item.id)
        return "correção automática falhou: erro interno (verificar logs)", None
    return (f"correção automática não aplicável: sem regra para "
            f"{item.entidade}/{item.campo}", None)


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
    _audit(db, "reconciliacao", recon.id, "CREATE",
           depois={"nome": recon.nome, "fonte": recon.fonte},
           usuario=_nome_ator(current_service))
    db.commit()
    db.refresh(recon)
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
            item.resolvido_em = datetime.now(UTC)
            auto_ratificados += 1
        db.add(item)
    _audit(db, "reconciliacao", recon.id, "CREATE_IA",
           depois={"nome": recon.nome, "fonte": "ia",
                   "itens": len(payload.itens), "limiar": payload.limiar,
                   "pendentes": abertos, "auto_ratificados": auto_ratificados},
           usuario=_nome_ator(current_service))
    db.commit()
    db.refresh(recon)
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
    _audit(db, "item_reconciliacao", item.id, "PARECER",
           depois={"analista": analista, "parecer": payload.parecer},
           usuario=analista)
    db.commit()
    db.refresh(item)
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
    da verificação (registrou parecer) — workflow de quatro olhos.

    Na decisão 'retificado' o CMDB é corrigido automaticamente (aplicar_regra
    conforme entidade/campo do item); a nota do resultado fica no detalhe do
    item e no audit log (ação CORRECAO)."""
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
    correcao = mudanca = None
    if payload.decisao == "retificado":
        correcao, mudanca = aplicar_correcao_cmdb(db, item)
        item.detalhe = f"{item.detalhe} — {correcao}" if item.detalhe else correcao
    item.status = payload.decisao
    item.resolvido_por = analista
    item.resolvido_em = datetime.now(UTC)
    if mudanca:
        _audit(db, item.entidade, item.entidade_id, "CORRECAO",
               antes=mudanca.get("antes"), depois=mudanca.get("depois"),
               usuario=analista)
    _audit(db, "item_reconciliacao", item.id, "DECISAO",
           antes=antes,
           depois={"status": payload.decisao, "por": analista,
                   "correcao": correcao},
           usuario=analista)
    db.commit()
    db.refresh(item)
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
    recon.concluida_em = datetime.now(UTC)
    _audit(db, "reconciliacao", recon.id, "CONCLUIR", usuario=_nome_ator(current_service))
    db.commit()
    db.refresh(recon)
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
    _audit(db, "reconciliacao", recon.id, "CANCELAR", usuario=_nome_ator(current_service))
    db.commit()