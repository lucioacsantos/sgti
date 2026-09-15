"""Build do crypto_lock: compila Cython -> .so embutindo os hashes do proprietário.

Uso:
    ../venv/bin/python build_crypto_lock.py "NOME" CPF
"""
import base64
import hashlib
import hmac
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "crypto_lock.pyx")


def main(nome: str, parte_cpf: str) -> None:
    if not nome.strip() or not parte_cpf.strip():
        raise SystemExit("nome e parte_cpf são obrigatórios")

    h_nome = hashlib.sha256(b"nome|" + nome.strip().upper().encode()).digest()
    h_cpf = hashlib.sha256(
        b"cpf|" + "".join(c for c in parte_cpf if c.isdigit()).encode()
    ).digest()

    # token de verificação derivado dos dados do proprietário (não reversível)
    iterations = 600_000
    check = hashlib.pbkdf2_hmac(
        "sha256", h_nome + h_cpf, b"SGTI|crypto_lock|salt", iterations, dklen=32
    )

    init_source = f'''_INIT_HASH_NAME = {h_nome!r}
_INIT_HASH_ID = {h_cpf!r}
_INIT_CHECK = {check!r}


def _bootstrap_init() -> None:
    cdef_init(_INIT_HASH_NAME, _INIT_HASH_ID, _INIT_CHECK)


_bootstrap_init()
'''

    with open(SRC, "r", encoding="utf-8") as f:
        source = f.read()
    if "_INIT_HASH_NAME" in source:
        raise SystemExit("crypto_lock.pyx já contém injeção — reverta antes de rebuild")

    injected = source + "\n\n" + init_source
    build_src = os.path.join(BASE, "_crypto_lock_build.pyx")
    with open(build_src, "w", encoding="utf-8") as f:
        f.write(injected)

    print("[1/3] Cythonizando…")
    subprocess.run(
        [sys.executable, "-m", "cython", "-3", "--module-name", "crypto_lock",
         "-o", os.path.join(BASE, "_crypto_lock_build.c"), build_src],
        check=True, cwd=BASE,
    )

    print("[2/3] Compilando .so…")
    include = sysconfig_dir()
    ext_suffix = so_suffix()
    out_so = os.path.join(BASE, f"crypto_lock{ext_suffix}")
    subprocess.run(
        ["gcc", "-O2", "-fPIC", "-shared", "-I", include,
         os.path.join(BASE, "_crypto_lock_build.c"),
         "-o", out_so],
        check=True, cwd=BASE,
    )
    print(f"      -> {out_so}")

    print("[3/3] Gerando selo de integridade…")
    os.makedirs(os.path.join(BASE, ".seal"), exist_ok=True)
    so_hash = hashlib.sha256(open(out_so, "rb").read()).digest()
    # selo = HMAC-SHA256(hash do .so) com a chave raiz embutida no binário
    seal = hmac.new(check, so_hash, hashlib.sha256).digest()
    with open(os.path.join(BASE, ".seal", "seal.bin"), "wb") as f:
        f.write(base64.b64encode(seal))
    os.remove(build_src)
    os.remove(os.path.join(BASE, "_crypto_lock_build.c"))
    print("OK — crypto_lock compilado e selado.")


def sysconfig_dir() -> str:
    import sysconfig
    return sysconfig.get_paths()["include"]


def so_suffix() -> str:
    import sysconfig
    return sysconfig.get_config_var("EXT_SUFFIX") or ".so"


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) != 3:
        raise SystemExit(f"uso: {_sys.argv[0]} 'NOME' PARTE_DO_CPF")
    main(_sys.argv[1], _sys.argv[2])