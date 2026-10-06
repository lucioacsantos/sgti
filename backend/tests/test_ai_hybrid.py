"""Testes da engine de IA híbrida (providers ollama/local) e da análise de
alarmes com engine local determinística."""
import datetime
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import ai_engine
import models
import main
from database import Base, engine as test_engine


# ============================================================
# Unitários — ai_engine
# ============================================================


class TestResolveProvider:
    def test_default(self, monkeypatch):
        assert ai_engine.resolve_provider(None) == ai_engine.DEFAULT_PROVIDER

    def test_validos(self):
        assert ai_engine.resolve_provider("ollama") == "ollama"
        assert ai_engine.resolve_provider("local") == "local"

    def test_invalido(self):
        with pytest.raises(Exception) as exc:
            ai_engine.resolve_provider("chatgpt")
        assert "inválido" in str(exc.value)

    def test_case_espacos(self):
        assert ai_engine.resolve_provider("  LOCAL ") == "local"


class TestProviderSignature:
    def test_ollama(self):
        assert ai_engine.provider_signature("ollama") == "ollama:nomic-embed-text"

    def test_local(self):
        sig = ai_engine.provider_signature("local")
        assert sig.startswith("local:")
        assert sig == f"local:{ai_engine.LOCAL_EMBED_MODEL}"


class TestTaxonomia:
    def test_disco(self):
        perfil = ai_engine._classificar("Disk space usage on /var is above threshold")
        assert perfil and perfil["categoria"] == "disco"

    def test_cpu(self):
        perfil = ai_engine._classificar("High CPU usage (over 90% for 5m)")
        assert perfil and perfil["categoria"] == "cpu"

    def test_memoria(self):
        perfil = ai_engine._classificar("Swap usage > 80% (oom risk)")
        assert perfil and perfil["categoria"] == "memória"

    def test_servico(self):
        perfil = ai_engine._classificar("Serviço parado: zabbix-agent2")
        assert perfil and perfil["categoria"] == "serviço"

    def test_rede(self):
        perfil = ai_engine._classificar("Interface eth0: erro de CRC em pacotes")
        assert perfil and perfil["categoria"] == "rede"

    def test_certificado(self):
        perfil = ai_engine._classificar("TLS certificate expires in 5 days")
        assert perfil and perfil["categoria"] == "certificado"

    def test_banco(self):
        perfil = ai_engine._classificar("PostgreSQL: too many connections")
        assert perfil and perfil["categoria"] == "banco de dados"

    def test_nao_classificado(self):
        assert ai_engine._classificar("Alarme místico sem padrão conhecido xyz123") is None


class TestLocalAlarmAnalysis:
    def test_estrutura_completa(self):
        alarme = {
            "event_id": "1",
            "host": "srv01",
            "problema": "Disk space usage /var 92%",
            "severidade": "High",
            "mensagem": "",
        }
        cmdb = {
            "ativo": {"nome": "srv01", "ambiente": "Produção", "criticidade": "Alta"},
            "relacionamentos": [{"outro_ativo": "db01", "tipo": "Depende de"}],
        }
        trechos = [{
            "documento": "Proc Disco",
            "titulo_secao": "Limpeza",
            "score": 0.82,
            "conteudo": "Rodar du e limpar logs.",
        }]
        texto = ai_engine.local_alarm_analysis(alarme, cmdb, trechos)
        assert "(1) Diagnóstico provável" in texto
        assert "disco" in texto
        assert "(2) Impacto e criticidade" in texto
        assert "srv01" in texto and "Produção" in texto and "db01" in texto
        assert "(3) Ação recomendada" in texto
        assert "[Proc Disco" in texto
        assert "(4) Escalação" in texto
        assert "engine local determinística" in texto

    def test_sem_cmdb_sem_trechos(self):
        texto = ai_engine.local_alarm_analysis(
            {"problema": "CPU load average high", "severidade": "Average"}, {}, []
        )
        assert "cpu" in texto
        assert "Ações padrão da categoria" in texto
        assert "escalar" in texto

    def test_nao_classificado(self):
        texto = ai_engine.local_alarm_analysis(
            {"problema": "xyzabc", "severidade": None}, {"ativo": {}}, []
        )
        assert "não classificado" in texto


