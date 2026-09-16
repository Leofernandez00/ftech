import requests
import pandas as pd
import time
import urllib
import threading
import tkinter as tk
import json
import math

from datetime import datetime
from tkinter import scrolledtext

from sqlalchemy import (
    create_engine,
    text
)


# ============================================================
# CONFIGURAÇÃO SQL SERVER
# ============================================================

SQL_SERVER = "188.220.168.222"
SQL_DATABASE = "FTECH"
SQL_USER = "ftech"

# COLOQUE SUA SENHA AQUI
SQL_PASSWORD = "ftech@1975"


conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={SQL_SERVER};"
    f"Database={SQL_DATABASE};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PASSWORD};"
    "TrustServerCertificate=yes;"
    "Connection Timeout=30;"
)


params = urllib.parse.quote_plus(conn_str)


engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    fast_executemany=True,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30
)


# ============================================================
# CONFIGURAÇÃO API QUARK
# ============================================================

url = (
    "https://api.quark.tec.br/"
    "rh/ext/v1/colaboradores/"
)


headers_base = {
    "accept": "*/*",

    # COLOQUE SEU TOKEN AQUI
    "Auth-token": "4cebd80553d725cbf3157b48e1d56c045423216062ee116652b45087a371ea19"
}


# ============================================================
# UNIDADES QUARK
# ============================================================

unidades = {

    2981000: "ALTA PAULISTA DRACENA",

    2971203:
        "ALTA PAULISTA EQUIPAMENTOS AGRICOLAS LTDA",

    2980997:
        "ALTA PAULISTA EQUIPAMENTOS AGRICOLAS LTDA",

    2981001:
        "ALTA PAULISTA NOVA ANDRADINA",

    2980996:
        "ARAÇATUBA",

    2980998:
        "DANIELE SPORNRAFT PAZINATO DIAS EPP",

    2980999:
        "DOURADOS",

    2981002:
        "TUPÃ",

    6317831:
        "TRÊS LAGOAS",

    8789215:
        "SÃO MIGUEL DOS CAMPOS",

    11612290:
        "CHICOTES BRASIL"
}


# ============================================================
# CONTROLE
# ============================================================

executando = False


# ============================================================
# LOG
# ============================================================

def log(msg=""):

    try:

        janela.after(
            0,
            lambda: adicionar_log(msg)
        )

    except Exception:

        pass


def adicionar_log(msg):

    try:

        log_box.insert(
            tk.END,
            str(msg) + "\n"
        )

        log_box.see(
            tk.END
        )

    except Exception:

        pass


# ============================================================
# TESTA NULL
# ============================================================

def eh_nulo(valor):

    if valor is None:
        return True

    try:

        resultado = pd.isna(valor)

        if isinstance(
            resultado,
            bool
        ):

            return resultado

    except Exception:

        pass

    return False


# ============================================================
# BUSCA ESTRUTURA COMPLETA DA TABELA SQL
# ============================================================

def obter_estrutura_sql():

    sql = text("""

        SELECT

            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,

            COLUMNPROPERTY(
                OBJECT_ID(
                    QUOTENAME(c.TABLE_SCHEMA)
                    + '.'
                    + QUOTENAME(c.TABLE_NAME)
                ),
                c.COLUMN_NAME,
                'IsIdentity'
            ) AS IS_IDENTITY,

            COLUMNPROPERTY(
                OBJECT_ID(
                    QUOTENAME(c.TABLE_SCHEMA)
                    + '.'
                    + QUOTENAME(c.TABLE_NAME)
                ),
                c.COLUMN_NAME,
                'IsComputed'
            ) AS IS_COMPUTED

        FROM
            INFORMATION_SCHEMA.COLUMNS c

        WHERE
            c.TABLE_SCHEMA = 'dbo'
            AND c.TABLE_NAME = 'COLABORADORES_QUARK'

        ORDER BY
            c.ORDINAL_POSITION

    """)

    estrutura = []

    with engine.connect() as conn:

        resultado = conn.execute(
            sql
        )

        for row in resultado:

            estrutura.append({

                "nome":
                    row[0],

                "tipo":
                    str(row[1]).lower(),

                "tamanho":
                    row[2],

                "precisao":
                    row[3],

                "escala":
                    row[4],

                "nullable":
                    row[5],

                "identity":
                    bool(row[6]),

                "computed":
                    bool(row[7])

            })

    return estrutura


