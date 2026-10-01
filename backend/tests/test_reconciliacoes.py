"""Testes do painel de reconciliações (workflow de quatro olhos).

Cenários cobertos:
- criação com auto-detecção de discrepâncias (ativos sem IP/ambiente etc.)
- parecer individual: mesmo analista não registra duas vezes
- criador da execução não pode retificar sozinho (separação de papéis)
- decisão exige >=2 analistas distintos e decisor participante + admin
- conclusão exige zero itens pendentes
- viewer (sem role admin) não pode decidir nem concluir
"""
import pytest
from tests.test_main import client, db_session
from sqlalchemy import text
import models


@pytest.fixture(autouse=True)
def _limpa_contas(db_session):
    yield
    db_session.execute(text("DELETE FROM service_accounts"))
    db_session.commit()


@pytest.fixture
def analista1(db_session):
    r = client.post("/auth/test/login", json={"username": "rec-a1", "roles": ["admin"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def analista2(db_session):
    r = client.post("/auth/test/login", json={"username": "rec-b2", "roles": ["viewer"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def ativo_sem_ip(db_session):
    tipo = models.TipoAtivo(nome="tipo-rec-test")
    db_session.add(tipo)
    db_session.commit()
    a = models.Ativo(nome="rec-ativo-sem-ip", tipo_id=tipo.id)
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def _nova_execucao(headers, nome="Recon teste"):
    r = client.post("/reconciliacoes/", json={"nome": nome, "fonte": "manual"},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_auto_deteccao_gera_itens_pendentes(db_session, analista1, ativo_sem_ip):
    recon = _nova_execucao(analista1)
    assert recon["pendentes"] >= 1
    assert recon["criado_por"] == "rec-a1"
    itens = client.get(f"/reconciliacoes/{recon['id']}/itens",
                       headers=analista1).json()
    alvo = [i for i in itens
            if i.get("entidade") == "ativo" and i.get("entidade_id") == ativo_sem_ip.id]
    assert alvo, "ativo sem IP deve gerar discrepância"
    assert all(i["status"] == "pendente" for i in itens)


def test_parecer_duplicado_bloqueado(db_session, analista1, ativo_sem_ip):
    recon = _nova_execucao(analista1)
    itens = client.get(f"/reconciliacoes/{recon['id']}/itens",
                       headers=analista1).json()
    item = itens[0]
    r1 = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/parecer",
                     json={"parecer": "ratificar"}, headers=analista1)
    assert r1.status_code == 200
    r2 = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/parecer",
                     json={"parecer": "ratificar"}, headers=analista1)
    assert r2.status_code == 409
    assert "já registrou parecer" in r2.json()["detail"]


def test_criador_nao_retifica_sozinho(db_session, analista1, ativo_sem_ip):
    recon = _nova_execucao(analista1)
    itens = client.get(f"/reconciliacoes/{recon['id']}/itens",
                       headers=analista1).json()
    item = itens[0]
    r = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/parecer",
                    json={"parecer": "retificar"}, headers=analista1)
    assert r.status_code == 403
    # ratificar é permitido (regra veda apenas 'retificar' do criador)
    r2 = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/parecer",
                     json={"parecer": "ratificar"}, headers=analista1)
    assert r2.status_code == 200


def test_decisao_exige_dois_analistas(db_session, analista1, analista2,
                                      ativo_sem_ip):
    recon = _nova_execucao(analista1)
    itens = client.get(f"/reconciliacoes/{recon['id']}/itens",
                       headers=analista1).json()
    item = itens[0]
    # 1 analista → decisão bloqueada
    client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/parecer",
                json={"parecer": "ratificar"}, headers=analista1)
    r = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/decisao",
                    json={"decisao": "ratificado"}, headers=analista1)
    assert r.status_code == 409
    # 2º analista registra
    r2 = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/parecer",
                     json={"parecer": "retificar", "comentario": "fonte está certa"},
                     headers=analista2)
    assert r2.status_code == 200
    # viewer não pode decidir (sem admin)
    r3 = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/decisao",
                     json={"decisao": "retificado"}, headers=analista2)
    assert r3.status_code == 403
    # admin participante decide → ok
    r4 = client.post(f"/reconciliacoes/{recon['id']}/itens/{item['id']}/decisao",
                     json={"decisao": "ratificado"}, headers=analista1)
    assert r4.status_code == 200, r4.text
    corpo = r4.json()
    assert corpo["status"] == "ratificado"
    assert sorted(corpo["analistas"]) == ["rec-a1", "rec-b2"]


def test_concluir_exige_zero_pendentes(db_session, analista1, analista2,
                                       ativo_sem_ip):
    recon = _nova_execucao(analista1)
    itens = client.get(f"/reconciliacoes/{recon['id']}/itens",
                       headers=analista1).json()
    assert itens
    # pendentes → bloqueia
    r = client.post(f"/reconciliacoes/{recon['id']}/concluir", headers=analista1)
    assert r.status_code == 409
    # resolve todos com os dois analistas
    for it in itens:
        # criador (analista1) não pode 'retificar' → usa 'retificar' só no p2;
        # analista1 ratifica e analista2 retifica; decisão final retificado
        client.post(f"/reconciliacoes/{recon['id']}/itens/{it['id']}/parecer",
                    json={"parecer": "ratificar"}, headers=analista1)
        client.post(f"/reconciliacoes/{recon['id']}/itens/{it['id']}/parecer",
                    json={"parecer": "retificar", "comentario": "fonte certa"},
                    headers=analista2)
        rd = client.post(f"/reconciliacoes/{recon['id']}/itens/{it['id']}/decisao",
                         json={"decisao": "retificado"}, headers=analista1)
        assert rd.status_code == 200, rd.text
    r2 = client.post(f"/reconciliacoes/{recon['id']}/concluir", headers=analista1)
    assert r2.status_code == 200
    assert r2.json()["status"] == "concluida"
    assert r2.json()["retificados"] == len(itens)
    # lista traz contadores
    lista = client.get("/reconciliacoes/", headers=analista1).json()
    alvo = [x for x in lista if x["id"] == recon["id"]]
    assert alvo and alvo[0]["pendentes"] == 0


