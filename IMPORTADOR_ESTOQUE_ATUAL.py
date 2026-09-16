import os
import time
import threading
import pandas as pd
import tkinter as tk
from tkinter import scrolledtext, messagebox
from sqlalchemy import create_engine, text
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ====== CONFIGURAÇÕES ======
PASTA_EXCEL = r"\\Server\z_powerbi\DADOS\ESTOQUE_DIA"
SERVER = "188.220.168.222"
DATABASE = "FTECH"
USERNAME = "ftech"
PASSWORD = "********"
TABELA = "ESTOQUE_ATUAL"
# ============================

# ====== CONEXÃO CORRIGIDA ======
conn_str = (
    "mssql+pyodbc:///?odbc_connect="
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={SERVER};"
    f"Database={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
)
engine = create_engine(conn_str)
# ===============================

# ===== Função de Log na interface =====
def log(msg):
    text_log.config(state=tk.NORMAL)
    text_log.insert(tk.END, msg + "\n")
    text_log.see(tk.END)
    text_log.config(state=tk.DISABLED)
    root.update()

# ===== Importação de Dados =====
def importar_dados():
    try:
        log("🔄 Iniciando atualização da tabela ESTOQUE_ATUAL...")

        # Apagar dados antigos
        with engine.connect() as conn:
            conn.execute(text(f"DELETE FROM {TABELA}"))
            conn.commit()
        log("🧹 Dados antigos apagados.")

        # Importar novos arquivos
        arquivos = [f for f in os.listdir(PASTA_EXCEL) if f.lower().endswith(".xlsx")]

        if not arquivos:
            log("⚠️ Nenhum arquivo .xlsx encontrado na pasta.")
            return

        for arquivo in arquivos:
            caminho = os.path.join(PASTA_EXCEL, arquivo)
            log(f"📂 Lendo arquivo: {arquivo}")

            df = pd.read_excel(caminho, dtype=str)
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

            # Converter colunas numéricas e datas
            for col in df.columns:
                if col in ["CUSTO STD", "SALDO", "TOTAL"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                if col in ["ULTIMA COMPRA", "ULTIMA VENDA"]:
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            # Inserir no SQL Server
            df.to_sql(TABELA, engine, if_exists="append", index=False)
            log(f"✅ {len(df)} registros importados do arquivo {arquivo}")

        log("🏁 Importação concluída com sucesso!\n")

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
root.title("Monitor de Importação - ESTOQUE_ATUAL")
root.geometry("750x420")

frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=10)

btn_importar = tk.Button(
    frame_buttons,
    text="⚙️ Forçar Importação Agora",
    command=forcar_importacao,
    bg="#0078D7",
    fg="white",
    font=("Segoe UI", 10, "bold"),
    width=30,
)
btn_importar.pack()

text_log = scrolledtext.ScrolledText(
    root, wrap=tk.WORD, state=tk.DISABLED, height=18, font=("Consolas", 9)
)
text_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# ===== Iniciar monitoramento em thread separada =====
threading.Thread(target=iniciar_monitoramento, daemon=True).start()

root.mainloop()
