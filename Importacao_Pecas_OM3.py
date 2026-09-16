import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import tkinter as tk
from datetime import datetime

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = "1SFCWKPD9FpyiEGXny7dDxA-wq5yMyRD4begQoOazktk"
SAMPLE_RANGE_NAME = "NF_Memorando!A:V"


def import_data():
    """Import data from Google Sheets."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "W:\\Programas\\credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME).execute()
        values = result.get("values", [])
        return values
    except HttpError as err:
        print(err)
        return None


def reorder_data(values):
    """Reorder the data as needed."""
    # Example: Reordering first two columns
    reordered_data = [[row[1], row[0]] for row in values]
    return reordered_data


def export_to_txt(data):
    """Export data to a text file."""
    now = datetime.now()
    month_year = now.strftime("%m%y")
    filename = f"INTALMOX_{month_year}.txt"
    with open(filename, "w") as file:
        for row in data:
            file.write("\t".join(row) + "\n")


def process_data():
    """Process data, import, reorder, and export."""
    values = import_data()
    if values:
        reordered_data = reorder_data(values)
        export_to_txt(reordered_data)
        status_label.config(text="Dados exportados com sucesso!")


# Create GUI
root = tk.Tk()
root.title("Exportador de Dados Google Sheets")

process_button = tk.Button(root, text="Processar", command=process_data)
process_button.pack(pady=10)

status_label = tk.Label(root, text="")
status_label.pack()

root.mainloop()
