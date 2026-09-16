import os
import time
import threading
import pandas as pd
import tkinter as tk
import urllib.parse
from tkinter import scrolledtext
from sqlalchemy import create_engine, text
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ====== CONFIGURAÇÕES ======
PASTA_EXCEL = r"\\Server\z_powerbi\DADOS\ORCAMENTOS"
SERVER = "188.220.168.222"
DATABASE = "FTECH"
USERNAME = "ftech"
PASSWORD = "ftech@1975"
TABELA = "dbo.ORCAMENTOS_TOTVS"
# ============================

# ====== CONEXÃO SQL SERVER ======
conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={SERVER};"
    f"Database={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "TrustServerCertificate=yes;"
)

params = urllib.parse.quote_plus(conn_str)
engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    fast_executemany=True
)
# ===============================

# ===== Interface de log =====
def log(msg):
    text_log.config(state=tk.NORMAL)
    text_log.insert(tk.END, msg + "\n")
    text_log.see(tk.END)
    text_log.config(state=tk.DISABLED)
    root.update_idletasks()

# ===== Padronização de colunas =====
def padronizar_colunas(df):
    mapa = {
        "Filial": "FILIAL",
        "Nro Orcam/o": "NRO_ORCAMENTO",
        "Pedido": "PEDIDO",
        "Loja": "LOJA",
        "Nome Cliente": "NOME_CLIENTE",
        "Dt Orcamento": "DT_ORCAMENTO",
        "Hr Orcamento": "HR_ORCAMENTO",
        "Nome Vended": "NOME_VENDEDOR",
        "Dt Validade": "DT_VALIDADE",
        "Tipos Pagto.": "TIPOS_PAGTO",
        "Nota Fiscal": "NOTA_FISCAL",
        "Serie": "SERIE",
        "Desp Acessor": "DESP_ACESSOR",
        "Vl. Desconto": "VL_DESCONTO",
        "ICM Calcul": "ICM_CALCUL",
        "Total da NF": "TOTAL_DA_NF",
        "Vlr.Bruto NF": "VLR_BRUTO_NF",
        "Volume 1": "VOLUME_1",
        "Especie 1": "ESPECIE_1",
        "Peso Liq.": "PESO_LIQ",
        "Peso Brut": "PESO_BRUT",
        "ICMS Compl.": "ICMS_COMPL",
        "Dif.de ICMS": "DIF_DE_ICMS",
        "St Impr.OrdB": "ST_IMPR_ORDB",
        "Frm Pgt Base": "FRM_PGT_BASE",
        "Obs.p/Confer": "OBS_P_CONFER",
        "Valor IRRF": "VALOR_IRRF",
        "Valor CSLL": "VALOR_CSLL",
        "Nome Transp": "NOME_TRANSP",
        "Dt Despacho": "DT_DESPACHO",
        "Hr Despacho": "HR_DESPACHO",
    }

    df = df.rename(columns=mapa)
    return df

# ===== Tratamento de dados =====
def tratar_dataframe(df):
    # Remove espaços em branco de textos
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({"nan": None, "": None})

    # Datas
    colunas_data = ["DT_ORCAMENTO", "DT_VALIDADE", "DT_DESPACHO"]
    for col in colunas_data:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Numéricas
    colunas_numericas = [
        "DESP_ACESSOR",
        "VL_DESCONTO",
        "ICM_CALCUL",
        "TOTAL_DA_NF",
        "VOLUME_1",
        "PESO_LIQ",
        "PESO_BRUT",
        "ICMS_COMPL",
        "DIF_DE_ICMS",
        "VALOR_IRRF",
        "VALOR_CSLL",
    ]

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Colunas que devem ficar como texto
    colunas_texto = [
        "FILIAL",
        "NRO_ORCAMENTO",
        "PEDIDO",
        "LOJA",
        "NOME_CLIENTE",
        "HR_ORCAMENTO",
        "NOME_VENDEDOR",
        "TIPOS_PAGTO",
        "NOTA_FISCAL",
        "SERIE",
        "VLR_BRUTO_NF",
        "ESPECIE_1",
        "ST_IMPR_ORDB",
        "FRM_PGT_BASE",
        "OBS_P_CONFER",
        "NOME_TRANSP",
        "HR_DESPACHO",
    ]

    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].astype(str)
            df[col] = df[col].replace({"nan": None, "None": None, "": None})

    return df

