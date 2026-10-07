from fastapi import HTTPException, status
from urllib import error, request
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent.parent / ".env")

ZABBIX_ADD_MESSAGE_ACTION = 4


class ZabbixClient:
    def __init__(self):
        self.api_url = self._normalize_api_url(os.getenv("ZABBIX_API_URL", ""))
        self.api_token = os.getenv("ZABBIX_API_TOKEN")
        self.username = os.getenv("ZABBIX_USER")
        self.password = os.getenv("ZABBIX_PASSWORD")
        self.use_bearer_token = os.getenv("ZABBIX_USE_BEARER_TOKEN", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        self._auth_token: str | None = None
        self._request_id = 1

        if not self.api_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variável de ambiente ZABBIX_API_URL não configurada.",
            )

        if not self.api_token and not (self.username and self.password):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Configure ZABBIX_API_TOKEN ou ZABBIX_USER/ZABBIX_PASSWORD.",
            )

    def get_open_problem(self, event_id: str) -> dict:
        result = self._call(
            "problem.get",
            {
                "output": ["eventid", "name", "severity", "clock", "objectid"],
                "eventids": [event_id],
                "recent": False,
            },
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alarme aberto não encontrado no Zabbix para o event_id informado.",
            )

        return result[0]

    def add_event_observation(self, event_id: str, message: str) -> dict:
        return self._call(
            "event.acknowledge",
            {
                "eventids": [event_id],
                "action": ZABBIX_ADD_MESSAGE_ACTION,
                "message": message,
            },
        )

    def _call(self, method: str, params: dict) -> dict | list:
        auth_token = self._get_auth_token()
        try:
            return self._json_rpc(method, params, auth_token)
        except HTTPException as exc:
            # Zabbix >= 7.0 não aceita mais o campo "auth" no payload e exige
            # o header "Authorization: Bearer". Ao detectar o erro de parâmetro
            # inválido, marca o cliente para usar Bearer e retenta uma vez.
            if (
                self.api_token
                and not self.use_bearer_token
                and "unexpected parameter \"auth\"" in str(getattr(exc, "detail", ""))
            ):
                self.use_bearer_token = True
                return self._json_rpc(method, params, None)
            raise

    def _get_auth_token(self) -> str | None:
        if self.api_token:
            return None if self.use_bearer_token else self.api_token

        if self._auth_token is None:
            self._auth_token = self._login()

        return self._auth_token

    def _login(self) -> str:
        try:
            return self._json_rpc(
                "user.login",
                {"username": self.username, "password": self.password},
                auth_token=None,
                include_auth=False,
            )
        except HTTPException:
            return self._json_rpc(
                "user.login",
                {"user": self.username, "password": self.password},
                auth_token=None,
                include_auth=False,
            )

    def _json_rpc(
        self,
        method: str,
        params: dict,
        auth_token: str | None,
        include_auth: bool = True,
    ) -> dict | list | str:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }
        self._request_id += 1

        if include_auth and auth_token:
            payload["auth"] = auth_token

        try:
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(
                self.api_url,
                data=data,
                headers=self._headers(),
                method="POST",
            )

            with request.urlopen(req, timeout=120) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            logger = logging.getLogger(__name__)
            logger.error("Erro HTTP %s na API do Zabbix (%s): %s",
                         exc.code, method, detail)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro HTTP {exc.code} na API do Zabbix: {detail or 'sem detalhes'}",
            ) from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao consultar a API do Zabbix: {exc}",
            )

        if "error" in response_data:
            zabbix_error = response_data["error"]
            # Zabbix >= 7.0: campo "auth" no payload não é mais aceito.
            if (
                include_auth
                and auth_token
                and "unexpected parameter \"auth\"" in str(zabbix_error.get("data", ""))
            ):
                self.use_bearer_token = True
                self._request_id -= 1
                return self._json_rpc(method, params, None)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro da API do Zabbix em {method}: {zabbix_error}",
            )

        if "result" not in response_data:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Resposta inválida recebida da API do Zabbix em {method}.",
            )

        return response_data["result"]

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json-rpc"}
        if self.api_token and self.use_bearer_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    @staticmethod
    def _normalize_api_url(api_url: str) -> str:
        if not api_url:
            return ""

        api_url = api_url.rstrip("/")
        if api_url.endswith("api_jsonrpc.php"):
            return api_url

        return f"{api_url}/api_jsonrpc.php"
