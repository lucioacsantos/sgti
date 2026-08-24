import pytest
from tests.test_main import client, db_session
import models


def test_create_ativo(db_session, auth_headers):
    # First create required reference data
    tipo = models.TipoAtivo(nome="Servidor")
    status = models.StatusAtivo(nome="Ativo")
    criticidade = models.Criticidade(nivel="Alta")
    ambiente = models.Ambiente(nome="Produção")
    sor = models.SistemaOperacional(abreviacao="Linux", descricao="Linux OS", lifecycle="Active")
    area = models.Areas(nome="TI", sigla="TI")
    db_session.add_all([tipo, status, criticidade, ambiente, sor, area])
    db_session.commit()

    response = client.post(
        "/ativos/",
        json={
            "nome": "server-01",
            "descricao": "Test server",
            "tipo_id": tipo.id,
            "status_id": status.id,
            "criticidade_id": criticidade.id,
            "ambiente_id": ambiente.id,
            "sor_id": sor.id,
            "areas_id": area.id,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "server-01"
    assert data["id"] is not None


def test_create_duplicate_ativo(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    # Create first
    client.post("/ativos/", json={"nome": "server-01", "tipo_id": tipo.id}, headers=auth_headers)

    # Try to create duplicate
    response = client.post("/ativos/", json={"nome": "server-01", "tipo_id": tipo.id}, headers=auth_headers)
    assert response.status_code == 409


def test_read_ativos(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    client.post("/ativos/", json={"nome": "server-01", "tipo_id": tipo.id}, headers=auth_headers)

    response = client.get("/ativos/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_upsert_ativo_create(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    response = client.put(
        "/ativos/server-new",
        json={"tipo_id": tipo.id, "descricao": "New server"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "server-new"


def test_upsert_ativo_update(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    client.post("/ativos/", json={"nome": "server-update", "tipo_id": tipo.id}, headers=auth_headers)

    response = client.put(
        "/ativos/server-update",
        json={"descricao": "Updated description"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["descricao"] == "Updated description"


def test_read_ativo(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    client.post("/ativos/", json={"nome": "server-read", "tipo_id": tipo.id}, headers=auth_headers)

    response = client.get("/ativos/server-read", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nome"] == "server-read"


def test_delete_ativo(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    client.post("/ativos/", json={"nome": "server-delete", "tipo_id": tipo.id}, headers=auth_headers)

    response = client.delete("/ativos/server-delete", headers=auth_headers)
    assert response.status_code == 204

    # Verify deleted
    response = client.get("/ativos/server-delete", headers=auth_headers)
    assert response.status_code == 404


def test_auth_required():
    response = client.get("/ativos/")
    assert response.status_code == 403