import os
import tkinter as tk
from tkinter import ttk, messagebox
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

# Arquivo de controle de processados
ARQUIVO_PROCESSADOS = "arquivos_processados.txt"

# Data de corte para dhEmi
data_corte = datetime(2025, 4, 1)

# Namespace
NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

ultima_execucao = None
proxima_execucao = None

# Interface
tk_root = tk.Tk()
tk_root.title("Importador de XML - Alta Paulista")
tk_root.geometry("500x250")

status_label = ttk.Label(tk_root, text="Status: Aguardando...")
status_label.pack(pady=5)

ultima_label = ttk.Label(tk_root, text="Última importação: --")
ultima_label.pack(pady=5)

proxima_label = ttk.Label(tk_root, text="Próxima importação: --")
proxima_label.pack(pady=5)

progress = ttk.Progressbar(tk_root, mode="indeterminate")
progress.pack(pady=10, fill=tk.X, padx=20)

def registrar_log(mensagem):
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO LOG_IMPORT_ALTA_PAULISTA (data_hora, mensagem) VALUES (?, ?)", datetime.now(), mensagem)
            conn.commit()
    except Exception as e:
        print("Erro ao registrar log:", e)

def carregar_arquivos_processados():
    if not os.path.exists(ARQUIVO_PROCESSADOS):
        return set()
    with open(ARQUIVO_PROCESSADOS, 'r', encoding='utf-8') as f:
        return set(linha.strip() for linha in f.readlines())

def salvar_arquivo_processado(nome_arquivo):
    with open(ARQUIVO_PROCESSADOS, 'a', encoding='utf-8') as f:
        f.write(nome_arquivo + '\n')

def limpar_arquivos_processados():
    if os.path.exists(ARQUIVO_PROCESSADOS):
        with open(ARQUIVO_PROCESSADOS, 'w', encoding='utf-8') as f:
            f.truncate(0)
        messagebox.showinfo("Limpeza concluída", "Lista de arquivos processados foi limpa.")
        registrar_log("Lista de arquivos processados limpa manualmente.")

