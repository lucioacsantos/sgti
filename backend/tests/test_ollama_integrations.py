"""Testes dos endpoints de integração Ollama (RAG + análise de alarmes)."""
import datetime
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import models
import main
from database import Base, engine as test_engine


@pytest.fixture
def client():
    Base.metadata.create_all(bind=test_engine)
    from database import get_db as real_get_db
    from tests.conftest import TestingSessionLocal

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    previous_override = main.app.dependency_overrides.get(real_get_db)
    main.app.dependency_overrides[real_get_db] = override_get_db
    from database import get_stream_db_factory

    def override_stream_factory():
        yield TestingSessionLocal

    previous_stream = main.app.dependency_overrides.get(get_stream_db_factory)
    main.app.dependency_overrides[get_stream_db_factory] = override_stream_factory
    with TestClient(main.app) as c:
        yield c
    if previous_override is not None:
        main.app.dependency_overrides[real_get_db] = previous_override
    else:
        main.app.dependency_overrides.pop(real_get_db, None)
    if previous_stream is not None:
        main.app.dependency_overrides[get_stream_db_factory] = previous_stream
    else:
        main.app.dependency_overrides.pop(get_stream_db_factory, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def headers(service_account):
    return {"X-Service-Token": "test-token-123"}


@pytest.fixture
def ativo(db_session):
    """Cria um ativo completo no CMDB para testes de análise de alarme."""
    tipo = models.TipoAtivo(nome="Servidor Virtual")
    ambiente = models.Ambiente(nome="Produção")
    status = models.StatusAtivo(nome="Ativo")
    criticidade = models.Criticidade(nivel="Crítica")
    sor = models.SistemaOperacional(abreviacao="Ubuntu 22.04", descricao="Ubuntu LTS")
    db_session.add_all([tipo, ambiente, status, criticidade, sor])
    db_session.commit()

    ativo = models.Ativo(
        nome="zbx-server01",
        descricao="Servidor Zabbix",
        tipo_id=tipo.id,
        ambiente_id=ambiente.id,
        status_id=status.id,
        criticidade_id=criticidade.id,
        sor_id=sor.id,
    )
    db_session.add(ativo)
    db_session.commit()

    db_session.add(models.EnderecoIp(ativo_id=ativo.id, ip="10.10.1.10", primario=True))
    db_session.commit()
    return ativo


FAKE_EMBED = [0.1] * 768


def _fake_embed(texts, model=None):
    return [FAKE_EMBED for _ in texts]


class TestListarModelos:
    def test_listar_modelos(self, client, headers):
        with patch("routers.integrations.ollama.list_models", return_value=[{"name": "llama3.2"}]):
            resp = client.get("/ollama/modelos/", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"modelos": [{"name": "llama3.2"}]}

    def test_requer_autenticacao(self, client):
        resp = client.get("/ollama/modelos/")
        assert resp.status_code in (401, 403)


class TestIndexarKnowledge:
    def test_diretorio_inexistente(self, client, headers):
        resp = client.post("/ollama/knowledge/indexar", json={"diretorio": "/tmp/não-existe-xyz"}, headers=headers)
        assert resp.status_code == 404

    def test_indexar_com_mock(self, client, headers, tmp_path, monkeypatch):
        import routers.integrations as integrations

        doc = tmp_path / "procedimento-teste.md"
        doc.write_text("# Titulo\n\nConteudo do procedimento de teste para embedding.", encoding="utf-8")

        monkeypatch.setattr("knowledge.ollama.embed", _fake_embed)
        resp = client.post("/ollama/knowledge/indexar", json={"diretorio": str(tmp_path)}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["documentos_indexados"] == 1
        assert body["trechos_indexados"] == 1

    def test_recriar(self, client, headers, tmp_path, monkeypatch):
        monkeypatch.setattr("knowledge.ollama.embed", _fake_embed)
        client.post("/ollama/knowledge/indexar", json={"diretorio": str(tmp_path)}, headers=headers)
        resp = client.post(
            "/ollama/knowledge/indexar",
            json={"diretorio": str(tmp_path), "recriar": True},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["arquivos_encontrados"] == 0
        assert body["documentos_removidos"] >= 0


class TestBuscarKnowledge:
    def test_buscar_sem_base(self, client, headers):
        with patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED):
            resp = client.post("/ollama/knowledge/buscar", json={"query": "disco cheio"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["resultados"] == []

    def test_buscar_com_documento(self, client, headers, tmp_path, monkeypatch):
        doc = tmp_path / "proc-disco.md"
        doc.write_text("# Disco Cheio\n\nProcedimento de limpeza de disco em servidor Linux.", encoding="utf-8")
        monkeypatch.setattr("knowledge.ollama.embed", _fake_embed)
        client.post("/ollama/knowledge/indexar", json={"diretorio": str(tmp_path)}, headers=headers)

        with patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED):
            resp = client.post("/ollama/knowledge/buscar", json={"query": "disco cheio", "top_k": 2}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["resultados"]) == 1
        assert body["resultados"][0]["documento"] == "Proc Disco"
        assert body["resultados"][0]["score"] == pytest.approx(1.0)

    def test_buscar_requer_query(self, client, headers):
        resp = client.post("/ollama/knowledge/buscar", json={}, headers=headers)
        assert resp.status_code == 422


class TestPerguntarKnowledge:
    def test_perguntar(self, client, headers, tmp_path, monkeypatch):
        doc = tmp_path / "proc-cpu.md"
        doc.write_text("# Alta CPU\n\nVerificar processos com top e pidstat.", encoding="utf-8")
        monkeypatch.setattr("knowledge.ollama.embed", _fake_embed)
        client.post("/ollama/knowledge/indexar", json={"diretorio": str(tmp_path)}, headers=headers)

        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat", return_value="Diagnóstico: processo com alta CPU."),
        ):
            resp = client.post(
                "/ollama/knowledge/perguntar",
                json={"pergunta": "o que fazer com alta de CPU?", "top_k": 2},
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["resposta"] == "Diagnóstico: processo com alta CPU."
        assert len(body["trechos"]) == 1

    def test_perguntar_sem_base(self, client, headers):
        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat", return_value="Sem procedimento documentado."),
        ):
            resp = client.post("/ollama/knowledge/perguntar", json={"pergunta": "x"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["trechos"] == []


class TestPerguntarStream:
    def test_stream_eventos(self, client, headers, tmp_path, monkeypatch):
        doc = tmp_path / "proc-net.md"
        doc.write_text("# Rede Lenta\n\nVerificar interface, erros de CRC e colisões.", encoding="utf-8")
        monkeypatch.setattr("knowledge.ollama.embed", _fake_embed)
        client.post("/ollama/knowledge/indexar", json={"diretorio": str(tmp_path)}, headers=headers)

        def fake_chat_stream(*args, **kwargs):
            yield "Diagnóstico: "
            yield "interface saturada."

        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat_stream", side_effect=fake_chat_stream),
        ):
            resp = client.post(
                "/ollama/knowledge/perguntar/stream",
                json={"pergunta": "rede lenta", "top_k": 2},
                headers=headers,
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        eventos = [json.loads(l) for l in resp.text.strip().splitlines() if l.strip()]
        tipos = [e["type"] for e in eventos]
        assert tipos[0] == "start"
        assert tipos[-1] == "end"
        conteudo = "".join(e.get("content", "") for e in eventos if e["type"] == "chunk")
        assert conteudo == "Diagnóstico: interface saturada."
        trechos_start = eventos[0]["trechos"]
        assert len(trechos_start) == 1

    def test_stream_erro_interno(self, client, headers):
        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat_stream", side_effect=RuntimeError("boom")),
        ):
            resp = client.post("/ollama/knowledge/perguntar/stream", json={"pergunta": "x"}, headers=headers)
        assert resp.status_code == 200
        eventos = [json.loads(l) for l in resp.text.strip().splitlines() if l.strip()]
        assert eventos[-1]["type"] == "error"
        assert "boom" in eventos[-1]["detail"]

    def test_stream_requer_autenticacao(self, client):
        resp = client.post("/ollama/knowledge/perguntar/stream", json={"pergunta": "x"})
        assert resp.status_code in (401, 403)


class TestAnalisarAlarme:
    def test_analisar_com_cmdb(self, client, headers, ativo, db_session, tmp_path, monkeypatch):
        doc = tmp_path / "proc-down.md"
        doc.write_text("# Serviço Down\n\nVerificar serviço com systemctl e escalar GOSD.", encoding="utf-8")
        monkeypatch.setattr("knowledge.ollama.embed", _fake_embed)
        client.post("/ollama/knowledge/indexar", json={"diretorio": str(tmp_path)}, headers=headers)

        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat", return_value="Diagnóstico: serviço indisponível. Escalar GOSD."),
        ):
            resp = client.post(
                "/ollama/alarmes/analisar",
                json={
                    "event_id": "12345",
                    "host": "zbx-server01",
                    "problema": "Service is down",
                    "severidade": "High",
                },
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["event_id"] == "12345"
        assert body["host"] == "zbx-server01"
        assert "indisponível" in body["analise"]
        assert body["contexto_cmdb"]["ativo"]["nome"] == "zbx-server01"
        assert body["contexto_cmdb"]["ativo"]["criticidade"] == "Crítica"
        assert body["contexto_cmdb"]["ips"] == [{"ip": "10.10.1.10", "interface": None, "primario": True}]

    def test_analisar_host_fqdn(self, client, headers, ativo):
        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat", return_value="ok"),
        ):
            resp = client.post(
                "/ollama/alarmes/analisar",
                json={"event_id": "1", "host": "zbx-server01.example.com", "problema": "down"},
                headers=headers,
            )
        assert resp.status_code == 200
        assert resp.json()["contexto_cmdb"]["ativo"]["nome"] == "zbx-server01"

    def test_analisar_host_desconhecido(self, client, headers):
        with (
            patch("knowledge.ollama.embed_one", return_value=FAKE_EMBED),
            patch("knowledge.ollama.chat", return_value="host não encontrado"),
        ):
            resp = client.post(
                "/ollama/alarmes/analisar",
                json={"event_id": "1", "host": "host-inexistente", "problema": "down"},
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["contexto_cmdb"] == {}

    def test_analisar_requer_autenticacao(self, client):
        resp = client.post(
            "/ollama/alarmes/analisar",
            json={"event_id": "1", "host": "x", "problema": "down"},
        )
        assert resp.status_code in (401, 403)


class TestOllamaLegado:
    def test_ask_ollama(self, client, headers):
        with patch("routers.integrations.ollama.generate", return_value="resposta"):
            resp = client.post("/ollama/", json={"question": "oi"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["response"] == "resposta"