"""
Importa todas as planilhas de uma pasta para o SQL Server sem repetir linhas.

Formatos aceitos: .xlsx, .xlsm, .xls, .csv e .txt.
Cada aba de cada arquivo Excel é processada.

Dependências:
    py -m pip install pandas openpyxl pyodbc xlrd
"""

from __future__ import annotations

import hashlib
import math
import re
import sys
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from tkinter import Tk, filedialog

import pandas as pd
import pyodbc


# =============================================================================
# CONFIGURAÇÃO DO SQL SERVER
# =============================================================================

SERVIDOR = r"188.220.168.222"
BANCO = "FTECH"

# Escolha somente uma forma de autenticação:
USAR_AUTENTICACAO_WINDOWS = False
USUARIO = "ftech"
SENHA = "ftech@1975"

# Deixe vazio para o programa abrir a janela de seleção de pasta.
PASTA_PLANILHAS = ""

# True também procura planilhas nas subpastas.
BUSCAR_SUBPASTAS = True


COLUNAS = [
    "FILIAL",
    "CLIENTE",
    "LOJA",
    "NOME CLIENTE",
    "CLASSIFICACAO",
    "CIDADE",
    "ESTADO",
    "NOME VENDEDOR",
    "PRODUTO",
    "DESCRICAO",
    "LINHA",
    "TIPO",
    "QTD",
    "PRECO",
    "VALOR TOTAL",
    "CUSTO STD",
    "CUSTO TOTAL",
    "MARGEM",
    "DT EMISSAO",
    "NF",
    "SERIE",
]

COLUNAS_TEXTO = [
    "FILIAL",
    "CLIENTE",
    "LOJA",
    "NOME CLIENTE",
    "CLASSIFICACAO",
    "CIDADE",
    "ESTADO",
    "NOME VENDEDOR",
    "PRODUTO",
    "DESCRICAO",
    "LINHA",
    "TIPO",
    "NF",
    "SERIE",
]

COLUNAS_DECIMAIS = [
    "QTD",
    "PRECO",
    "VALOR TOTAL",
    "CUSTO STD",
    "CUSTO TOTAL",
    "MARGEM",
]

ESCALA_DECIMAIS = {
    "QTD": 4,
    "PRECO": 6,
    "VALOR TOTAL": 6,
    "CUSTO STD": 6,
    "CUSTO TOTAL": 6,
    "MARGEM": 10,
}

COLUNAS_SQL = {
    "FILIAL": "FILIAL",
    "CLIENTE": "CLIENTE",
    "LOJA": "LOJA",
    "NOME CLIENTE": "NOME_CLIENTE",
    "CLASSIFICACAO": "CLASSIFICACAO",
    "CIDADE": "CIDADE",
    "ESTADO": "ESTADO",
    "NOME VENDEDOR": "NOME_VENDEDOR",
    "PRODUTO": "PRODUTO",
    "DESCRICAO": "DESCRICAO",
    "LINHA": "LINHA",
    "TIPO": "TIPO",
    "QTD": "QTD",
    "PRECO": "PRECO",
    "VALOR TOTAL": "VALOR_TOTAL",
    "CUSTO STD": "CUSTO_STD",
    "CUSTO TOTAL": "CUSTO_TOTAL",
    "MARGEM": "MARGEM",
    "DT EMISSAO": "DT_EMISSAO",
    "NF": "NF",
    "SERIE": "SERIE",
}


def normalizar_cabecalho(valor: object) -> str:
    texto = str(valor).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


def limpar_texto(valor: object) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    return texto if texto else None