# ============================================================
# MOSTRA COLUNAS SQL
# ============================================================

def mostrar_estrutura_sql(
    estrutura
):

    log("")
    log(
        "=============================================="
    )

    log(
        "ESTRUTURA DA TABELA SQL SERVER"
    )

    log(
        "=============================================="
    )

    log(
        f"Total de colunas SQL: {len(estrutura)}"
    )

    for coluna in estrutura:

        detalhe = (
            f"{coluna['nome']} "
            f"[{coluna['tipo']}]"
        )

        if coluna["identity"]:

            detalhe += " IDENTITY"

        if coluna["computed"]:

            detalhe += " COMPUTED"

        log(
            f"  -> {detalhe}"
        )


# ============================================================
# CONVERTE UNIX MILISSEGUNDOS -> DATETIME
# ============================================================

def converter_datetime(
    valor
):

    if eh_nulo(valor):

        return None

    # ================================================
    # VALOR NUMÉRICO
    # ================================================

    if isinstance(
        valor,
        (int, float)
    ):

        try:

            numero = float(valor)

            if math.isnan(numero):

                return None

            # ----------------------------------------
            # TIMESTAMP EM MILISSEGUNDOS
            # Ex:
            # 1775444400000
            # ----------------------------------------

            if abs(numero) > 100000000000:

                data = pd.to_datetime(
                    numero,
                    unit="ms",
                    errors="coerce"
                )

            # ----------------------------------------
            # TIMESTAMP EM SEGUNDOS
            # ----------------------------------------

            elif abs(numero) > 1000000000:

                data = pd.to_datetime(
                    numero,
                    unit="s",
                    errors="coerce"
                )

            else:

                return None

            if pd.isna(data):

                return None

            return data.to_pydatetime()

        except Exception:

            return None

    # ================================================
    # DATA EM TEXTO
    # ================================================

    try:

        data = pd.to_datetime(
            valor,
            errors="coerce"
        )

        if pd.isna(data):

            return None

        return data.to_pydatetime()

    except Exception:

        return None


# ============================================================
# CONVERTE DATE
# ============================================================

def converter_date(
    valor
):

    data = converter_datetime(
        valor
    )

    if data is None:

        return None

    return data.date()


# ============================================================
# CONVERTE INTEGER
# ============================================================

def converter_inteiro(
    valor
):

    if eh_nulo(valor):

        return None

    try:

        return int(
            float(valor)
        )

    except Exception:

        return None


# ============================================================
# CONVERTE DECIMAL / FLOAT
# ============================================================

def converter_decimal(
    valor
):

    if eh_nulo(valor):

        return None

    try:

        return float(
            valor
        )

    except Exception:

        return None


# ============================================================
# CONVERTE BIT
# ============================================================

def converter_bit(
    valor
):

    if eh_nulo(valor):

        return None

    if isinstance(
        valor,
        bool
    ):

        return valor

    if isinstance(
        valor,
        (int, float)
    ):

        return bool(
            int(valor)
        )

    texto = str(
        valor
    ).strip().lower()

    if texto in [
        "true",
        "1",
        "sim",
        "yes",
        "s"
    ]:

        return True

    if texto in [
        "false",
        "0",
        "nao",
        "não",
        "no",
        "n"
    ]:

        return False

    return None


# ============================================================
# CONVERTE TEXTO
# ============================================================

