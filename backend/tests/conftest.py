import pytest
import os
from datetime import datetime
os.environ["TESTING"] = "1"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import models
from database import Base
import bcrypt


# Use file-based SQLite for tests to share across connections
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Make SQLite use JSON instead of JSONB for testing
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Get a database session for direct model manipulation in tests."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Auto-create and clean tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    # Clean up data after each test
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
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