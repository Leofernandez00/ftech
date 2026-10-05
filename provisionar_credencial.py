from pathlib import Path
import os
import getpass
import win32crypt

APPDIR = (
    Path(os.environ.get("PROGRAMDATA", str(Path.home())))
    / "Alta Paulista"
    / "FTECH Compras"
)

DEST = APPDIR / "sql.secret"

ENTROPY = b"AltaPaulista.FTECHCompras.v1"

# CRYPTPROTECT_LOCAL_MACHINE
DPAPI_LOCAL_MACHINE = 0x4


print("=" * 60)
print("FTECH COMPRAS - PROVISIONAMENTO DA CREDENCIAL SQL")
print("=" * 60)
print()

senha = getpass.getpass(
    "Senha do login FTECH_COMPRAS_APP: "
)

if not senha:
    raise SystemExit("Senha vazia. Operação cancelada.")

try:

    APPDIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # CryptProtectData retorna diretamente os bytes criptografados.
    blob = win32crypt.CryptProtectData(
        senha.encode("utf-8"),
        "FTECH Compras SQL",
        ENTROPY,
        None,
        None,
        DPAPI_LOCAL_MACHINE
    )

    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError(
            f"Retorno inesperado do DPAPI: {type(blob).__name__}"
        )

    DEST.write_bytes(blob)

    print()
    print("=" * 60)
    print("CREDENCIAL PROTEGIDA COM SUCESSO")
    print("=" * 60)
    print()
    print(f"Arquivo: {DEST}")
    print(f"Tamanho: {len(blob)} bytes")
    print()
    print("A senha SQL não foi gravada em texto puro.")

except Exception as erro:

    print()
    print("=" * 60)
    print("ERRO AO PROTEGER A CREDENCIAL")
    print("=" * 60)
    print()
    print(erro)

    raise