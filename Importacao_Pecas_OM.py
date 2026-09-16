import os
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

SAMPLE_SPREADSHEET_ID = "1SFCWKPD9FpyiEGXny7dDxA-wq5yMyRD4begQoOazktk"
SAMPLE_RANGE_NAME = "NF_Memorando!A:V"

CREDENTIALS_PATH = r"W:\Programas\credentials.json"
TOKEN_PATH = "token.json"


def autenticar_google():
    creds = None

    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            print(f"Erro ao carregar token.json: {e}")
            creds = None

    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise Exception("Token inválido ou ausente.")
        except Exception as e:
            print(f"Erro ao renovar token: {e}")

            if os.path.exists(TOKEN_PATH):
                os.remove(TOKEN_PATH)

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH,
                    SCOPES
                )
                creds = flow.run_local_server(port=0)

                with open(TOKEN_PATH, "w") as token:
                    token.write(creds.to_json())

            except Exception as auth_error:
                messagebox.showerror(
                    "Erro de Autenticação",
                    f"Falha ao autenticar com Google:\n{auth_error}"
                )
                return None

    return creds


def import_data():
    creds = autenticar_google()

    if not creds:
        return None

    try:
        service = build("sheets", "v4", credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range=SAMPLE_RANGE_NAME
        ).execute()

        return result.get("values", [])

    except HttpError as err:
        messagebox.showerror(
            "Erro de API Google",
            f"Erro ao acessar Google Sheets:\n{err}"
        )
        return None


def get_col(row, index):
    if index == -1:
        return ""

    if len(row) > index and row[index]:
        return str(row[index]).strip()

    return ""


def limpar_texto(valor):
    valor = str(valor)

    valor = valor.replace("\n", " ")
    valor = valor.replace("\r", " ")
    valor = valor.replace("\t", " ")

    # Evita quebrar o layout separado por ;
    valor = valor.replace(";", ",")

    return " ".join(valor.split()).strip()


def localizar_coluna(header, nomes_possiveis):
    for nome in nomes_possiveis:
        if nome in header:
            return header.index(nome)
    return -1


def reorder_data(values):
    """
    Layout final:
    CODIGO;DATA;0;DESCRICAO;UN;1;VALOR;1;1;0;1;1
    """

    if not values:
        return []

    header = values[0]
    rows = values[1:]

    col_codigo = localizar_coluna(header, [
        "Ordem de Serviço Oficina",
        "Ordem de Servico Oficina",
        "OS Oficina",
        "Nº OS Oficina",
        "No OS Oficina",
        "Numero OS Oficina"
    ])

    if col_codigo == -1:
        messagebox.showerror(
            "Erro",
            f"Coluna 'Ordem de Serviço Oficina' não encontrada.\n\n"
            f"Colunas encontradas:\n{', '.join(header)}"
        )
        return []

    col_data = localizar_coluna(header, [
        "Data Encerramento",
        "Data/Hora",
        "Data",
        "DATA"
    ])

    col_descricao = localizar_coluna(header, [
        "Serviço Executado",
        "Servico Executado",
        "Prognóstico",
        "Prognostico",
        "Descrição",
        "Descricao"
    ])

    col_valor = localizar_coluna(header, [
        "Valor Total",
        "Valor Total NF Peças",
        "Valor Total NF Pecas",
        "Valor Total NF Mão de Obra",
        "Valor Total NF Mao de Obra"
    ])

    if col_codigo == -1:
        messagebox.showerror("Erro", "Coluna 'Cód Memorando' não encontrada.")
        return []

    if col_data == -1:
        messagebox.showerror("Erro", "Coluna de data não encontrada.")
        return []

    if col_descricao == -1:
        messagebox.showerror("Erro", "Coluna 'Serviço Executado' não encontrada.")
        return []

    if col_valor == -1:
        messagebox.showerror("Erro", "Coluna de valor não encontrada.")
        return []

    data_final = []

    for row in rows:
        codigo = limpar_texto(get_col(row, col_codigo))
        data = limpar_texto(get_col(row, col_data))
        descricao = limpar_texto(get_col(row, col_descricao))
        valor = limpar_texto(get_col(row, col_valor))

        if not codigo or not descricao:
            continue

        linha = [
            codigo,
            data,
            "0",
            descricao,
            "UN",
            "1",
            valor,
            "1",
            "1",
            "0",
            "1",
            "1"
        ]

        data_final.append(linha)

    return data_final


def export_to_txt(data):
    if not data:
        messagebox.showwarning("Aviso", "Nenhum dado válido para exportar.")
        return

    now = datetime.now()
    default_filename = f"INTALMOX{now.strftime('%m%y')}.txt"

    filepath = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt")],
        initialfile=default_filename,
        title="Salvar arquivo como..."
    )

    if not filepath:
        status_label.config(text="⚠️ Exportação cancelada pelo usuário.")
        return

    try:
        with open(filepath, "w", encoding="ansi", newline="") as file:
            for row in data:
                file.write(";".join(row) + "\r\n")

        status_label.config(text="✅ Dados salvos com sucesso!")

    except Exception as e:
        messagebox.showerror(
            "Erro ao salvar",
            f"Não foi possível salvar o arquivo:\n{e}"
        )


def process_data():
    status_label.config(text="⏳ Importando dados...")
    root.update_idletasks()

    values = import_data()

    if values:
        data = reorder_data(values)
        export_to_txt(data)
    else:
        status_label.config(text="❌ Falha ao importar dados.")


root = tk.Tk()
root.title("Exportador de Dados Google Sheets")
root.geometry("450x160")

process_button = tk.Button(
    root,
    text="Processar",
    command=process_data,
    height=2,
    width=25
)
process_button.pack(pady=15)

status_label = tk.Label(root, text="", font=("Arial", 10))
status_label.pack()

root.mainloop()