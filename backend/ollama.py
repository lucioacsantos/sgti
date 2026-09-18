from fastapi import HTTPException, status
from urllib import error, request
import json
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
DEFAULT_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434").rstrip("/")
# Mantem modelos residentes na GPU/RAM entre chamadas (evita cold-start de
# segundos a cada troca embed<->chat em GPUs pequenas). "-1" = nunca descarrega.
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")


def _post(path: str, payload: dict, timeout: int = 300) -> dict:
    url = f"{OLLAMA_BASE_URL}{path}"
    try:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8") or "Erro ao consultar a API do Ollama."
        raise HTTPException(status_code=exc.code, detail=detail)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao consultar a API do Ollama: {exc}",
        )


def chat(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.2,
    num_ctx: int = 8192,
    num_predict: int | None = None,
    images: list[str] | None = None,
) -> str:
    """Gera uma resposta conversacional (llama3.2) a partir de um prompt."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    options: dict = {"temperature": temperature, "num_ctx": num_ctx}
    if num_predict is not None:
        options["num_predict"] = num_predict

    payload: dict = {
        "model": model or DEFAULT_CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": options,
    }
    if images:
        payload["messages"][-1]["images"] = images

    response_data = _post("/api/chat", payload)
    content = response_data.get("message", {}).get("content")
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida recebida da API do Ollama (/api/chat).",
        )
    return content


def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Gera embeddings (nomic-embed-text) para uma lista de textos."""
    if not texts:
        return []
    response_data = _post(
        "/api/embed",
        {"model": model or DEFAULT_EMBED_MODEL, "input": texts, "keep_alive": OLLAMA_KEEP_ALIVE},
    )
    embeddings = response_data.get("embeddings")
    if embeddings is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida recebida da API do Ollama (/api/embed).",
        )
    if len(embeddings) != len(texts):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Quantidade de embeddings retornada difere da solicitada.",
        )
    return embeddings


def embed_one(text: str, model: str | None = None) -> list[float]:
    return embed([text], model)[0]


def generate(question: str, model: str | None = None) -> str:
    """Compatibilidade com o formato legado /api/generate."""
    response_data = _post(
        "/api/generate",
        {
            "model": model or DEFAULT_CHAT_MODEL,
            "prompt": question,
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
        },
    )
    answer = response_data.get("response")
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resposta inválida recebida da API do Ollama.",
        )
    return answer


def list_models() -> list[dict]:
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=30) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8") or "Erro ao listar modelos do Ollama."
        raise HTTPException(status_code=exc.code, detail=detail)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao listar modelos do Ollama: {exc}",
        )
    return response_data.get("models", [])


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similaridade cosseno pura em Python (sem numpy), usada na busca vetorial."""
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))


def wait_for_ollama(retries: int = 30, delay: float = 2.0) -> bool:
    """Aguarda o Ollama responder (usado em scripts de seed/setup)."""
    for _ in range(retries):
        try:
            list_models()
            return True
        except HTTPException:
            time.sleep(delay)
    return False