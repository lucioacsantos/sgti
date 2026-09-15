"""Wrapper de alto nível do crypto_lock para uso pela aplicação SGTI.

Gerencia o estado de desbloqueio (dados do proprietário vêm de variáveis de
ambiente injetadas no processo, nunca gravadas em disco) e expõe funções para
cifrar/decifrar valores que vão para o banco.
"""
import base64
import hashlib
import os
from pathlib import Path

try:
    import crypto_lock as _cl
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "crypto_lock.compilado ausente: rode build_crypto_lock.py com os dados do proprietário"
    ) from exc

SEAL_PATH = Path(__file__).parent / ".seal" / "seal.bin"


class CryptoLockError(RuntimeError):
    pass


class CryptoLockedError(CryptoLockError):
    pass


class CryptoTamperError(CryptoLockError):
    pass


def _owner_from_env() -> tuple[str, str]:
    nome = os.environ.get("SGTI_OWNER_NAME", "")
    cpf = os.environ.get("SGTI_OWNER_CPF", "")
    if not nome or not cpf:
        raise CryptoLockedError(
            "SGTI_OWNER_NAME/SGTI_OWNER_CPF não definidos — sistema bloqueado"
        )
    return nome, cpf


def unlock() -> None:
    """Verifica os dados do proprietário contra o binário compilado."""
    nome, cpf = _owner_from_env()
    if not _cl.verify_owner(nome, cpf):
        raise CryptoLockedError(
            "Dados do proprietário inválidos — sistema bloqueado"
        )
    # verify_owner() já liberou o módulo; agora valida a integridade do binário
    _verify_seal()


def is_unlocked() -> bool:
    return _cl.is_unlocked()


def _verify_seal() -> None:
    """Revalida o selo de integridade do .so (detecção de binário adulterado)."""
    if not SEAL_PATH.exists():
        return  # selo ainda não gerado (primeiro boot pré-build)
    so_path = _so_path()
    if so_path is None:
        raise CryptoLockError("crypto_lock compilado não encontrado")
    so_hash = hashlib.sha256(so_path.read_bytes()).digest()
    stored = base64.b64decode(SEAL_PATH.read_bytes())
    if not _cl.verify_seal(so_hash, stored):
        raise CryptoTamperError(
            "Selo de integridade inválido: binário crypto_lock adulterado"
        )


def _so_path() -> Path | None:
    parent = Path(__file__).parent
    for p in sorted(parent.glob("crypto_lock*.so")):
        return p
    return None


def encrypt_value(value: str) -> str:
    """Cifra um valor para gravar no banco. Requer unlock prévio."""
    if not _cl.is_unlocked():
        raise CryptoLockedError("crypto_lock bloqueado: chame unlock() no boot")
    nome, cpf = _owner_from_env()
    return _cl.seal_data(value, nome, cpf)


def decrypt_value(token: str) -> str:
    """Decifra um valor vindo do banco. Levanta CryptoTamperError se inválido."""
    if not _cl.is_unlocked():
        raise CryptoLockedError("crypto_lock bloqueado: chame unlock() no boot")
    nome, cpf = _owner_from_env()
    try:
        return _cl.open_data(token, nome, cpf)
    except ValueError as exc:
        raise CryptoTamperError(str(exc)) from exc


def is_encrypted(value: str | None) -> bool:
    """True se o valor está no formato v1.<nonce>.<ct> (cifrado)."""
    if not value:
        return False
    parts = value.split(".")
    return (
        len(parts) == 3
        and parts[0] == "v1"
        and parts[1].isascii()
        and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in parts[1])
    )