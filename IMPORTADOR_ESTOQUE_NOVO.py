import os
import time
import threading
import pandas as pd
import tkinter as tk

from tkinter import scrolledtext
from sqlalchemy import create_engine, text
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, date, timedelta


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# ------------------------------------------------------------
# ESTOQUE ATUAL
# ------------------------------------------------------------

PASTA_EXCEL = r"\\10.0.0.254\z_powerbi\DADOS\ESTOQUE_DIA"
TABELA = "ESTOQUE_ATUAL"


# ------------------------------------------------------------
# HISTÓRICO
# ------------------------------------------------------------

PASTA_EXCEL_HISTORICO = r"\\10.0.0.254\z_powerbi\DADOS\DADOS_ESTOQUE"
TABELA_HISTORICO = "ESTOQUE_HISTORICO"


# ------------------------------------------------------------
# QUANTIDADE DE DIAS QUE FICARÃO NO HISTÓRICO
#
# Exemplo:
# Hoje = 08/09/2026
#
# Mantém:
# 03/09/2026
# 04/09/2026
# 05/09/2026
# 06/09/2026
# 07/09/2026
# ------------------------------------------------------------

DIAS_HISTORICO = 5


# ------------------------------------------------------------
# SQL SERVER
# ------------------------------------------------------------

SERVER = "188.220.168.222"
DATABASE = "FTECH"
USERNAME = "ftech"
PASSWORD = "ftech@1975"


# ============================================================
# CONEXÃO SQL SERVER
# ============================================================

conn_str = (
    "mssql+pyodbc:///?odbc_connect="
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={SERVER};"
    f"Database={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
)

engine = create_engine(
    conn_str,
    pool_pre_ping=True
)


# ============================================================
# LOCKS
#
# Evitam duas importações simultâneas
# ============================================================

lock_atual = threading.Lock()
lock_historico = threading.Lock()


# ============================================================
# LOG
# ============================================================

def log(msg):

    def escrever():

        try:

            horario = datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            )

            text_log.config(
                state=tk.NORMAL
            )

            text_log.insert(
                tk.END,
                f"[{horario}] {msg}\n"
            )

            text_log.see(
                tk.END
            )

            text_log.config(
                state=tk.DISABLED
            )

        except Exception:
            pass

    try:

        root.after(
            0,
            escrever
        )

    except Exception:
        pass


# ============================================================
# TRATAR DATAFRAME
# ============================================================

def tratar_dataframe(df):

    # --------------------------------------------------------
    # Remover espaços em campos texto
    # --------------------------------------------------------

    df = df.apply(
        lambda x: x.str.strip()
        if x.dtype == "object"
        else x
    )

    # --------------------------------------------------------
    # Converter campos
    # --------------------------------------------------------

    for col in df.columns:

        if col in [
            "CUSTO STD",
            "SALDO",
            "TOTAL"
        ]:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        if col in [
            "ULTIMA COMPRA",
            "ULTIMA VENDA"
        ]:

            df[col] = pd.to_datetime(
                df[col],
                errors="coerce"
            )

    return df


# ============================================================
# AGUARDAR ARQUIVO TERMINAR DE SER GRAVADO
# ============================================================

def aguardar_arquivo(
    caminho,
    tentativas=10
):

    tamanho_anterior = -1

    for _ in range(tentativas):

        try:

            tamanho_atual = os.path.getsize(
                caminho
            )

            if (
                tamanho_atual > 0
                and
                tamanho_atual == tamanho_anterior
            ):

                return True

            tamanho_anterior = tamanho_atual

        except (
            OSError,
            FileNotFoundError
        ):
            pass

        time.sleep(1)

    return os.path.exists(
        caminho
    )


# ============================================================
# OBTER DATA DO ESTOQUE PELO NOME DO ARQUIVO
#
# Exemplo:
#
# 01.06.2026.xlsx
#
# retorna:
#
# 01/06/2026
# ============================================================

