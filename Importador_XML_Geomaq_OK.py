import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import pyodbc
import threading

# Configurações do banco
conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=187.17.206.167;"
    "Database=FTECH;"
    "UID=ftech;"
    "PWD=ftech@1975;"
)

# CNPJs autorizados
CNPJS_AUTORIZADOS = {
    '14100563000166', '14100563000247', '14100563000328',
    '14100563000409', '14100563000590', '14100563000670',
    '14100563000751', '14100563000832', '14100563000913'
}

# Diretório dos XMLs
CAMINHO_XML = r"\\SERVER\XML"

# Data de corte para dhEmi
data_corte = datetime(2025, 4, 1)

# Namespace
NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

ultima_execucao = None
proxima_execucao = None

# Interface
root = tk.Tk()
root.title("Importador de XML - Geomaq")
root.geometry("500x200")

status_label = ttk.Label(root, text="Status: Aguardando...")
status_label.pack(pady=5)

ultima_label = ttk.Label(root, text="Última importação: --")
ultima_label.pack(pady=5)

proxima_label = ttk.Label(root, text="Próxima importação: --")
proxima_label.pack(pady=5)

progress = ttk.Progressbar(root, mode="indeterminate")
progress.pack(pady=10, fill=tk.X, padx=20)

def registrar_log(mensagem):
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO LOG_IMPORT_GEOMAQ (data_hora, mensagem) VALUES (?, ?)", datetime.now(), mensagem)
            conn.commit()
    except Exception as e:
        print("Erro ao registrar log:", e)

def processar_xmls():
    global ultima_execucao, proxima_execucao

    progress.start()
    status_label.config(text="Status: Importando...")

    try:
        arquivos = [f for f in os.listdir(CAMINHO_XML) if f.lower().endswith(".xml")]
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()

            for arquivo in arquivos:
                caminho = os.path.join(CAMINHO_XML, arquivo)
                try:
                    tree = ET.parse(caminho)
                    root_xml = tree.getroot()
                    infNFe = root_xml.find('.//nfe:infNFe', NS)

                    if infNFe is None:
                        registrar_log(f"Ignorado arquivo {arquivo}: Elemento infNFe não encontrado (provável XML não é NF-e).")
                        continue

                    ide = infNFe.find('nfe:ide', NS)
                    dhEmi_text = ide.findtext('nfe:dhEmi', default='', namespaces=NS)
                    if not dhEmi_text:
                        registrar_log(f"Ignorado arquivo {arquivo}: dhEmi ausente.")
                        continue

                    try:
                        dhEmi = datetime.fromisoformat(dhEmi_text[:19])
                    except ValueError:
                        registrar_log(f"Ignorado arquivo {arquivo}: dhEmi inválido.")
                        continue

                    if dhEmi < data_corte:
                        registrar_log(f"Ignorado arquivo {arquivo}: NF anterior a 01/04/2025.")
                        continue

                    dhSaiEnt_text = ide.findtext('nfe:dhSaiEnt', default='', namespaces=NS)
                    try:
                        dhSaiEnt = datetime.fromisoformat(dhSaiEnt_text[:19]) if dhSaiEnt_text else None
                    except:
                        dhSaiEnt = None

                    emit = infNFe.find('nfe:emit', NS)
                    emit_cnpj = emit.findtext('nfe:CNPJ', default='', namespaces=NS)
                    emit_nome = emit.findtext('nfe:xNome', default='', namespaces=NS)
                    emit_mun = emit.findtext('nfe:xMun', default='', namespaces=NS)
                    emit_uf = emit.findtext('nfe:UF', default='', namespaces=NS)

                    dest = infNFe.find('nfe:dest', NS)
                    dest_cnpj = dest.findtext('nfe:CNPJ', default='', namespaces=NS)
                    dest_nome = dest.findtext('nfe:xNome', default='', namespaces=NS)

                    if emit_cnpj not in CNPJS_AUTORIZADOS and dest_cnpj not in CNPJS_AUTORIZADOS:
                        registrar_log(f"Ignorado arquivo {arquivo}: CNPJ não autorizado.")
                        continue

                    chave_nfe = infNFe.attrib.get('Id', '').replace('NFe', '')
                    campos_ide = {
                        'cUF': ide.findtext('nfe:cUF', default='', namespaces=NS),
                        'cNF': ide.findtext('nfe:cNF', default='', namespaces=NS),
                        'natOp': ide.findtext('nfe:natOp', default='', namespaces=NS),
                        'mod': ide.findtext('nfe:mod', default='', namespaces=NS),
                        'serie': ide.findtext('nfe:serie', default='', namespaces=NS),
                        'nNF': ide.findtext('nfe:nNF', default='', namespaces=NS),
                        'tpNF': ide.findtext('nfe:tpNF', default='', namespaces=NS)
                    }

                    infCpl = infNFe.findtext('.//nfe:infAdic/nfe:infCpl', default='', namespaces=NS)

                    for det in infNFe.findall('nfe:det', NS):
                        prod = det.find('nfe:prod', NS)
                        cursor.execute('''
                            INSERT INTO FTECH_XML (
                                chave_nfe, cUF, cNF, natOp, mod, serie, nNF, dhEmi, dhSaiEnt, tpNF,
                                emitente_cnpj, emitente_nome, emitente_municipio, emitente_uf,
                                destinatario_cnpj, destinatario_nome,
                                prod_codigo, prod_nome, prod_cfop, prod_quantidade, prod_valor_unitario, prod_valor_total, infCpl
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            chave_nfe,
                            campos_ide['cUF'], campos_ide['cNF'], campos_ide['natOp'], campos_ide['mod'], campos_ide['serie'], campos_ide['nNF'],
                            dhEmi, dhSaiEnt, campos_ide['tpNF'],
                            emit_cnpj, emit_nome, emit_mun, emit_uf,
                            dest_cnpj, dest_nome,
                            prod.findtext('nfe:cProd', default='', namespaces=NS),
                            prod.findtext('nfe:xProd', default='', namespaces=NS),
                            prod.findtext('nfe:CFOP', default='', namespaces=NS),
                            float(prod.findtext('nfe:qCom', default='0', namespaces=NS)),
                            float(prod.findtext('nfe:vUnCom', default='0', namespaces=NS)),
                            float(prod.findtext('nfe:vProd', default='0', namespaces=NS)),
                            infCpl
                        ))
                    conn.commit()
                    registrar_log(f"Importado com sucesso: {arquivo}")

                except Exception as e:
                    registrar_log(f"Erro ao inserir dados do arquivo {arquivo}: {str(e)}")

    except Exception as e:
        registrar_log(f"Erro geral na importação: {str(e)}")

    progress.stop()
    ultima_execucao = datetime.now()
    proxima_execucao = ultima_execucao + timedelta(minutes=15)
    ultima_label.config(text=f"Última importação: {ultima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")
    proxima_label.config(text=f"Próxima importação: {proxima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")
    status_label.config(text="Status: Aguardando...")
    root.after(900000, iniciar_importacao)  # 15 minutos

def iniciar_importacao():
    threading.Thread(target=processar_xmls, daemon=True).start()

def sair():
    root.destroy()

btn_importar = ttk.Button(root, text="Importar Agora", command=iniciar_importacao)
btn_importar.pack(pady=5)

btn_sair = ttk.Button(root, text="Sair", command=sair)
btn_sair.pack(pady=5)

# Começa a primeira importação ao iniciar
iniciar_importacao()

root.mainloop()

