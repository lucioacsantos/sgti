# Objetivo: Testa CRUD, upsert, correlação (bios_uuid/fqdn) e filtros de ativos do CMDB.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

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
            "bios_uuid": "4210a1b2-c3d4-e5f6-7890-123456789abc",
            "fqdn": "server-01.corp.local",
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
    assert data["bios_uuid"] == "4210a1b2-c3d4-e5f6-7890-123456789abc"
    assert data["fqdn"] == "server-01.corp.local"
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


def test_upsert_ativo_correlacao_vcenter_satellite(db_session, auth_headers):
    """Garante que vCenter e Satellite atualizam o mesmo Ativo via bios_uuid ou FQDN."""
    tipo = models.TipoAtivo(nome="Servidor Virtual")
    db_session.add(tipo)
    db_session.commit()

    # 1. Playbook vCenter cria a VM pelo nome curto e bios_uuid
    r1 = client.put(
        "/ativos/srv-app-01",
        json={
            "tipo_id": tipo.id,
            "bios_uuid": "4200-uuid-vcenter-01",
            "descricao": "VM vSphere",
        },
        headers=auth_headers,
    )
    assert r1.status_code == 201
    ativo_id = r1.json()["id"]

    # 2. Playbook Satellite envia FQDN na rota com o mesmo bios_uuid -> deve atualizar (200) sem duplicar
    r2 = client.put(
        "/ativos/srv-app-01.dominio.local",
        json={
            "bios_uuid": "4200-uuid-vcenter-01",
            "descricao": "Host gerenciado Satellite",
        },
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == ativo_id
    assert r2.json()["fqdn"] == "srv-app-01.dominio.local"


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

def _criar_referencias(db_session):
    tipo = models.TipoAtivo(nome="Servidor")
    status = models.StatusAtivo(nome="Ativo")
    ambiente_prod = models.Ambiente(nome="Produção")
    ambiente_dev = models.Ambiente(nome="Desenvolvimento")
    area_ti = models.Areas(nome="Tecnologia", sigla="TI")
    area_rh = models.Areas(nome="Recursos Humanos", sigla="RH")
    db_session.add_all([tipo, status, ambiente_prod, ambiente_dev, area_ti, area_rh])
    db_session.commit()
    return tipo, status, ambiente_prod, ambiente_dev, area_ti, area_rh


def test_read_ativos_filtro_search(db_session, auth_headers):
    tipo, _, _, _, ti, rh = _criar_referencias(db_session)
    client.post("/ativos/", json={"nome": "server-web", "tipo_id": tipo.id, "areas_id": ti.id}, headers=auth_headers)
    client.post("/ativos/", json={"nome": "server-banco", "tipo_id": tipo.id, "areas_id": rh.id}, headers=auth_headers)

    response = client.get("/ativos/", params={"search": "web"}, headers=auth_headers)
    assert response.status_code == 200
    nomes = [a["nome"] for a in response.json()]
    assert nomes == ["server-web"]


def test_read_ativos_filtro_ambiente(db_session, auth_headers):
    tipo, _, prod, dev, _, _ = _criar_referencias(db_session)
    client.post("/ativos/", json={"nome": "server-prod", "tipo_id": tipo.id, "ambiente_id": prod.id}, headers=auth_headers)
    client.post("/ativos/", json={"nome": "server-dev", "tipo_id": tipo.id, "ambiente_id": dev.id}, headers=auth_headers)

    response = client.get("/ativos/", params={"ambiente_id": prod.id}, headers=auth_headers)
    nomes = [a["nome"] for a in response.json()]
    assert nomes == ["server-prod"]


def test_read_ativos_filtro_areas(db_session, auth_headers):
    tipo, _, _, _, ti, rh = _criar_referencias(db_session)
    client.post("/ativos/", json={"nome": "server-ti", "tipo_id": tipo.id, "areas_id": ti.id}, headers=auth_headers)
    client.post("/ativos/", json={"nome": "server-rh", "tipo_id": tipo.id, "areas_id": rh.id}, headers=auth_headers)

    response = client.get("/ativos/", params={"areas_id": rh.id}, headers=auth_headers)
    nomes = [a["nome"] for a in response.json()]
    assert nomes == ["server-rh"]


def test_read_ativos_ordenado_alfabeticamente(db_session, auth_headers):
    tipo, _, _, _, _, _ = _criar_referencias(db_session)
    for nome in ["zulu", "Alfa", "mike", "Bravo"]:
        client.post("/ativos/", json={"nome": nome, "tipo_id": tipo.id}, headers=auth_headers)

    response = client.get("/ativos/", headers=auth_headers)
    nomes = [a["nome"] for a in response.json()]
    assert nomes == sorted(nomes, key=str.lower)