def test_parecer_invalido_rejeitado(db_session, analista1, ativo_sem_ip):
    recon = _nova_execucao(analista1)
    itens = client.get(f"/reconciliacoes/{recon['id']}/itens",
                       headers=analista1).json()
    r = client.post(f"/reconciliacoes/{recon['id']}/itens/{itens[0]['id']}/parecer",
                    json={"parecer": "talvez"}, headers=analista1)
    assert r.status_code == 422


def test_endpoint_requer_autenticacao(db_session, ativo_sem_ip):
    r = client.get("/reconciliacoes/")
    assert r.status_code in (401, 403)


# ===== Inferência IA → reconciliação =====

def _reporta_inferencia(headers, itens, limiar=None, nome=None):
    payload = {"itens": itens}
    if limiar is not None:
        payload["limiar"] = limiar
    if nome is not None:
        payload["nome"] = nome
    return client.post("/reconciliacoes/inferencia", json=payload, headers=headers)


def test_inferencia_confianca_baixa_abre_pendentes(db_session, analista1):
    r = _reporta_inferencia(analista1, [
        {"acao": "criar_instancia", "entidade": "instancias_aplicacao",
         "valor_proposto": "App X @ srv-01", "confianca": 0.72},
        {"acao": "criar_servico", "entidade": "servico",
         "valor_proposto": "Apache NiFi", "confianca": 0.95},
    ], nome="Inferência IA teste")
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["recebidos"] == 2
    assert corpo["pendentes_abertos"] == 1
    assert corpo["auto_ratificados"] == 1
    assert corpo["reconciliacao"]["fonte"] == "ia"
    assert corpo["reconciliacao"]["pendentes"] == 1
    assert corpo["reconciliacao"]["ratificados"] == 1
    itens = client.get(f"/reconciliacoes/{corpo['reconciliacao']['id']}/itens",
                       headers=analista1).json()
    pendente = next(i for i in itens if i["status"] == "pendente")
    assert pendente["confianca"] == 0.72
    assert "0.72" in pendente["detalhe"] or "72%" in pendente["detalhe"]
    ratificado = next(i for i in itens if i["status"] == "ratificado")
    assert ratificado["resolvido_por"] == "inferencia_ia"


def test_inferencia_abaixo_do_limiar_padrao_90(db_session, analista1):
    r = _reporta_inferencia(analista1, [
        {"acao": "criar_relacionamento", "entidade": "relacionamento",
         "valor_proposto": "srv-a → srv-b [Depende de]", "confianca": 0.899},
        {"acao": "criar_relacionamento", "entidade": "relacionamento",
         "valor_proposto": "srv-c → srv-d [Depende de]", "confianca": 0.9},
    ])
    assert r.status_code == 201, r.text
    corpo = r.json()
    # 0.899 < 0.90 → pendente; 0.9 == limiar → ratificado
    assert corpo["pendentes_abertos"] == 1
    assert corpo["auto_ratificados"] == 1


def test_inferencia_workflow_quatro_olhos(db_session, analista1, analista2):
    r = _reporta_inferencia(analista1, [
        {"acao": "criar_instancia", "entidade": "instancias_aplicacao",
         "valor_proposto": "App Y @ srv-02", "confianca": 0.55},
    ])
    recon_id = r.json()["reconciliacao"]["id"]
    itens = client.get(f"/reconciliacoes/{recon_id}/itens", headers=analista1).json()
    item = itens[0]
    # item de inferência segue o mesmo fluxo de 4-olhos (2+ analistas)
    client.post(f"/reconciliacoes/{recon_id}/itens/{item['id']}/parecer",
                json={"parecer": "ratificar"}, headers=analista1)
    client.post(f"/reconciliacoes/{recon_id}/itens/{item['id']}/parecer",
                json={"parecer": "retificar", "comentario": "confirmado no host"},
                headers=analista2)
    rd = client.post(f"/reconciliacoes/{recon_id}/itens/{item['id']}/decisao",
                     json={"decisao": "retificado"}, headers=analista2)
    assert rd.status_code == 403  # viewer não decide
    r4 = client.post(f"/reconciliacoes/{recon_id}/itens/{item['id']}/decisao",
                     json={"decisao": "retificado"}, headers=analista1)
    assert r4.status_code == 200, r4.text
    assert r4.json()["status"] == "retificado"


def test_inferencia_confianca_invalida_rejeitada(db_session, analista1):
    r = _reporta_inferencia(analista1, [
        {"acao": "criar_servico", "entidade": "servico",
         "valor_proposto": "X", "confianca": 1.5},
    ])
    assert r.status_code == 422
    r2 = _reporta_inferencia(analista1, [], limiar=0)
    assert r2.status_code == 422


def test_inferencia_lista_vazia_ainda_cria_execucao(db_session, analista1):
    r = _reporta_inferencia(analista1, [])
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["recebidos"] == 0
    assert corpo["pendentes_abertos"] == 0
    assert corpo["auto_ratificados"] == 0
    assert corpo["reconciliacao"]["total_itens"] == 0