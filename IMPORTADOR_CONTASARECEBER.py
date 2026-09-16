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
caminho_arquivo = r'\\Server\z_financeiro\BD_COBRANCA\CONTAS_A_RECEBER.xlsx'
nome_tabela_excel = 'Entradas'
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
    with open(caminho_log, 'a', encoding='utf-8') as f:
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

        # Ajustar para 23 colunas do Excel
        df.columns = [
            'filial', 'prefixo', 'numero_titulo', 'parcela', 'tipo', 'cliente', 'loja', 'nome_cliente',
            'dt_emissao', 'vencto_real', 'moeda', 'natureza', 'taxa_moeda', 'vlr_titulo',
            'saldo_moeda', 'saldo', 'saldo_a_receber', 'sld_decresc', 'sld_acresc',
            'abatimentos', 'vl_acessorio', 'multa', 'juros'
        ]

        novos_registros = 0

        for _, row in df.iterrows():
            cursor.execute("""
                SELECT COUNT(*) FROM CONTASARECEBER
                WHERE numero_titulo = ? AND parcela = ? AND cliente = ?
            """, row['numero_titulo'], row['parcela'], row['cliente'])

            if cursor.fetchone()[0] == 0:
                sql = """
                INSERT INTO CONTASARECEBER (
                    filial, prefixo, numero_titulo, parcela, tipo, cliente, loja, nome_cliente,
                    dt_emissao, vencto_real, moeda, natureza, taxa_moeda, vlr_titulo,
                    saldo_moeda, saldo, saldo_a_receber, sld_decresc, sld_acresc,
                    abatimentos, vl_acessorio, multa, juros, usuario
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                valores = [
                    row['filial'], row['prefixo'], row['numero_titulo'], row['parcela'], row['tipo'],
                    row['cliente'], row['loja'], row['nome_cliente'], row['dt_emissao'], row['vencto_real'],
                    row['moeda'], row['natureza'], row['taxa_moeda'], row['vlr_titulo'], row['saldo_moeda'],
                    row['saldo'], row['saldo_a_receber'], row['sld_decresc'], row['sld_acresc'],
                    row['abatimentos'], row['vl_acessorio'], row['multa'], row['juros'],
                    None  # usuario não vem do Excel
                ]

                valores = [None if pd.isna(v) else v for v in valores]
                cursor.execute(sql, valores)
                novos_registros += 1

        conn.commit()
        cursor.close()
        conn.close()

        ultimo_import = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = f'Última importação: {ultimo_import} - {novos_registros} novos registros.'
        status_label.config(text=status)

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
