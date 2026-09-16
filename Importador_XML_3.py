import os
import threading
import time
from datetime import datetime, timedelta
import tkinter as tk
import xml.etree.ElementTree as ET
import pyodbc

# Configurações
PASTA_XML = r'\\SERVER\XML'
ARQUIVO_PROCESSADOS = 'arquivos_processados.txt'
INTERVALO_MINUTOS = 15

# Configura conexão SQL Server
SERVER = '187.17.206.167,1433'
DATABASE = 'FTECH'
USERNAME = 'ftech'
PASSWORD = 'ftech@1975'

def to_float(valor):
    try:
        return float(valor)
    except:
        return 0

def importar_xmls(status_label, proxima_label):
    try:
        with open(ARQUIVO_PROCESSADOS, 'r') as f:
            processados = set(line.strip() for line in f)
    except FileNotFoundError:
        processados = set()

    arquivos = [f for f in os.listdir(PASTA_XML) if f.lower().endswith('.xml')]
    novos = []

    for nome_arquivo in arquivos:
        if nome_arquivo in processados:
            continue

        caminho = os.path.join(PASTA_XML, nome_arquivo)
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()

            # Detectar namespace, se existir
            ns = {}
            if root.tag.startswith('{'):
                uri = root.tag[root.tag.find("{")+1:root.tag.find("}")]
                ns = {'ns': uri}

            # Buscar o elemento infNFe com ou sem namespace
            if ns:
                nfe = root.find('.//ns:infNFe', ns)
            else:
                nfe = root.find('.//infNFe')

            if nfe is None:
                print(f"Ignorado arquivo {nome_arquivo}: Elemento infNFe não encontrado (provável XML não é NF-e).")
                continue

            def get_text(node, tag):
                if ns:
                    el = node.find(f'ns:{tag}', ns)
                else:
                    el = node.find(tag)
                return el.text if el is not None else ''

            chave_nfe = nfe.attrib.get('Id', '').replace('NFe', '')

            dados_comuns = {
                'chave_nfe': chave_nfe,
                'cUF': get_text(nfe, 'ide/cUF'),
                'cNF': get_text(nfe, 'ide/cNF'),
                'natOp': get_text(nfe, 'ide/natOp'),
                'mod': get_text(nfe, 'ide/mod'),
                'serie': get_text(nfe, 'ide/serie'),
                'nNF': get_text(nfe, 'ide/nNF'),
                'dhEmi': get_text(nfe, 'ide/dhEmi'),
                'dhSaiEnt': get_text(nfe, 'ide/dhSaiEnt'),
                'tpNF': get_text(nfe, 'ide/tpNF'),
                'idDest': get_text(nfe, 'ide/idDest'),
                'cMunFG': get_text(nfe, 'ide/cMunFG'),
                'tpImp': get_text(nfe, 'ide/tpImp'),
                'tpEmis': get_text(nfe, 'ide/tpEmis'),
                'cDV': get_text(nfe, 'ide/cDV'),
                'tpAmb': get_text(nfe, 'ide/tpAmb'),
                'finNFe': get_text(nfe, 'ide/finNFe'),
                'indFinal': get_text(nfe, 'ide/indFinal'),
                'indPres': get_text(nfe, 'ide/indPres'),
                'procEmi': get_text(nfe, 'ide/procEmi'),
                'verProc': get_text(nfe, 'ide/verProc'),
            }

            emit = nfe.find('ns:emit' if ns else 'emit', ns if ns else None)
            if emit is not None:
                dados_comuns.update({
                    'emitente_cnpj': get_text(emit, 'CNPJ'),
                    'emitente_nome': get_text(emit, 'xNome'),
                    'emitente_fantasia': get_text(emit, 'xFant'),
                    'emitente_endereco': get_text(emit, 'enderEmit/xLgr'),
                    'emitente_numero': get_text(emit, 'enderEmit/nro'),
                    'emitente_complemento': get_text(emit, 'enderEmit/xCpl'),
                    'emitente_bairro': get_text(emit, 'enderEmit/xBairro'),
                    'emitente_municipio': get_text(emit, 'enderEmit/xMun'),
                    'emitente_uf': get_text(emit, 'enderEmit/UF'),
                    'emitente_cep': get_text(emit, 'enderEmit/CEP'),
                    'emitente_pais': get_text(emit, 'enderEmit/xPais'),
                    'emitente_telefone': get_text(emit, 'enderEmit/fone'),
                    'emitente_ie': get_text(emit, 'IE'),
                    'emitente_crt': get_text(emit, 'CRT'),
                })
            else:
                for chave in ['emitente_cnpj','emitente_nome','emitente_fantasia','emitente_endereco','emitente_numero',
                              'emitente_complemento','emitente_bairro','emitente_municipio','emitente_uf','emitente_cep',
                              'emitente_pais','emitente_telefone','emitente_ie','emitente_crt']:
                    dados_comuns[chave] = ''

            dest = nfe.find('ns:dest' if ns else 'dest', ns if ns else None)
            if dest is not None:
                dados_comuns.update({
                    'destinatario_cnpj': get_text(dest, 'CNPJ'),
                    'destinatario_nome': get_text(dest, 'xNome'),
                    'destinatario_endereco': get_text(dest, 'enderDest/xLgr'),
                    'destinatario_numero': get_text(dest, 'enderDest/nro'),
                    'destinatario_bairro': get_text(dest, 'enderDest/xBairro'),
                    'destinatario_municipio': get_text(dest, 'enderDest/xMun'),
                    'destinatario_uf': get_text(dest, 'enderDest/UF'),
                    'destinatario_cep': get_text(dest, 'enderDest/CEP'),
                    'destinatario_pais': get_text(dest, 'enderDest/xPais'),
                    'destinatario_telefone': get_text(dest, 'enderDest/fone'),
                    'destinatario_ie': get_text(dest, 'IE'),
                    'destinatario_email': get_text(dest, 'email'),
                })
            else:
                for chave in ['destinatario_cnpj','destinatario_nome','destinatario_endereco','destinatario_numero',
                              'destinatario_bairro','destinatario_municipio','destinatario_uf','destinatario_cep',
                              'destinatario_pais','destinatario_telefone','destinatario_ie','destinatario_email']:
                    dados_comuns[chave] = ''

            total = nfe.find('ns:total/ns:ICMSTot' if ns else 'total/ICMSTot', ns if ns else None)
            if total is not None:
                dados_comuns.update({
                    'valor_frete': to_float(get_text(total, 'vFrete')),
                    'valor_seguro': to_float(get_text(total, 'vSeg')),
                    'valor_desconto': to_float(get_text(total, 'vDesc')),
                    'valor_despesas': to_float(get_text(total, 'vOutro')),
                    'valor_importacao': 0,
                    'valor_outros': 0,
                    'valor_icms': to_float(get_text(total, 'vICMS')),
                    'valor_nota': to_float(get_text(total, 'vNF')),
                })
            else:
                for chave in ['valor_frete','valor_seguro','valor_desconto','valor_despesas','valor_importacao',
                              'valor_outros','valor_icms','valor_nota']:
                    dados_comuns[chave] = 0

            conn = pyodbc.connect(
                f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}'
            )
            cursor = conn.cursor()

            dets = nfe.findall('ns:det' if ns else 'det', ns if ns else None)
            if not dets:
                print(f"Aviso: arquivo {nome_arquivo} não possui produtos (det). Ignorando.")
                continue

            for det in dets:
                prod = det.find('ns:prod' if ns else 'prod', ns if ns else None)
                imposto = det.find('ns:imposto' if ns else 'imposto', ns if ns else None)
                icms = None
                ipi = None
                if imposto is not None:
                    icms = imposto.find('ns:ICMS' if ns else 'ICMS', ns if ns else None)
                    ipi = imposto.find('ns:IPI' if ns else 'IPI', ns if ns else None)

                dados_produto = {
                    'prod_codigo': get_text(prod, 'cProd') if prod is not None else '',
                    'prod_ean': get_text(prod, 'cEAN') if prod is not None else '',
                    'prod_nome': get_text(prod, 'xProd') if prod is not None else '',
                    'prod_ncm': get_text(prod, 'NCM') if prod is not None else '',
                    'prod_cest': get_text(prod, 'CEST') if prod is not None else '',
                    'prod_cfop': get_text(prod, 'CFOP') if prod is not None else '',
                    'prod_unidade': get_text(prod, 'uCom') if prod is not None else '',
                    'prod_quantidade': to_float(get_text(prod, 'qCom')) if prod is not None else 0,
                    'prod_valor_unitario': to_float(get_text(prod, 'vUnCom')) if prod is not None else 0,
                    'prod_valor_total': to_float(get_text(prod, 'vProd')) if prod is not None else 0,
                }

                dados_imposto = {
                    'imposto_icms_cst': '',
                    'imposto_icms_vbc': 0,
                    'imposto_icms_vicms': 0,
                    'imposto_ipi_cst': '',
                    'imposto_ipi_vbc': 0,
                    'imposto_ipi_pipi': 0,
                    'imposto_ipi_vipi': 0,
                }

                if icms is not None:
                    # Como o ICMS pode ter subelementos como ICMS00, ICMS20, etc, pegamos o primeiro
                    icms_sub = list(icms)[0] if len(icms) > 0 else None
                    if icms_sub is not None:
                        dados_imposto['imposto_icms_cst'] = get_text(icms_sub, 'CST')
                        dados_imposto['imposto_icms_vbc'] = to_float(get_text(icms_sub, 'vBC'))
                        dados_imposto['imposto_icms_vicms'] = to_float(get_text(icms_sub, 'vICMS'))

                if ipi is not None:
                    ipi_sub = list(ipi)[0] if len(ipi) > 0 else None
                    if ipi_sub is not None:
                        dados_imposto['imposto_ipi_cst'] = get_text(ipi_sub, 'CST')
                        dados_imposto['imposto_ipi_vbc'] = to_float(get_text(ipi_sub, 'vBC'))
                        dados_imposto['imposto_ipi_pipi'] = to_float(get_text(ipi_sub, 'pIPI'))
                        dados_imposto['imposto_ipi_vipi'] = to_float(get_text(ipi_sub, 'vIPI'))

                infCpl = ''
                # Inf adcional complementar - opcional
                infAdic = nfe.find('ns:infAdic' if ns else 'infAdic', ns if ns else None)
                if infAdic is not None:
                    infCpl = get_text(infAdic, 'infCpl')

                # Junta todos dados para inserir
                dados = {**dados_comuns, **dados_produto, **dados_imposto, 'infCpl': infCpl}

                # Monta SQL INSERT
                colunas = ','.join(dados.keys())
                valores = ','.join('?' for _ in dados)
                sql = f"INSERT INTO FTECH_XML ({colunas}) VALUES ({valores})"
                cursor.execute(sql, tuple(dados.values()))

            conn.commit()
            cursor.close()
            conn.close()

            # Marca arquivo como processado
            with open(ARQUIVO_PROCESSADOS, 'a') as f:
                f.write(nome_arquivo + '\n')

            print(f"Importado arquivo {nome_arquivo} com sucesso.")
            novos.append(nome_arquivo)

        except Exception as e:
            print(f"Erro no arquivo {nome_arquivo}: {e}")

    if novos:
        status_label.config(text=f'Última importação: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
    else:
        status_label.config(text='Nenhum arquivo novo para importar.')

    proxima_importacao = datetime.now() + timedelta(minutes=INTERVALO_MINUTOS)
    proxima_label.config(text=f'Próxima importação: {proxima_importacao.strftime("%d/%m/%Y %H:%M:%S")}')

def iniciar_importacao(status_label, proxima_label, botao_importar):
    botao_importar.config(state='disabled')
    threading.Thread(target=importar_xmls, args=(status_label, proxima_label), daemon=True).start()
    # Reabilitar botão após 1 minuto para evitar múltiplos cliques
    status_label.after(60000, lambda: botao_importar.config(state='normal'))

def atualizar_automatico(status_label, proxima_label, botao_importar):
    iniciar_importacao(status_label, proxima_label, botao_importar)
    status_label.after(INTERVALO_MINUTOS * 60 * 1000, lambda: atualizar_automatico(status_label, proxima_label, botao_importar))

def criar_janela():
    root = tk.Tk()
    root.title('Importação XML para SQL Server')

    lbl_status = tk.Label(root, text='Última importação: Nunca')
    lbl_status.pack(pady=5)

    lbl_proxima = tk.Label(root, text='Próxima importação: ---')
    lbl_proxima.pack(pady=5)

    btn_importar = tk.Button(root, text='Importar XMLs Agora', command=lambda: iniciar_importacao(lbl_status, lbl_proxima, btn_importar))
    btn_importar.pack(pady=10)

    btn_sair = tk.Button(root, text='Fechar', command=root.destroy)
    btn_sair.pack(pady=10)

    atualizar_automatico(lbl_status, lbl_proxima, btn_importar)

    root.mainloop()

if __name__ == '__main__':
    criar_janela()
