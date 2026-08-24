import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app
from database import get_db
from tests.conftest import TestingSessionLocal, engine
import models
from database import Base
from datetime import datetime


# Override the get_db dependency for testing
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a test client with the overridden dependency
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    # Create tables fresh for each test
    Base.metadata.create_all(bind=engine)
    yield
    # Clean up data after each test
    db = TestingSessionLocal()
    try:
        # Delete all data in reverse order of dependencies
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db_session():
    """Get a database session for direct model manipulation in tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def service_account(db_session):
    """Create a test service account."""
    account = models.ServiceAccount(
        name="test-service",
        expires_at=datetime(2099, 12, 31, 23, 59, 59),
        is_active=True,
    )
    account.set_token("test-token-123")
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def auth_headers(service_account):
    return {"X-Service-Token": "test-token-123"}