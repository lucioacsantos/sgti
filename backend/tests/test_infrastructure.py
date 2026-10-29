# Objetivo: Testa CRUD idempotente de clusters, namespaces (multi-cluster), serviços e instâncias por ativo.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

import pytest
from tests.test_main import client, db_session
import models


def test_create_cluster(db_session, auth_headers):
    # Create asset first
    tipo = models.TipoAtivo(nome="Cluster")
    db_session.add(tipo)
    db_session.commit()

    ativo = models.Ativo(nome="cluster-asset", tipo_id=tipo.id)
    db_session.add(ativo)
    db_session.commit()

    response = client.post(
        "/clusters/",
        json={"nome": "prod-cluster", "descricao": "Production cluster", "ativo_id": ativo.id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "prod-cluster"
    assert data["ativo_id"] == ativo.id

    # Reexecução idempotente deve atualizar e retornar 200
    r2 = client.post(
        "/clusters/",
        json={"nome": "prod-cluster", "descricao": "Production cluster v2", "ativo_id": ativo.id},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]
    assert r2.json()["descricao"] == "Production cluster v2"


def test_read_clusters(db_session, auth_headers):
    cluster = models.Cluster(nome="test-cluster", descricao="Test cluster")
    db_session.add(cluster)
    db_session.commit()

    response = client.get("/clusters/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(c["nome"] == "test-cluster" for c in data)


def test_create_namespace_multi_cluster_e_idempotente(db_session, auth_headers):
    c_prod = models.Cluster(nome="ocp-prod")
    c_hml = models.Cluster(nome="ocp-hml")
    db_session.add_all([c_prod, c_hml])
    db_session.commit()

    # Mesmo nome de namespace ('default') em dois clusters OpenShift distintos
    r1 = client.post(
        "/namespaces/",
        json={"nome": "default", "cluster_id": c_prod.id},
        headers=auth_headers,
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/namespaces/",
        json={"nome": "default", "cluster_id": c_hml.id},
        headers=auth_headers,
    )
    assert r2.status_code == 201
    assert r2.json()["id"] != r1.json()["id"]

    # Reexecução no mesmo cluster é idempotente (200 OK)
    r3 = client.post(
        "/namespaces/",
        json={"nome": "default", "cluster_id": c_prod.id},
        headers=auth_headers,
    )
    assert r3.status_code == 200
    assert r3.json()["id"] == r1.json()["id"]


def test_read_namespaces(db_session, auth_headers):
    cluster = models.Cluster(nome="ns-test-cluster")
    db_session.add(cluster)
    db_session.commit()

    ns = models.Namespace(nome="test-ns", cluster_id=cluster.id)
    db_session.add(ns)
    db_session.commit()

    response = client.get("/namespaces/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_create_multiplos_servicos_e_instancias_no_mesmo_ativo(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor Virtual")
    db_session.add(tipo)
    db_session.commit()

    ativo = models.Ativo(nome="srv-multi-01", tipo_id=tipo.id)
    app1 = models.Aplicacao(sistema="Portal Corporativo")
    app2 = models.Aplicacao(sistema="API Pagamentos")
    db_session.add_all([ativo, app1, app2])
    db_session.commit()

    # Dois serviços distintos no mesmo ativo
    s1 = client.post(
        "/servicos/",
        json={"nome": "Nginx", "tipo": "web", "ativo_id": ativo.id},
        headers=auth_headers,
    )
    assert s1.status_code == 201

    s2 = client.post(
        "/servicos/",
        json={"nome": "PostgreSQL", "tipo": "database", "ativo_id": ativo.id},
        headers=auth_headers,
    )
    assert s2.status_code == 201
    assert s2.json()["id"] != s1.json()["id"]

    # Duas instâncias de aplicações distintas no mesmo ativo
    i1 = client.post(
        "/instancias-aplicacao/",
        json={"aplicacao_id": app1.id, "ativo_id": ativo.id, "porta": 8080},
        headers=auth_headers,
    )
    assert i1.status_code == 201

    i2 = client.post(
        "/instancias-aplicacao/",
        json={"aplicacao_id": app2.id, "ativo_id": ativo.id, "porta": 8443},
        headers=auth_headers,
    )
    assert i2.status_code == 201
    assert i2.json()["id"] != i1.json()["id"]


def test_read_servicos(db_session, auth_headers):
    svc = models.Servico(nome="db-service", tipo="database", host_id=1)
    db_session.add(svc)
    db_session.commit()

    response = client.get("/servicos/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1