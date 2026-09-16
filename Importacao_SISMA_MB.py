import pandas as pd
import os
import tkinter as tk
from tkinter import filedialog, messagebox

def formatar_hora(hora):
    if isinstance(hora, str):
        partes = hora.split(':')
        if len(partes) == 3:
            return ''.join(partes[:2])
    return hora

def substituir_ponto_por_virgula(valor):
    if isinstance(valor, str):
        return valor.replace('.', ',')
    return valor

def mapear_tipo_combustivel(tipo):
    mapeamento = {
        'GASOLINA COMUM': '403',
        'ETANOL': '401',
        'DIESEL S-10 COMUM': '404',
        'Arla 32': '408',
        'DIESEL': '402',
        'GASOLINA ADITIVADA': '403',
        'ETANOL ADITIVADO': '401',
        'DIESEL S-10 ADITIVADO': '404'
    }

    if tipo in mapeamento:
        return mapeamento[tipo]
    else:
        messagebox.showwarning(
            "Alerta",
            f"Tipo de combustível não relacionado na tabela: {tipo}"
        )
        return tipo

def mapear_estabelecimento(tipo2):
    if tipo2 == 12677677:
        return 1
    else:
        return 2

def processar_arquivo():
    arquivo_excel = filedialog.askopenfilename(
        initialdir="X:/Temp",
        title="Selecione o arquivo Excel",
        filetypes=(("Arquivos Excel", "*.xlsx"), ("Todos os arquivos", "*.*"))
    )

    if not arquivo_excel:
        return

    pasta_destino = filedialog.askdirectory(
        title="Selecione a pasta onde deseja salvar o arquivo CSV"
    )

    if not pasta_destino:
        messagebox.showwarning(
            "Atenção",
            "Nenhuma pasta de destino foi selecionada."
        )
        return

    try:
        lbl_progresso.config(text="Processando arquivo...")

        df = pd.read_excel(arquivo_excel)

        df['LITROS'] = pd.to_numeric(df['LITROS'], errors='coerce')
        df['LITROS'] = df['LITROS'].astype(str).apply(substituir_ponto_por_virgula)

        df['VALOR EMISSAO'] = pd.to_numeric(df['VALOR EMISSAO'], errors='coerce')
        df['VALOR EMISSAO'] = df['VALOR EMISSAO'].astype(str).apply(substituir_ponto_por_virgula)

        df['DATA'] = pd.to_datetime(df['DATA TRANSACAO']).dt.strftime('%d/%m/%Y')
        df['HORA'] = pd.to_datetime(df['DATA TRANSACAO']).dt.strftime('%H:%M:%S')
        df['HORA'] = df['HORA'].apply(formatar_hora)

        df.drop(columns=['DATA TRANSACAO'], inplace=True)

        df.dropna(subset=['DATA'], inplace=True)

        df['NUMERO FROTA'] = df['NUMERO FROTA'].fillna(0)
        df['MATRICULA'] = df['MATRICULA'].fillna(0)

        df['NUMERO FROTA'] = df['NUMERO FROTA'].astype(int)
        df['MATRICULA'] = df['MATRICULA'].astype(int)
        df['HODOMETRO OU HORIMETRO'] = df['HODOMETRO OU HORIMETRO'].astype(int)

        df['TIPO COMBUSTIVEL'] = df['TIPO COMBUSTIVEL'].apply(mapear_tipo_combustivel)
        df['CODIGO ESTABELECIMENTO'] = df['CODIGO ESTABELECIMENTO'].apply(mapear_estabelecimento)

        colunas_reordenadas = [
            'DATA',
            'HORA',
            'PLACA',
            'NUMERO FROTA',
            'MATRICULA',
            'TIPO COMBUSTIVEL',
            'LITROS',
            'HODOMETRO OU HORIMETRO',
            'VALOR EMISSAO',
            'CODIGO ESTABELECIMENTO'
        ]

        df = df[colunas_reordenadas]

        nome_arquivo_csv = os.path.join(
            pasta_destino,
            os.path.basename(arquivo_excel).replace('.xlsx', '_exportado.csv')
        )

        df.to_csv(nome_arquivo_csv, index=False, sep=';')

        os.startfile(pasta_destino)

        lbl_progresso.config(text="Arquivo CSV exportado com sucesso!")

        messagebox.showinfo(
            "Concluído",
            f"Arquivo salvo com sucesso em:\n\n{nome_arquivo_csv}"
        )

    except Exception as e:
        messagebox.showerror(
            "Erro",
            f"Ocorreu um erro ao processar o arquivo:\n\n{str(e)}"
        )
        lbl_progresso.config(text="Erro ao processar o arquivo.")

root = tk.Tk()
root.title("Processamento de Arquivo")

btn_selecionar_arquivo = tk.Button(
    root,
    text="Selecionar Arquivo Excel",
    command=processar_arquivo
)
btn_selecionar_arquivo.pack(pady=10)

lbl_progresso = tk.Label(root, text="")
lbl_progresso.pack(pady=5)

root.mainloop()