def obter_data_estoque(
    arquivo
):

    nome_sem_extensao = os.path.splitext(
        arquivo
    )[0].strip()

    try:

        data_estoque = datetime.strptime(
            nome_sem_extensao,
            "%d.%m.%Y"
        ).date()

        return data_estoque

    except ValueError:

        return None


# ============================================================
# CALCULAR PERÍODO DO HISTÓRICO
#
# Hoje NÃO entra.
#
# Exemplo:
#
# Hoje: 08/09/2026
#
# Início: 03/09/2026
# Final:  07/09/2026
# ============================================================

def obter_periodo_historico():

    hoje = date.today()

    data_inicial = (
        hoje -
        timedelta(
            days=DIAS_HISTORICO
        )
    )

    data_final = (
        hoje -
        timedelta(
            days=1
        )
    )

    return (
        data_inicial,
        data_final
    )


# ============================================================
# IMPORTAÇÃO ESTOQUE ATUAL
#
# CONTINUA COM A MESMA LÓGICA:
#
# DELETE
# +
# IMPORTAÇÃO COMPLETA
# ============================================================

def importar_dados():

    if not lock_atual.acquire(
        blocking=False
    ):

        log(
            "⏳ Atualização da ESTOQUE_ATUAL "
            "já está em andamento."
        )

        return

    try:

        log(
            "🔄 Iniciando atualização da "
            "ESTOQUE_ATUAL..."
        )

        # ----------------------------------------------------
        # Verificar pasta
        # ----------------------------------------------------

        if not os.path.exists(
            PASTA_EXCEL
        ):

            log(
                "❌ Pasta do ESTOQUE_ATUAL "
                "não encontrada:"
            )

            log(
                PASTA_EXCEL
            )

            return

        # ----------------------------------------------------
        # Apagar tabela atual
        # ----------------------------------------------------

        with engine.begin() as conn:

            conn.execute(
                text(
                    f"""
                    DELETE
                    FROM dbo.{TABELA}
                    """
                )
            )

        log(
            "🧹 Dados antigos da "
            "ESTOQUE_ATUAL apagados."
        )

        # ----------------------------------------------------
        # Localizar arquivos
        # ----------------------------------------------------

        arquivos = [
            f
            for f in os.listdir(
                PASTA_EXCEL
            )
            if
            f.lower().endswith(
                ".xlsx"
            )
            and
            not f.startswith(
                "~$"
            )
        ]

        arquivos.sort()

        if not arquivos:

            log(
                "⚠️ Nenhum arquivo .xlsx "
                "encontrado no ESTOQUE_ATUAL."
            )

            return

        total_registros = 0

        # ----------------------------------------------------
        # Importar arquivos
        # ----------------------------------------------------

        for arquivo in arquivos:

            caminho = os.path.join(
                PASTA_EXCEL,
                arquivo
            )

            log(
                f"📂 Lendo ESTOQUE_ATUAL: "
                f"{arquivo}"
            )

            try:

                aguardar_arquivo(
                    caminho
                )

                df = pd.read_excel(
                    caminho,
                    dtype=str
                )

                df = tratar_dataframe(
                    df
                )

                df.to_sql(
                    TABELA,
                    engine,
                    schema="dbo",
                    if_exists="append",
                    index=False,
                    chunksize=1000
                )

                total_registros += len(
                    df
                )

                log(
                    f"✅ {len(df)} registros "
                    f"importados de {arquivo}"
                )

            except Exception as e:

                log(
                    f"❌ Erro ao importar "
                    f"{arquivo}: {e}"
                )

        log(
            f"🏁 ESTOQUE_ATUAL concluído. "
            f"Total: {total_registros} registros."
        )

        log("")

    except Exception as e:

        log(
            f"❌ Erro durante atualização "
            f"da ESTOQUE_ATUAL: {e}"
        )

    finally:

        lock_atual.release()


# ============================================================
# VERIFICAR SE HISTÓRICO EXISTE
# ============================================================

def tabela_historico_existe():

    sql = text(
        """
        SELECT COUNT(*)

        FROM INFORMATION_SCHEMA.TABLES

        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = :tabela
        """
    )

    with engine.connect() as conn:

        resultado = conn.execute(
            sql,
            {
                "tabela": TABELA_HISTORICO
            }
        ).scalar()

    return resultado > 0


