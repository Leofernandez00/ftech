import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import pyodbc
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import threading
import time
import os

# CONFIGURAÇÕES GLOBAIS
INTERVALO_MINUTOS = 15
PLANILHA_GOOGLE = "IMPORTACAO_FTECH"
ARQUIVO_CREDENCIAIS = "credenciais.json"
LOG_PATH = "log_importacao.txt"

# CONEXÃO SQL SERVER
def conectar_sql():
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=10.0.0.254,1433;'
        'DATABASE=FTECH;'
        'UID=ftech;'
        'PWD=ftech@1975'
    )
    return pyodbc.connect(conn_str)

# CONEXÃO GOOGLE SHEETS
def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(ARQUIVO_CREDENCIAIS, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(PLANILHA_GOOGLE)
    return spreadsheet.sheet1

# ENCONTRAR ÍNDICE DA COLUNA
def encontrar_indice_coluna(cabecalho, nome_coluna):
    for i, col in enumerate(cabecalho):
        if col.strip().lower() == nome_coluna.lower():
            return i
    raise ValueError(f"Coluna '{nome_coluna}' não encontrada no cabeçalho")

# ESCREVER LOG
def escrever_log(mensagem):
    timestamp = datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {mensagem}\n")

# FUNÇÃO DE IMPORTAÇÃO
def importar_dados():
    try:
        conn = conectar_sql()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM FTECH_XML")
        dados = cursor.fetchall()
        colunas_banco = [col[0].lower() for col in cursor.description]
        idx_chave = colunas_banco.index("chave_nfe")
        idx_produto = colunas_banco.index("prod_codigo")

        sheet = conectar_sheets()
        dados_existentes = sheet.get_all_values()

        cabecalho_esperado = [
            "id", "chave_nfe", "cUF", "cNF", "natOp", "mod", "serie", "nNF", "dhEmi", "dhSaiEnt",
            "tpNF", "emitente_cnpj", "emitente_nome", "emitente_municipio", "emitente_uf",
            "destinatario_cnpj", "destinatario_nome", "prod_codigo", "prod_nome", "prod_cfop",
            "prod_quantidade", "prod_valor_unitario", "prod_valor_total", "infCpl"
        ]

        if not dados_existentes:
            sheet.insert_row(cabecalho_esperado, index=1)
            dados_existentes = sheet.get_all_values()
        elif dados_existentes[0] != cabecalho_esperado:
            sheet.delete_rows(1)
            sheet.insert_row(cabecalho_esperado, index=1)
            dados_existentes = sheet.get_all_values()

        idx_chave_planilha = encontrar_indice_coluna(dados_existentes[0], "chave_nfe")
        idx_produto_planilha = encontrar_indice_coluna(dados_existentes[0], "prod_codigo")
        idx_nome_planilha = encontrar_indice_coluna(dados_existentes[0], "prod_nome")

        chaves_existentes = {
            (linha[idx_chave_planilha], linha[idx_produto_planilha], linha[idx_nome_planilha])
            for linha in dados_existentes[1:]
        }

        linhas_para_inserir = []
        for row in dados:
            chave = row[idx_chave]
            cod_prod = row[idx_produto]
            nome_prod = row[idx_nome_planilha]
            if (chave, cod_prod, nome_prod) not in chaves_existentes:
                linha_limpa = [str(c) if not isinstance(c, datetime) else c.strftime("%Y-%m-%d %H:%M:%S") for c in row]
                linhas_para_inserir.append(linha_limpa)

        if linhas_para_inserir:
            sheet.insert_rows(linhas_para_inserir, row=len(dados_existentes)+1)
            escrever_log(f"{len(linhas_para_inserir)} linhas inseridas com sucesso.")
            return len(linhas_para_inserir)

        escrever_log("Nenhuma nova linha para inserir.")
        return 0

    except Exception as e:
        escrever_log(f"Erro durante importação: {e}")
        return 0
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# INTERFACE GRÁFICA
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Exportador SQL → Google Sheets")
        self.root.geometry("400x220")

        self.label_status = ttk.Label(root, text="Aguardando...", font=("Segoe UI", 10))
        self.label_status.pack(pady=10)

        self.label_ultima = ttk.Label(root, text="Última importação: --", font=("Segoe UI", 9))
        self.label_ultima.pack(pady=5)

        self.label_proxima = ttk.Label(root, text="Próxima importação: --", font=("Segoe UI", 9))
        self.label_proxima.pack(pady=5)

        self.btn_importar = ttk.Button(root, text="Importar Agora", command=self.executar_importacao)
        self.btn_importar.pack(pady=10)

        self.btn_fechar = ttk.Button(root, text="Fechar", command=root.quit)
        self.btn_fechar.pack(pady=5)

        self.proxima_execucao = None
        self.agendar_importacao()

    def executar_importacao(self):
        self.label_status.config(text="Importando...")
        self.root.update()
        inseridos = importar_dados()
        agora = datetime.now()
        self.label_ultima.config(text=f"Última importação: {agora.strftime('%d/%m/%Y %H:%M:%S')}")
        self.label_status.config(text=f"{inseridos} linhas inseridas.")
        self.proxima_execucao = agora + timedelta(minutes=INTERVALO_MINUTOS)
        self.label_proxima.config(text=f"Próxima importação: {self.proxima_execucao.strftime('%H:%M:%S')}")

    def agendar_importacao(self):
        def agendador():
            while True:
                agora = datetime.now()
                if self.proxima_execucao is None or agora >= self.proxima_execucao:
                    self.root.after(0, self.executar_importacao)
                time.sleep(60)

        t = threading.Thread(target=agendador, daemon=True)
        t.start()

# EXECUÇÃO
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()

