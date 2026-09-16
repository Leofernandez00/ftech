import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

# Define the scope for Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Google Sheets ID and range
SAMPLE_SPREADSHEET_ID = "1SFCWKPD9FpyiEGXny7dDxA-wq5yMyRD4begQoOazktk"
SAMPLE_RANGE_NAME = "Integra_OM!A2:L"

def import_data():
    """Import data from Google Sheets."""
    creds = None

    # If token.json exists, load the credentials from it
    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        except Exception as e:
            print(f"Erro ao carregar credenciais: {e}. Excluindo o arquivo token.json e tentando autenticação novamente.")
            os.remove("token.json")
            creds = None

    # If there are no valid credentials, ask the user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "W:\\Programas\\credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME).execute()
        values = result.get("values", [])

        # Filter rows containing data in the "Tipo Movimento" column
        filtered_values = [row for row in values if len(row) > 5 and row[5]]

        return filtered_values
    except HttpError as err:
        print(f"Erro na API do Google Sheets: {err}")
        return None

def export_to_txt(data, filepath):
    """Export data to a text file."""
    with open(filepath, "w") as file:
        for row in data:
            file.write(";".join(row) + "\n")

def process_data():
    """Process data, import, and export."""
    values = import_data()
    if values:
        filepath = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if filepath:
            export_to_txt(values, filepath)
            status_label.config(text="Dados exportados com sucesso!")
        else:
            status_label.config(text="Exportação cancelada pelo usuário.")

# Create GUI
root = tk.Tk()
root.title("Exportador de Dados Google Sheets")

process_button = tk.Button(root, text="Processar", command=process_data)
process_button.pack(pady=10)

status_label = tk.Label(root, text="")
status_label.pack()

root.mainloop()
