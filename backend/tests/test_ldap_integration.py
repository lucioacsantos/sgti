"""Testes de integração LDAP com Docker (backend/tests/ldap).

Requisitos:
    cd backend/tests/ldap && bash setup_ldap.sh
    export SGTI_OWNER_NAME/SGTI_OWNER_CPF (crypto_lock)
    export AD_* conforme .env.ldap

Os testes pulam automaticamente se o OpenLDAP de teste não estiver acessível.
"""
import os

import pytest

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SGTI_OWNER_NAME", "LUCIO AC SANTOS")
os.environ.setdefault("SGTI_OWNER_CPF", "010662")

# Config de teste antes do import do módulo ad_auth_slapd (lê env no import)
TEST_LDAP_ENV = {
    "AD_SERVER": "ldap://127.0.0.1",
    "AD_PORT": "389",
    "AD_DOMAIN": "lacstech.local",
    "AD_BASE_DN": "dc=lacstech,dc=local",
    "AD_USE_SSL": "false",
    "AD_BIND_DN": "cn=admin,dc=lacstech,dc=local",
    "AD_BIND_PASSWORD": "admin",
    "AD_SEARCH_FILTER": "(uid={username})",
}
for key, value in TEST_LDAP_ENV.items():
    os.environ[key] = value

import ldap3  # noqa: E402

from tests.conftest import TestingSessionLocal, engine  # noqa: E402
from database import Base  # noqa: E402
import ad_auth_slapd  # noqa: E402
import crypto_guard  # noqa: E402


def _ldap_reachable() -> bool:
    try:
        server = ldap3.Server("127.0.0.1", port=389, get_info=None, connect_timeout=3)
        conn = ldap3.Connection(server, auto_bind=True, read_only=True)
        conn.unbind()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ldap_reachable(),
    reason="OpenLDAP de teste não acessível — rode backend/tests/ldap/setup_ldap.sh",
)


@pytest.fixture(autouse=True)
def unlock_crypto():
    crypto_guard.unlock()
    yield


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestAuthenticateUser:
    def test_login_admin_valido(self):
        user = ad_auth_slapd.authenticate_user("lucio", "Admin123")
        assert user is not None
        assert user["username"] == "lucio"
        assert user["display_name"] == "Lucio Santos"
        assert user["email"] == "luciosantos@lacstech.local"

    def test_grupos_do_admin(self):
        user = ad_auth_slapd.authenticate_user("lucio", "Admin123")
        groups = [g.split(",")[0] for g in user["groups"]]
        assert "cn=G_GESIN_GOSD_OMIS" in groups

    def test_roles_do_admin(self):
        user = ad_auth_slapd.authenticate_user("lucio", "Admin123")
        roles = ad_auth_slapd.map_ad_groups_to_roles(user["groups"])
        assert "admin" in roles

    def test_role_read_do_analista(self):
        user = ad_auth_slapd.authenticate_user("analista", "Analista123")
        assert user is not None
        roles = ad_auth_slapd.map_ad_groups_to_roles(user["groups"])
        assert "read" in roles

    def test_usuario_sem_grupo_vira_viewer(self):
        user = ad_auth_slapd.authenticate_user("estagio", "Estagio123")
        assert user is not None
        roles = ad_auth_slapd.map_ad_groups_to_roles(user["groups"])
        assert roles == ["viewer"]

    def test_senha_errada_rejeitada(self):
        assert ad_auth_slapd.authenticate_user("lucio", "SenhaErrada") is None

    def test_usuario_inexistente(self):
        assert ad_auth_slapd.authenticate_user("fantasma", "x") is None


class TestCreateOrUpdateLocalUser:
    def test_cria_usuario_local(self, db_session):
        user = ad_auth_slapd.authenticate_user("lucio", "Admin123")
        local = ad_auth_slapd.create_or_update_local_user(db_session, user)
        assert local.name == "lucio"
        import json

        payload = json.loads(local.token_hash)
        assert payload["ad_user"] is True
        assert "admin" in payload["roles"]