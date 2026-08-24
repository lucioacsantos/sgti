import pytest
from tests.test_main import client, db_session
import models
from datetime import datetime


def test_get_service_account(db_session):
    account = models.ServiceAccount(
        name="test-auth",
        expires_at=datetime(2099, 12, 31, 23, 59, 59),
        is_active=True,
    )
    account.set_token("valid-token-123")
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    response = client.get("/ativos/", headers={"X-Service-Token": "valid-token-123"})
    # Should not be 401/403 (might be 200 or 422 depending on data)
    assert response.status_code != 401
    assert response.status_code != 403


def test_invalid_token(db_session):
    response = client.get("/ativos/", headers={"X-Service-Token": "invalid-token"})
    assert response.status_code == 401


def test_missing_token():
    response = client.get("/ativos/")
    assert response.status_code == 403


def test_expired_token(db_session):
    account = models.ServiceAccount(
        name="expired-service",
        expires_at=datetime(2020, 1, 1, 0, 0, 0),  # Expired
        is_active=True,
    )
    account.set_token("expired-token")
    db_session.add(account)
    db_session.commit()

    response = client.get("/ativos/", headers={"X-Service-Token": "expired-token"})
    assert response.status_code == 401


def test_inactive_account(db_session):
    account = models.ServiceAccount(
        name="inactive-service",
        expires_at=datetime(2099, 12, 31, 23, 59, 59),
        is_active=False,
    )
    account.set_token("inactive-token")
    db_session.add(account)
    db_session.commit()

    response = client.get("/ativos/", headers={"X-Service-Token": "inactive-token"})
    assert response.status_code == 401