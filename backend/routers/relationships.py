# Objetivo: CRUD idempotente e auditado de tipos de relacionamento e vínculos entre ativos.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
import models, schemas, auth, audit
from database import get_db
import logging

logger = logging.getLogger(__name__)


def _require_admin(current_service: models.ServiceAccount) -> None:
    """Verifica se o ator (usuário AD) possui perfil admin."""
    import json
    try:
        user_data = json.loads(current_service.token_hash)
        roles = user_data.get("roles", [])
    except Exception:
        roles = []
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Required role(s): ['admin']")


def _audit_change(db: Session, entidade: str, entidade_id, acao: str,
                  antes=None, depois=None, usuario: str = None) -> None:
    try:
        audit.create_audit_log(
            db=db, entidade=entidade, entidade_id=entidade_id, acao=acao,
            antes=antes, depois=depois, usuario=usuario)
        db.commit()
    except Exception:
        logger.warning("Falha ao gravar audit log", exc_info=True)

router = APIRouter(prefix="/tipos-relacionamento", tags=["Tipos de Relacionamento"])


@router.post("/", response_model=schemas.TipoRelacionamentoResponse, status_code=201)
def create_tipo_relacionamento(
    tipo: schemas.TipoRelacionamentoCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting relationship type", extra={"service_account": current_service.name, "tipo_nome": tipo.nome})
    dados = tipo.model_dump(exclude_unset=True)
    existente = db.query(models.TipoRelacionamento).filter(
        func.lower(models.TipoRelacionamento.nome) == tipo.nome.strip().lower()
    ).first()
    if existente:
        antes = audit.model_to_dict(existente)
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.commit()
        db.refresh(existente)
        _audit_change(db, "tipo_relacionamento", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_tipo = models.TipoRelacionamento(**dados)
    db.add(db_tipo)
    db.commit()
    db.refresh(db_tipo)
    _audit_change(db, "tipo_relacionamento", db_tipo.id, "CREATE",
                  depois=audit.model_to_dict(db_tipo), usuario=current_service.name)
    response.status_code = 201
    return db_tipo


@router.get("/", response_model=list[schemas.TipoRelacionamentoResponse])
def read_tipos_relacionamento(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing relationship types", extra={"service_account": current_service.name})
    return db.query(models.TipoRelacionamento).all()


@router.get("/{tipo_id}", response_model=schemas.TipoRelacionamentoResponse)
def read_tipo_relacionamento(
    tipo_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading relationship type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")
    return tipo


@router.put("/{tipo_id}", response_model=schemas.TipoRelacionamentoResponse)
def update_tipo_relacionamento(
    tipo_id: int,
    tipo: schemas.TipoRelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um tipo de relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")

    dados = tipo.model_dump(exclude_unset=True)
    antes = audit.model_to_dict(db_tipo)
    for campo, valor in dados.items():
        setattr(db_tipo, campo, valor)
    db.commit()
    db.refresh(db_tipo)
    _audit_change(db, "tipo_relacionamento", db_tipo.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_tipo), usuario=current_service.name)
    logger.info("Updating relationship type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    return db_tipo


@router.delete("/{tipo_id}", status_code=204)
def delete_tipo_relacionamento(
    tipo_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um tipo de relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")

    em_uso = db.query(models.Relacionamento).filter(models.Relacionamento.tipo_id == tipo_id).count()
    if em_uso > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Tipo em uso por {em_uso} relacionamento(s). Retifique-os antes de excluir.")

    antes = audit.model_to_dict(db_tipo)
    db.delete(db_tipo)
    db.commit()
    _audit_change(db, "tipo_relacionamento", tipo_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting relationship type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    return None


# ENDPOINTS DE RELACIONAMENTO
rel_router = APIRouter(prefix="/relacionamentos", tags=["Relacionamentos"])


@rel_router.get("/grafo", response_model=schemas.GrafoResponse)
def read_grafo_relacionamentos(
    ambiente_id: Optional[int] = None,
    tipo_ativo_id: Optional[int] = None,
    criticidade_id: Optional[int] = None,
    status_id: Optional[int] = None,
    tipo_relacionamento_id: Optional[int] = None,
    q: Optional[str] = None,
    grau_minimo: int = 0,
    incluir_isolados: bool = False,
    limite: int = 500,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Mapa de TI em grafo: nós = ativos, arestas = relacionamentos, com metadados e filtros.

    Filtros por atributo do ativo (ambiente/tipo/criticidade/status/busca), por tipo de
    relacionamento, grau mínimo de conexões, inclusão de nós isolados e limite de nós.
    Arestanda só permanece quando os dois extremos sobrevivem aos filtros de nós.
    """
    logger.debug(
        "Loading relationship graph",
        extra={
            "service_account": current_service.name,
            "ambiente_id": ambiente_id,
            "tipo_ativo_id": tipo_ativo_id,
            "tipo_relacionamento_id": tipo_relacionamento_id,
            "q": q,
        },
    )

    limite = max(1, min(limite, 5000))
    grau_minimo = max(0, grau_minimo)
    termo = q.strip().lower() if q and q.strip() else None

    # 1. Nós (ativos) com metadados para filtros/legenda
    ativos_query = db.query(models.Ativo).options(
        joinedload(models.Ativo.tipo),
        joinedload(models.Ativo.ambiente),
        joinedload(models.Ativo.status),
        joinedload(models.Ativo.criticidade),
    )
    if ambiente_id:
        ativos_query = ativos_query.filter(models.Ativo.ambiente_id == ambiente_id)
    if tipo_ativo_id:
        ativos_query = ativos_query.filter(models.Ativo.tipo_id == tipo_ativo_id)
    if criticidade_id:
        ativos_query = ativos_query.filter(models.Ativo.criticidade_id == criticidade_id)
    if status_id:
        ativos_query = ativos_query.filter(models.Ativo.status_id == status_id)
    if termo:
        padrao = f"%{termo}%"
        ativos_query = ativos_query.filter(
            func.lower(models.Ativo.nome).like(padrao)
            | func.lower(func.coalesce(models.Ativo.fqdn, "")).like(padrao)
            | func.lower(func.coalesce(models.Ativo.descricao, "")).like(padrao)
        )

    nos: dict[int, dict] = {}
    for ativo in ativos_query.all():
        nos[ativo.id] = {
            "id": ativo.id,
            "nome": ativo.nome,
            "descricao": ativo.descricao,
            "fqdn": ativo.fqdn,
            "tipo_id": ativo.tipo_id,
            "tipo": ativo.tipo.nome if ativo.tipo else None,
            "ambiente_id": ativo.ambiente_id,
            "ambiente": ativo.ambiente.nome if ativo.ambiente else None,
            "status_id": ativo.status_id,
            "status": ativo.status.nome if ativo.status else None,
            "criticidade_id": ativo.criticidade_id,
            "criticidade": ativo.criticidade.nivel if ativo.criticidade else None,
        }

    # 2. Arestas (relacionamentos) — filtro por tipo + corte pelos extremos sobreviventes
    rels_query = db.query(models.Relacionamento).options(
        joinedload(models.Relacionamento.tipo)
    )
    if tipo_relacionamento_id:
        rels_query = rels_query.filter(models.Relacionamento.tipo_id == tipo_relacionamento_id)

    edges: list[dict] = []
    for rel in rels_query.all():
        if rel.origem_id not in nos or rel.destino_id not in nos:
            continue
        edges.append({
            "id": rel.id,
            "origem_id": rel.origem_id,
            "destino_id": rel.destino_id,
            "tipo_id": rel.tipo_id,
            "tipo_nome": rel.tipo.nome if rel.tipo else None,
            "descricao": rel.descricao,
        })

    # 3. Corte iterativo por grau mínimo (remover um nó pode baixar o grau de outro)
    if grau_minimo > 0:
        for _ in range(10):
            graus: dict[int, int] = {no_id: 0 for no_id in nos}
            for aresta in edges:
                graus[aresta["origem_id"]] = graus.get(aresta["origem_id"], 0) + 1
                graus[aresta["destino_id"]] = graus.get(aresta["destino_id"], 0) + 1
            removidos = {no_id for no_id, grau in graus.items() if grau < grau_minimo}
            if not removidos:
                break
            nos = {no_id: dados for no_id, dados in nos.items() if no_id not in removidos}
            edges = [
                aresta for aresta in edges
                if aresta["origem_id"] in nos and aresta["destino_id"] in nos
            ]

    # 4. Isolados (sem vínculos) — opcional
    graus = {no_id: 0 for no_id in nos}
    for aresta in edges:
        graus[aresta["origem_id"]] = graus.get(aresta["origem_id"], 0) + 1
        graus[aresta["destino_id"]] = graus.get(aresta["destino_id"], 0) + 1
    if not incluir_isolados:
        nos = {no_id: dados for no_id, dados in nos.items() if graus[no_id] > 0}
        edges = [
            aresta for aresta in edges
            if aresta["origem_id"] in nos and aresta["destino_id"] in nos
        ]

    # 5. Limite de nós priorizando hubs (maior grau) e remoção das arestas órfãs
    nos_truncados = False
    if len(nos) > limite:
        ordenados = sorted(nos.items(), key=lambda item: (-graus.get(item[0], 0), item[1]["nome"]))
        nos = dict(ordenados[:limite])
        nos_truncados = True
        edges = [
            aresta for aresta in edges
            if aresta["origem_id"] in nos and aresta["destino_id"] in nos
        ]

    nodes_payload = []
    for no_id, dados in nos.items():
        nodes_payload.append({**dados, "grau": graus.get(no_id, 0)})
    nodes_payload.sort(key=lambda item: (-item["grau"], item["nome"]))
    edges.sort(key=lambda aresta: aresta["id"])

    # 6. Opções para os controles de filtro
    opcoes = schemas.GrafoOpcoes(
        ambientes=[
            schemas.GrafoOpcao(id=item.id, nome=item.nome)
            for item in db.query(models.Ambiente).order_by(models.Ambiente.nome).all()
        ],
        tipos_ativo=[
            schemas.GrafoOpcao(id=item.id, nome=item.nome)
            for item in db.query(models.TipoAtivo).order_by(models.TipoAtivo.nome).all()
        ],
        criticidades=[
            schemas.GrafoOpcao(id=item.id, nome=item.nivel)
            for item in db.query(models.Criticidade).order_by(models.Criticidade.nivel).all()
        ],
        status=[
            schemas.GrafoOpcao(id=item.id, nome=item.nome)
            for item in db.query(models.StatusAtivo).order_by(models.StatusAtivo.nome).all()
        ],
        tipos_relacionamento=[
            schemas.GrafoOpcao(id=item.id, nome=item.nome)
            for item in db.query(models.TipoRelacionamento).order_by(models.TipoRelacionamento.nome).all()
        ],
    )

    meta = schemas.GrafoMeta(
        total_nos=len(nodes_payload),
        total_arestas=len(edges),
        nos_truncados=nos_truncados,
        opcoes=opcoes,
    )
    logger.info(
        "Relationship graph ready",
        extra={
            "service_account": current_service.name,
            "nodes": len(nodes_payload),
            "edges": len(edges),
        },
    )
    return schemas.GrafoResponse(nodes=nodes_payload, edges=edges, meta=meta)


@rel_router.post("/", response_model=schemas.RelacionamentoResponse, status_code=201)
def create_relacionamento(
    rel: schemas.RelacionamentoCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting relationship", extra={"service_account": current_service.name, "origem_id": rel.origem_id, "destino_id": rel.destino_id, "tipo_id": rel.tipo_id})
    origem = db.query(models.Ativo).filter(models.Ativo.id == rel.origem_id).first()
    if not origem:
        raise HTTPException(status_code=404, detail=f"Ativo origem id={rel.origem_id} não encontrado")
    destino = db.query(models.Ativo).filter(models.Ativo.id == rel.destino_id).first()
    if not destino:
        raise HTTPException(status_code=404, detail=f"Ativo destino id={rel.destino_id} não encontrado")
    tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == rel.tipo_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail=f"Tipo relacionamento id={rel.tipo_id} não encontrado")

    dados = rel.model_dump(exclude_unset=True)
    existente = db.query(models.Relacionamento).filter(
        models.Relacionamento.origem_id == rel.origem_id,
        models.Relacionamento.destino_id == rel.destino_id,
        models.Relacionamento.tipo_id == rel.tipo_id,
    ).first()

    if existente:
        antes = audit.model_to_dict(existente)
        if "descricao" in dados:
            existente.descricao = dados["descricao"]
        db.commit()
        db.refresh(existente)
        _audit_change(db, "relacionamento", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_rel = models.Relacionamento(**dados)
    db.add(db_rel)
    db.commit()
    db.refresh(db_rel)
    _audit_change(db, "relacionamento", db_rel.id, "CREATE",
                  depois=audit.model_to_dict(db_rel), usuario=current_service.name)
    response.status_code = 201
    return db_rel


@rel_router.get("/", response_model=list[schemas.RelacionamentoResponse])
def read_relacionamentos(
    origem_id: Optional[int] = None,
    destino_id: Optional[int] = None,
    tipo_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing relationships", extra={"service_account": current_service.name, "origem_id": origem_id, "destino_id": destino_id, "tipo_id": tipo_id})
    query = db.query(models.Relacionamento).options(
        joinedload(models.Relacionamento.origem),
        joinedload(models.Relacionamento.destino),
        joinedload(models.Relacionamento.tipo)
    )
    if origem_id:
        query = query.filter(models.Relacionamento.origem_id == origem_id)
    if destino_id:
        query = query.filter(models.Relacionamento.destino_id == destino_id)
    if tipo_id:
        query = query.filter(models.Relacionamento.tipo_id == tipo_id)
    return query.order_by(models.Relacionamento.id).offset(skip).limit(min(limit, 5000)).all()


@rel_router.get("/{rel_id}", response_model=schemas.RelacionamentoResponse)
def read_relacionamento(
    rel_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading relationship", extra={"service_account": current_service.name, "rel_id": rel_id})
    rel = db.query(models.Relacionamento).options(
        joinedload(models.Relacionamento.origem),
        joinedload(models.Relacionamento.destino),
        joinedload(models.Relacionamento.tipo)
    ).filter(models.Relacionamento.id == rel_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")
    return rel


@rel_router.put("/{rel_id}", response_model=schemas.RelacionamentoResponse)
def update_relacionamento(
    rel_id: int,
    rel: schemas.RelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_rel = db.query(models.Relacionamento).filter(models.Relacionamento.id == rel_id).first()
    if not db_rel:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")

    dados = rel.model_dump(exclude_unset=True)
    if "origem_id" in dados and not db.query(models.Ativo).filter(models.Ativo.id == dados["origem_id"]).first():
        raise HTTPException(status_code=404, detail=f"Ativo origem id={dados['origem_id']} não encontrado")
    if "destino_id" in dados and not db.query(models.Ativo).filter(models.Ativo.id == dados["destino_id"]).first():
        raise HTTPException(status_code=404, detail=f"Ativo destino id={dados['destino_id']} não encontrado")
    if "tipo_id" in dados and not db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == dados["tipo_id"]).first():
        raise HTTPException(status_code=404, detail=f"Tipo relacionamento id={dados['tipo_id']} não encontrado")

    antes = audit.model_to_dict(db_rel)
    for campo, valor in dados.items():
        setattr(db_rel, campo, valor)
    db.commit()
    db.refresh(db_rel)
    _audit_change(db, "relacionamento", db_rel.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_rel), usuario=current_service.name)
    logger.info("Updating relationship", extra={"service_account": current_service.name, "rel_id": rel_id})
    return db_rel


@rel_router.delete("/{rel_id}", status_code=204)
def delete_relacionamento(
    rel_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_rel = db.query(models.Relacionamento).filter(models.Relacionamento.id == rel_id).first()
    if not db_rel:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")

    antes = audit.model_to_dict(db_rel)
    db.delete(db_rel)
    db.commit()
    _audit_change(db, "relacionamento", rel_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting relationship", extra={"service_account": current_service.name, "rel_id": rel_id})
    return None