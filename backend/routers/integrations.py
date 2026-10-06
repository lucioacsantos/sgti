from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import ai_engine
import models, schemas, auth, zabbix, knowledge, ollama
import database
from database import get_db
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ollama", tags=["Integração Ollama"])


@router.post("/", response_model=schemas.OllamaResponse)
def ask_ollama(
    question: schemas.OllamaRequest,
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Querying AI engine", extra={"service_account": current_service.name, "model": question.model})
    provider = ai_engine.resolve_provider(question.provider)
    if provider == "local":
        response = ai_engine.local_generate(question.question)
    else:
        response = ollama.generate(question.question, question.model)
    return {"response": response, "provider": provider}


@router.get("/modelos/")
def list_ollama_models(
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Listing Ollama models", extra={"service_account": current_service.name})
    try:
        modelos_ollama = ollama.list_models()
    except HTTPException as exc:
        # Ollama pode não estar disponível; o provider local continua utilizável
        logger.warning("Ollama indisponível ao listar modelos: %s", exc.detail)
        modelos_ollama = []
    return {
        "modelos": modelos_ollama,
        "local": {
            "embed_model": ai_engine.LOCAL_EMBED_MODEL,
            "disponivel": ai_engine._get_local_model is not None,
        },
        "default_provider": ai_engine.DEFAULT_PROVIDER,
    }


# ---- Base de conhecimento (RAG) ----

knowledge_router = APIRouter(prefix="/ollama/knowledge", tags=["Ollama - Base de Conhecimento"])


@knowledge_router.post("/indexar", response_model=schemas.KnowledgeIndexResponse)
def index_knowledge(
    payload: schemas.KnowledgeIndexRequest,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info(
        "Indexing knowledge base",
        extra={
            "service_account": current_service.name,
            "diretorio": payload.diretorio,
            "recriar": payload.recriar,
        },
    )
    try:
        resultado = knowledge.index_directory(db, payload.diretorio, payload.recriar, payload.provider)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return resultado


@knowledge_router.post("/buscar", response_model=schemas.KnowledgeSearchResponse)
def search_knowledge(
    payload: schemas.KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info(
        "Searching knowledge base",
        extra={"query": payload.query, "provider": payload.provider},
    )
    provider = ai_engine.resolve_provider(payload.provider)
    resultados = knowledge.search(db, payload.query, payload.top_k, provider=provider)
    return {"query": payload.query, "provider": provider, "resultados": resultados}


@knowledge_router.post("/perguntar", response_model=schemas.KnowledgeAskResponse)
def ask_knowledge(
    payload: schemas.KnowledgeAskRequest,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info(
        "RAG question",
        extra={"service_account": current_service.name, "pergunta": payload.pergunta,
               "provider": payload.provider},
    )
    return knowledge.answer_question(
        db,
        payload.pergunta,
        payload.top_k,
        payload.chat_model,
        payload.embed_model,
        payload.provider,
    )


@knowledge_router.post("/perguntar/stream")
def ask_knowledge_stream(
    payload: schemas.KnowledgeAskRequest,
    db: Session = Depends(get_db),
    session_factory = Depends(database.get_stream_db_factory),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """RAG com streaming NDJSON: start (trechos) -> chunk (tokens) -> end."""
    logger.info(
        "RAG question (stream)",
        extra={"service_account": current_service.name, "pergunta": payload.pergunta,
               "provider": payload.provider},
    )

    def gerar():
        # Sessão criada dentro do generator: o stream consome o provider depois
        # do fim da request, quando a sessão de Depends(get_db) já foi fechada.
        stream_db = session_factory()
        try:
            yield from knowledge.answer_question_stream(
                stream_db,
                payload.pergunta,
                payload.top_k,
                payload.chat_model,
                payload.embed_model,
                payload.provider,
            )
        finally:
            stream_db.close()

    return StreamingResponse(
        gerar(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ---- Análise de alarmes Zabbix (RAG + CMDB) ----

alarm_router = APIRouter(prefix="/ollama/alarmes", tags=["Ollama - Análise de Alarmes"])

SYSTEM_ALARM_PROMPT = (
    "Você é um analista sênior de monitoramento (NOC) do SGTI. Responda em português do Brasil. "
    "Receberá um alarme do Zabbix, dados do CMDB do host afetado e trechos de manuais/procedimentos. "
    "Produza uma análise curta e objetiva com: (1) diagnóstico provável, (2) impacto e criticidade "
    "considerando o CMDB e as dependências, (3) ação recomendada passo a passo baseada nos procedimentos, "
    "(4) quando e para quem escalar. Se não houver procedimento documentado, diga isso explicitamente. "
    "Cite os documentos usados entre colchetes, ex.: [Nome do Documento]."
)

ALARM_USER_TEMPLATE = (
    "ALARME ZABBIX\n"
    "event_id: {event_id}\n"
    "host: {host}\n"
    "problema: {problema}\n"
    "severidade: {severidade}\n"
    "mensagem: {mensagem}\n\n"
    "CONTEXTO CMDB\n{cmdb}\n\n"
    "TRECHOS DE MANUAIS/PROCEDIMENTOS (RAG)\n{rag}\n\n"
    "Gere a análise para o analista."
)


@alarm_router.post("/analisar", response_model=schemas.AlarmAnalysisResponse)
def analyze_alarm(
    payload: schemas.AlarmAnalysisRequest,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info(
        "Alarm analysis requested",
        extra={
            "service_account": current_service.name,
            "event_id": payload.event_id,
            "host": payload.host,
            "provider": payload.provider,
        },
    )
    provider = ai_engine.resolve_provider(payload.provider)
    contexto_cmdb = knowledge_cmdb_context(db, payload.host)
    trechos = knowledge.search(
        db,
        f"{payload.problema} host {payload.host} {payload.mensagem or ''}",
        payload.top_k,
        provider=provider,
    )
    if provider == "local":
        # Engine local determinística: taxonomia + CMDB + extração do RAG
        analise = ai_engine.local_alarm_analysis(
            {
                "event_id": payload.event_id,
                "host": payload.host,
                "problema": payload.problema,
                "severidade": payload.severidade,
                "mensagem": payload.mensagem,
            },
            contexto_cmdb,
            trechos,
        )
    else:
        prompt = ALARM_USER_TEMPLATE.format(
            event_id=payload.event_id,
            host=payload.host,
            problema=payload.problema,
            severidade=payload.severidade or "não informada",
            mensagem=payload.mensagem or "—",
            cmdb=contexto_cmdb or "(host não encontrado no CMDB)",
            rag=knowledge.build_context(trechos) or "(nenhum procedimento recuperado)",
        )
        analise = ollama.chat(prompt, system=SYSTEM_ALARM_PROMPT, num_predict=knowledge.RAG_NUM_PREDICT)
    return {
        "event_id": payload.event_id,
        "host": payload.host,
        "problema": payload.problema,
        "analise": analise,
        "trechos": trechos,
        "contexto_cmdb": contexto_cmdb,
        "provider": provider,
    }


def knowledge_cmdb_context(db: Session, host: str) -> dict:
    """Monta contexto do host no CMDB: ativo, IPs, relacionamentos, serviços, instâncias."""
    ativo = (
        db.query(models.Ativo)
        .filter(models.Ativo.nome.ilike(host))
        .one_or_none()
    )
    if not ativo:
        host_stripped = host.split(".")[0]
        ativo = (
            db.query(models.Ativo)
            .filter(models.Ativo.nome.ilike(f"{host_stripped}%"))
            .one_or_none()
        )
    if not ativo:
        return {}

    def ref(obj, campo):
        return getattr(obj, campo) if obj else None

    ips = db.query(models.EnderecoIp).filter(models.EnderecoIp.ativo_id == ativo.id).all()
    relacionamentos = (
        db.query(models.Relacionamento)
        .filter(
            (models.Relacionamento.origem_id == ativo.id)
            | (models.Relacionamento.destino_id == ativo.id)
        )
        .all()
    )
    servicos = db.query(models.Servico).filter(models.Servico.ativo_id == ativo.id).all()
    instancias = (
        db.query(models.InstanciaAplicacao)
        .filter(models.InstanciaAplicacao.ativo_id == ativo.id)
        .all()
    )
    aplicacoes = []
    for inst in instancias:
        if inst.aplicacao:
            aplicacoes.append(inst.aplicacao.sistema)

    return {
        "ativo": {
            "id": ativo.id,
            "nome": ativo.nome,
            "descricao": ativo.descricao,
            "tipo": ref(ativo.tipo, "nome"),
            "ambiente": ref(ativo.ambiente, "nome"),
            "status": ref(ativo.status, "nome"),
            "criticidade": ref(ativo.criticidade, "nivel"),
            "sistema_operacional": ref(ativo.sor, "abreviacao"),
        },
        "ips": [{"ip": ip.ip, "interface": ip.interface, "primario": ip.primario} for ip in ips],
        "relacionamentos": [
            {
                "direcao": "origem" if rel.origem_id == ativo.id else "destino",
                "outro_ativo": (rel.origem.nome if rel.origem_id != ativo.id else rel.destino.nome),
                "tipo": ref(rel.tipo, "nome"),
            }
            for rel in relacionamentos
        ],
        "servicos": [s.nome for s in servicos],
        "aplicacoes": aplicacoes,
    }


zabbix_router = APIRouter(prefix="/zabbix", tags=["Integração Zabbix"])


@zabbix_router.post("/alarmes/observacao-ollama/", response_model=schemas.ZabbixOllamaObservationResponse)
def add_ollama_response_to_zabbix_alarm(
    payload: schemas.ZabbixOllamaObservationRequest,
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Adding AI observation to Zabbix alarm", extra={"service_account": current_service.name, "event_id": payload.event_id})
    provider = ai_engine.resolve_provider(payload.provider)
    zabbix_client = zabbix.ZabbixClient()
    problem = zabbix_client.get_open_problem(payload.event_id)
    if provider == "local":
        analise_alarme = ai_engine.local_alarm_analysis(
            {
                "event_id": payload.event_id,
                "host": None,
                "problema": problem.get("name") or "",
                "severidade": str(problem.get("severity") or ""),
                "mensagem": problem.get("objectid") or "",
            },
            {},
            [],
        )
    else:
        ollama_prompt = (
            "Analise o alarme aberto do Zabbix abaixo e gere uma observação objetiva "
            "para registrar no próprio alarme.\n\n"
            f"Event ID: {payload.event_id}\n"
            f"Nome do problema: {problem.get('name')}\n"
            f"Severidade: {problem.get('severity')}\n"
            f"Object ID: {problem.get('objectid')}\n\n"
            f"Solicitação: {payload.question}"
        )
        analise_alarme = ollama.generate(ollama_prompt, payload.model)
    zabbix_result = zabbix_client.add_event_observation(payload.event_id, analise_alarme)

    return {
        "event_id": payload.event_id,
        "problem_name": problem.get("name"),
        "ollama_response": analise_alarme,
        "zabbix_result": zabbix_result,
        "provider": provider,
    }