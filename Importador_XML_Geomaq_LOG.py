import os
import xml.etree.ElementTree as ET
import pyodbc
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from datetime import datetime, timedelta
import threading

# Configurações do banco de dados
DB_CONFIG = {
    'server': '187.17.206.167',
    'database': 'FTECH',
    'username': 'protheus',
    'password': 'Protheus12133'
}

# CNPJs permitidos
CNPJS_PERMITIDOS = {
    "14100563000166", "14100563000247", "14100563000328", "14100563000409",
    "14100563000590", "14100563000670", "14100563000751", "14100563000832", "14100563000913"
}

PASTA_XML = r""
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

def carregar_arquivos_processados():
    if os.path.exists(ARQUIVO_CONTROLE):
        with open(ARQUIVO_CONTROLE, 'r') as f:
            return set(f.read().splitlines())
    return set()

def salvar_arquivo_processado(nome):
    with open(ARQUIVO_CONTROLE, 'a') as f:
        f.write(nome + '\n')

ultima_execucao = None

def importar_xmls():
    global ultima_execucao, proxima_execucao_label
    if not PASTA_XML:
        messagebox.showwarning("Aviso", "Selecione a pasta contendo os arquivos XML.")
        return

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
                log_text.insert(tk.END, f"Ignorado arquivo {nome_arquivo}: Elemento infNFe não encontrado.\n")
                continue

            ide = infNFe.find('ns:ide', ns)
            emit = infNFe.find('ns:emit', ns)
            dest = infNFe.find('ns:dest', ns)
            det_list = infNFe.findall('ns:det', ns)
            total = infNFe.find('ns:total', ns)
            infAdic = infNFe.find('ns:infAdic', ns)

            cnpj_emit = emit.findtext('ns:CNPJ', '', ns)
            cnpj_dest = dest.findtext('ns:CNPJ', '', ns) if dest is not None else ''

            if cnpj_emit not in CNPJS_PERMITIDOS and cnpj_dest not in CNPJS_PERMITIDOS:
                log_text.insert(tk.END, f"Ignorado arquivo {nome_arquivo}: CNPJ não autorizado.\n")
                continue

            chave = infNFe.attrib.get('Id', '').replace('NFe', '')

            for det in det_list:
                prod = det.find('ns:prod', ns)
                imposto = det.find('ns:imposto', ns)
                icms = imposto.find('.//ns:ICMS', ns) if imposto is not None else None
                ipi = imposto.find('.//ns:IPI', ns) if imposto is not None else None

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
                    cnpj_emit,
                    emit.findtext('ns:xNome', '', ns),
                    emit.findtext('ns:enderEmit/ns:xMun', '', ns),
                    emit.findtext('ns:enderEmit/ns:UF', '', ns),
                    cnpj_dest,
                    dest.findtext('ns:xNome', '', ns) if dest is not None else '',
                    prod.findtext('ns:cProd', '', ns),
                    prod.findtext('ns:xProd', '', ns),
                    prod.findtext('ns:CFOP', '', ns),
                    prod.findtext('ns:qCom', '0', ns),
                    prod.findtext('ns:vUnCom', '0', ns),
                    prod.findtext('ns:vProd', '0', ns),
                    infAdic.findtext('ns:infCpl', '', ns) if infAdic is not None else None
                ]

                try:
                    dados[7] = datetime.fromisoformat(dados[7].replace('Z', '+00:00')) if dados[7] else None
                    dados[8] = datetime.fromisoformat(dados[8].replace('Z', '+00:00')) if dados[8] else None
                except:
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
            log_text.insert(tk.END, f"Importado com sucesso: {nome_arquivo}\n")

        except Exception as e:
            log_text.insert(tk.END, f"Erro no arquivo {nome_arquivo}: {e}\n")

    conn.close()
    ultima_execucao = datetime.now()
    atualizar_labels()

def selecionar_pasta():
    global PASTA_XML
    pasta = filedialog.askdirectory()
    if pasta:
        PASTA_XML = pasta
        log_text.insert(tk.END, f"Pasta selecionada: {PASTA_XML}\n")

root = tk.Tk()
root.title("Importador de XML para SQL Server")

ultima_label = tk.Label(root, text="Última importação: Nunca")
ultima_label.pack(pady=5)

proxima_execucao_label = tk.Label(root, text="Próxima importação: -")
proxima_execucao_label.pack(pady=5)

btn_selecionar_pasta = tk.Button(root, text="Selecionar Pasta de XML", command=selecionar_pasta)
btn_selecionar_pasta.pack(pady=5)

def atualizar_labels():
    if ultima_execucao:
        ultima_label.config(text=f"Última importação: {ultima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")
        proxima = ultima_execucao + timedelta(minutes=15)
        proxima_execucao_label.config(text=f"Próxima importação: {proxima.strftime('%d/%m/%Y %H:%M:%S')}")

def agendar_importacao():
    importar_xmls()
    root.after(15 * 60 * 1000, agendar_importacao)

btn_importar = tk.Button(root, text="Importar Agora", command=importar_xmls)
btn_importar.pack(pady=10)

btn_fechar = tk.Button(root, text="Fechar", command=root.destroy)
btn_fechar.pack(pady=10)

log_text = scrolledtext.ScrolledText(root, width=100, height=20)
log_text.pack(padx=10, pady=10)

root.after(1000, agendar_importacao)
root.mainloop()