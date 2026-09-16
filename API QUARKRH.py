import requests

def importar_dados(chave_acesso):
    url = "https://api.quark.tec.br/rh/ext/"
    headers = {
        "Authorization": f"Bearer {chave_acesso}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Aqui você pode processar os dados recebidos
            dados = response.json()
            print("Dados importados com sucesso:")
            print(dados)
        else:
            print(f"Erro ao importar dados. Código de status: {response.status_code}")
    except Exception as e:
        print(f"Erro ao importar dados: {e}")

# Chave de acesso fornecida
chave_acesso = "4cebd80553d725cbf3157b48e1d56c045423216062ee116652b45087a371ea19"
importar_dados(chave_acesso)
