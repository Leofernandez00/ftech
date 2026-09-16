import pandas as pd
from tkinter import filedialog, messagebox
import os

# Função para selecionar o arquivo Excel
def selecionar_arquivo():
    filepath = filedialog.askopenfilename(initialdir="X:/Temp", title="Selecione o arquivo Excel",
                                          filetypes=(("Arquivos Excel", "*.xlsx"), ("Todos os arquivos", "*.*")))
    return filepath

# Função para formatar a hora
def formatar_hora(hora):
    # Verifica se é uma string
    if isinstance(hora, str):
        # Separa a hora, os minutos e os segundos
        partes = hora.split(':')
        # Verifica se há três partes
        if len(partes) == 3:
            # Retorna apenas a hora no formato ####
            return ''.join(partes[:2])
    # Retorna a hora original se não puder ser formatada
    return hora

# Função para substituir vírgulas por pontos
def substituir_virgula_por_ponto(valor):
    if isinstance(valor, str):
        return valor.replace(',', '.')
    return valor

# Mapeamento dos tipos de combustível para códigos
def mapear_tipo_combustivel(tipo):
    mapeamento = {
        'GASOLINA COMUM': '403',
        'ETANOL': '401',
        'DIESEL S-10 COMUM': '404',
        'Arla 32': '408',
        'DIESEL': '402'
    }
    if tipo in mapeamento:
        return mapeamento[tipo]
    else:
        messagebox.showwarning("Alerta", f"Tipo de combustível não relacionado na tabela: {tipo}")
        return tipo

# Selecionar o arquivo Excel
arquivo_excel = selecionar_arquivo()

# Verificar se o arquivo foi selecionado
if arquivo_excel:
    try:
        # Ler o arquivo Excel
        df = pd.read_excel(arquivo_excel)

        # Separação da coluna DATA TRANSACAO
        df['DATA'] = pd.to_datetime(df['DATA TRANSACAO']).dt.strftime('%d/%m/%Y')
        df['HORA'] = pd.to_datetime(df['DATA TRANSACAO']).dt.strftime('%H:%M:%S')
        df['HORA'] = df['HORA'].apply(formatar_hora)

        # Remover a coluna DATA TRANSACAO
        df.drop(columns=['DATA TRANSACAO'], inplace=True)

        # Remover linhas com valores nulos na coluna 'DATA'
        df.dropna(subset=['DATA'], inplace=True)

        # Preencher valores não finitos com 0 nas colunas 'NUMERO FROTA' e 'MATRICULA'
        df['NUMERO FROTA'].fillna(0, inplace=True)
        df['MATRICULA'].fillna(0, inplace=True)

        # Converter as colunas para tipo inteiro
        df['NUMERO FROTA'] = df['NUMERO FROTA'].astype(int)
        df['MATRICULA'] = df['MATRICULA'].astype(int)
        df['HODOMETRO OU HORIMETRO'] = df['HODOMETRO OU HORIMETRO'].astype(int)

        # Substituir vírgula por ponto na coluna 'VALOR EMISSAO'
        df['VALOR EMISSAO'] = df['VALOR EMISSAO'].map(substituir_virgula_por_ponto)

        # Converter a coluna 'VALOR EMISSAO' para um formato numérico
        df['VALOR EMISSAO'] = df['VALOR EMISSAO'].astype(float)

        # Mapear os tipos de combustível para códigos
        df['TIPO COMBUSTIVEL'] = df['TIPO COMBUSTIVEL'].apply(mapear_tipo_combustivel)

        # Reordenar e selecionar as colunas desejadas
        colunas_desejadas = ['DATA', 'PLACA', 'NUMERO FROTA', 'MATRICULA', 'TIPO COMBUSTIVEL', 'LITROS' , 'HODOMETRO OU HORIMETRO',
                             'HORA', 'VALOR EMISSAO']
        df = df[colunas_desejadas]

        # Reordenar as colunas na sequência desejada
        colunas_reordenadas = ['DATA', 'HORA', 'PLACA', 'NUMERO FROTA', 'MATRICULA', 'TIPO COMBUSTIVEL', 'LITROS' , 'HODOMETRO OU HORIMETRO', 'VALOR EMISSAO']
        df = df[colunas_reordenadas]

        # Exportar para arquivo CSV
        nome_arquivo_csv = os.path.join("X:/Combustível e Lubrificantes",
                                        os.path.basename(arquivo_excel).replace('.xlsx', '_exportado.csv'))
        df.to_csv(nome_arquivo_csv, index=False)

        # Abrir o diretório onde o arquivo CSV foi salvo
        os.startfile(os.path.dirname(nome_arquivo_csv))

        # Mostrar mensagem de sucesso
        messagebox.showinfo("Sucesso", f"Arquivo CSV exportado com sucesso: {nome_arquivo_csv}")
    except Exception as e:
        # Mostrar mensagem de erro
        messagebox.showerror("Erro", f"Ocorreu um erro ao exportar o arquivo: {str(e)}")
else:
    # Mostrar mensagem de cancelamento
    messagebox.showinfo("Cancelado", "Nenhum arquivo selecionado.")