def converter_texto(
    valor,
    tamanho=None
):

    if eh_nulo(valor):

        return None

    # OBJETO JSON
    if isinstance(
        valor,
        (dict, list)
    ):

        valor = json.dumps(
            valor,
            ensure_ascii=False,
            default=str
        )

    else:

        valor = str(
            valor
        )

    # -1 significa VARCHAR(MAX) / NVARCHAR(MAX)
    if (
        tamanho is not None
        and tamanho != -1
        and tamanho > 0
    ):

        if len(valor) > tamanho:

            valor = valor[
                :tamanho
            ]

    return valor


# ============================================================
# CONVERSÃO BASEADA NO TIPO REAL DO SQL SERVER
# ============================================================

def converter_valor_sql(
    valor,
    coluna
):

    tipo = coluna[
        "tipo"
    ]

    tamanho = coluna[
        "tamanho"
    ]

    # ================================================
    # NULL
    # ================================================

    if eh_nulo(valor):

        return None

    # ================================================
    # DATAS
    # ================================================

    if tipo in [

        "datetime",
        "datetime2",
        "smalldatetime",
        "datetimeoffset"

    ]:

        return converter_datetime(
            valor
        )

    if tipo == "date":

        return converter_date(
            valor
        )

    # ================================================
    # INTEIROS
    # ================================================

    if tipo in [

        "bigint",
        "int",
        "smallint",
        "tinyint"

    ]:

        return converter_inteiro(
            valor
        )

    # ================================================
    # DECIMAIS
    # ================================================

    if tipo in [

        "decimal",
        "numeric",
        "float",
        "real",
        "money",
        "smallmoney"

    ]:

        return converter_decimal(
            valor
        )

    # ================================================
    # BOOLEAN
    # ================================================

    if tipo == "bit":

        return converter_bit(
            valor
        )

    # ================================================
    # TEXTO
    # ================================================

    if tipo in [

        "varchar",
        "nvarchar",
        "char",
        "nchar",
        "text",
        "ntext",
        "xml"

    ]:

        return converter_texto(
            valor,
            tamanho
        )

    # ================================================
    # OUTROS
    # ================================================

    if isinstance(
        valor,
        (dict, list)
    ):

        return json.dumps(
            valor,
            ensure_ascii=False,
            default=str
        )

    return valor


# ============================================================
# BUSCAR DADOS NA API QUARK
# ============================================================

def buscar_api():

    all_data = []

    for unidade_id, unidade_nome in unidades.items():

        if not executando:

            break

        log("")
        log(
            f"Importando unidade: "
            f"{unidade_nome} "
            f"| ID: {unidade_id}"
        )

        page = 0

        while executando:

            params_api = {

                "page":
                    page,

                "size":
                    100

            }

            headers = (
                headers_base.copy()
            )

            headers[
                "Unidade-Id"
            ] = str(
                unidade_id
            )

            try:

                response = requests.get(

                    url,

                    headers=headers,

                    params=params_api,

                    timeout=30

                )

                response.raise_for_status()

            except requests.exceptions.Timeout:

                log(
                    "TIMEOUT ao consultar API."
                )

                break

            except requests.exceptions.ConnectionError as e:

                log(
                    "Erro de conexão com API:"
                )

                log(
                    str(e)
                )

                break

            except requests.exceptions.HTTPError as e:

                log(
                    f"Erro HTTP: {e}"
                )

                try:

                    log(
                        response.text
                    )

                except Exception:

                    pass

                break

            except Exception as e:

                log(
                    f"Erro na API: {e}"
                )

                break

            # ========================================
            # JSON
            # ========================================

            try:

                result = (
                    response.json()
                )

            except Exception as e:

                log(
                    f"Erro JSON: {e}"
                )

                break

            data = result.get(
                "dados",
                []
            )

            if not data:

                break

            log(
                f"Página {page + 1}"
                f" - "
                f"{len(data)} registros"
            )

            # ========================================
            # ADICIONA UNIDADE AO REGISTRO
            # ========================================

            for item in data:

                item[
                    "unidade_id"
                ] = unidade_id

                item[
                    "unidade_nome"
                ] = unidade_nome

            all_data.extend(
                data
            )

            # ========================================
            # ÚLTIMA PÁGINA
            # ========================================

            if len(data) < 100:

                break

            page += 1

            time.sleep(
                0.3
            )

    return all_data


