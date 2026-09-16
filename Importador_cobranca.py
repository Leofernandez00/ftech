import pandas as pd
import pyodbc
import tkinter as tk
from tkinter import messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import threading
from datetime import datetime
import os

# Configurações
caminho_arquivo = r'\\Server\z_financeiro\BD_COBRANCA\finr130.xlsx'
nome_tabela_excel = '2-Titulos a receber'
caminho_log = r'\\Server\z_financeiro\BD_COBRANCA\import_log.txt'
ultimo_import = None

# Conexão com SQL Server
conn_str = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    r'SERVER=10.0.0.254;'
    r'DATABASE=FTECH;'
    r'UID=ftech;'
    r'PWD=ftech@1975;'
    r'Trusted_Connection=no;'
)


def registrar_log(mensagem):
    with open(caminho_log, 'a') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {mensagem}\n")


def importar_dados():
    global ultimo_import
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        df = pd.read_excel(
            caminho_arquivo,
            sheet_name=nome_tabela_excel,
            skiprows=1
        )

        df.columns = [
            'Codigo_Lj_Nome_do_Cliente', 'Prf_Numero_Parcela', 'TP', 'Natureza',
            'Data_de_Emissao', 'Vencto_Titulo', 'Vencto_Real', 'Bco_St',
            'Valor_Original', 'Tit_Vencidos_Valor_Atual', 'Tit_Vencidos_Valor_Corrigido',
            'Titulos_a_Vencer_Valor_Atual', 'Num_Banco', 'Vlr_juros_ou_permanencia',
            'Dias_Atraso', 'Historico', 'Vencidos_Vencer'
        ]

        novos_registros = 0

        for _, row in df.iterrows():
            codigo = row['Codigo_Lj_Nome_do_Cliente']
            parcela = row['Prf_Numero_Parcela']
            emissao = row['Data_de_Emissao']

            cursor.execute("""
                SELECT COUNT(*) FROM COBRANCA_FINAN
                WHERE Codigo_Lj_Nome_do_Cliente = ? AND Prf_Numero_Parcela = ? AND Data_de_Emissao = ?
            """, codigo, parcela, emissao)

            if cursor.fetchone()[0] == 0:
                sql = """
                INSERT INTO COBRANCA_FINAN (
                    Codigo_Lj_Nome_do_Cliente, Prf_Numero_Parcela, TP, Natureza,
                    Data_de_Emissao, Vencto_Titulo, Vencto_Real, Bco_St,
                    Valor_Original, Tit_Vencidos_Valor_Atual, Tit_Vencidos_Valor_Corrigido,
                    Titulos_a_Vencer_Valor_Atual, Num_Banco, Vlr_juros_ou_permanencia,
                    Dias_Atraso, Historico, Vencidos_Vencer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                valores = [None if pd.isna(v) else v for v in row]
                cursor.execute(sql, valores)
                novos_registros += 1

        conn.commit()
        cursor.close()
        conn.close()

        ultimo_import = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = f'Última importação: {ultimo_import} - {novos_registros} novos registros.'
        status_label.config(text=status)

        # Log
        registrar_log(f"{novos_registros} novos registros importados.")

    except Exception as e:
        registrar_log(f"Erro na importação: {str(e)}")
        messagebox.showerror("Erro", str(e))


# Watchdog Handler
class ExcelEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.abspath(event.src_path) == os.path.abspath(caminho_arquivo):
            registrar_log("Arquivo Excel modificado. Iniciando importação automática.")
            importar_dados()


# Thread para monitorar arquivo
def iniciar_monitoramento():
    event_handler = ExcelEventHandler()
    observer = Observer()
    pasta = os.path.dirname(caminho_arquivo)
    observer.schedule(event_handler, path=pasta, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


# Interface Tkinter
root = tk.Tk()
root.title("Importador COBRANCA_FINAN")
root.geometry("400x200")

status_label = tk.Label(root, text="Última importação: Nenhuma", font=("Arial", 12))
status_label.pack(pady=20)


def forcar_importacao():
    registrar_log("Importação forçada pelo usuário.")
    importar_dados()


botao_importar = tk.Button(root, text="Forçar Importação", command=forcar_importacao)
botao_importar.pack(pady=10)

botao_sair = tk.Button(root, text="Sair", command=root.destroy)
botao_sair.pack(pady=10)

# Iniciar monitoramento em thread separada
thread_monitoramento = threading.Thread(target=iniciar_monitoramento, daemon=True)
thread_monitoramento.start()

root.mainloop()