# ============================================================
# LIMPAR HISTÓRICO ANTIGO
#
# Exclui SOMENTE o que saiu da janela.
#
# Não apaga os últimos 5 dias.
# ============================================================

def limpar_historico_antigo():

    if not tabela_historico_existe():

        return

    data_inicial, data_final = (
        obter_periodo_historico()
    )

    try:

        with engine.begin() as conn:

            resultado = conn.execute(
                text(
                    f"""
                    DELETE
                    FROM dbo.{TABELA_HISTORICO}

                    WHERE
                        DATA_ESTOQUE < :data_inicial

                        OR

                        DATA_ESTOQUE > :data_final
                    """
                ),
                {
                    "data_inicial": data_inicial,
                    "data_final": data_final
                }
            )

        qtd = resultado.rowcount

        log(
            "🧹 Limpeza do histórico concluída."
        )

        log(
            f"📅 Período mantido: "
            f"{data_inicial.strftime('%d/%m/%Y')} "
            f"até "
            f"{data_final.strftime('%d/%m/%Y')}"
        )

        if qtd is not None and qtd > 0:

            log(
                f"🗑️ {qtd} registros antigos "
                f"removidos."
            )

    except Exception as e:

        log(
            f"❌ Erro ao limpar "
            f"histórico antigo: {e}"
        )

        raise


# ============================================================
# VERIFICAR SE ARQUIVO JÁ FOI IMPORTADO
# ============================================================

def arquivo_historico_ja_importado(
    arquivo
):

    if not tabela_historico_existe():

        return False

    sql = text(
        f"""
        SELECT TOP 1
            ARQUIVO_ORIGEM

        FROM dbo.{TABELA_HISTORICO}

        WHERE ARQUIVO_ORIGEM = :arquivo
        """
    )

    with engine.connect() as conn:

        resultado = conn.execute(
            sql,
            {
                "arquivo": arquivo
            }
        ).fetchone()

    return resultado is not None


# ============================================================
# IMPORTAR HISTÓRICO
#
# REGRAS:
#
# 1. NÃO apaga tudo
# 2. Mantém somente últimos 5 dias anteriores
# 3. Arquivos fora do período NÃO são abertos
# 4. Arquivos já importados NÃO são reimportados
# ============================================================