# ============================================================
# PREPARAR DATAFRAME
# ============================================================

def preparar_dataframe(
    all_data,
    estrutura_sql
):

    log("")
    log(
        "Preparando DataFrame..."
    )

    df_api = pd.json_normalize(
        all_data
    )

    # ================================================
    # TROCA "." POR "_"
    # ================================================

    df_api.columns = (
        df_api.columns
        .str.replace(
            ".",
            "_",
            regex=False
        )
    )

    log(
        f"API retornou "
        f"{len(df_api.columns)} colunas."
    )

    # ================================================
    # COLUNAS INSERTÁVEIS SQL
    # ================================================

    colunas_sql = [
        coluna
        for coluna in estrutura_sql
        if not coluna["identity"]
        and not coluna["computed"]
        and coluna["tipo"]
        not in [
            "timestamp",
            "rowversion"
        ]
    ]

    nomes_sql = [
        coluna["nome"]
        for coluna in colunas_sql
    ]

    # ================================================
    # COLUNAS DA API QUE NÃO EXISTEM NO SQL
    # ================================================

    extras_api = [

        coluna

        for coluna
        in df_api.columns

        if coluna
        not in nomes_sql

    ]

    if extras_api:

        log("")
        log(
            "Colunas recebidas da API "
            "que não existem no SQL:"
        )

        for coluna in extras_api:

            log(
                f"  -> {coluna}"
            )

        log(
            "Essas colunas serão ignoradas."
        )

    # ================================================
    # CRIA DATAFRAME EXATAMENTE COM COLUNAS SQL
    # ================================================

    df_final = pd.DataFrame()

    for coluna_sql in colunas_sql:

        nome = coluna_sql[
            "nome"
        ]

        tipo = coluna_sql[
            "tipo"
        ]

        # --------------------------------------------
        # EXISTE NA API
        # --------------------------------------------

        if nome in df_api.columns:

            log(
                f"Tratando: "
                f"{nome} "
                f"[{tipo}]"
            )

            df_final[
                nome
            ] = df_api[
                nome
            ].apply(

                lambda valor,
                col=coluna_sql:

                    converter_valor_sql(
                        valor,
                        col
                    )

            )

        # --------------------------------------------
        # NÃO EXISTE NA API
        # --------------------------------------------

        else:

            log(
                f"SQL sem correspondente API: "
                f"{nome}"
            )

            df_final[
                nome
            ] = None

    # ================================================
    # TROCA NaN / NaT POR NONE
    # ================================================

    df_final = df_final.astype(
        object
    )

    df_final = df_final.where(
        pd.notnull(
            df_final
        ),
        None
    )

    log("")
    log(
        f"DataFrame final: "
        f"{len(df_final)} registros "
        f"x {len(df_final.columns)} colunas."
    )

    return df_final


# ============================================================
# MOSTRAR REGISTRO COM ERRO
# ============================================================

def mostrar_registro_erro(
    indice,
    row,
    erro
):

    log("")
    log(
        "=============================================="
    )

    log(
        f"ERRO NO REGISTRO: {indice}"
    )

    log(
        "=============================================="
    )

    log(
        f"Tipo: "
        f"{type(erro).__name__}"
    )

    if hasattr(
        erro,
        "orig"
    ):

        log("")
        log(
            "ERRO ORIGINAL SQL SERVER:"
        )

        log(
            str(
                erro.orig
            )
        )

    else:

        log(
            str(
                erro
            )
        )

    log("")
    log(
        "DADOS DO REGISTRO:"
    )

    log(
        "----------------------------------------------"
    )

    for coluna, valor in row.items():

        log(
            f"{coluna} = "
            f"{repr(valor)}"
        )

    log(
        "----------------------------------------------"
    )