class TestLocalRagAnswer:
    def test_com_trechos(self):
        trechos = [
            {"documento": "Doc A", "titulo_secao": "S1", "score": 0.9, "conteudo": "Passo 1: reiniciar."},
            {"documento": "Doc B", "titulo_secao": None, "score": 0.5, "conteudo": "Passo 2: escalar."},
        ]
        resposta = ai_engine.local_rag_answer("como reiniciar?", trechos)
        assert "extraída da base de conhecimento" in resposta
        assert "[1] Doc A" in resposta and "[2] Doc B" in resposta
        assert "reiniciar" in resposta

    def test_sem_trechos(self):
        resposta = ai_engine.local_rag_answer("qualquer", [])
        assert "Nenhum trecho" in resposta
        assert "escale" in resposta


class TestLocalGenerate:
    def test_classifica(self):
        resposta = ai_engine.local_generate("disco cheio em /var")
        assert "Engine local" in resposta
        assert "disco" in resposta

    def test_nao_classifica(self):
        resposta = ai_engine.local_generate("olá, tudo bem?")
        assert "Engine local" in resposta


# ============================================================
# Integração — endpoints com provider
# ============================================================


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


LOCAL_FAKE_EMBED = [0.1] * 384


def _fake_local_embed(texts):
    return [LOCAL_FAKE_EMBED for _ in texts]


