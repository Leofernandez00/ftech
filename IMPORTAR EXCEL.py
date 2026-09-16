import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
import pandas as pd
import pyodbc
import threading
import os

# =========================
# CONFIGURAÇÕES DO BANCO
# =========================
SERVER = "10.0.0.254"
DATABASE = "FTECH"
USERNAME = "ftech"
PASSWORD = "ftech@1975"
TABELA = "ITEM_ORCAMENTOS_TOTVS"

# =========================
# CONEXÃO SQL SERVER
# =========================
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "TrustServerCertificate=yes;"
)

arquivo_excel = ""


# =========================
# LOG NA TELA
# =========================
def log(msg):
    txt_log.insert(tk.END, msg + "\n")
    txt_log.see(tk.END)
    janela.update_idletasks()


# =========================
# CRIAR TABELA
# =========================
def criar_tabela_sql():
    sql = f"""
    IF OBJECT_ID('dbo.{TABELA}', 'U') IS NOT NULL
        DROP TABLE dbo.{TABELA};

    CREATE TABLE dbo.{TABELA}
    (
        [ID] INT NOT NULL,
        [ORÇAMENTO] VARCHAR(20) NOT NULL,
        [JUSTIFICATIVA] VARCHAR(1000) NULL,
        [DATA DA JUSTIFICATIVA] DATETIME NULL,
        [OBSERVAÇÃO] VARCHAR(1000) NULL,
        [USEREMAIL] VARCHAR(255) NULL,
        [DATA/HORA] DATETIME NULL
    );

    ALTER TABLE dbo.{TABELA}
    ADD CONSTRAINT PK_{TABELA} PRIMARY KEY ([ID]);
    """
    return sql


def criar_tabela():
    try:
        log("Conectando ao SQL Server...")
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        log(f"Criando tabela {TABELA}...")
        cursor.execute(criar_tabela_sql())
        conn.commit()

        cursor.close()
        conn.close()

        log("Tabela criada com sucesso.")
        messagebox.showinfo("Sucesso", f"Tabela {TABELA} criada com sucesso.")

    except Exception as e:
        log(f"Erro ao criar tabela: {e}")
        messagebox.showerror("Erro", f"Erro ao criar tabela:\n{e}")


# =========================
# SELECIONAR ARQUIVO
# =========================
def selecionar_arquivo():
    global arquivo_excel
    arquivo_excel = filedialog.askopenfilename(
        title="Selecione a planilha Excel",
        filetypes=[("Arquivos Excel", "*.xlsx *.xls")]
    )

    if arquivo_excel:
        lbl_arquivo.config(text=f"Arquivo: {arquivo_excel}")
        log(f"Planilha selecionada: {arquivo_excel}")


