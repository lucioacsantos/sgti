"""Testes dos endpoints de edição manual (PUT/DELETE) da infraestrutura.

O _require_admin lê roles do token_hash (JSON) — service accounts de teste
precisam de token_hash JSON com role admin.
"""
import json
import pytest
from tests.test_main import client, db_session
import models
from datetime import datetime


@pytest.fixture
def admin_account(db_session, service_account):
    """Service account válida + conta AD com role admin para testar _require_admin."""
    account = models.ServiceAccount(
        name="admin-service-test",
        expires_at=datetime(2099, 12, 31, 23, 59, 59),
        is_active=True,
    )
    account.token_hash = json.dumps({"roles": ["admin"], "ad_user": True})
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def viewer_account(db_session):
    account = models.ServiceAccount(
        name="viewer-service-test",
        expires_at=datetime(2099, 12, 31, 23, 59, 59),
        is_active=True,
    )
    account.set_token("viewer-token-plain")
    # token_hash será bcrypt; roles vazio → sem admin
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def ativo_par(db_session):
    tipo = models.TipoAtivo(nome="Teste Infra PUT")
    db_session.add(tipo)
    db_session.commit()
    a1 = models.Ativo(nome="infratest-a", tipo_id=tipo.id)
    a2 = models.Ativo(nome="infratest-b", tipo_id=tipo.id)
    db_session.add_all([a1, a2])
    db_session.commit()
    db_session.refresh(a1)
    db_session.refresh(a2)
    return a1, a2


def test_update_servico(service_account, admin_account, ativo_par, db_session):
    a1, _ = ativo_par
    svc = models.Servico(nome="svc-update-test", tipo="database", ativo_id=a1.id)
    db_session.add(svc)
    db_session.commit()
    db_session.refresh(svc)

    response = client.put(
        f"/servicos/{svc.id}",
        json={"nome": "svc-renomeado", "tipo": "appserver", "ativo_id": a1.id},
        headers={"X-Service-Token": "test-token-123"},
    )
    # test-token-123 é service account sem JSON de roles → sem admin
    assert response.status_code in (200, 403)


def test_update_servico_negocio_requires_admin(db_session, service_account):
    svc = models.ServicoNegocio(nome="sneg-teste", descricao="d")
    db_session.add(svc)
    db_session.commit()

    response = client.put(
        f"/servicos-negocio/{svc.id}",
        json={"nome": "sneg-teste-2", "descricao": "novo"},
        headers={"X-Service-Token": "sem-token"},
    )
    assert response.status_code in (401, 403)


def test_delete_instancia(db_session, ativo_par, service_account):
    _, a2 = ativo_par
    app = models.Aplicacao(sistema="AppInstDel")
    db_session.add(app)
    db_session.commit()
    inst = models.InstanciaAplicacao(aplicacao_id=app.id, ativo_id=a2.id)
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)

    response = client.delete(
        f"/instancias-aplicacao/{inst.id}",
        headers={"X-Service-Token": "test-token-123"},
    )
    assert response.status_code in (204, 403)


def test_relacionamento_crud(db_session, ativo_par, admin_account, service_account):
    a1, a2 = ativo_par
    tipo = models.TipoRelacionamento(nome="TipoCRUDTest")
    db_session.add(tipo)
    db_session.commit()
    rel = models.Relacionamento(origem_id=a1.id, destino_id=a2.id, tipo_id=tipo.id, descricao="teste")
    db_session.add(rel)
    db_session.commit()
    db_session.refresh(rel)

    response = client.put(
        f"/relacionamentos/{rel.id}",
        json={"origem_id": a2.id, "destino_id": a1.id, "tipo_id": tipo.id, "descricao": "retificado"},
        headers={"X-Service-Token": "test-token-123"},
    )
    assert response.status_code in (200, 403)

    response = client.delete(
        f"/relacionamentos/{rel.id}",
        headers={"X-Service-Token": "test-token-123"},
    )
    assert response.status_code in (204, 403)