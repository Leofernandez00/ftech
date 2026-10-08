# -*- coding: utf-8 -*-
"""Importação contínua TOTVS -> SQL Server FTECH. Python 3.10+ / pip install pyodbc.
Configurar FTECH_SQL_SERVER, FTECH_SQL_USER, FTECH_SQL_PASSWORD (ou login integrado).
Importação por substituição: quando a planilha muda, apaga os dados da tabela de destino e grava novamente a partir do Excel.
"""
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import time
import uuid
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import zipfile
from xml.etree import ElementTree as ET

try:
    import pyodbc
except ImportError as exc:
    raise SystemExit('Instale a dependencia: pip install pyodbc') from exc

# IMPORTANTE: altere o nome do servidor se o compartilhamento usar outro hostname.
PASTAS = {
    'clientes': r'\\server\BASE_TOTVS_FTECH\CLIENTES\mata030.xlsx',
    'fornecedores': r'\\server\BASE_TOTVS_FTECH\FORNECEDORES\mata020.xlsx',
    'produtos': r'\\server\BASE_TOTVS_FTECH\PRODUTOS\mata010.xlsx',
}
INTERVALO_SEGUNDOS = 120
ESTABILIZACAO_SEGUNDOS = 5
LOTE = 1000
# Versão lógica da carga. Alterar este valor força UMA substituição completa das tabelas
# e, após sucesso, as próximas execuções só recarregam quando o Excel mudar.
VERSAO_CARGA = 'SUBSTITUICAO_TOTAL_V3'
# ============================================================
# CREDENCIAIS DO SQL SERVER - PREENCHA ANTES DE GERAR O .EXE
# ============================================================
SQL_SERVER = r'188.220.168.222'
SQL_DATABASE = 'FTECH'
SQL_USER = r'ftech'
SQL_PASSWORD = r'ftech@1975'
ODBC_DRIVER = 'ODBC Driver 17 for SQL Server'
TRUST_CERT = 'yes'
# ============================================================
EXECUTOR = os.getenv('COMPUTERNAME', 'IMPORTADOR_TOTVS')[:100]
DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
LOG_DIR = DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
_handlers = [RotatingFileHandler(LOG_DIR / 'importador_totvs.log', maxBytes=8_000_000,
                                         backupCount=5, encoding='utf-8')]
if sys.stdout is not None:
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    handlers=_handlers)
LOG = logging.getLogger('totvs')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

# A segunda linha do XLSX contém os cabeçalhos. Use mapeamento por POSIÇÃO
# validado contra os cabeçalhos esperados para impedir atualização de colunas erradas.
CLIENTES_CAMPOS = '''Codigo|Loja|CNPJ_CPF|Nome|N_Fantasia|Tipo|Municipio|Regiao|DDI|Ins_Estad|C_Contabil|Grp_Clientes|E_Mail|Cod_Segmento|Descricao|Cod_Abics|Dt_Fim_Vincu|Reg_Paraiba|Usa_DDA|Opt_Simples|Cod_Mun_SIAF|Rg_Simp_MT|P_Carga_Med|End_Not_Form|Contr_TARE|Aliq_Fixa|Destaca_IE|Opt_Simp_Nac|Inc_Cultura|Fil_Transf|URL_Img_uMov|Tipo_Camp|Codigo_1|Inovar_Auto|TPJ|Desc_Membro|Outros_Mun|Cod_Terr|Membro|Nome_Territ|Desc_Camp|Contribuinte|TDA|Recolhe_IRRF'''.split('|')
CLIENTES_CABECALHOS = '''Codigo|Loja|CNPJ/CPF|Nome|N Fantasia|Tipo|Municipio|Regiao|DDI|Ins. Estad.|C. Contabil|Grp.Clientes|E-Mail|Cod.Segmento|Descricao|Cod. Abics|Dt Fim Vincu|Reg.Paraiba|Usa DDA|Opt. Simples|Cod.Mun.SIAF|Rg. Simp. MT|P. Carga Med|End.Not.Form|Contr TARE ?|Aliq. Fixa|Destaca IE|Opt Simp Nac|Inc. Cultura|Fil. Transf.|URL.Img.uMov|Tipo Camp|Codigo|Inovar Auto|TPJ|Desc. Membro|Outros Mun.|Cod. Terr.|Membro|Nome Territ.|Desc. Camp.|Contribuinte|TDA|Recolhe IRRF'''.split('|')
PRODUTOS_CABECALHOS_PRINCIPAIS = {'Codigo': 'CODIGO_TOTVS', 'Unidade': 'UNIDADE', 'Descricao': 'PRODUTO'}