def importar_historico():

    if not lock_historico.acquire(
        blocking=False
    ):

        log(
            "⏳ Importação histórica "
            "já está em andamento."
        )

        return

    try:

        log(
            "📚 Iniciando verificação "
            "do ESTOQUE_HISTORICO..."
        )

        # ====================================================
        # PERÍODO
        # ====================================================

        data_inicial, data_final = (
            obter_periodo_historico()
        )

        log(
            f"📅 Histórico permitido: "
            f"{data_inicial.strftime('%d/%m/%Y')} "
            f"até "
            f"{data_final.strftime('%d/%m/%Y')}"
        )

        # ====================================================
        # LIMPAR REGISTROS ANTIGOS
        # ====================================================

        limpar_historico_antigo()

        # ====================================================
        # VERIFICAR PASTA
        # ====================================================

        if not os.path.exists(
            PASTA_EXCEL_HISTORICO
        ):

            log(
                "❌ Pasta do histórico "
                "não encontrada:"
            )

            log(
                PASTA_EXCEL_HISTORICO
            )

            return

        # ====================================================
        # LISTAR XLSX
        #
        # Aqui só pegamos nomes.
        #
        # NÃO abrimos os Excel ainda.
        # ====================================================

        arquivos = [
            f
            for f in os.listdir(
                PASTA_EXCEL_HISTORICO
            )
            if
            f.lower().endswith(
                ".xlsx"
            )
            and
            not f.startswith(
                "~$"
            )
        ]

        arquivos.sort()

        if not arquivos:

            log(
                "⚠️ Nenhum arquivo .xlsx "
                "encontrado na pasta histórica."
            )

            return

        quantidade_importada = 0
        registros_importados = 0
        arquivos_ja_importados = 0
        arquivos_fora_periodo = 0
        arquivos_invalidos = 0

        # ====================================================
        # PERCORRER NOMES DOS ARQUIVOS
        # ====================================================

        for arquivo in arquivos:

            # ------------------------------------------------
            # IDENTIFICAR DATA PELO NOME
            # ------------------------------------------------

            data_estoque = obter_data_estoque(
                arquivo
            )

            # ------------------------------------------------
            # NOME INVÁLIDO
            # ------------------------------------------------

            if data_estoque is None:

                log(
                    f"⚠️ Nome inválido: "
                    f"{arquivo}"
                )

                log(
                    "   Esperado: "
                    "DD.MM.AAAA.xlsx"
                )

                arquivos_invalidos += 1

                continue

            # =================================================
            # FILTRO DOS 5 DIAS
            #
            # IMPORTANTE:
            #
            # O arquivo ainda NÃO foi aberto.
            # =================================================

            if not (
                data_inicial
                <=
                data_estoque
                <=
                data_final
            ):

                arquivos_fora_periodo += 1

                continue

            # ------------------------------------------------
            # MOSTRAR ARQUIVO VÁLIDO
            # ------------------------------------------------

            log(
                f"📅 Verificando: "
                f"{arquivo} "
                f"({data_estoque.strftime('%d/%m/%Y')})"
            )

            # =================================================
            # VERIFICAR SE JÁ ESTÁ NO SQL
            # =================================================

            try:

                if arquivo_historico_ja_importado(
                    arquivo
                ):

                    log(
                        f"⏭️ Já importado: "
                        f"{arquivo}"
                    )

                    arquivos_ja_importados += 1

                    continue

            except Exception as e:

                log(
                    f"❌ Erro ao verificar "
                    f"{arquivo}: {e}"
                )

                log(
                    "⚠️ Histórico interrompido "
                    "para evitar duplicidade."
                )

                return

            # =================================================
            # SOMENTE AGORA O EXCEL SERÁ ABERTO
            # =================================================

            caminho = os.path.join(
                PASTA_EXCEL_HISTORICO,
                arquivo
            )

            # ------------------------------------------------
            # Aguardar gravação
            # ------------------------------------------------

            if not aguardar_arquivo(
                caminho
            ):

                log(
                    f"⚠️ Arquivo indisponível: "
                    f"{arquivo}"
                )

                continue

            try:

                log(
                    f"📖 Importando: "
                    f"{arquivo}"
                )

                # ------------------------------------------------
                # LER EXCEL
                # ------------------------------------------------

                df = pd.read_excel(
                    caminho,
                    dtype=str
                )

                df = tratar_dataframe(
                    df
                )

                # =================================================
                # COLUNAS DE HISTÓRICO
                # =================================================

                df[
                    "ARQUIVO_ORIGEM"
                ] = arquivo

                df[
                    "DATA_ESTOQUE"
                ] = pd.to_datetime(
                    data_estoque
                )

                df[
                    "DATA_IMPORTACAO"
                ] = pd.Timestamp.now()

                # =================================================
                # INSERIR SQL
                #
                # NÃO EXISTE DELETE DA TABELA TODA
                # =================================================

                df.to_sql(
                    TABELA_HISTORICO,
                    engine,
                    schema="dbo",
                    if_exists="append",
                    index=False,
                    chunksize=1000
                )

                quantidade_importada += 1

                registros_importados += len(
                    df
                )

                log(
                    f"✅ {arquivo} importado."
                )

                log(
                    f"   Data estoque: "
                    f"{data_estoque.strftime('%d/%m/%Y')}"
                )

                log(
                    f"   Registros: "
                    f"{len(df)}"
                )

            except Exception as e:

                log(
                    f"❌ Erro ao importar "
                    f"{arquivo}: {e}"
                )

        # ====================================================
        # RESUMO
        # ====================================================

        log("")

        log(
            "════════════════════════════════"
        )

        log(
            "📊 RESUMO DO HISTÓRICO"
        )

        log(
            "════════════════════════════════"
        )

        log(
            f"📅 Período: "
            f"{data_inicial.strftime('%d/%m/%Y')} "
            f"até "
            f"{data_final.strftime('%d/%m/%Y')}"
        )

        log(
            f"✅ Arquivos novos: "
            f"{quantidade_importada}"
        )

        log(
            f"📊 Registros adicionados: "
            f"{registros_importados}"
        )

        log(
            f"⏭️ Já existentes: "
            f"{arquivos_ja_importados}"
        )

        log(
            f"📁 Fora do período: "
            f"{arquivos_fora_periodo}"
        )

        log(
            f"⚠️ Nome inválido: "
            f"{arquivos_invalidos}"
        )

        if quantidade_importada == 0:

            log(
                "✅ Histórico já estava atualizado."
            )

        else:

            log(
                "🏁 Histórico atualizado "
                "com sucesso."
            )

        log("")

    except Exception as e:

        log(
            f"❌ Erro durante importação "
            f"histórica: {e}"
        )

    finally:

        lock_historico.release()


