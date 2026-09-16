import requests
import pandas as pd
import os
import time

# URL da API
url = "https://api.quark.tec.br/rh/ext/v1/colaboradores/"

# Cabeçalhos da requisição
headers = {
    "accept": "*/*",
    "Auth-token": "4cebd80553d725cbf3157b48e1d56c045423216062ee116652b45087a371ea19",
    "Unidade-Id": "2980998"
}

# Lista para armazenar todos os dados
all_data = []

# Parâmetros de paginação
page = 1
page_size = 30

while True:
    # Parâmetros da requisição
    params = {
        "page": page,
        "size": page_size
    }

    # Fazer a requisição GET
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # Levanta um erro para códigos de status HTTP não bem-sucedidos
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        break

    # Obter os dados da resposta JSON
    data = response.json()

    # Verificar se a resposta contém a chave esperada com os dados
    if 'dados' in data:
        registros = data['dados']
    else:
        print("Formato de resposta inesperado. Verifique a estrutura da resposta JSON.")
        break

    # Verificar se há dados na resposta
    if not registros:
        print("Nenhum dado retornado. Finalizando a coleta de dados.")
        break  # Sai do loop se não houver mais dados

    # Adicionar os dados à lista
    all_data.extend(registros)

    # Informar o progresso
    print(f"Página {page} obtida com {len(registros)} registros.")

    # Incrementar a página para a próxima requisição
    page += 1

    # Aguardar um pequeno intervalo para evitar sobrecarregar a API
    time.sleep(1)

# Verificar se há dados acumulados
if all_data:
    # Converter a lista de dados em um DataFrame do pandas
    df = pd.DataFrame(all_data)

    # Nome do arquivo Excel
    filename = "colaboradores2.xlsx"

    # Salvar o DataFrame em um arquivo Excel
    df.to_excel(filename, index=False)

    # Obter o caminho absoluto do arquivo salvo
    filepath = os.path.abspath(filename)
    print(f"Dados salvos com sucesso em '{filepath}'.")
else:
    print("Nenhum dado foi coletado.")