# Colunas da planilha fornecedores, conferidas com a exportação mata020.
FORNECEDORES_CABECALHOS = '''Codigo|Loja|CNPJ/CPF|Razao Social|N Fantasia|Endereco|Contrib.Prev|Bairro|CEP|Caixa Postal|DDI|C Contabil|Vinculacao|E-Mail|Home-Page|OK|Classe Forn.|Tipo AWB|Cod. Abics|P. Vinculo|Cod. Adm.|SUBCON|Rg. Simp. MT|Contr TARE ?|Nome Empres.|Tipo Contrat|M.Juridico|Ins. no Munc|Opt Simp Nac|Assoc. Desp.|Codigo Pais|Codigo NIF|Calc.INSS.Pt|Form. Pgto|TPJ|SitEspRes BH|Inc. Cultura|CPF IR Progr|Logradouro|Numero|Complemento|Benef.Rend.|Rendimento|Forma Trib.|Est./Prov.|Telefone|End.Not.Form|Fome Zero|Fil. Transf.|CNPJ Empr.Ex|Data Inicio|Data Fim|Cidade|Cod.Postal|Num. Apolice|Cargo Resp.|Cod. Cliente|Ded.PIS/COF|Loja Cliente|CPF Rural|SubDivPais'''.split('|')
FORNECEDORES_CAMPOS = '''CODIGO|LOJA|CNPJ_CPF|RAZAO_SOCIAL|N_FANTASIA|ENDERECO|CONTRIB_PREV|BAIRRO|CEP|CAIXA_POSTAL|DDI|C_CONTABIL|VINCULACAO|E_MAIL|HOME_PAGE|OK|CLASSE_FORN|TIPO_AWB|COD_ABICS|P_VINCULO|COD_ADM|SUBCON|RG_SIMP_MT|CONTR_TARE|NOME_EMPRES|TIPO_CONTRAT|M_JURIDICO|INS_NO_MUNC|OPT_SIMP_NAC|ASSOC_DESP|CODIGO_PAIS|CODIGO_NIF|CALC_INSS_PT|FORM_PGTO|TPJ|SITESPRES_BH|INC_CULTURA|CPF_IR_PROGR|LOGRADOURO|NUMERO|COMPLEMENTO|BENEF_REND|RENDIMENTO|FORMA_TRIB|EST_PROV|TELEFONE|END_NOT_FORM|FOME_ZERO|FIL_TRANSF|CNPJ_EMPR_EX|DATA_INICIO|DATA_FIM|CIDADE|COD_POSTAL|NUM_APOLICE|CARGO_RESP|COD_CLIENTE|DED_PIS_COF|LOJA_CLIENTE|CPF_RURAL|SUBDIVPAIS'''.split('|')

CONFIG = {
    'clientes': dict(tabela='CLIENTES_TOTVS', campos=CLIENTES_CAMPOS,
                     cabecalhos=CLIENTES_CABECALHOS, chave=['Codigo', 'Loja'],
                     extras=['DATA_IMPORTACAO', 'USUARIO', 'DATA_HORA']),
    'fornecedores': dict(tabela='FORNECEDORES_TOTVS', campos=FORNECEDORES_CAMPOS,
                         cabecalhos=FORNECEDORES_CABECALHOS, chave=['CODIGO', 'LOJA'],
                         extras=['DATA_IMPORTACAO', 'USUARIO', 'DATA_HORA']),
    'produtos': dict(tabela='PRODUTO_TOTVS', campos=['CODIGO_TOTVS', 'UNIDADE', 'PRODUTO'],
                     cabecalhos=None, chave=['CODIGO_TOTVS'], extras=['USUARIO', 'DATAHORA']),
}


def q(nome):
    # Aceita nomes normais e tabelas temporárias globais (##...).
    if not re.fullmatch(r'(?:##)?[A-Za-z_][A-Za-z0-9_]*', nome):
        raise ValueError(f'Identificador SQL inválido: {nome}')
    return f'[{nome}]'


def texto(v):
    if v is None: return None
    s = str(v).strip()
    return s if s else None