# ============================================================
# BOTÕES
# ============================================================

def forcar_importacao():

    threading.Thread(
        target=importar_dados,
        daemon=True
    ).start()


def forcar_importacao_historico():

    threading.Thread(
        target=importar_historico,
        daemon=True
    ).start()


def importar_tudo():

    def executar():

        importar_dados()

        importar_historico()

    threading.Thread(
        target=executar,
        daemon=True
    ).start()


# ============================================================
# MONITOR ESTOQUE ATUAL
# ============================================================

class MonitorExcelHandler(
    FileSystemEventHandler
):

    def on_any_event(
        self,
        event
    ):

        if event.is_directory:
            return

        caminho = event.src_path

        if not caminho.lower().endswith(
            ".xlsx"
        ):
            return

        nome = os.path.basename(
            caminho
        )

        if nome.startswith(
            "~$"
        ):
            return

        log(
            "📢 Alteração detectada "
            "no ESTOQUE_ATUAL:"
        )

        log(
            f"   {nome}"
        )

        time.sleep(2)

        importar_dados()


# ============================================================
# MONITOR HISTÓRICO
# ============================================================

class MonitorHistoricoHandler(
    FileSystemEventHandler
):

    def on_any_event(
        self,
        event
    ):

        if event.is_directory:
            return

        caminho = event.src_path

        if not caminho.lower().endswith(
            ".xlsx"
        ):
            return

        nome = os.path.basename(
            caminho
        )

        if nome.startswith(
            "~$"
        ):
            return

        # ----------------------------------------------------
        # Verifica a data antes mesmo de chamar
        # a importação histórica
        # ----------------------------------------------------

        data_estoque = obter_data_estoque(
            nome
        )

        if data_estoque is None:

            return

        data_inicial, data_final = (
            obter_periodo_historico()
        )

        # ----------------------------------------------------
        # Se estiver fora dos 5 dias,
        # nem chama importação
        # ----------------------------------------------------

        if not (
            data_inicial
            <=
            data_estoque
            <=
            data_final
        ):

            return

        log(
            "📢 Novo arquivo válido "
            "detectado no HISTÓRICO:"
        )

        log(
            f"   {nome}"
        )

        time.sleep(3)

        importar_historico()


# ============================================================
# MONITORAMENTO ESTOQUE ATUAL
# ============================================================

def iniciar_monitoramento():

    try:

        if not os.path.exists(
            PASTA_EXCEL
        ):

            log(
                "❌ Não foi possível iniciar "
                "monitoramento do ESTOQUE_ATUAL."
            )

            log(
                f"Pasta inexistente: "
                f"{PASTA_EXCEL}"
            )

            return

        log(
            "👀 Monitorando ESTOQUE_ATUAL:"
        )

        log(
            f"   {PASTA_EXCEL}"
        )

        event_handler = (
            MonitorExcelHandler()
        )

        observer = Observer()

        observer.schedule(
            event_handler,
            PASTA_EXCEL,
            recursive=False
        )

        observer.start()

        while True:

            time.sleep(5)

    except Exception as e:

        log(
            f"❌ Erro no monitoramento "
            f"ESTOQUE_ATUAL: {e}"
        )


