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


# ===== Zabbix → reconciliação =====

@pytest.fixture
def tipo_ativo(db_session):
    t = models.TipoAtivo(nome="Servidor Virtual")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


def _alarme(headers, host, **extra):
    payload = {"event_id": "1001", "host": host}
    payload.update(extra)
    return client.post("/reconciliacoes/zabbix/alarme", json=payload,
                       headers=headers)


def test_zabbix_host_fora_do_cmdb_abre_reconciliacao_e_dedupe(
        db_session, analista1, tipo_ativo):
    r = _alarme(analista1, "srv-ghost-01")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["registrou"] is True
    assert corpo["reconciliacao"]["fonte"] == "zabbix"
    assert corpo["novos_itens"] == 1
    assert "sem ativo correspondente" in corpo["achados"][0]
    itens = client.get(f"/reconciliacoes/{corpo['reconciliacao']['id']}/itens",
                       headers=analista1).json()
    assert itens[0]["campo"] == "host_nao_cadastrado"
    assert itens[0]["valor_fonte"] == "srv-ghost-01"
    assert itens[0]["entidade_id"] is None
    assert "Alarme Zabbix 1001" in itens[0]["detalhe"]
    # dedupe: mesmo host reportado de novo não duplica item
    r2 = _alarme(analista1, "srv-ghost-01")
    corpo2 = r2.json()
    assert corpo2["novos_itens"] == 0
    assert corpo2["duplicados_ignorados"] == 1
    assert corpo2["reconciliacao"]["id"] == corpo["reconciliacao"]["id"]
    # uma única execução zabbix acumula os alarmes
    lista = client.get("/reconciliacoes/", headers=analista1).json()
    assert len([x for x in lista if x["fonte"] == "zabbix"]) == 1


def test_zabbix_ip_divergente_item_e_correcao(db_session, analista1, analista2,
                                              ativo_sem_ip):
    r = _alarme(analista1, "rec-ativo-sem-ip", ip="10.99.0.5")
    corpo = r.json()
    assert corpo["registrou"] is True
    assert corpo["reconciliacao"]["fonte"] == "zabbix"
    assert corpo["novos_itens"] == 1
    itens = client.get(f"/reconciliacoes/{corpo['reconciliacao']['id']}/itens",
                       headers=analista1).json()
    item = next(i for i in itens if i["campo"] == "endereco_ip")
    assert item["valor_fonte"] == "10.99.0.5"
    assert item["valor_cmdb"] is None  # ativo sem nenhum IP
    # quatro olhos: criador não pode retificar, segundo analista registra
    client.post(f"/reconciliacoes/{corpo['reconciliacao']['id']}/itens/"
                f"{item['id']}/parecer", json={"parecer": "ratificar"},
                headers=analista1)
    client.post(f"/reconciliacoes/{corpo['reconciliacao']['id']}/itens/"
                f"{item['id']}/parecer",
                json={"parecer": "retificar", "comentario": "IP real"},
                headers=analista2)
    rd = client.post(f"/reconciliacoes/{corpo['reconciliacao']['id']}/itens/"
                     f"{item['id']}/decisao",
                     json={"decisao": "retificado"}, headers=analista1)
    assert rd.status_code == 200, rd.text
    corpo_d = rd.json()
    assert corpo_d["status"] == "retificado"
    assert "correção automática aplicada: IP 10.99.0.5" in corpo_d["detalhe"]
    # CMDB corrigido de fato (não só o status do item)
    ip_row = (db_session.query(models.EnderecoIp)
              .filter(models.EnderecoIp.ativo_id == ativo_sem_ip.id).first())
    assert ip_row is not None and ip_row.ip == "10.99.0.5"
    assert ip_row.primario is True
    audit_corr = (db_session.query(models.AuditLog)
                  .filter(models.AuditLog.acao == "CORRECAO",
                          models.AuditLog.entidade == "ativo",
                          models.AuditLog.entidade_id == ativo_sem_ip.id)
                  .first())
    assert audit_corr is not None
    assert audit_corr.depois["adicionado"] == "10.99.0.5"