def conexao():
    dsn = (f'DRIVER={{{ODBC_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};'
           f'TrustServerCertificate={TRUST_CERT};Encrypt=yes;Connection Timeout=30;')
    if SQL_USER:
        dsn += f'UID={SQL_USER};PWD={SQL_PASSWORD};'
    else:
        dsn += 'Trusted_Connection=yes;'
    return pyodbc.connect(dsn, autocommit=False, timeout=120)


def hash_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(bloco)
    return h.hexdigest()


def stat(caminho):
    s = os.stat(caminho)
    return (s.st_size, s.st_mtime_ns)


def xlsx_linhas(caminho):
    """Leitura incremental do XML XLSX sem ocupar RAM com todas as linhas.
    Strings compartilhadas são mantidas na memória; permite arquivos grandes.
    """
    with zipfile.ZipFile(caminho) as z:
        compartilhadas = []
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as arq:
                for _, elem in ET.iterparse(arq, events=('end',)):
                    if elem.tag == NS + 'si':
                        compartilhadas.append(''.join(n.text or '' for n in elem.iter(NS + 't')))
                        elem.clear()
        planilhas = sorted((n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n)))
        if not planilhas: raise ValueError('XLSX sem planilha')
        with z.open(planilhas[0]) as arq:
            for _, row in ET.iterparse(arq, events=('end',)):
                if row.tag != NS + 'row': continue
                numeros = []
                for cel in row.findall(NS+'c'):
                    endereco = cel.get('r', '')
                    m = re.match(r'[A-Z]+', endereco)
                    if not m: continue
                    index = 0
                    for letra in m.group(): index = index * 26 + ord(letra) - 64
                    index -= 1
                    no = cel.find(NS + 'v')
                    inline = cel.find(NS + 'is')
                    valor = (no.text or '') if no is not None else None
                    if cel.get('t') == 's' and valor is not None:
                        valor = compartilhadas[int(valor)]
                    elif cel.get('t') == 'inlineStr' and inline is not None:
                        valor = ''.join(t.text or '' for t in inline.iter(NS+'t'))
                    numeros.append((index, valor))
                n = max((i for i, _ in numeros), default=-1) + 1
                cells = [None] * n
                for i, v in numeros: cells[i] = texto(v)
                yield int(row.get('r')), cells
                row.clear()


def planilha_registros(tipo, arquivo):
    config = CONFIG[tipo]
    cabe = None
    indices = None
    for numero, cells in xlsx_linhas(arquivo):
        if numero == 2:
            cabe = cells
            if tipo != 'produtos':
                if [texto(x) for x in cabe] != config['cabecalhos']:
                    raise ValueError(f'Cabeçalhos diferentes na planilha {arquivo}! Confira layout TOTVS.')
                indices = list(range(len(config['campos'])))
            else:
                faltantes = set(PRODUTOS_CABECALHOS_PRINCIPAIS) - set(cabe)
                if faltantes: raise ValueError(f'Faltando colunas de produto: {faltantes}')
                indices = [cabe.index('Codigo'), cabe.index('Unidade'), cabe.index('Descricao')]
            continue
        if numero < 3: continue
        if indices is None: raise ValueError('Segunda linha não contém cabeçalhos.')
        row = tuple(cells[i] if i < len(cells) else None for i in indices)
        if not any(v is not None for v in row): continue
        yield numero, row
    if cabe is None: raise ValueError('XLSX sem segunda linha de cabeçalho')


def checar_estrutura(cursor, cfg):
    tabela = cfg['tabela']
    cursor.execute('''SELECT c.name FROM sys.columns c
        WHERE c.object_id=OBJECT_ID(?)''', f'dbo.{tabela}')
    existentes = {r[0].lower() for r in cursor.fetchall()}
    if not existentes: raise ValueError(f'Tabela dbo.{tabela} não existe. Rode o SQL primeiro.')
    faltam = [c for c in cfg['campos'] + ['ID'] if c.lower() not in existentes]
    if faltam: raise ValueError(f'Colunas ausentes em dbo.{tabela}: {faltam}')
    return [c for c in cfg['extras'] if c.lower() in existentes]