# ===== Importação =====
def importar_dados():
    try:
        log("🔄 Iniciando atualização da tabela ORCAMENTOS_TOTVS...")

        arquivos = [f for f in os.listdir(PASTA_EXCEL) if f.lower().endswith(".xlsx")]

        if not arquivos:
            log("⚠️ Nenhum arquivo .xlsx encontrado na pasta.")
            return

        # Limpa a tabela uma vez antes de importar tudo novamente
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {TABELA}"))
        log("🧹 Dados antigos apagados.")

        total_geral = 0

        for arquivo in arquivos:
            caminho = os.path.join(PASTA_EXCEL, arquivo)
            log(f"📂 Lendo arquivo: {arquivo}")

            # header=1 => usa a SEGUNDA LINHA como cabeçalho
            df = pd.read_excel(
                caminho,
                sheet_name=0,
                header=1,
                dtype=object
            )

            # Remove linhas totalmente vazias
            df = df.dropna(how="all")

            # Padroniza nomes das colunas
            df = padronizar_colunas(df)

            # Mantém somente as colunas esperadas
            colunas_esperadas = [
                "FILIAL", "NRO_ORCAMENTO", "PEDIDO", "LOJA", "NOME_CLIENTE",
                "DT_ORCAMENTO", "HR_ORCAMENTO", "NOME_VENDEDOR", "DT_VALIDADE",
                "TIPOS_PAGTO", "NOTA_FISCAL", "SERIE", "DESP_ACESSOR",
                "VL_DESCONTO", "ICM_CALCUL", "TOTAL_DA_NF", "VLR_BRUTO_NF",
                "VOLUME_1", "ESPECIE_1", "PESO_LIQ", "PESO_BRUT", "ICMS_COMPL",
                "DIF_DE_ICMS", "ST_IMPR_ORDB", "FRM_PGT_BASE", "OBS_P_CONFER",
                "VALOR_IRRF", "VALOR_CSLL", "NOME_TRANSP", "DT_DESPACHO",
                "HR_DESPACHO"
            ]

            df = df[colunas_esperadas]

            # Trata dados
            df = tratar_dataframe(df)

            # Insere no banco
            df.to_sql(
                name="ORCAMENTOS_TOTVS",
                con=engine,
                schema="dbo",
                if_exists="append",
                index=False,
                chunksize=1000,
                method=None
            )

            total_geral += len(df)
            log(f"✅ {len(df)} registros importados do arquivo {arquivo}")

        log(f"🏁 Importação concluída com sucesso! Total importado: {total_geral} registros.\n")

    except Exception as e:
        log(f"❌ Erro durante a importação: {e}")

# ===== Forçar importação manual =====
def forcar_importacao():
    threading.Thread(target=importar_dados, daemon=True).start()

# ===== Monitoramento automático =====
class MonitorExcelHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory:
            return

        if event.src_path.lower().endswith(".xlsx"):
            log(f"📢 Alteração detectada em: {event.src_path}")
            time.sleep(2)
            importar_dados()

def iniciar_monitoramento():
    log(f"👀 Monitorando a pasta: {PASTA_EXCEL}")
    event_handler = MonitorExcelHandler()
    observer = Observer()
    observer.schedule(event_handler, PASTA_EXCEL, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

# ===== Interface Tkinter =====
root = tk.Tk()
root.title("Monitor de Importação - ORCAMENTOS")
root.geometry("800x450")

frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=10)

btn_importar = tk.Button(
    frame_buttons,
    text="⚙️ Forçar Importação Agora",
    command=forcar_importacao,
    bg="#0078D7",
    fg="white",
    font=("Segoe UI", 10, "bold"),
    width=30
)
btn_importar.pack()

text_log = scrolledtext.ScrolledText(
    root,
    wrap=tk.WORD,
    state=tk.DISABLED,
    height=20,
    font=("Consolas", 9)
)
text_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# ===== Iniciar monitoramento =====
threading.Thread(target=iniciar_monitoramento, daemon=True).start()

root.mainloop()