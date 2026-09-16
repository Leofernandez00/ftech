import os
import xml.etree.ElementTree as ET
import pyodbc
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta
import threading

# Configurações do banco de dados
DB_CONFIG = {
    'server': '187.17.206.167',
    'database': 'FTECH',
    'username': 'protheus',
    'password': 'Protheus12133'
}

# Pasta dos XMLs
PASTA_XML = r"\\SERVER\\XML"
# Arquivo de controle de arquivos já processados
ARQUIVO_CONTROLE = "arquivos_processados.txt"

# Conexão com banco
def conectar_sql():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_CONFIG['server']},1433;"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(conn_str)

# Carregar arquivos já processados
def carregar_arquivos_processados():
    if os.path.exists(ARQUIVO_CONTROLE):
        with open(ARQUIVO_CONTROLE, 'r') as f:
            return set(f.read().splitlines())
    return set()

# Salvar novo arquivo processado
def salvar_arquivo_processado(nome):
    with open(ARQUIVO_CONTROLE, 'a') as f:
        f.write(nome + '\n')

# Importar XMLs para o banco de dados
ultima_execucao = None
def importar_xmls():
    global ultima_execucao, proxima_execucao_label
    arquivos_processados = carregar_arquivos_processados()
    arquivos = [f for f in os.listdir(PASTA_XML) if f.endswith('.xml')]

    conn = conectar_sql()
    cursor = conn.cursor()

    for nome_arquivo in arquivos:
        if nome_arquivo in arquivos_processados:
            continue

        caminho = os.path.join(PASTA_XML, nome_arquivo)
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()

            ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
            infNFe = root.find('.//ns:infNFe', ns)

            if infNFe is None:
                print(f"Ignorado arquivo {nome_arquivo}: Elemento infNFe não encontrado.")
                continue

            ide = infNFe.find('ns:ide', ns)
            emit = infNFe.find('ns:emit', ns)
            dest = infNFe.find('ns:dest', ns)
            det_list = infNFe.findall('ns:det', ns)
            total = infNFe.find('ns:total', ns)
            infAdic = infNFe.find('ns:infAdic', ns)

            chave = infNFe.attrib.get('Id', '').replace('NFe', '')

            for det in det_list:
                prod = det.find('ns:prod', ns)
                imposto = det.find('ns:imposto', ns)
                icms = imposto.find('.//ns:ICMS', ns) if imposto is not None else None
                ipi = imposto.find('.//ns:IPI', ns) if imposto is not None else None

                # Valores
                valores = total.find('ns:ICMSTot', ns) if total is not None else None

                dados = [
                    chave,
                    ide.findtext('ns:cUF', '', ns),
                    ide.findtext('ns:cNF', '', ns),
                    ide.findtext('ns:natOp', '', ns),
                    ide.findtext('ns:mod', '', ns),
                    ide.findtext('ns:serie', '', ns),
                    ide.findtext('ns:nNF', '', ns),
                    ide.findtext('ns:dhEmi', '', ns),
                    ide.findtext('ns:dhSaiEnt', '', ns),
                    ide.findtext('ns:tpNF', '', ns),
                    emit.findtext('ns:CNPJ', '', ns),
                    emit.findtext('ns:xNome', '', ns),
                    emit.findtext('ns:enderEmit/ns:xMun', '', ns),
                    emit.findtext('ns:enderEmit/ns:UF', '', ns),
                    dest.findtext('ns:CNPJ', '', ns) if dest is not None else '',
                    dest.findtext('ns:xNome', '', ns) if dest is not None else '',
                    prod.findtext('ns:cProd', '', ns),
                    prod.findtext('ns:xProd', '', ns),
                    prod.findtext('ns:CFOP', '', ns),
                    prod.findtext('ns:qCom', '0', ns),
                    prod.findtext('ns:vUnCom', '0', ns),
                    prod.findtext('ns:vProd', '0', ns),
                    infAdic.findtext('ns:infCpl', '', ns) if infAdic is not None else None
                ]

                # Conversão de datas
                try:
                    dados[7] = datetime.fromisoformat(dados[7].replace('Z', '+00:00')) if dados[7] else None
                    dados[8] = datetime.fromisoformat(dados[8].replace('Z', '+00:00')) if dados[8] else None
                except Exception as e:
                    dados[7] = dados[8] = None

                cursor.execute("""
                    INSERT INTO FTECH_XML (
                        chave_nfe, cUF, cNF, natOp, mod, serie, nNF, dhEmi, dhSaiEnt, tpNF,
                        emitente_cnpj, emitente_nome, emitente_municipio, emitente_uf,
                        destinatario_cnpj, destinatario_nome,
                        prod_codigo, prod_nome, prod_cfop, prod_quantidade,
                        prod_valor_unitario, prod_valor_total, infCpl
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, dados)

            conn.commit()
            salvar_arquivo_processado(nome_arquivo)
            print(f"Importado com sucesso: {nome_arquivo}")

        except Exception as e:
            print(f"Erro no arquivo {nome_arquivo}: {e}")

    conn.close()
    ultima_execucao = datetime.now()
    atualizar_labels()

# Interface Gráfica
root = tk.Tk()
root.title("Importador de XML para SQL Server")

ultima_label = tk.Label(root, text="Última importação: Nunca")
ultima_label.pack(pady=5)

proxima_execucao_label = tk.Label(root, text="Próxima importação: -")
proxima_execucao_label.pack(pady=5)

def atualizar_labels():
    if ultima_execucao:
        ultima_label.config(text=f"Última importação: {ultima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")
        proxima = ultima_execucao + timedelta(minutes=15)
        proxima_execucao_label.config(text=f"Próxima importação: {proxima.strftime('%d/%m/%Y %H:%M:%S')}")

def agendar_importacao():
    importar_xmls()
    root.after(15 * 60 * 1000, agendar_importacao)  # 15 minutos

btn_importar = tk.Button(root, text="Importar Agora", command=importar_xmls)
btn_importar.pack(pady=10)

btn_fechar = tk.Button(root, text="Fechar", command=root.destroy)
btn_fechar.pack(pady=10)

# Inicializar agendamento
root.after(1000, agendar_importacao)
root.mainloop()