def test_zabbix_sem_discrepancia_nao_abre_execucao(db_session, analista1,
                                                   ativo_sem_ip):
    # ativo com IP registrado já coincide com o reportado
    db_session.add(models.EnderecoIp(ativo_id=ativo_sem_ip.id, ip="10.0.0.9",
                                     primario=True))
    db_session.commit()
    existia = client.get("/reconciliacoes/", headers=analista1).json()
    r = _alarme(analista1, "rec-ativo-sem-ip", ip="10.0.0.9")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["registrou"] is False
    assert corpo["reconciliacao"] is None
    depois = client.get("/reconciliacoes/", headers=analista1).json()
    assert {x["id"] for x in depois} == {x["id"] for x in existia}


# ===== Correção automática na decisão 'retificado' =====

def _item_correcao(db_session, recon_id, **kwargs):
    tipo = models.TipoAtivo(nome="tipo-corr")
    db_session.add(tipo)
    db_session.commit()
    ativo = models.Ativo(nome=kwargs.pop("nome", "corr-ativo"), tipo_id=tipo.id)
    db_session.add(ativo)
    db_session.commit()
    db_session.refresh(ativo)
    item = models.ItemReconciliacao(reconciliacao_id=recon_id,
                                    entidade="ativo", entidade_id=ativo.id,
                                    campo=kwargs.pop("campo"),
                                    valor_cmdb=kwargs.pop("valor_cmdb", None),
                                    valor_fonte=kwargs.pop("valor_fonte"),
                                    detalhe="discrepância de teste")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def _retifica_por_quatro_olhos(recon_id, item_id, analista1, analista2):
    client.post(f"/reconciliacoes/{recon_id}/itens/{item_id}/parecer",
                json={"parecer": "inconcluso"}, headers=analista1)
    client.post(f"/reconciliacoes/{recon_id}/itens/{item_id}/parecer",
                json={"parecer": "retificar"}, headers=analista2)
    return client.post(f"/reconciliacoes/{recon_id}/itens/{item_id}/decisao",
                       json={"decisao": "retificado"}, headers=analista1)


@pytest.fixture
def recon_manual(db_session, analista1):
    r = _nova_execucao(analista1, nome="Recon correção")
    return r


def test_retificado_corrige_ambiente_de_referencia(db_session, analista1,
                                                   analista2, recon_manual):
    amb = models.Ambiente(nome="Produção")
    db_session.add(amb)
    db_session.commit()
    item = _item_correcao(db_session, recon_manual["id"], campo="ambiente",
                          valor_fonte="Produção")
    r = _retifica_por_quatro_olhos(recon_manual["id"], item.id,
                                   analista1, analista2)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert "ambiente de 'ausente' para 'Produção'" in corpo["detalhe"]
    ativo = db_session.query(models.Ativo).get(item.entidade_id)
    db_session.refresh(ativo)
    assert ativo.ambiente is not None and ativo.ambiente.nome == "Produção"


def test_retificado_cria_ativo_de_host_zabbix(db_session, analista1,
                                              analista2, tipo_ativo):
    r = _alarme(analista1, "srv-fantasma-09")
    recon_id = r.json()["reconciliacao"]["id"]
    itens = client.get(f"/reconciliacoes/{recon_id}/itens",
                       headers=analista1).json()
    item = itens[0]
    r2 = _retifica_por_quatro_olhos(recon_id, item["id"], analista1, analista2)
    assert r2.status_code == 200, r2.text
    corpo = r2.json()
    assert "ativo #" in corpo["detalhe"] and "srv-fantasma-09" in corpo["detalhe"]
    novo = db_session.query(models.Ativo).filter(
        models.Ativo.nome == "srv-fantasma-09").first()
    assert novo is not None
    assert novo.tipo.nome == "Servidor Virtual"
    # entidade_id do item passa a apontar para o ativo criado
    assert corpo["entidade_id"] == novo.id


def test_retificado_sem_regra_aplicavel_registra_nota(db_session, analista1,
                                                      analista2, recon_manual):
    item = _item_correcao(db_session, recon_manual["id"], campo="descricao",
                          valor_fonte="texto livre qualquer")
    r = _retifica_por_quatro_olhos(recon_manual["id"], item.id,
                                   analista1, analista2)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["status"] == "retificado"
    assert "correção automática não aplicável" in corpo["detalhe"]
    # audit da decisão registra a nota, sem CORRECAO no alvo
    dec = (db_session.query(models.AuditLog)
           .filter(models.AuditLog.acao == "DECISAO",
                   models.AuditLog.entidade == "item_reconciliacao",
                   models.AuditLog.entidade_id == item.id).first())
    assert dec.depois["correcao"].startswith("correção automática não aplicável")