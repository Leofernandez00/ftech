import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import pyodbc
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import threading
import time

# CONFIGURAÇÕES GLOBAIS
INTERVALO_MINUTOS = 15
PLANILHA_GOOGLE = "IMPORTACAO_FTECH"
ARQUIVO_CREDENCIAIS = "credenciais.json"
LOG_PATH = "log_importacao_cobranca.txt"

# CONEXÃO SQL SERVER
def conectar_sql():
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=187.17.206.167,1433;'
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
    return spreadsheet.worksheet("COBRANCA_PROTHEUS")

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

# NORMALIZAR VALOR
def normalizar_valor(val):
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")  # Sempre só data
    if isinstance(val, (float, int)):
        if val == int(val):
            return str(int(val))
        return f"{val:.2f}".replace(',', '.')
    return str(val).strip().upper()

# FUNÇÃO DE IMPORTAÇÃO
def importar_dados():
    try:
        conn = conectar_sql()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM COBRANCA_FINAN")
        dados = cursor.fetchall()
        colunas_banco = [col[0] for col in cursor.description]

        sheet = conectar_sheets()
        dados_existentes = sheet.get_all_values()

        cabecalho_esperado = [
            "Codigo_Lj_Nome_do_Cliente", "Prf_Numero_Parcela", "TP", "Natureza",
            "Data_de_Emissao", "Vencto_Titulo", "Vencto_Real", "Bco_St",
            "Valor_Original", "Tit_Vencidos_Valor_Atual", "Tit_Vencidos_Valor_Corrigido",
            "Titulos_a_Vencer_Valor_Atual", "Num_Banco", "Vlr_juros_ou_permanencia",
            "Dias_Atraso", "Historico", "Vencidos_Vencer"
        ]

        if not dados_existentes:
            sheet.insert_row(cabecalho_esperado, index=1)
            dados_existentes = sheet.get_all_values()
        elif dados_existentes[0] != cabecalho_esperado:
            sheet.delete_rows(1)
            sheet.insert_row(cabecalho_esperado, index=1)
            dados_existentes = sheet.get_all_values()

        # CAMPOS PARA VERIFICAR DUPLICIDADE
        CAMPOS_CHAVE = ["Codigo_Lj_Nome_do_Cliente", "Prf_Numero_Parcela", "Data_de_Emissao"]

        # ENCONTRAR ÍNDICES
        indices_chave_planilha = [encontrar_indice_coluna(dados_existentes[0], campo) for campo in CAMPOS_CHAVE]
        indices_chave_banco = [colunas_banco.index(campo) for campo in CAMPOS_CHAVE]

        # CONJUNTO DE CHAVES EXISTENTES NORMALIZADAS
        chaves_existentes = set(
            tuple(normalizar_valor(linha[idx]) for idx in indices_chave_planilha)
            for linha in dados_existentes[1:]
        )

        linhas_para_inserir = []

        for row in dados:
            chave = tuple(
                normalizar_valor(row[idx])
                for idx in indices_chave_banco
            )
            if chave not in chaves_existentes:
                linha_limpa = [
                    normalizar_valor(c)
                    for c in row
                ]
                linhas_para_inserir.append(linha_limpa)
                chaves_existentes.add(chave)  # evita duplicar na mesma execução

        if linhas_para_inserir:
            sheet.append_rows(linhas_para_inserir)
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
        self.root.title("Exportador SQL → Google Sheets - Cobrança")
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