# ============================================================
# INSERIR LINHA POR LINHA
# ============================================================

def inserir_registros(
    df,
    conn
):

    total = len(
        df
    )

    log("")
    log(
        f"Iniciando inserção "
        f"de {total} registros..."
    )

    for contador, (
        indice,
        row
    ) in enumerate(
        df.iterrows(),
        start=1
    ):

        if not executando:

            raise Exception(
                "Importação interrompida."
            )

        try:

            linha = pd.DataFrame(
                [row.to_dict()]
            )

            # troca novamente qualquer NaN
            linha = linha.astype(
                object
            )

            linha = linha.where(
                pd.notnull(
                    linha
                ),
                None
            )

            linha.to_sql(

                "COLABORADORES_QUARK",

                con=conn,

                schema="dbo",

                if_exists="append",

                index=False

            )

        except Exception as e:

            mostrar_registro_erro(
                indice,
                row,
                e
            )

            raise

        if contador % 25 == 0:

            log(
                f"Gravados "
                f"{contador}/{total}"
            )

    log("")
    log(
        f"Gravados "
        f"{total}/{total} registros."
    )


# ============================================================
# TESTAR SQL SERVER
# ============================================================

def testar_sql():

    try:

        with engine.connect() as conn:

            conn.execute(
                text(
                    "SELECT 1"
                )
            )

        return True

    except Exception as e:

        log("")
        log(
            "Erro na conexão SQL:"
        )

        log(
            str(e)
        )

        engine.dispose()

        return False


# ============================================================
# GRAVAR SQL
# ============================================================

def gravar_sql(
    df
):

    max_tentativas = 3

    for tentativa in range(
        1,
        max_tentativas + 1
    ):

        try:

            log("")
            log(
                "=============================================="
            )

            log(
                f"GRAVAÇÃO SQL - "
                f"TENTATIVA "
                f"{tentativa}/{max_tentativas}"
            )

            log(
                "=============================================="
            )

            # ========================================
            # TESTA SQL
            # ========================================

            if not testar_sql():

                raise Exception(
                    "SQL Server indisponível."
                )

            # ========================================
            # TRANSAÇÃO
            # ========================================

            with engine.begin() as conn:

                log("")
                log(
                    "Removendo dados antigos..."
                )

                conn.execute(
                    text(
                        """
                        DELETE FROM
                        dbo.COLABORADORES_QUARK
                        """
                    )
                )

                log(
                    "Dados antigos removidos."
                )

                inserir_registros(
                    df,
                    conn
                )

            log("")
            log(
                "=============================================="
            )

            log(
                "IMPORTAÇÃO CONCLUÍDA COM SUCESSO!"
            )

            log(
                f"TOTAL GRAVADO: "
                f"{len(df)} REGISTROS"
            )

            log(
                "=============================================="
            )

            return True

        except Exception as e:

            log("")
            log(
                "=============================================="
            )

            log(
                "ERRO NA GRAVAÇÃO SQL"
            )

            log(
                "=============================================="
            )

            log(
                f"Tentativa: "
                f"{tentativa}/"
                f"{max_tentativas}"
            )

            if hasattr(
                e,
                "orig"
            ):

                log(
                    "ERRO ORIGINAL:"
                )

                log(
                    str(
                        e.orig
                    )
                )

            else:

                log(
                    str(e)
                )

            log("")
            log(
                "ROLLBACK executado."
            )

            log(
                "Os dados antigos "
                "foram preservados."
            )

            engine.dispose()

            if tentativa < max_tentativas:

                log("")
                log(
                    "Reconectando em "
                    "5 segundos..."
                )

                for _ in range(
                    5
                ):

                    if not executando:

                        return False

                    time.sleep(
                        1
                    )

    return False