# =========================
# TRATAMENTO DOS DADOS
# =========================
def tratar_dataframe(df):
    # remove espaços extras dos nomes das colunas
    df.columns = [str(col).strip() for col in df.columns]

    colunas_esperadas = [
        "ID",
        "ORÇAMENTO",
        "JUSTIFICATIVA",
        "DATA DA JUSTIFICATIVA",
        "OBSERVAÇÃO",
        "USEREMAIL",
        "DATA/HORA"
    ]

    for col in colunas_esperadas:
        if col not in df.columns:
            raise Exception(f"Coluna obrigatória não encontrada na planilha: {col}")

    df = df[colunas_esperadas].copy()

    # remove linhas totalmente vazias
    df.dropna(how="all", inplace=True)

    # trata ID
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df = df[df["ID"].notna()]
    df["ID"] = df["ID"].astype(int)

    # ORÇAMENTO como texto para preservar zeros à esquerda
    df["ORÇAMENTO"] = df["ORÇAMENTO"].astype(str).str.strip()

    # texto
    for col in ["JUSTIFICATIVA", "OBSERVAÇÃO", "USEREMAIL"]:
        df[col] = df[col].astype(str)
        df[col] = df[col].replace({"nan": None, "": None, "None": None})

    # datas
    for col in ["DATA DA JUSTIFICATIVA", "DATA/HORA"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        df[col] = df[col].where(df[col].notna(), None)

    return df


# =========================
# IMPORTAR DADOS
# =========================
def importar_dados():
    global arquivo_excel

    if not arquivo_excel:
        messagebox.showwarning("Atenção", "Selecione uma planilha primeiro.")
        return

    if not os.path.exists(arquivo_excel):
        messagebox.showerror("Erro", "O arquivo selecionado não foi encontrado.")
        return

    try:
        btn_importar.config(state="disabled")
        btn_criar.config(state="disabled")
        progresso.start()
        txt_log.delete("1.0", tk.END)

        log("Lendo planilha Excel...")
        # Cabeçalho está na linha 1 da planilha enviada
        df = pd.read_excel(arquivo_excel, dtype=object)

        log(f"Linhas lidas: {len(df)}")
        df = tratar_dataframe(df)
        log(f"Linhas válidas para importação: {len(df)}")

        if df.empty:
            raise Exception("Nenhum dado válido encontrado para importar.")

        log("Conectando ao SQL Server...")
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        if var_apagar.get() == 1:
            log(f"Apagando dados existentes da tabela {TABELA}...")
            cursor.execute(f"DELETE FROM dbo.{TABELA}")
            conn.commit()

        log("Preparando dados para inserção...")
        dados = []
        for _, row in df.iterrows():
            dados.append((
                int(row["ID"]) if pd.notna(row["ID"]) else None,
                str(row["ORÇAMENTO"]) if pd.notna(row["ORÇAMENTO"]) else None,
                row["JUSTIFICATIVA"] if pd.notna(row["JUSTIFICATIVA"]) else None,
                row["DATA DA JUSTIFICATIVA"] if pd.notna(row["DATA DA JUSTIFICATIVA"]) else None,
                row["OBSERVAÇÃO"] if pd.notna(row["OBSERVAÇÃO"]) else None,
                row["USEREMAIL"] if pd.notna(row["USEREMAIL"]) else None,
                row["DATA/HORA"] if pd.notna(row["DATA/HORA"]) else None
            ))

        sql_insert = f"""
        INSERT INTO dbo.{TABELA}
        (
            [ID],
            [ORÇAMENTO],
            [JUSTIFICATIVA],
            [DATA DA JUSTIFICATIVA],
            [OBSERVAÇÃO],
            [USEREMAIL],
            [DATA/HORA]
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        log("Importando dados para o SQL Server...")
        cursor.executemany(sql_insert, dados)
        conn.commit()

        total = len(dados)

        cursor.close()
        conn.close()

        log(f"Importação concluída com sucesso. Total de registros importados: {total}")
        messagebox.showinfo("Sucesso", f"Importação concluída com sucesso.\nTotal importado: {total}")

    except Exception as e:
        log(f"Erro na importação: {e}")
        messagebox.showerror("Erro", f"Erro na importação:\n{e}")

    finally:
        progresso.stop()
        btn_importar.config(state="normal")
        btn_criar.config(state="normal")


def importar_em_thread():
    thread = threading.Thread(target=importar_dados)
    thread.start()


def criar_em_thread():
    thread = threading.Thread(target=criar_tabela)
    thread.start()


# =========================
# INTERFACE
# =========================
janela = tk.Tk()
janela.title("Importador de ITEM_ORCAMENTOS_TOTVS")
janela.geometry("750x500")
janela.resizable(False, False)

frame_topo = tk.Frame(janela)
frame_topo.pack(pady=10)

titulo = tk.Label(
    frame_topo,
    text="Importador Excel -> SQL Server",
    font=("Arial", 16, "bold")
)
titulo.pack()

subtitulo = tk.Label(
    frame_topo,
    text=f"Tabela destino: {TABELA}",
    font=("Arial", 10)
)
subtitulo.pack()

frame_arquivo = tk.Frame(janela)
frame_arquivo.pack(pady=10)

btn_selecionar = tk.Button(
    frame_arquivo,
    text="Selecionar Planilha",
    width=20,
    command=selecionar_arquivo
)
btn_selecionar.grid(row=0, column=0, padx=5)

lbl_arquivo = tk.Label(
    frame_arquivo,
    text="Nenhum arquivo selecionado",
    anchor="w",
    justify="left",
    wraplength=500
)
lbl_arquivo.grid(row=0, column=1, padx=5)

frame_opcoes = tk.Frame(janela)
frame_opcoes.pack(pady=10)

var_apagar = tk.IntVar(value=1)
chk_apagar = tk.Checkbutton(
    frame_opcoes,
    text="Apagar dados existentes antes de importar",
    variable=var_apagar
)
chk_apagar.pack()

frame_botoes = tk.Frame(janela)
frame_botoes.pack(pady=10)

btn_criar = tk.Button(
    frame_botoes,
    text="Criar Tabela",
    width=20,
    bg="#1f6aa5",
    fg="white",
    command=criar_em_thread
)
btn_criar.grid(row=0, column=0, padx=10)

btn_importar = tk.Button(
    frame_botoes,
    text="Importar Dados",
    width=20,
    bg="#2e8b57",
    fg="white",
    command=importar_em_thread
)
btn_importar.grid(row=0, column=1, padx=10)

progresso = ttk.Progressbar(janela, mode="indeterminate", length=400)
progresso.pack(pady=10)

txt_log = scrolledtext.ScrolledText(janela, width=90, height=18, font=("Consolas", 9))
txt_log.pack(padx=10, pady=10)

janela.mainloop()