import pytest
from tests.test_main import client, db_session
import models


def test_create_tipo_relacionamento(db_session, auth_headers):
    response = client.post(
        "/tipos-relacionamento/",
        json={"nome": "Depende de", "descricao": "Relacionamento de dependência"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Depende de"
    assert data["id"] is not None


def test_read_tipos_relacionamento(db_session, auth_headers):
    tipo = models.TipoRelacionamento(nome="Contém", descricao="Contém outros ativos")
    db_session.add(tipo)
    db_session.commit()

    response = client.get("/tipos-relacionamento/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(t["nome"] == "Contém" for t in data)


def test_create_relacionamento(db_session, auth_headers):
    # Create assets first
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    ativo1 = models.Ativo(nome="server-01", tipo_id=tipo.id)
    ativo2 = models.Ativo(nome="server-02", tipo_id=tipo.id)
    db_session.add_all([ativo1, ativo2])
    db_session.commit()

    # Create relationship type
    rel_tipo = models.TipoRelacionamento(nome="Conecta a")
    db_session.add(rel_tipo)
    db_session.commit()

    response = client.post(
        "/relacionamentos/",
        json={
            "origem_id": ativo1.id,
            "destino_id": ativo2.id,
            "tipo_id": rel_tipo.id,
            "descricao": "Conexão de rede",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["origem_id"] == ativo1.id
    assert data["destino_id"] == ativo2.id
    assert data["tipo_id"] == rel_tipo.id


def test_read_relacionamentos(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    ativo1 = models.Ativo(nome="server-01", tipo_id=tipo.id)
    ativo2 = models.Ativo(nome="server-02", tipo_id=tipo.id)
    db_session.add_all([ativo1, ativo2])
    db_session.commit()

    rel_tipo = models.TipoRelacionamento(nome="Conecta a")
    db_session.add(rel_tipo)
    db_session.commit()

    rel = models.Relacionamento(origem_id=ativo1.id, destino_id=ativo2.id, tipo_id=rel_tipo.id)
    db_session.add(rel)
    db_session.commit()

    response = client.get("/relacionamentos/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_read_relacionamento_by_id(db_session, auth_headers):
    tipo = models.TipoAtivo(nome="Servidor")
    db_session.add(tipo)
    db_session.commit()

    ativo1 = models.Ativo(nome="server-01", tipo_id=tipo.id)
    ativo2 = models.Ativo(nome="server-02", tipo_id=tipo.id)
    db_session.add_all([ativo1, ativo2])
    db_session.commit()

    rel_tipo = models.TipoRelacionamento(nome="Conecta a")
    db_session.add(rel_tipo)
    db_session.commit()

    rel = models.Relacionamento(origem_id=ativo1.id, destino_id=ativo2.id, tipo_id=rel_tipo.id)
    db_session.add(rel)
    db_session.commit()

    response = client.get(f"/relacionamentos/{rel.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rel.id
    assert data["origem_id"] == ativo1.id
    assert data["destino_id"] == ativo2.id