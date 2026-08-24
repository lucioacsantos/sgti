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


def test_read_clusters(db_session, auth_headers):
    cluster = models.Cluster(nome="test-cluster", descricao="Test cluster")
    db_session.add(cluster)
    db_session.commit()

    response = client.get("/clusters/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(c["nome"] == "test-cluster" for c in data)


def test_create_namespace(db_session, auth_headers):
    cluster = models.Cluster(nome="test-cluster-ns")
    db_session.add(cluster)
    db_session.commit()

    response = client.post(
        "/namespaces/",
        json={"nome": "prod-namespace", "cluster_id": cluster.id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "prod-namespace"
    assert data["cluster_id"] == cluster.id


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


def test_create_servico(db_session, auth_headers):
    response = client.post(
        "/servicos/",
        json={"nome": "web-service", "tipo": "web", "host_id": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "web-service"
    assert data["tipo"] == "web"


def test_read_servicos(db_session, auth_headers):
    svc = models.Servico(nome="db-service", tipo="database", host_id=1)
    db_session.add(svc)
    db_session.commit()

    response = client.get("/servicos/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1