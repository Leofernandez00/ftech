import os
import time
import pandas as pd
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import messagebox
from threading import Thread
from datetime import datetime, timedelta

# Caminhos de origem e destino
pasta_origem = r'\\Server\xml'
caminho_excel = r'\\Server\Importações\Notas_Fiscais_XML.xlsx'


# Função para extrair os dados do XML

def extrair_dados_xml(caminho_xml):
    tree = ET.parse(caminho_xml)
    root = tree.getroot()
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    def get_text(element, path):
        el = element.find(path, namespaces=ns)
        return el.text.strip() if el is not None and el.text else ''

    def get_attr(element, path, attr):
        el = element.find(path, namespaces=ns)
        return el.attrib.get(attr, '').strip() if el is not None else ''

    # Dados comuns à nota
    nota_info = {
        'chave_nfe': get_attr(root, './/nfe:infNFe', 'Id'),
        'cUF': get_text(root, './/nfe:ide/nfe:cUF'),
        'cNF': get_text(root, './/nfe:ide/nfe:cNF'),
        'natOp': get_text(root, './/nfe:ide/nfe:natOp'),
        'mod': get_text(root, './/nfe:ide/nfe:mod'),
        'serie': get_text(root, './/nfe:ide/nfe:serie'),
        'nNF': get_text(root, './/nfe:ide/nfe:nNF'),
        'dhEmi': get_text(root, './/nfe:ide/nfe:dhEmi'),
        'dhSaiEnt': get_text(root, './/nfe:ide/nfe:dhSaiEnt'),
        'tpNF': get_text(root, './/nfe:ide/nfe:tpNF'),
        'idDest': get_text(root, './/nfe:ide/nfe:idDest'),
        'cMunFG': get_text(root, './/nfe:ide/nfe:cMunFG'),
        'tpImp': get_text(root, './/nfe:ide/nfe:tpImp'),
        'tpEmis': get_text(root, './/nfe:ide/nfe:tpEmis'),
        'cDV': get_text(root, './/nfe:ide/nfe:cDV'),
        'tpAmb': get_text(root, './/nfe:ide/nfe:tpAmb'),
        'finNFe': get_text(root, './/nfe:ide/nfe:finNFe'),
        'indFinal': get_text(root, './/nfe:ide/nfe:indFinal'),
        'indPres': get_text(root, './/nfe:ide/nfe:indPres'),
        'procEmi': get_text(root, './/nfe:ide/nfe:procEmi'),
        'verProc': get_text(root, './/nfe:ide/nfe:verProc'),
        'emitente_cnpj': get_text(root, './/nfe:emit/nfe:CNPJ'),
        'emitente_nome': get_text(root, './/nfe:emit/nfe:xNome'),
        'emitente_fantasia': get_text(root, './/nfe:emit/nfe:xFant'),
        'emitente_endereco': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:xLgr'),
        'emitente_numero': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:nro'),
        'emitente_complemento': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:xCpl'),
        'emitente_bairro': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:xBairro'),
        'emitente_municipio': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:xMun'),
        'emitente_uf': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:UF'),
        'emitente_cep': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:CEP'),
        'emitente_pais': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:xPais'),
        'emitente_telefone': get_text(root, './/nfe:emit/nfe:enderEmit/nfe:fone'),
        'emitente_ie': get_text(root, './/nfe:emit/nfe:IE'),
        'emitente_crt': get_text(root, './/nfe:emit/nfe:CRT'),
        'destinatario_cnpj': get_text(root, './/nfe:dest/nfe:CNPJ'),
        'destinatario_nome': get_text(root, './/nfe:dest/nfe:xNome'),
        'destinatario_endereco': get_text(root, './/nfe:dest/nfe:enderDest/nfe:xLgr'),
        'destinatario_numero': get_text(root, './/nfe:dest/nfe:enderDest/nfe:nro'),
        'destinatario_bairro': get_text(root, './/nfe:dest/nfe:enderDest/nfe:xBairro'),
        'destinatario_municipio': get_text(root, './/nfe:dest/nfe:enderDest/nfe:xMun'),
        'destinatario_uf': get_text(root, './/nfe:dest/nfe:enderDest/nfe:UF'),
        'destinatario_cep': get_text(root, './/nfe:dest/nfe:enderDest/nfe:CEP'),
        'destinatario_pais': get_text(root, './/nfe:dest/nfe:enderDest/nfe:xPais'),
        'destinatario_telefone': get_text(root, './/nfe:dest/nfe:enderDest/nfe:fone'),
        'destinatario_ie': get_text(root, './/nfe:dest/nfe:IE'),
        'destinatario_email': get_text(root, './/nfe:dest/nfe:email'),
        'valor_frete': get_text(root, './/nfe:transp/nfe:vFrete'),
        'valor_seguro': get_text(root, './/nfe:transp/nfe:vSeg'),
        'valor_desconto': get_text(root, './/nfe:total/nfe:ICMS/nfe:vDesc'),
        'valor_despesas': get_text(root, './/nfe:total/nfe:ICMS/nfe:vDesp'),
        'valor_importacao': get_text(root, './/nfe:total/nfe:ICMS/nfe:vImport'),
        'valor_outros': get_text(root, './/nfe:total/nfe:ICMS/nfe:vOutro'),
        'valor_icms': get_text(root, './/nfe:total/nfe:ICMS/nfe:vICMS'),
        'valor_nota': get_text(root, './/nfe:total/nfe:ICMS/nfe:vNF'),
    }

    dados_itens = []
    for det in root.findall('.//nfe:det', namespaces=ns):
        dados_item = nota_info.copy()
        dados_item.update({
            'prod_codigo': get_text(det, './nfe:prod/nfe:cProd'),
            'prod_ean': get_text(det, './nfe:prod/nfe:cEAN'),
            'prod_nome': get_text(det, './nfe:prod/nfe:xProd'),
            'prod_ncm': get_text(det, './nfe:prod/nfe:NCM'),
            'prod_cest': get_text(det, './nfe:prod/nfe:CEST'),
            'prod_cfop': get_text(det, './nfe:prod/nfe:CFOP'),
            'prod_unidade': get_text(det, './nfe:prod/nfe:uCom'),
            'prod_quantidade': get_text(det, './nfe:prod/nfe:qCom'),
            'prod_valor_unitario': get_text(det, './nfe:prod/nfe:vUnCom'),
            'prod_valor_total': get_text(det, './nfe:prod/nfe:vProd'),
            'imposto_icms_cst': get_text(det, './nfe:imposto/nfe:ICMS/nfe:ICMS60/nfe:CST'),
            'imposto_icms_vbc': get_text(det, './nfe:imposto/nfe:ICMS/nfe:ICMS60/nfe:vBC'),
            'imposto_icms_vicms': get_text(det, './nfe:imposto/nfe:ICMS/nfe:ICMS60/nfe:vICMS'),
            'imposto_ipi_cst': get_text(det, './nfe:imposto/nfe:IPI/nfe:IPINT/nfe:CST'),
            'imposto_ipi_vbc': get_text(det, './nfe:imposto/nfe:IPI/nfe:IPINT/nfe:vBC'),
            'imposto_ipi_pipi': get_text(det, './nfe:imposto/nfe:IPI/nfe:IPINT/nfe:pIPI'),
            'imposto_ipi_vipi': get_text(det, './nfe:imposto/nfe:IPI/nfe:IPINT/nfe:vIPI'),
            'infCpl': get_text(root, './/nfe:infAdic/nfe:infCpl')  # Adiciona o infCpl
        })
        dados_itens.append(dados_item)

    return dados_itens

