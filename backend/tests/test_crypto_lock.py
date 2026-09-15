"""Testes do módulo crypto_lock (criptografia dependente do proprietário)."""
import os

import pytest

os.environ.setdefault("SGTI_OWNER_NAME", "LUCIO AC SANTOS")
os.environ.setdefault("SGTI_OWNER_CPF", "010662")

import crypto_guard
import models


@pytest.fixture(scope="module", autouse=True)
def unlock_module():
    crypto_guard.unlock()
    yield


class TestCryptoGuard:
    def test_unlock_valido(self):
        crypto_guard.unlock()
        assert crypto_guard.is_unlocked() is True

    def test_roundtrip_cifra_e_decifra(self):
        token = crypto_guard.encrypt_value("meu-segredo-123")
        assert token.startswith("v1.")
        assert "meu-segredo-123" not in token
        assert crypto_guard.decrypt_value(token) == "meu-segredo-123"

    def test_ciphertexts_diferentes_por_nonce(self):
        a = crypto_guard.encrypt_value("mesmo valor")
        b = crypto_guard.encrypt_value("mesmo valor")
        assert a != b

    def test_dados_errados_nao_desbloqueiam(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"SGTI_OWNER_NAME": "OUTRA PESSOA"}):
            with pytest.raises(crypto_guard.CryptoLockedError):
                crypto_guard.unlock()
        crypto_guard.unlock()  # restaura estado

    def test_tamper_detectado(self):
        token = crypto_guard.encrypt_value("dado importante")
        bad = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(crypto_guard.CryptoTamperError):
            crypto_guard.decrypt_value(bad)

    def test_sem_env_bloqueado(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"SGTI_OWNER_NAME": "", "SGTI_OWNER_CPF": ""}):
            with pytest.raises(crypto_guard.CryptoLockedError):
                crypto_guard.unlock()
        crypto_guard.unlock()  # restaura estado

    def test_is_encrypted(self):
        assert crypto_guard.is_encrypted(None) is False
        assert crypto_guard.is_encrypted("texto comum") is False
        assert crypto_guard.is_encrypted(crypto_guard.encrypt_value("x")) is True


class TestColunasCifradas:
    def test_totp_secret_cifrado_no_banco(self, db_session):
        acc = models.ServiceAccount(
            name="acc-crypto-test",
            expires_at=datetime_expiry(),
            is_active=True,
        )
        acc.set_token("tok-crypto-test")
        acc.totp_secret = "SEGREDO_TOTP_PLAIN"
        db_session.add(acc)
        db_session.commit()

        # valor cru no banco (sem o TypeDecorator) deve estar cifrado
        from sqlalchemy import text
        raw = db_session.execute(
            text("SELECT totp_secret FROM service_accounts WHERE name='acc-crypto-test'")
        ).scalar()
        assert raw is not None
        assert raw.startswith("v1.")
        assert "SEGREDO_TOTP" not in raw

        # ORM decripta na leitura
        db_session.expire_all()
        obj = db_session.query(models.ServiceAccount).filter_by(name="acc-crypto-test").first()
        assert obj.totp_secret == "SEGREDO_TOTP_PLAIN"

    def test_audit_usuario_cifrado(self, db_session):
        db_session.add(
            models.AuditLog(entidade="x", entidade_id=1, acao="TESTE", usuario="user@ad.local")
        )
        db_session.commit()

        from sqlalchemy import text
        raw = db_session.execute(
            text("SELECT usuario FROM audit_log WHERE acao='TESTE'")
        ).scalar()
        assert raw.startswith("v1.")
        assert "user@ad.local" not in raw

        db_session.expire_all()
        log = db_session.query(models.AuditLog).filter_by(acao="TESTE").first()
        assert log.usuario == "user@ad.local"


def datetime_expiry():
    import datetime as _dt
    return _dt.datetime(2099, 12, 31, 23, 59, 59)