# ============================================================
# IMPORTAÇÃO PRINCIPAL
# ============================================================

def importar():

    global executando

    while executando:

        try:

            log("")
            log(
                "##############################################"
            )

            log(
                "INICIANDO IMPORTAÇÃO QUARK"
            )

            log(
                "##############################################"
            )

            # ========================================
            # ESTRUTURA SQL
            # ========================================

            log("")
            log(
                "Lendo estrutura da tabela SQL..."
            )

            estrutura_sql = (
                obter_estrutura_sql()
            )

            if not estrutura_sql:

                raise Exception(
                    "Tabela "
                    "dbo.COLABORADORES_QUARK "
                    "não encontrada."
                )

            mostrar_estrutura_sql(
                estrutura_sql
            )

            # ========================================
            # API
            # ========================================

            all_data = (
                buscar_api()
            )

            if not executando:

                break

            if not all_data:

                log("")
                log(
                    "Nenhum colaborador "
                    "retornado pela API."
                )

            else:

                log("")
                log(
                    f"TOTAL COLETADO: "
                    f"{len(all_data)}"
                )

                # ====================================
                # DATAFRAME
                # ====================================

                df = preparar_dataframe(
                    all_data,
                    estrutura_sql
                )

                # ====================================
                # SQL
                # ====================================

                gravar_sql(
                    df
                )

        except Exception as e:

            log("")
            log(
                "=============================================="
            )

            log(
                "ERRO GERAL"
            )

            log(
                "=============================================="
            )

            log(
                f"Tipo: "
                f"{type(e).__name__}"
            )

            log(
                str(e)
            )

            engine.dispose()

        # ============================================
        # PRÓXIMA EXECUÇÃO
        # ============================================

        if not executando:

            break

        log("")
        log(
            "Próxima execução em "
            "15 minutos..."
        )

        log("")

        for segundo in range(
            900
        ):

            if not executando:

                break

            time.sleep(
                1
            )


# ============================================================
# BOTÃO INICIAR
# ============================================================

def iniciar():

    global executando

    if executando:

        log(
            "O script já está rodando."
        )

        return

    executando = True

    thread = threading.Thread(
        target=importar,
        daemon=True
    )

    thread.start()

    log(
        "Script iniciado."
    )


# ============================================================
# BOTÃO PARAR
# ============================================================

def parar():

    global executando

    executando = False

    log("")
    log(
        "Solicitação de parada enviada..."
    )


# ============================================================
# FECHAR
# ============================================================

def fechar():

    global executando

    executando = False

    try:

        engine.dispose()

    except Exception:

        pass

    janela.destroy()


# ============================================================
# INTERFACE
# ============================================================

janela = tk.Tk()

janela.title(
    "Integração API Quark → SQL Server"
)

janela.geometry(
    "1050x700"
)


# ============================================================
# FRAME BOTÕES
# ============================================================

frame = tk.Frame(
    janela
)

frame.pack(
    pady=10
)


btn_iniciar = tk.Button(

    frame,

    text="Iniciar",

    width=15,

    command=iniciar

)

btn_iniciar.grid(

    row=0,

    column=0,

    padx=10

)


btn_parar = tk.Button(

    frame,

    text="Parar",

    width=15,

    command=parar

)

btn_parar.grid(

    row=0,

    column=1,

    padx=10

)


# ============================================================
# LOG
# ============================================================

log_box = scrolledtext.ScrolledText(

    janela,

    width=130,

    height=40,

    font=(
        "Consolas",
        10
    )

)

log_box.pack(

    padx=10,

    pady=10,

    fill=tk.BOTH,

    expand=True

)


# ============================================================
# EVENTO FECHAR
# ============================================================

janela.protocol(

    "WM_DELETE_WINDOW",

    fechar

)


# ============================================================
# INICIA INTERFACE
# ============================================================

janela.mainloop()