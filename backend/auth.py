from fastapi import Security, HTTPException, Depends, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from database import get_db
from typing import cast
from urllib import error, request
import json
import models, datetime
import os

# Define o nome do Header que a automação deve enviar
API_KEY_NAME = "X-Service-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_service_account(
    api_key: str = Depends(api_key_header), 
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Token de serviço ausente."
        )

    # Busca o token no banco de dados
    account = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.token == api_key,
        models.ServiceAccount.is_active == True
    ).first()

    # Validações: Existência e Expiração
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou conta inativa."
        )
    
    expires_at = cast(datetime.datetime, account.expires_at)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if expires_at.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=None)

    if expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de serviço expirado."
        )

    return account

def ask_ollama(question: str, model: str | None = None) -> str:
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    ollama_model = model or os.getenv("OLLAMA_MODEL", "llama3")
    payload = {
        "model": ollama_model,
        "prompt": question,
        "stream": False
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            ollama_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with request.urlopen(req, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8") or "Erro ao consultar a API do Ollama."
        raise HTTPException(status_code=exc.code, detail=detail)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao consultar a API do Ollama: {exc}"
        )

    answer = response_data.get("response")
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida recebida da API do Ollama."
        )

    return answer
