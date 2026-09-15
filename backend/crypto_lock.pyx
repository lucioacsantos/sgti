# cython: language_level=3, embedsignature=False, binding=False
# -*- coding: utf-8 -*-
"""
crypto_lock — módulo proprietário SGTI.

Cifra dados sensíveis com AES-256-GCM. A chave é derivada dos dados do
proprietário (nome + parte do CPF) que ficam EMBUTIDOS no binário compilado
apenas como hashes SHA-256 com salt — os dados em claro não existem no .so.

Se este módulo for removido dos códigos, ou os dados do proprietário mudarem,
o sistema não inicializa e os dados cifrados ficam ilegíveis.
"""

import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

__all__ = [
    "is_unlocked", "verify_owner", "derive_key", "encrypt", "decrypt",
    "seal_data", "open_data", "compute_seal", "verify_seal",
]

_SALT = b"SGTI|crypto_lock|v1"
_PBKDF2_ITERATIONS = 600_000
_OWNER_NAME_HASH: bytes | None = None
_OWNER_ID_HASH: bytes | None = None
_CHECK_TOKEN: bytes | None = None
_UNLOCKED = False


def cdef_init(owner_name_hash: bytes, owner_id_hash: bytes, check_token: bytes):
    """Injetado pelo build com os hashes do proprietário. Sem isto, trava."""
    global _OWNER_NAME_HASH, _OWNER_ID_HASH, _CHECK_TOKEN
    _OWNER_NAME_HASH = bytes(owner_name_hash)
    _OWNER_ID_HASH = bytes(owner_id_hash)
    _CHECK_TOKEN = bytes(check_token)
    _UNLOCKED = False


def is_unlocked() -> bool:
    return _UNLOCKED


def verify_owner(nome: str, parte_cpf: str) -> bool:
    """Confere os dados em claro contra os hashes embutidos e libera o uso."""
    global _UNLOCKED
    if _OWNER_NAME_HASH is None or _OWNER_ID_HASH is None or _CHECK_TOKEN is None:
        return False
    h_nome = hashlib.sha256(
        b"nome|" + nome.strip().upper().encode("utf-8")
    ).digest()
    h_cpf = hashlib.sha256(
        b"cpf|" + "".join(ch for ch in parte_cpf if ch.isdigit()).encode()
    ).digest()
    if not hmac.compare_digest(h_nome, _OWNER_NAME_HASH):
        return False
    if not hmac.compare_digest(h_cpf, _OWNER_ID_HASH):
        return False
    if not hmac.compare_digest(
        derive_key(nome, parte_cpf, _PBKDF2_ITERATIONS), _CHECK_TOKEN
    ):
        return False
    _UNLOCKED = True
    return True


def derive_key(nome: str, parte_cpf: str, iterations: int = _PBKDF2_ITERATIONS) -> bytes:
    """Deriva a chave-mestra: SHA-256(SHA-256(nome) || SHA-256(cpf) || salt)."""
    h_nome = hashlib.sha256(b"nome|" + nome.strip().upper().encode("utf-8")).digest()
    h_cpf = hashlib.sha256(
        b"cpf|" + "".join(ch for ch in parte_cpf if ch.isdigit()).encode()
    ).digest()
    return hashlib.pbkdf2_hmac(
        "sha256", h_nome + h_cpf, b"SGTI|crypto_lock|salt", iterations, dklen=32
    )


def _aesgcm(key: bytes) -> AESGCM:
    if len(key) != 32:
        raise ValueError("chave AES-256 precisa ter 32 bytes")
    return AESGCM(key)


def encrypt(plaintext: str, key: bytes) -> str:
    """AES-256-GCM com nonce aleatório. Formato: v1.<nonce b64>.<ciphertext b64>."""
    import base64

    nonce = os.urandom(12)
    ct = _aesgcm(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return "v1." + base64.urlsafe_b64encode(nonce).decode().rstrip("=") + "." + base64.urlsafe_b64encode(ct).decode().rstrip("=")


def decrypt(token: str, key: bytes) -> str:
    """Reverte encrypt(). Levanta ValueError se chave errada ou dado adulterado."""
    import base64

    if not token or not token.startswith("v1."):
        raise ValueError("formato de ciphertext desconhecido")
    try:
        _, nonce_b64, ct_b64 = token.split(".", 2)
        pad = lambda s: s + "=" * (-len(s) % 4)
        nonce = base64.urlsafe_b64decode(nonce_b64)
        ct = base64.urlsafe_b64decode(pad(ct_b64))
        pt = _aesgcm(key).decrypt(nonce, ct, None)
    except Exception as exc:
        raise ValueError("falha ao decifrar (chave incorreta ou dado adulterado)") from exc
    return pt.decode("utf-8")


def seal_data(plaintext: str, nome: str, parte_cpf: str) -> str:
    """API de alto nível: deriva a chave do proprietário e cifra."""
    if not _UNLOCKED:
        raise RuntimeError("crypto_lock bloqueado: proprietário não verificado")
    return encrypt(plaintext, derive_key(nome, parte_cpf))


def open_data(token: str, nome: str, parte_cpf: str) -> str:
    """API de alto nível: decifra com a chave do proprietário."""
    if not _UNLOCKED:
        raise RuntimeError("crypto_lock bloqueado: proprietário não verificado")
    return decrypt(token, derive_key(nome, parte_cpf))


def compute_seal(material: bytes) -> bytes:
    """Selo de integridade: HMAC-SHA256 do material informado com a chave raiz."""
    if not _UNLOCKED:
        raise RuntimeError("crypto_lock bloqueado: proprietário não verificado")
    key = _CHECK_TOKEN
    return hmac.new(key, material, hashlib.sha256).digest()


def verify_seal(material: bytes, seal: bytes) -> bool:
    try:
        return hmac.compare_digest(compute_seal(material), bytes(seal))
    except Exception:
        return False