def processar(tipo, forcar=False):
    """Substitui integralmente os dados da tabela pela planilha correspondente.

    A staging é carregada primeiro. Somente depois, DELETE + INSERT são executados
    na mesma transação; em caso de erro, rollback preserva a carga anterior.
    """
    cfg = CONFIG[tipo]
    caminho = PASTAS[tipo]
    if not os.path.isfile(caminho):
        LOG.warning('Arquivo indisponível: %s', caminho)
        return {'status':'Arquivo indisponível','lidas':0,'novas':0,'atualizadas':0,'ignoradas':0}

    inicio = stat(caminho)
    time.sleep(ESTABILIZACAO_SEGUNDOS)
    if stat(caminho) != inicio:
        LOG.info('%s ainda está sendo gerado; aguardando próxima verificação', caminho)
        return {'status':'Arquivo em uso','lidas':0,'novas':0,'atualizadas':0,'ignoradas':0}

    digest = hash_arquivo(caminho)
    if stat(caminho) != inicio:
        LOG.warning('Arquivo modificado durante a leitura: %s', caminho)
        return {'status':'Arquivo alterado','lidas':0,'novas':0,'atualizadas':0,'ignoradas':0}

    # Não gravamos a versão em texto no banco para não depender do tamanho da coluna HASH_SHA256.
    # O hash abaixo continua tendo exatamente 64 caracteres, mas muda quando a lógica de carga muda.
    hash_controle = hashlib.sha256((VERSAO_CARGA + ':' + digest).encode('utf-8')).hexdigest()

    tabela = cfg['tabela']
    with conexao() as conn:
        cr = conn.cursor()
        cr.execute('SELECT HASH_SHA256, DATA_IMPORTACAO, QTDE_LIDAS, QTDE_NOVAS FROM dbo.TOTVS_IMPORTACAO_CONTROLE WHERE TABELA=?', tabela)
        status = cr.fetchone()

        # Confere também a quantidade física da tabela. Assim uma tabela vazia/incompleta
        # nunca será considerada "sem alterações" apenas porque o Excel tem o mesmo hash.
        cr.execute(f'SELECT COUNT(*) FROM dbo.{q(tabela)}')
        qtd_sql_atual = int(cr.fetchone()[0])

        if status and status[0] == hash_controle and not forcar:
            qtd_esperada = int(status[3] or 0)
            if qtd_esperada > 0 and qtd_sql_atual == qtd_esperada:
                ultima = status[1]
                ultima_txt = ultima.strftime('%d/%m/%Y %H:%M:%S') if ultima else 'não registrada'
                LOG.info('%s sem alterações - tabela SQL contém %d registros; última carga completa: %s', tabela, qtd_sql_atual, ultima_txt)
                return {'status':'Sem alterações','lidas':int(status[2] or 0),'novas':qtd_sql_atual,'atualizadas':0,'ignoradas':0}

            LOG.warning('%s: hash é o mesmo, porém a tabela está inconsistente (SQL=%d, esperado=%d). Será feita substituição completa.',
                        tabela, qtd_sql_atual, qtd_esperada)
        elif status and not forcar:
            LOG.info('%s: primeira carga desta versão ou arquivo alterado. Será feita substituição completa.', tabela)

        if forcar:
            LOG.info('%s: importação FORÇADA pelo botão Importar agora', tabela)

        extras = checar_estrutura(cr, cfg)
        stg = '##TOTVS_' + uuid.uuid4().hex[:20]
        fields = cfg['campos']
        key_idx = [fields.index(k) for k in cfg['chave']]

        cr.execute(
            f'CREATE TABLE {q(stg)} (' +
            ','.join(f'{q(c)} NVARCHAR(MAX) COLLATE DATABASE_DEFAULT NULL' for c in fields) +
            ')'
        )
        conn.commit()

        n_lidas = n_ignoradas = 0
        unicos = set()
        lotes = []
        insert_stage = (
            f'INSERT INTO {q(stg)} (' + ','.join(q(c) for c in fields) + ') VALUES (' +
            ','.join('?' for _ in fields) + ')'
        )

        try:
            cr.fast_executemany = True
            for n_linha, valores in planilha_registros(tipo, caminho):
                chave = tuple(valores[i] for i in key_idx)
                if any(k is None for k in chave):
                    n_ignoradas += 1
                    LOG.warning('%s, linha %s, sem chave: ignorada', tipo, n_linha)
                    continue
                if chave in unicos:
                    n_ignoradas += 1
                    LOG.warning('%s, linha %s, chave duplicada na planilha: ignorada (%s)', tipo, n_linha, chave)
                    continue
                unicos.add(chave)
                lotes.append(valores)
                n_lidas += 1
                if len(lotes) >= LOTE:
                    cr.executemany(insert_stage, lotes)
                    conn.commit()
                    lotes.clear()

            if lotes:
                cr.executemany(insert_stage, lotes)
                conn.commit()
            cr.fast_executemany = False

            if stat(caminho) != inicio:
                raise ValueError('Arquivo alterado durante a importação. Tentaremos na próxima execução.')
            if n_lidas == 0:
                raise ValueError('A planilha não possui registros válidos. A tabela SQL NÃO será apagada.')

            nome_tabela = f'dbo.{q(tabela)}'
            cr.execute("SELECT COLUMNPROPERTY(OBJECT_ID(?), ?, 'IsIdentity')", f'dbo.{tabela}', 'ID')
            row = cr.fetchone()
            identity = bool(row and row[0] == 1)

            insert_fields = fields + extras
            select_fields = [f's.{q(c)}' for c in fields] + [
                'SYSDATETIME()' if c in ('DATA_IMPORTACAO','DATA_HORA','DATAHORA') else '?'
                for c in extras
            ]
            if not identity:
                insert_fields = ['ID'] + insert_fields
                select_fields = [
                    'ROW_NUMBER() OVER (ORDER BY ' + ','.join('s.' + q(k) for k in cfg['chave']) + ')'
                ] + select_fields

            # A partir daqui começa a troca real da carga.
            cr.execute('SET XACT_ABORT ON')
            cr.execute(f'SELECT COUNT(*) FROM {nome_tabela}')
            antigos = int(cr.fetchone()[0])
            LOG.info('%s: substituindo carga. Registros atuais=%d, registros novos=%d', tabela, antigos, n_lidas)

            cr.execute(f'DELETE FROM {nome_tabela}')
            LOG.info('%s: DELETE concluído - %d registros antigos removidos. Iniciando gravação da planilha atual.', tabela, antigos)
            if identity:
                cr.execute(f"DBCC CHECKIDENT ('{nome_tabela}', RESEED, 0) WITH NO_INFOMSGS")

            parametros = [EXECUTOR] if 'USUARIO' in extras else []
            sql_insert = (
                'INSERT INTO ' + nome_tabela + ' (' + ','.join(q(c) for c in insert_fields) + ') '
                'SELECT ' + ','.join(select_fields) + ' FROM ' + q(stg) + ' s'
            )
            cr.execute(sql_insert, *parametros)
            gravados = n_lidas if cr.rowcount in (-1, None) else int(cr.rowcount)

            sql_update_controle = (
                'UPDATE dbo.TOTVS_IMPORTACAO_CONTROLE SET HASH_SHA256=?, ARQUIVO=?, '
                'DATA_IMPORTACAO=SYSDATETIME(), QTDE_LIDAS=?, QTDE_NOVAS=?, QTDE_ATUALIZADAS=? WHERE TABELA=?'
            )
            cr.execute(sql_update_controle, hash_controle, caminho, n_lidas, gravados, 0, tabela)
            if cr.rowcount == 0:
                cr.execute(
                    'INSERT INTO dbo.TOTVS_IMPORTACAO_CONTROLE '
                    '(TABELA,HASH_SHA256,ARQUIVO,QTDE_LIDAS,QTDE_NOVAS,QTDE_ATUALIZADAS) VALUES (?,?,?,?,?,?)',
                    tabela, hash_controle, caminho, n_lidas, gravados, 0
                )

            conn.commit()
            LOG.info('%s substituída com sucesso: removidos=%d, gravados=%d, ignorados=%d',
                     tabela, antigos, gravados, n_ignoradas)
            return {'status':'Concluído','lidas':n_lidas,'novas':gravados,'atualizadas':0,'ignoradas':n_ignoradas}

        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                cr.execute(f'DROP TABLE IF EXISTS {q(stg)}')
                conn.commit()
            except Exception:
                LOG.warning('Não foi possível remover a tabela temporária %s', stg)



