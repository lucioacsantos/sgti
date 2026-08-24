import pytest
from tests.test_main import client, db_session
import models


def test_upsert_endereco_ip_create(db_session, auth_headers):
    # Create asset first
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    ativo_response = client.post("/ativos/", json={"nome": "server-ip", "tipo_id": tipo.id}, headers=auth_headers)
    ativo_id = ativo_response.json()["id"]

    response = client.post(
        "/enderecos-ip/",
        json={"ativo_id": ativo_id, "ip": "192.168.1.10", "primario": True},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ip"] == "192.168.1.10"
    assert data["primario"] is True


def test_upsert_endereco_ip_update(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    ativo_response = client.post("/ativos/", json={"nome": "server-ip2", "tipo_id": tipo.id}, headers=auth_headers)
    ativo_id = ativo_response.json()["id"]

    # Create
    client.post("/enderecos-ip/", json={"ativo_id": ativo_id, "ip": "192.168.1.20"}, headers=auth_headers)
    
    # Update - may return 201 (created) or 200 (updated) depending on DB
    response = client.post(
        "/enderecos-ip/",
        json={"ativo_id": ativo_id, "ip": "192.168.1.20", "descricao": "Updated IP"},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201)
    data = response.json()
    assert data["descricao"] == "Updated IP"


def test_upsert_endereco_ip_primary(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    ativo_response = client.post("/ativos/", json={"nome": "server-ip3", "tipo_id": tipo.id}, headers=auth_headers)
    ativo_id = ativo_response.json()["id"]

    # Create first IP as primary
    client.post("/enderecos-ip/", json={"ativo_id": ativo_id, "ip": "192.168.1.30", "primario": True}, headers=auth_headers)
    
    # Create second IP as primary - should demote first
    response = client.post("/enderecos-ip/", json={"ativo_id": ativo_id, "ip": "192.168.1.31", "primario": True}, headers=auth_headers)
    assert response.status_code == 201
    
    # Verify first is no longer primary
    response = client.get(f"/enderecos-ip/?ativo_id={ativo_id}", headers=auth_headers)
    ips = response.json()
    primary_ips = [ip for ip in ips if ip["primario"]]
    assert len(primary_ips) == 1
    assert primary_ips[0]["ip"] == "192.168.1.31"


def test_read_enderecos_ip(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    ativo_response = client.post("/ativos/", json={"nome": "server-ip4", "tipo_id": tipo.id}, headers=auth_headers)
    ativo_id = ativo_response.json()["id"]
    
    client.post("/enderecos-ip/", json={"ativo_id": ativo_id, "ip": "10.0.0.1"}, headers=auth_headers)
    
    response = client.get("/enderecos-ip/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_delete_endereco_ip(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()
    ativo_response = client.post("/ativos/", json={"nome": "server-ip5", "tipo_id": tipo.id}, headers=auth_headers)
    ativo_id = ativo_response.json()["id"]
    
    ip_response = client.post("/enderecos-ip/", json={"ativo_id": ativo_id, "ip": "10.0.0.2"}, headers=auth_headers)
    ip_id = ip_response.json()["id"]
    
    response = client.delete(f"/enderecos-ip/{ip_id}", headers=auth_headers)
    assert response.status_code == 204
    
    # Verify deleted
    response = client.get("/enderecos-ip/", headers=auth_headers)
    ips = response.json()
    assert not any(ip["id"] == ip_id for ip in ips)