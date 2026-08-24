from fastapi import APIRouter, Depends
import models, schemas, auth, zabbix
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ollama", tags=["Integração Ollama"])


@router.post("/", response_model=schemas.OllamaResponse)
def ask_ollama(
    question: schemas.OllamaRequest,
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Querying Ollama", extra={"service_account": current_service.name, "model": question.model})
    response = auth.ask_ollama(question.question, question.model)
    return {"response": response}


zabbix_router = APIRouter(prefix="/zabbix", tags=["Integração Zabbix"])


@zabbix_router.post("/alarmes/observacao-ollama/", response_model=schemas.ZabbixOllamaObservationResponse)
def add_ollama_response_to_zabbix_alarm(
    payload: schemas.ZabbixOllamaObservationRequest,
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Adding Ollama observation to Zabbix alarm", extra={"service_account": current_service.name, "event_id": payload.event_id})
    zabbix_client = zabbix.ZabbixClient()
    problem = zabbix_client.get_open_problem(payload.event_id)
    ollama_prompt = (
        "Analise o alarme aberto do Zabbix abaixo e gere uma observação objetiva "
        "para registrar no próprio alarme.\n\n"
        f"Event ID: {payload.event_id}\n"
        f"Nome do problema: {problem.get('name')}\n"
        f"Severidade: {problem.get('severity')}\n"
        f"Object ID: {problem.get('objectid')}\n\n"
        f"Solicitação: {payload.question}"
    )
    ollama_response = auth.ask_ollama(ollama_prompt, payload.model)
    zabbix_result = zabbix_client.add_event_observation(payload.event_id, ollama_response)

    return {
        "event_id": payload.event_id,
        "problem_name": problem.get("name"),
        "ollama_response": ollama_response,
        "zabbix_result": zabbix_result,
    }