# ============================================================
# MONITORAMENTO HISTÓRICO
# ============================================================

def iniciar_monitoramento_historico():

    try:

        if not os.path.exists(
            PASTA_EXCEL_HISTORICO
        ):

            log(
                "❌ Não foi possível iniciar "
                "monitoramento do HISTÓRICO."
            )

            log(
                f"Pasta inexistente: "
                f"{PASTA_EXCEL_HISTORICO}"
            )

            return

        log(
            "👀 Monitorando ESTOQUE_HISTORICO:"
        )

        log(
            f"   {PASTA_EXCEL_HISTORICO}"
        )

        event_handler = (
            MonitorHistoricoHandler()
        )

        observer = Observer()

        observer.schedule(
            event_handler,
            PASTA_EXCEL_HISTORICO,
            recursive=False
        )

        observer.start()

        while True:

            time.sleep(5)

    except Exception as e:

        log(
            f"❌ Erro no monitoramento "
            f"ESTOQUE_HISTORICO: {e}"
        )


# ============================================================
# INTERFACE
# ============================================================

root = tk.Tk()

root.title(
    "Monitor de Importação - Estoque Atual + Histórico"
)

root.geometry(
    "900x620"
)

root.minsize(
    750,
    500
)


# ============================================================
# TÍTULO
# ============================================================

lbl_titulo = tk.Label(
    root,
    text="IMPORTADOR DE ESTOQUE",
    font=(
        "Segoe UI",
        15,
        "bold"
    )
)

lbl_titulo.pack(
    pady=(15, 5)
)


lbl_subtitulo = tk.Label(
    root,
    text=(
        "Estoque Atual + Histórico "
        f"dos últimos {DIAS_HISTORICO} dias"
    ),
    font=(
        "Segoe UI",
        10
    )
)

lbl_subtitulo.pack(
    pady=(0, 10)
)


# ============================================================
# BOTÕES
# ============================================================

frame_buttons = tk.Frame(
    root
)

frame_buttons.pack(
    pady=10
)


btn_importar = tk.Button(
    frame_buttons,
    text="⚙️ Atualizar ESTOQUE_ATUAL",
    command=forcar_importacao,
    bg="#0078D7",
    fg="white",
    font=(
        "Segoe UI",
        10,
        "bold"
    ),
    width=30,
    height=2
)

btn_importar.grid(
    row=0,
    column=0,
    padx=5,
    pady=5
)


btn_historico = tk.Button(
    frame_buttons,
    text="📚 Atualizar HISTÓRICO",
    command=forcar_importacao_historico,
    bg="#107C10",
    fg="white",
    font=(
        "Segoe UI",
        10,
        "bold"
    ),
    width=30,
    height=2
)

btn_historico.grid(
    row=0,
    column=1,
    padx=5,
    pady=5
)


btn_tudo = tk.Button(
    frame_buttons,
    text="🔄 Atualizar TUDO",
    command=importar_tudo,
    bg="#5C2D91",
    fg="white",
    font=(
        "Segoe UI",
        10,
        "bold"
    ),
    width=30,
    height=2
)

btn_tudo.grid(
    row=1,
    column=0,
    columnspan=2,
    padx=5,
    pady=5
)


# ============================================================
# LOG
# ============================================================

text_log = scrolledtext.ScrolledText(
    root,
    wrap=tk.WORD,
    state=tk.DISABLED,
    height=22,
    font=(
        "Consolas",
        9
    )
)

text_log.pack(
    padx=10,
    pady=10,
    fill=tk.BOTH,
    expand=True
)


# ============================================================
# INICIAR MONITORAMENTOS
# ============================================================

threading.Thread(
    target=iniciar_monitoramento,
    daemon=True
).start()


threading.Thread(
    target=iniciar_monitoramento_historico,
    daemon=True
).start()


# ============================================================
# INICIAR INTERFACE
# ============================================================

root.mainloop()