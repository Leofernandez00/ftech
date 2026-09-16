import pandas as pd
from sqlalchemy import create_engine
import time
import tkinter as tk
from tkinter import messagebox

# Função para importar dados do Excel para SQL Server
def importar_dados_excel():
    try:
        # Caminho do arquivo Excel
        caminho_excel = r'\\ANALISTA_SISTEM\Importações\Notas_Fiscais_XML.xlsx'

        # Leia a planilha do Excel
        df = pd.read_excel(caminho_excel)

        # Configuração da conexão com o SQL Server
        server = 'SERVER\\SQL2017'
        database = 'AltaPaulista'
        username = 'sa'
        password = 'Sonoda455b'
        tabela_destino = 'dbo.XML_NFS'

        # Crie a string de conexão
        connection_string = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
        engine = create_engine(connection_string)

        # Apagar todos os dados antes de inserir novos
        with engine.connect() as conn:
            conn.execute(f"DELETE FROM {tabela_destino}")
            print(f"Todos os dados da tabela {tabela_destino} foram apagados.")

        # Importe os dados para a tabela SQL Server
        df.to_sql(tabela_destino, engine, if_exists='append', index=False)

        # Atualiza o status na interface
        status_var.set(f"Dados importados com sucesso para a tabela {tabela_destino}!")
    except Exception as e:
        # Atualiza o status com o erro na interface
        status_var.set(f"Erro: {str(e)}")
        # Exibe uma mensagem de erro em uma caixa de diálogo
        messagebox.showerror("Erro na Importação", f"Ocorreu um erro: {str(e)}")

# Função que executa a importação a cada 15 minutos
def executar_importacao_periodica():
    importar_dados_excel()
    root.after(900000, executar_importacao_periodica)  # 900000 ms = 15 minutos

# Configuração da interface gráfica
root = tk.Tk()
root.title("Importação de Dados XML para SQL Server")

# Variável de status
status_var = tk.StringVar()
status_var.set("Aguardando início da importação...")

# Rótulo para mostrar o status
status_label = tk.Label(root, textvariable=status_var, wraplength=400)
status_label.pack(pady=20)

# Botão para iniciar a importação manualmente
start_button = tk.Button(root, text="Iniciar Importação Agora", command=importar_dados_excel)
start_button.pack(pady=10)

# Inicia a primeira execução e a interface gráfica
root.after(0, executar_importacao_periodica)
root.mainloop()