class QueueLogHandler(logging.Handler):
    def __init__(self, fila):
        super().__init__()
        self.fila = fila
    def emit(self, record):
        try:
            self.fila.put(self.format(record))
        except Exception:
            pass


def ciclo(callback=None, forcar=False):
    resultados = {}
    for tipo in ('clientes', 'fornecedores', 'produtos'):
        try:
            resultado = processar(tipo, forcar=forcar) or {'status':'Concluído'}
            resultados[tipo] = resultado
            if callback:
                callback(tipo, resultado)
        except Exception as exc:
            LOG.exception('Falha ao importar %s; demais tabelas continuarão', tipo)
            resultado = {'status':f'ERRO: {exc}', 'lidas':0, 'novas':0, 'atualizadas':0, 'ignoradas':0}
            resultados[tipo] = resultado
            if callback:
                callback(tipo, resultado)
    return resultados


class ImportadorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('FTECH - Importador TOTVS')
        self.geometry('900x650')
        self.minsize(820, 560)
        self.protocol('WM_DELETE_WINDOW', self.fechar)
        self.parar_evento = threading.Event()
        self.executando = False
        self.automatico = False
        self.fila_log = queue.Queue()
        self.status_vars = {}
        self._montar_interface()
        self._ligar_log_gui()
        self.after(150, self._consumir_logs)
        self.after(1000, self.iniciar_automatico)

    def _montar_interface(self):
        topo = ttk.Frame(self, padding=12)
        topo.pack(fill='x')
        ttk.Label(topo, text='FTECH - Importador Automático TOTVS', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(topo, text=f'SQL Server: {SQL_SERVER}   |   Banco: {SQL_DATABASE}   |   Intervalo: {INTERVALO_SEGUNDOS}s').pack(anchor='w', pady=(4,0))

        botoes = ttk.Frame(self, padding=(12,0,12,8))
        botoes.pack(fill='x')
        self.btn_importar = ttk.Button(botoes, text='Importar agora', command=self.importar_agora)
        self.btn_importar.pack(side='left', padx=(0,6))
        self.btn_auto = ttk.Button(botoes, text='Iniciar automático', command=self.alternar_automatico)
        self.btn_auto.pack(side='left', padx=6)
        ttk.Button(botoes, text='Testar conexão SQL', command=self.testar_conexao).pack(side='left', padx=6)
        ttk.Button(botoes, text='Abrir pasta de logs', command=self.abrir_logs).pack(side='left', padx=6)

        quadro = ttk.LabelFrame(self, text='Status das importações', padding=10)
        quadro.pack(fill='x', padx=12, pady=(0,10))
        ttk.Label(quadro, text='Base', width=18).grid(row=0,column=0,sticky='w')
        ttk.Label(quadro, text='Status', width=28).grid(row=0,column=1,sticky='w')
        ttk.Label(quadro, text='Lidas', width=10).grid(row=0,column=2,sticky='e')
        ttk.Label(quadro, text='Na tabela', width=10).grid(row=0,column=3,sticky='e')
        ttk.Label(quadro, text='Atualizadas', width=12).grid(row=0,column=4,sticky='e')
        nomes={'clientes':'Clientes','fornecedores':'Fornecedores','produtos':'Produtos'}
        for i,tipo in enumerate(('clientes','fornecedores','produtos'), start=1):
            vars_={k:tk.StringVar(value='-' if k!='status' else 'Aguardando') for k in ('status','lidas','novas','atualizadas')}
            self.status_vars[tipo]=vars_
            ttk.Label(quadro,text=nomes[tipo]).grid(row=i,column=0,sticky='w',pady=4)
            ttk.Label(quadro,textvariable=vars_['status']).grid(row=i,column=1,sticky='w')
            ttk.Label(quadro,textvariable=vars_['lidas']).grid(row=i,column=2,sticky='e')
            ttk.Label(quadro,textvariable=vars_['novas']).grid(row=i,column=3,sticky='e')
            ttk.Label(quadro,textvariable=vars_['atualizadas']).grid(row=i,column=4,sticky='e')

        self.lbl_geral = tk.StringVar(value='Pronto')
        ttk.Label(self, textvariable=self.lbl_geral, padding=(12,0,12,6)).pack(fill='x')
        self.progresso = ttk.Progressbar(self, mode='indeterminate')
        self.progresso.pack(fill='x', padx=12, pady=(0,8))

        logs = ttk.LabelFrame(self, text='Log', padding=6)
        logs.pack(fill='both', expand=True, padx=12, pady=(0,12))
        self.txt_log = tk.Text(logs, wrap='word', state='disabled', font=('Consolas',9))
        scroll = ttk.Scrollbar(logs, orient='vertical', command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)
        self.txt_log.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

    def _ligar_log_gui(self):
        h=QueueLogHandler(self.fila_log)
        h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%d/%m/%Y %H:%M:%S'))
        LOG.addHandler(h)

    def _consumir_logs(self):
        try:
            while True:
                msg=self.fila_log.get_nowait()
                self.txt_log.configure(state='normal')
                self.txt_log.insert('end', msg+'\n')
                self.txt_log.see('end')
                self.txt_log.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(150, self._consumir_logs)

    def atualizar_status(self, tipo, resultado):
        def aplicar():
            v=self.status_vars[tipo]
            v['status'].set(str(resultado.get('status','-'))[:60])
            v['lidas'].set(str(resultado.get('lidas',0)))
            v['novas'].set(str(resultado.get('novas',0)))
            v['atualizadas'].set(str(resultado.get('atualizadas',0)))
        self.after(0, aplicar)

    def importar_agora(self):
        # Clique manual SEMPRE força uma carga completa: lê a planilha, apaga a tabela
        # e grava novamente dentro de uma transação.
        self._iniciar_ciclo(forcar=True, origem='manual')

    def _iniciar_ciclo(self, forcar=False, origem='automático'):
        if self.executando:
            return
        self.executando=True
        self.btn_importar.configure(state='disabled')
        self.lbl_geral.set('Importação em andamento...')
        self.progresso.start(10)
        threading.Thread(target=self._executar_ciclo, args=(forcar, origem), daemon=True).start()

    def _executar_ciclo(self, forcar=False, origem='automático'):
        LOG.info('Iniciando ciclo de importação %s%s', origem, ' (forçado)' if forcar else '')
        ciclo(self.atualizar_status, forcar=forcar)
        LOG.info('Ciclo de importação finalizado')
        self.after(0,self._fim_ciclo)

    def _fim_ciclo(self):
        self.executando=False
        self.btn_importar.configure(state='normal')
        self.progresso.stop()
        self.lbl_geral.set('Aguardando próxima execução automática...' if self.automatico else 'Pronto')

    def iniciar_automatico(self):
        if self.automatico:
            return
        self.automatico=True
        self.parar_evento.clear()
        self.btn_auto.configure(text='Parar automático')
        self.lbl_geral.set('Importação automática ativada')
        threading.Thread(target=self._loop_automatico, daemon=True).start()

    def parar_automatico(self):
        self.automatico=False
        self.parar_evento.set()
        self.btn_auto.configure(text='Iniciar automático')
        self.lbl_geral.set('Importação automática parada')

    def alternar_automatico(self):
        self.parar_automatico() if self.automatico else self.iniciar_automatico()

    def _loop_automatico(self):
        while not self.parar_evento.is_set():
            if not self.executando:
                self.after(0, lambda: self._iniciar_ciclo(forcar=False, origem='automático'))
            if self.parar_evento.wait(INTERVALO_SEGUNDOS):
                break

    def testar_conexao(self):
        def worker():
            try:
                with conexao() as conn:
                    cur=conn.cursor()
                    cur.execute('SELECT @@SERVERNAME, DB_NAME()')
                    servidor,banco=cur.fetchone()
                self.after(0, lambda: messagebox.showinfo('Conexão SQL','Conexão realizada com sucesso!\n\nServidor: '+str(servidor)+'\nBanco: '+str(banco)))
            except Exception as exc:
                LOG.exception('Falha no teste de conexão')
                self.after(0, lambda e=str(exc): messagebox.showerror('Erro na conexão SQL',e))
        threading.Thread(target=worker,daemon=True).start()

    def abrir_logs(self):
        try:
            os.startfile(str(LOG_DIR))
        except Exception as exc:
            messagebox.showerror('Erro',str(exc))

    def fechar(self):
        if messagebox.askyesno('Sair','Deseja fechar o Importador TOTVS?'):
            self.parar_evento.set()
            self.destroy()


def main():
    LOG.info('Importador TOTVS iniciado; servidor=%s, banco=%s', SQL_SERVER, SQL_DATABASE)
    if '--uma-vez' in sys.argv:
        ciclo(forcar=True)
        return
    app=ImportadorApp()
    app.mainloop()


if __name__ == '__main__':
    main()