class TestIndexarComLocal:
    def test_indexar_provider_local(self, client, headers, tmp_path):
        doc = tmp_path / "proc-disco.md"
        doc.write_text("# Disco Cheio\n\nProcedimento de limpeza de disco.", encoding="utf-8")

        with patch("ai_engine.local_embed", side_effect=_fake_local_embed):
            resp = client.post(
                "/ollama/knowledge/indexar",
                json={"diretorio": str(tmp_path), "provider": "local"},
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["documentos_indexados"] == 1
        assert body["provider"] == ai_engine.provider_signature("local")

    def test_provider_invalido(self, client, headers, tmp_path):
        resp = client.post(
            "/ollama/knowledge/indexar",
            json={"diretorio": str(tmp_path), "provider": "gpt"},
            headers=headers,
        )
        assert resp.status_code == 400


class TestBuscarComLocal:
    def test_buscar_provider_local(self, client, headers, tmp_path):
        doc = tmp_path / "proc-disco.md"
        doc.write_text("# Disco Cheio\n\nProcedimento de limpeza de disco em servidor Linux.", encoding="utf-8")

        with patch("ai_engine.local_embed", side_effect=_fake_local_embed):
            client.post(
                "/ollama/knowledge/indexar",
                json={"diretorio": str(tmp_path), "provider": "local"},
                headers=headers,
            )

        with patch("ai_engine.embed_one", return_value=LOCAL_FAKE_EMBED):
            resp = client.post(
                "/ollama/knowledge/buscar",
                json={"query": "disco cheio", "provider": "local"},
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"
        assert len(body["resultados"]) == 1
        assert body["resultados"][0]["score"] == pytest.approx(1.0)

    def test_isolamento_entre_providers(self, client, headers, tmp_path):
        """Busca 'local' NÃO vê documento indexado com ollama (e vice-versa)."""
        doc = tmp_path / "proc-disco.md"
        doc.write_text("# Disco Cheio\n\nProcedimento de disco.", encoding="utf-8")

        with patch("ai_engine.local_embed", side_effect=_fake_local_embed):
            client.post(
                "/ollama/knowledge/indexar",
                json={"diretorio": str(tmp_path), "provider": "local"},
                headers=headers,
            )
        # busca com provider ollama não encontra (assinatura diferente)
        with patch("ai_engine.embed_one", return_value=[0.1] * 768):
            resp = client.post(
                "/ollama/knowledge/buscar",
                json={"query": "disco", "provider": "ollama"},
                headers=headers,
            )
        assert resp.status_code == 200
        assert resp.json()["resultados"] == []


class TestRagLocal:
    def test_perguntar_provider_local(self, client, headers, tmp_path):
        doc = tmp_path / "proc-cpu.md"
        doc.write_text("# Alta CPU\n\nVerificar processos com top e pidstat.", encoding="utf-8")

        with patch("ai_engine.local_embed", side_effect=_fake_local_embed):
            client.post(
                "/ollama/knowledge/indexar",
                json={"diretorio": str(tmp_path), "provider": "local"},
                headers=headers,
            )

        with patch("ai_engine.embed_one", return_value=LOCAL_FAKE_EMBED):
            resp = client.post(
                "/ollama/knowledge/perguntar",
                json={"pergunta": "o que fazer com alta de CPU?", "provider": "local"},
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"
        assert "extraída da base de conhecimento" in body["resposta"]
        assert len(body["trechos"]) == 1

    def test_perguntar_stream_provider_local(self, client, headers, tmp_path):
        doc = tmp_path / "proc-net.md"
        doc.write_text("# Rede Lenta\n\nVerificar interface e erros de CRC.", encoding="utf-8")

        with patch("ai_engine.local_embed", side_effect=_fake_local_embed):
            client.post(
                "/ollama/knowledge/indexar",
                json={"diretorio": str(tmp_path), "provider": "local"},
                headers=headers,
            )

        with patch("ai_engine.embed_one", return_value=LOCAL_FAKE_EMBED):
            resp = client.post(
                "/ollama/knowledge/perguntar/stream",
                json={"pergunta": "rede lenta", "provider": "local"},
                headers=headers,
            )
        assert resp.status_code == 200
        eventos = [json.loads(l) for l in resp.text.strip().splitlines() if l.strip()]
        assert eventos[0]["type"] == "start"
        assert eventos[-1]["type"] == "end"
        conteudo = "".join(e.get("content", "") for e in eventos if e["type"] == "chunk")
        assert "extraída da base de conhecimento" in conteudo


class TestAnalisarAlarmeLocal:
    def test_analisar_provider_local(self, client, headers, ativo, tmp_path):
        doc = tmp_path / "proc-disco.md"
        doc.write_text("# Disco Cheio\n\nRodar du -sh e limpar logs.", encoding="utf-8")

        with patch("ai_engine.local_embed", side_effect=_fake_local_embed):
            client.post(
                "/ollama/knowledge/indexar",
                json={"diretorio": str(tmp_path), "provider": "local"},
                headers=headers,
            )

        alarme_payload = {
            "event_id": "999",
            "host": "zbx-server01",
            "problema": "Disk space usage on /var 92%",
            "severidade": "High",
            "provider": "local",
        }
        with patch("ai_engine.embed_one", return_value=LOCAL_FAKE_EMBED):
            resp = client.post("/ollama/alarmes/analisar", json=alarme_payload, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"
        assert body["event_id"] == "999"
        assert "disco" in body["analise"]
        assert "zbx-server01" in body["analise"]
        assert body["contexto_cmdb"]["ativo"]["nome"] == "zbx-server01"

    def test_analisar_provider_invalido(self, client, headers):
        resp = client.post(
            "/ollama/alarmes/analisar",
            json={"event_id": "1", "host": "x", "problema": "down", "provider": "gpt"},
            headers=headers,
        )
        assert resp.status_code == 400


class TestObservacaoZabbixLocal:
    def test_observacao_provider_local(self, client, headers):
        problem = [{"eventid": "777", "name": "CPU load high", "severity": "3", "objectid": "42"}]

        class FakeZabbix:
            def get_open_problem(self, event_id):
                return problem[0]

            def add_event_observation(self, event_id, message):
                return {"eventids": [event_id], "ok": True}

        with patch("zabbix.ZabbixClient", return_value=FakeZabbix()):
            resp = client.post(
                "/zabbix/alarmes/observacao-ollama/",
                json={"event_id": "777", "question": "analisar", "provider": "local"},
                headers=headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"
        assert "engine local determinística" in body["ollama_response"]
        assert body["zabbix_result"]["ok"] is True


class TestAskOllamaLocal:
    def test_ask_provider_local(self, client, headers):
        resp = client.post(
            "/ollama/",
            json={"question": "disco cheio no /var", "provider": "local"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"
        assert "Engine local" in body["response"]

    def test_listar_modelos_com_local(self, client, headers):
        with patch(
            "routers.integrations.ollama.list_models",
            return_value=[{"name": "llama3.2"}],
        ):
            resp = client.get("/ollama/modelos/", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["modelos"] == [{"name": "llama3.2"}]
        assert body["default_provider"] in ("ollama", "local")
        assert "embed_model" in body["local"]