def inserir_nf_cancelada(cursor, chave_nfe, campos_ide, dhEmi, dhSaiEnt,
                         emit_cnpj, emit_nome, emit_mun, emit_uf,
                         dest_cnpj, dest_nome, infNFe, infCpl, arquivo):
    for det in infNFe.findall('nfe:det', NS):
        prod = det.find('nfe:prod', NS)
        if prod is None:
            continue

        cProd = prod.findtext('nfe:cProd', default='', namespaces=NS).strip()
        xProd = prod.findtext('nfe:xProd', default='', namespaces=NS).strip()

        cursor.execute('''
            SELECT 1 FROM FTECH_XML_CANCELADAS
            WHERE chave_nfe = ? AND prod_codigo = ? AND prod_nome = ?
        ''', (chave_nfe, cProd, xProd))
        if cursor.fetchone():
            continue

        try:
            cursor.execute('''
                INSERT INTO FTECH_XML_CANCELADAS (
                    chave_nfe, cUF, cNF, natOp, mod, serie, nNF, dhEmi, dhSaiEnt, tpNF,
                    emitente_cnpj, emitente_nome, emitente_municipio, emitente_uf,
                    destinatario_cnpj, destinatario_nome,
                    prod_codigo, prod_nome, prod_cfop, prod_quantidade, prod_valor_unitario, prod_valor_total, infCpl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chave_nfe, campos_ide['cUF'], campos_ide['cNF'], campos_ide['natOp'], campos_ide['mod'],
                campos_ide['serie'], campos_ide['nNF'], dhEmi, dhSaiEnt, campos_ide['tpNF'],
                emit_cnpj, emit_nome, emit_mun, emit_uf, dest_cnpj, dest_nome,
                cProd, xProd,
                prod.findtext('nfe:CFOP', default='', namespaces=NS),
                float(prod.findtext('nfe:qCom', default='0', namespaces=NS)),
                float(prod.findtext('nfe:vUnCom', default='0', namespaces=NS)),
                float(prod.findtext('nfe:vProd', default='0', namespaces=NS)),
                infCpl
            ))
        except Exception as e:
            registrar_log(f"Erro ao inserir NF cancelada {arquivo} produto {cProd}: {str(e)}")

def processar_xmls():
    global ultima_execucao, proxima_execucao

    progress.start()
    status_label.config(text="Status: Importando...")

    try:
        arquivos_processados = carregar_arquivos_processados()
        arquivos = [f for f in os.listdir(CAMINHO_XML) if f.lower().endswith(".xml") and f not in arquivos_processados]

        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()

            for arquivo in arquivos:
                caminho = os.path.join(CAMINHO_XML, arquivo)

                try:
                    tree = ET.parse(caminho)
                    root_xml = tree.getroot()
                except ET.ParseError as parse_err:
                    registrar_log(f"Erro ao processar arquivo {arquivo}: XML malformado ({parse_err})")
                    salvar_arquivo_processado(arquivo)
                    continue

                infNFe = root_xml.find('.//nfe:infNFe', NS)
                if infNFe is None:
                    registrar_log(f"Ignorado arquivo {arquivo}: Elemento infNFe não encontrado.")
                    salvar_arquivo_processado(arquivo)
                    continue

                ide = infNFe.find('nfe:ide', NS)
                dhEmi_text = ide.findtext('nfe:dhEmi', default='', namespaces=NS)
                if not dhEmi_text:
                    registrar_log(f"Ignorado arquivo {arquivo}: dhEmi ausente.")
                    salvar_arquivo_processado(arquivo)
                    continue

                try:
                    dhEmi = datetime.fromisoformat(dhEmi_text[:19])
                except ValueError:
                    registrar_log(f"Ignorado arquivo {arquivo}: dhEmi inválido.")
                    salvar_arquivo_processado(arquivo)
                    continue

                if dhEmi < data_corte:
                    registrar_log(f"Ignorado arquivo {arquivo}: NF anterior a 01/04/2025.")
                    salvar_arquivo_processado(arquivo)
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
                    salvar_arquivo_processado(arquivo)
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

                nfe_cancelada = False
                procEvento = root_xml.find('.//nfe:procEvento', NS)
                if procEvento is not None:
                    for evento in procEvento.findall('.//nfe:infEvento', NS):
                        if evento.findtext('nfe:tpEvento', default='', namespaces=NS) == '110111':
                            nfe_cancelada = True

                cStat = root_xml.findtext('.//nfe:cStat', default='', namespaces=NS)
                if cStat == '101':
                    nfe_cancelada = True

                if nfe_cancelada:
                    inserir_nf_cancelada(cursor, chave_nfe, campos_ide, dhEmi, dhSaiEnt,
                                         emit_cnpj, emit_nome, emit_mun, emit_uf,
                                         dest_cnpj, dest_nome, infNFe, infCpl, arquivo)
                    conn.commit()
                    registrar_log(f"NF cancelada importada: {arquivo}")
                    salvar_arquivo_processado(arquivo)
                    continue

                for det in infNFe.findall('nfe:det', NS):
                    prod = det.find('nfe:prod', NS)
                    if prod is None:
                        continue

                    cProd = prod.findtext('nfe:cProd', default='', namespaces=NS).strip()
                    xProd = prod.findtext('nfe:xProd', default='', namespaces=NS).strip()

                    cursor.execute('''
                        SELECT 1 FROM FTECH_XML
                        WHERE chave_nfe = ? AND prod_codigo = ? AND prod_nome = ?
                    ''', (chave_nfe, cProd, xProd))
                    if cursor.fetchone():
                        continue

                    try:
                        cursor.execute('''
                            INSERT INTO FTECH_XML (
                                chave_nfe, cUF, cNF, natOp, mod, serie, nNF, dhEmi, dhSaiEnt, tpNF,
                                emitente_cnpj, emitente_nome, emitente_municipio, emitente_uf,
                                destinatario_cnpj, destinatario_nome,
                                prod_codigo, prod_nome, prod_cfop, prod_quantidade, prod_valor_unitario, prod_valor_total, infCpl
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            chave_nfe, campos_ide['cUF'], campos_ide['cNF'], campos_ide['natOp'], campos_ide['mod'],
                            campos_ide['serie'], campos_ide['nNF'], dhEmi, dhSaiEnt, campos_ide['tpNF'],
                            emit_cnpj, emit_nome, emit_mun, emit_uf, dest_cnpj, dest_nome,
                            cProd, xProd,
                            prod.findtext('nfe:CFOP', default='', namespaces=NS),
                            float(prod.findtext('nfe:qCom', default='0', namespaces=NS)),
                            float(prod.findtext('nfe:vUnCom', default='0', namespaces=NS)),
                            float(prod.findtext('nfe:vProd', default='0', namespaces=NS)),
                            infCpl
                        ))
                    except Exception as e:
                        registrar_log(f"Erro ao inserir produto {cProd} - {xProd} do arquivo {arquivo}: {str(e)}")

                conn.commit()
                registrar_log(f"Importado com sucesso: {arquivo}")
                salvar_arquivo_processado(arquivo)

    except Exception as e:
        registrar_log(f"Erro geral na importação: {str(e)}")

    progress.stop()
    ultima_execucao = datetime.now()
    proxima_execucao = ultima_execucao + timedelta(minutes=15)
    ultima_label.config(text=f"Última importação: {ultima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")
    proxima_label.config(text=f"Próxima importação: {proxima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")
    status_label.config(text="Status: Aguardando...")
    tk_root.after(900000, iniciar_importacao)

def iniciar_importacao():
    threading.Thread(target=processar_xmls, daemon=True).start()

def sair():
    tk_root.destroy()

btn_importar = ttk.Button(tk_root, text="Importar Agora", command=iniciar_importacao)
btn_importar.pack(pady=5)

btn_limpar = ttk.Button(tk_root, text="Limpar Lista de Processados", command=limpar_arquivos_processados)
btn_limpar.pack(pady=5)

btn_sair = ttk.Button(tk_root, text="Sair", command=sair)
btn_sair.pack(pady=5)

iniciar_importacao()
tk_root.mainloop()
