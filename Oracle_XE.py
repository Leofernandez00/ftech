import cx_Oracle
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys


class TextRedirector:
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, msg):
        self.widget.insert(tk.END, msg)
        self.widget.see(tk.END)

    def flush(self):
        pass


def escolher_destino():
    destino = filedialog.askdirectory()
    if destino:
        entry_destino.delete(0, tk.END)
        entry_destino.insert(tk.END, destino)


def importar_dados():
    tabelas_selecionadas = [tabela for tabela, var in checkbox_vars.items() if var.get()]
    if not tabelas_selecionadas:
        messagebox.showwarning("Atenção", "Nenhuma tabela selecionada!")
        return

    destino = entry_destino.get()
    if not destino:
        messagebox.showwarning("Atenção", "Selecione um diretório de destino!")
        return

    dsn_tns = cx_Oracle.makedsn(entry_host.get(), entry_port.get(), service_name=entry_service.get())

    try:
        connection = cx_Oracle.connect(user=entry_usuario.get(), password=entry_senha.get(), dsn=dsn_tns)
        print("Conexão estabelecida com sucesso!")

        for tabela in tabelas_selecionadas:
            query = f"SELECT * FROM {tabela.strip()}"
            print(f"Executando query: {query}")
            cursor = connection.cursor()
            cursor.execute(query)

            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            # Criar DataFrame garantindo todas as colunas presentes
            df = pd.DataFrame(rows, columns=columns)

            # Substituir valores ausentes por NULL
            df = df.where(pd.notnull(df), None)

            if not df.empty:
                caminho_arquivo_excel = f"{destino}/{tabela.strip()}.xlsx"
                caminho_arquivo_csv = f"{destino}/{tabela.strip()}.csv"

                # Salvar no Excel com xlsxwriter
                writer = pd.ExcelWriter(caminho_arquivo_excel, engine='xlsxwriter')
                df.to_excel(writer, index=False, na_rep='NULL', sheet_name='Dados')

                # Configurar formatação das colunas (opcional)
                workbook = writer.book
                worksheet = writer.sheets['Dados']
                for idx, col in enumerate(df):
                    series = df[col]
                    max_len = max((
                        series.astype(str).map(len).max(),
                        len(str(series.name))
                    )) + 1
                    worksheet.set_column(idx, idx, max_len)

                writer.close()  # Fechar o escritor após salvar

                # Salvar no CSV
                df.to_csv(caminho_arquivo_csv, index=False, na_rep='NULL')

                text_status.insert(tk.END,
                                   f'Tabela {tabela.strip()} importada com sucesso para {caminho_arquivo_excel} e {caminho_arquivo_csv}.\n')
            else:
                text_status.insert(tk.END, f'AVISO: Tabela {tabela.strip()} está vazia e não foi importada.\n')

        connection.close()
        text_status.insert(tk.END, "Todos os dados foram salvos com sucesso.\n")
    except cx_Oracle.Error as e:
        messagebox.showerror("Erro Oracle", f"Erro Oracle: {str(e)}")
        text_status.insert(tk.END, f"Erro Oracle: {str(e)}\n")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro: {str(e)}")
        text_status.insert(tk.END, f"Erro: {str(e)}\n")
    finally:
        text_status.insert(tk.END, "Operação concluída.\n")


root = tk.Tk()
root.title("Importar Dados do Oracle para Excel e CSV")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

ttk.Label(frame, text="Host").grid(row=0, column=0, sticky=tk.W)
entry_host = ttk.Entry(frame, width=20)
entry_host.insert(tk.END, "SERVER")
entry_host.grid(row=0, column=1, pady=5)

ttk.Label(frame, text="Porta").grid(row=1, column=0, sticky=tk.W)
entry_port = ttk.Entry(frame, width=20)
entry_port.insert(tk.END, "1521")
entry_port.grid(row=1, column=1, pady=5)

ttk.Label(frame, text="Service Name").grid(row=2, column=0, sticky=tk.W)
entry_service = ttk.Entry(frame, width=20)
entry_service.insert(tk.END, "XE")
entry_service.grid(row=2, column=1, pady=5)

ttk.Label(frame, text="Usuário").grid(row=3, column=0, sticky=tk.W)
entry_usuario = ttk.Entry(frame, width=20)
entry_usuario.insert(tk.END, "assiste")
entry_usuario.grid(row=3, column=1, pady=5)

ttk.Label(frame, text="Senha").grid(row=4, column=0, sticky=tk.W)
entry_senha = ttk.Entry(frame, show='*', width=20)
entry_senha.insert(tk.END, "terceiro")
entry_senha.grid(row=4, column=1, pady=5)

ttk.Label(frame, text="Caminho de Destino").grid(row=5, column=0, sticky=tk.W)
entry_destino = ttk.Entry(frame, width=40)
entry_destino.grid(row=5, column=1, pady=5)

button_escolher_destino = ttk.Button(frame, text="Escolher", command=escolher_destino)
button_escolher_destino.grid(row=5, column=2, pady=5)

tabelas = ['EQUIPAMENTO', 'MODELO', 'CLASSMECAN']

checkbox_vars = {}
ttk.Label(frame, text="Selecione as Tabelas").grid(row=6, column=0, sticky=tk.W)
for i, tabela in enumerate(tabelas, start=7):
    var = tk.BooleanVar()
    checkbox_vars[tabela] = var
    chk = ttk.Checkbutton(frame, text=tabela, variable=var)
    chk.grid(row=i, column=0, columnspan=2, sticky=tk.W)

button_importar = ttk.Button(frame, text="Importar Dados", command=importar_dados)
button_importar.grid(row=i + 1, column=0, columnspan=2, pady=10)

text_status = tk.Text(frame, width=70, height=10, wrap='word')
text_status.grid(row=i + 2, column=0, columnspan=2, pady=10)

sys.stdout = TextRedirector(text_status)

root.mainloop()
