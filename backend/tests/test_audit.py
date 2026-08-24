import pytest
from tests.test_main import client, db_session
import models


def test_read_audit_logs(db_session, auth_headers):
    # Create an asset first to generate audit logs
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    response = client.post(
        "/ativos/",
        json={"nome": "server-audit", "tipo_id": tipo.id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    asset_data = response.json()

    # Read audit logs
    response = client.get("/audit-logs/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    # Check that the CREATE action was logged
    assert any(log["entidade"] == "ativo" and log["acao"] == "CREATE" for log in data)


def test_read_audit_logs_filtered(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    response = client.post(
        "/ativos/",
        json={"nome": "server-filter", "tipo_id": tipo.id},
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Filter by entity
    response = client.get("/audit-logs/?entidade=ativo", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert all(log["entidade"] == "ativo" for log in data)


def test_read_audit_logs_by_entity_id(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    response = client.post(
        "/ativos/",
        json={"nome": "server-entity-id", "tipo_id": tipo.id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    asset_data = response.json()

    # Filter by entity_id
    response = client.get(f"/audit-logs/?entidade=ativo&entidade_id={asset_data['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(log["entidade_id"] == asset_data['id'] for log in data)