def converter_decimal(valor: object, casas_decimais: int) -> Decimal | None:
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, Decimal):
        numero = valor
    elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor)):
            return None
        numero = Decimal(str(valor))
    else:
        texto = str(valor).strip().replace("R$", "").replace("%", "").replace(" ", "")
        if not texto:
            return None

        # Aceita 1.234,56 e 1,234.56, além de números simples.
        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        try:
            numero = Decimal(texto)
        except InvalidOperation as exc:
            raise ValueError(f"valor numérico inválido: {valor!r}") from exc

    # Ajusta previamente à mesma escala da coluna no SQL Server. Isso evita
    # o erro pyodbc HY000 "Converting decimal loses precision".
    unidade = Decimal(1).scaleb(-casas_decimais)
    try:
        return numero.quantize(unidade, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(
            f"valor fora da precisão suportada: {valor!r}"
        ) from exc


def converter_data(valor: object) -> datetime | None:
    if valor is None or pd.isna(valor):
        return None
    data = pd.to_datetime(valor, dayfirst=True, errors="coerce")
    if pd.isna(data):
        raise ValueError(f"data inválida: {valor!r}")
    return data.to_pydatetime().replace(tzinfo=None)


def valor_para_hash(valor: object) -> str:
    if valor is None:
        return "<NULL>"
    if isinstance(valor, Decimal):
        normalizado = format(valor.normalize(), "f")
        return "0" if normalizado in ("-0", "") else normalizado
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(valor)


def preparar_dataframe(df: pd.DataFrame) -> list[tuple]:
    df = df.copy()
    df.columns = [normalizar_cabecalho(c) for c in df.columns]

    colunas_encontradas = [c for c in COLUNAS if c in df.columns]
    if not colunas_encontradas:
        raise ValueError(
            "nenhuma das colunas esperadas foi encontrada nesta aba"
        )

    # Colunas ausentes são criadas vazias e serão gravadas como NULL.
    # Dessa forma, planilhas antigas ou incompletas também podem ser importadas.
    for coluna in COLUNAS:
        if coluna not in df.columns:
            df[coluna] = pd.NA

    df = df[COLUNAS].dropna(how="all")
    registros: list[tuple] = []

    for numero_linha, (_, linha) in enumerate(df.iterrows(), start=2):
        try:
            valores: list[object] = []
            for coluna in COLUNAS:
                valor = linha[coluna]
                if coluna in COLUNAS_TEXTO:
                    valor = limpar_texto(valor)
                elif coluna in COLUNAS_DECIMAIS:
                    valor = converter_decimal(valor, ESCALA_DECIMAIS[coluna])
                elif coluna == "DT EMISSAO":
                    valor = converter_data(valor)
                valores.append(valor)

            conteudo_hash = "\x1f".join(valor_para_hash(v) for v in valores)
            hash_linha = hashlib.sha256(conteudo_hash.encode("utf-8")).digest()

            # Envia Decimal como texto numérico normalizado. O SQL Server faz
            # a conversão para decimal(p,s) na coluna de destino. Isso evita
            # que o pyodbc infira uma precisão pequena pela primeira linha e
            # depois gere HY000 "Converting decimal loses precision".
            valores_sql = [
                format(v, "f") if isinstance(v, Decimal) else v
                for v in valores
            ]
            registros.append(tuple(valores_sql) + (hash_linha,))
        except Exception as exc:
            raise ValueError(f"erro na linha {numero_linha}: {exc}") from exc

    # Elimina repetições existentes no mesmo arquivo/aba.
    unicos = {}
    for registro in registros:
        unicos[registro[-1]] = registro
    return list(unicos.values())


def ler_arquivo(caminho: Path):
    extensao = caminho.suffix.lower()

    if extensao in {".xlsx", ".xlsm", ".xls"}:
        planilha = pd.ExcelFile(caminho)
        for aba in planilha.sheet_names:
            yield aba, pd.read_excel(
                caminho,
                sheet_name=aba,
                dtype={c: str for c in COLUNAS_TEXTO},
            )
    else:
        # sep=None detecta automaticamente vírgula, ponto e vírgula ou tabulação.
        yield caminho.stem, pd.read_csv(
            caminho,
            sep=None,
            engine="python",
            dtype={c: str for c in COLUNAS_TEXTO},
            encoding="utf-8-sig",
        )


def selecionar_pasta() -> Path:
    if PASTA_PLANILHAS.strip():
        return Path(PASTA_PLANILHAS).expanduser().resolve()

    raiz = Tk()
    raiz.withdraw()
    raiz.attributes("-topmost", True)
    selecionada = filedialog.askdirectory(title="Selecione a pasta com as planilhas")
    raiz.destroy()

    if not selecionada:
        raise SystemExit("Nenhuma pasta foi selecionada.")
    return Path(selecionada).resolve()


def listar_arquivos(pasta: Path) -> list[Path]:
    extensoes = {".xlsx", ".xlsm", ".xls", ".csv", ".txt"}
    busca = pasta.rglob("*") if BUSCAR_SUBPASTAS else pasta.glob("*")
    return sorted(
        p for p in busca
        if p.is_file()
        and p.suffix.lower() in extensoes
        and not p.name.startswith("~$")
    )


def conectar() -> pyodbc.Connection:
    partes = [
        "DRIVER={ODBC Driver 17 for SQL Server}",
        f"SERVER={SERVIDOR}",
        f"DATABASE={BANCO}",
        "TrustServerCertificate=yes",
    ]
    if USAR_AUTENTICACAO_WINDOWS:
        partes.append("Trusted_Connection=yes")
    else:
        partes.extend([f"UID={USUARIO}", f"PWD={SENHA}"])
    return pyodbc.connect(";".join(partes) + ";", autocommit=False)


SQL_CRIAR_STAGE = """
IF OBJECT_ID('tempdb..#VENDAS_STAGE') IS NOT NULL
    DROP TABLE #VENDAS_STAGE;

CREATE TABLE #VENDAS_STAGE (
    FILIAL           varchar(10)     NULL,
    CLIENTE          varchar(20)     NULL,
    LOJA             varchar(10)     NULL,
    NOME_CLIENTE     varchar(255)    NULL,
    CLASSIFICACAO    varchar(20)     NULL,
    CIDADE           varchar(100)    NULL,
    ESTADO           char(2)         NULL,
    NOME_VENDEDOR    varchar(100)    NULL,
    PRODUTO          varchar(50)     NULL,
    DESCRICAO        varchar(500)    NULL,
    LINHA            varchar(100)    NULL,
    TIPO             varchar(20)     NULL,
    QTD              decimal(18,4)   NULL,
    PRECO            decimal(19,6)   NULL,
    VALOR_TOTAL      decimal(19,6)   NULL,
    CUSTO_STD        decimal(19,6)   NULL,
    CUSTO_TOTAL      decimal(19,6)   NULL,
    MARGEM           decimal(19,10)  NULL,
    DT_EMISSAO       datetime2(0)    NULL,
    NF               varchar(20)     NULL,
    SERIE            varchar(10)     NULL,
    HASH_LINHA       binary(32)      NOT NULL
);
"""

SQL_GARANTIR_TABELA = """
IF OBJECT_ID(N'dbo.VENDAS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.VENDAS
    (
        ID                bigint IDENTITY(1,1) NOT NULL,
        FILIAL            varchar(10)     NULL,
        CLIENTE           varchar(20)     NULL,
        LOJA              varchar(10)     NULL,
        NOME_CLIENTE      varchar(255)    NULL,
        CLASSIFICACAO     varchar(20)     NULL,
        CIDADE            varchar(100)    NULL,
        ESTADO            char(2)         NULL,
        NOME_VENDEDOR     varchar(100)    NULL,
        PRODUTO           varchar(50)     NULL,
        DESCRICAO         varchar(500)    NULL,
        LINHA             varchar(100)    NULL,
        TIPO              varchar(20)     NULL,
        QTD               decimal(18,4)   NULL,
        PRECO             decimal(19,6)   NULL,
        VALOR_TOTAL       decimal(19,6)   NULL,
        CUSTO_STD         decimal(19,6)   NULL,
        CUSTO_TOTAL       decimal(19,6)   NULL,
        MARGEM            decimal(19,10)  NULL,
        DT_EMISSAO        datetime2(0)    NULL,
        NF                varchar(20)     NULL,
        SERIE             varchar(10)     NULL,
        HASH_LINHA        binary(32)      NOT NULL,
        ARQUIVO_ORIGEM    nvarchar(260)   NULL,
        ABA_ORIGEM        nvarchar(128)   NULL,
        IMPORTADO_EM      datetime2(0)    NOT NULL
            CONSTRAINT DF_VENDAS_IMPORTADO_EM DEFAULT SYSDATETIME(),

        CONSTRAINT PK_VENDAS PRIMARY KEY CLUSTERED (ID),
        CONSTRAINT UQ_VENDAS_HASH_LINHA UNIQUE (HASH_LINHA)
    );

    CREATE INDEX IX_VENDAS_DT_EMISSAO
        ON dbo.VENDAS (DT_EMISSAO);

    CREATE INDEX IX_VENDAS_NF
        ON dbo.VENDAS (NF, SERIE, FILIAL);

    CREATE INDEX IX_VENDAS_PRODUTO
        ON dbo.VENDAS (PRODUTO);
END;
"""

SQL_INSERIR_STAGE = """
INSERT INTO #VENDAS_STAGE (
    FILIAL, CLIENTE, LOJA, NOME_CLIENTE, CLASSIFICACAO, CIDADE, ESTADO,
    NOME_VENDEDOR, PRODUTO, DESCRICAO, LINHA, TIPO, QTD, PRECO,
    VALOR_TOTAL, CUSTO_STD, CUSTO_TOTAL, MARGEM, DT_EMISSAO, NF, SERIE,
    HASH_LINHA
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

SQL_IMPORTAR_NOVOS = """
INSERT INTO dbo.VENDAS (
    FILIAL, CLIENTE, LOJA, NOME_CLIENTE, CLASSIFICACAO, CIDADE, ESTADO,
    NOME_VENDEDOR, PRODUTO, DESCRICAO, LINHA, TIPO, QTD, PRECO,
    VALOR_TOTAL, CUSTO_STD, CUSTO_TOTAL, MARGEM, DT_EMISSAO, NF, SERIE,
    HASH_LINHA, ARQUIVO_ORIGEM, ABA_ORIGEM
)
SELECT
    S.FILIAL, S.CLIENTE, S.LOJA, S.NOME_CLIENTE, S.CLASSIFICACAO,
    S.CIDADE, S.ESTADO, S.NOME_VENDEDOR, S.PRODUTO, S.DESCRICAO,
    S.LINHA, S.TIPO, S.QTD, S.PRECO, S.VALOR_TOTAL, S.CUSTO_STD,
    S.CUSTO_TOTAL, S.MARGEM, S.DT_EMISSAO, S.NF, S.SERIE,
    S.HASH_LINHA, ?, ?
FROM #VENDAS_STAGE AS S
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.VENDAS AS V WITH (UPDLOCK, HOLDLOCK)
    WHERE V.HASH_LINHA = S.HASH_LINHA
);
"""


def garantir_tabela(conexao: pyodbc.Connection) -> None:
    cursor = conexao.cursor()
    cursor.execute(SQL_GARANTIR_TABELA)
    conexao.commit()
    cursor.close()


def importar_registros(
    conexao: pyodbc.Connection,
    registros: list[tuple],
    arquivo: str,
    aba: str,
) -> int:
    if not registros:
        return 0

    cursor = conexao.cursor()
    cursor.execute(SQL_CRIAR_STAGE)
    # fast_executemany não é usado aqui porque algumas versões do pyodbc/ODBC
    # inferem incorretamente a precisão decimal usando a primeira linha.
    cursor.fast_executemany = False
    cursor.executemany(SQL_INSERIR_STAGE, registros)
    cursor.execute(SQL_IMPORTAR_NOVOS, arquivo, aba)
    inseridos = cursor.rowcount
    conexao.commit()
    cursor.close()
    return max(inseridos, 0)


def main() -> None:
    pasta = selecionar_pasta()
    if not pasta.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {pasta}")

    arquivos = listar_arquivos(pasta)
    if not arquivos:
        print(f"Nenhuma planilha encontrada em: {pasta}")
        return

    print(f"Pasta: {pasta}")
    print(f"Arquivos encontrados: {len(arquivos)}")

    total_lidos = 0
    total_inseridos = 0
    total_ignorados = 0
    erros = 0

    with conectar() as conexao:
        garantir_tabela(conexao)
        print(f"Tabela verificada: [{BANCO}].[dbo].[VENDAS]")

        for caminho in arquivos:
            try:
                for aba, dataframe in ler_arquivo(caminho):
                    registros = preparar_dataframe(dataframe)
                    inseridos = importar_registros(
                        conexao, registros, caminho.name, str(aba)
                    )
                    ignorados = len(registros) - inseridos
                    total_lidos += len(registros)
                    total_inseridos += inseridos
                    total_ignorados += ignorados
                    print(
                        f"[OK] {caminho.name} | aba {aba}: "
                        f"{inseridos} inseridos, {ignorados} já existentes."
                    )
            except Exception as exc:
                conexao.rollback()
                erros += 1
                print(f"[ERRO] {caminho.name}: {exc}")

    print("\n========== RESUMO ==========")
    print(f"Linhas válidas lidas: {total_lidos}")
    print(f"Linhas novas inseridas: {total_inseridos}")
    print(f"Linhas já existentes: {total_ignorados}")
    print(f"Arquivos com erro: {erros}")

    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()