# Função para excluir tudo antes de importar

def atualizar_excel():
    global ultima_execucao
    global proxima_execucao

    try:
        arquivos_xml = [os.path.join(pasta_origem, f) for f in os.listdir(pasta_origem) if f.endswith('.xml')]

        todas_linhas = []  # Esta lista vai conter todos os DataFrames dos produtos

        for arquivo_xml in arquivos_xml:
            itens = extrair_dados_xml(arquivo_xml)
            for item in itens:
                df_item = pd.DataFrame([item])
                todas_linhas.append(df_item)

        if todas_linhas:
            df_final = pd.concat(todas_linhas, ignore_index=True)
            df_final.to_excel(caminho_excel, index=False)

        ultima_execucao.set(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        proxima_execucao_time = datetime.now() + timedelta(minutes=15)
        proxima_execucao.set(proxima_execucao_time.strftime('%Y-%m-%d %H:%M:%S'))
        proxima_execucao_secs.set(proxima_execucao_time.timestamp())

        error_message.set("Importação concluída com sucesso.")

    except Exception as e:
        error_message.set(f"Erro: {str(e)}")


def atualizar_interface():
    global ultima_execucao
    global proxima_execucao
    global error_message
    global tempo_restante

    while True:
        try:
            atualizar_excel()
        except Exception as e:
            error_message.set(f"Erro: {str(e)}")

        agora = datetime.now()
        proxima = datetime.fromtimestamp(proxima_execucao_secs.get())
        tempo_restante_delta = proxima - agora

        minutos_restantes = tempo_restante_delta.seconds // 60
        segundos_restantes = tempo_restante_delta.seconds % 60

        tempo_restante.set(f"Próxima Extração em: {minutos_restantes:02d}:{segundos_restantes:02d}")

        time.sleep(60)  # Atualiza a interface a cada minuto


def cronometro():
    global tempo_restante

    while True:
        agora = datetime.now()
        proxima = datetime.fromtimestamp(proxima_execucao_secs.get())
        restante = proxima - agora

        if restante.total_seconds() <= 0:
            restante = timedelta(0)

        minutos_restantes = restante.seconds // 60
        segundos_restantes = restante.seconds % 60

        tempo_restante.set(f"Próxima Extração em: {minutos_restantes:02d}:{segundos_restantes:02d}")

        time.sleep(1)  # Atualiza o cronômetro a cada segundo


# Função para criar a interface gráfica
def criar_interface():
    global error_message
    global ultima_execucao
    global proxima_execucao
    global tempo_restante
    global proxima_execucao_secs

    root = tk.Tk()
    root.title("Monitor de Importação de XML")

    tk.Label(root, text="Última Extração:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
    ultima_execucao = tk.StringVar()
    tk.Label(root, textvariable=ultima_execucao).grid(row=0, column=1, padx=10, pady=5)

    tk.Label(root, text="Próxima Extração:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
    proxima_execucao = tk.StringVar()
    tk.Label(root, textvariable=proxima_execucao).grid(row=1, column=1, padx=10, pady=5)

    tk.Label(root, text="Tempo Restante:").grid(row=2, column=0, padx=10, pady=5, sticky='e')
    tempo_restante = tk.StringVar()
    tk.Label(root, textvariable=tempo_restante).grid(row=2, column=1, padx=10, pady=5)

    tk.Label(root, text="Status:").grid(row=3, column=0, padx=10, pady=5, sticky='e')
    error_message = tk.StringVar()
    tk.Label(root, textvariable=error_message).grid(row=3, column=1, padx=10, pady=5)

    tk.Button(root, text="Sair", command=root.quit).grid(row=4, column=0, columnspan=2, pady=10)

    root.update()  # Atualiza a interface com os valores iniciais


    proxima_execucao_secs = tk.DoubleVar()  # Armazena o timestamp da próxima execução

    # Inicia threads para atualizar a interface e o cronômetro
    Thread(target=atualizar_interface, daemon=True).start()
    Thread(target=cronometro, daemon=True).start()

    root.mainloop()


# Executar a interface gráfica
if __name__ == "__main__":
    criar_interface()

