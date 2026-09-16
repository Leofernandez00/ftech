# -*- coding: utf-8 -*-
"""
FTECH - IMPORTADOR ENTRADA DE NFs
Interface visual + monitoramento automático de pasta de rede.

Dependências:
    pip install openpyxl pyodbc

Funcionalidades:
- Interface visual em Tkinter.
- SQL Login com credenciais embutidas no código (evita erro 18452 de domínio não confiável).
- Permite também autenticação integrada do Windows, se necessário.
- Monitora continuamente a pasta de rede.
- Importa somente arquivos novos ou alterados.
- Aguarda o arquivo ficar estável antes de importar.
- Se um arquivo existente for alterado, apaga os registros daquele arquivo
  e importa novamente, evitando registros antigos/sobrando.
- Cria automaticamente:
      dbo.ENTRADA_NFS
      dbo.ENTRADA_NFS_ARQUIVOS
- Mantém log na tela e em arquivo.
- Botões:
      Testar conexão
      Sincronizar agora
      Iniciar monitoramento
      Parar monitoramento
- Preserva códigos com zeros à esquerda quando o Excel usa formatação 0000 etc.
"""

import json
import os
import queue
import re
import sys
import threading
import time
import traceback
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import openpyxl
import pyodbc


# ============================================================
# CONFIGURAÇÕES PADRÃO
# ============================================================

PASTA_PADRAO = r"\\10.0.0.254\DADOS_CUSTOS_ENTRADA"
SQL_SERVER = r"10.0.0.254"
SQL_DATABASE = "FTECH"

# Importar somente registros a partir desta data
DATA_MINIMA_IMPORTACAO = date(2026, 1, 1)

# ============================================================
# CREDENCIAIS SQL SERVER - PREENCHA UMA ÚNICA VEZ AQUI
# ============================================================
# ATENÇÃO: estas credenciais ficarão embutidas no código e também
# poderão ser extraídas de um .exe gerado com PyInstaller.
SQL_USUARIO = "ftech"
SQL_SENHA = "ftech@1975"

INTERVALO_PADRAO_SEGUNDOS = 15

TABELA_DADOS = "dbo.ENTRADA_NFS"
TABELA_CONTROLE = "dbo.ENTRADA_NFS_ARQUIVOS"

EXTENSOES = {".xlsx", ".xlsm"}


# ============================================================
# PASTAS / CONFIG LOCAL
# ============================================================

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

ARQUIVO_LOG = BASE_DIR / "importador_entrada_nfs.log"
ARQUIVO_CONFIG = BASE_DIR / "importador_entrada_nfs_config.json"


# ============================================================
# SQL - CRIAÇÃO DE TABELAS
# ============================================================

SQL_CRIAR_TABELAS = r"""
IF OBJECT_ID('dbo.ENTRADA_NFS', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ENTRADA_NFS
    (
        ID                  BIGINT IDENTITY(1,1) NOT NULL
                            CONSTRAINT PK_ENTRADA_NFS PRIMARY KEY,

        CODIGO_PROTHEUS     VARCHAR(30)     NULL,
        FILIAL              VARCHAR(10)     NULL,
        DESCRICAO           VARCHAR(300)    NULL,
        TIPO                VARCHAR(20)     NULL,

        CUSTO_ATUAL         DECIMAL(19,6)   NULL,
        DATA                DATE            NULL,
        ARMAZEM             VARCHAR(10)     NULL,
        SALDO_ATUAL         DECIMAL(19,6)   NULL,
        QTD_ENTRADA         DECIMAL(19,6)   NULL,

        DOC_ENTRADA         VARCHAR(30)     NULL,
        FORNECEDOR          VARCHAR(300)    NULL,
        CUSTO_ANTERIOR      DECIMAL(19,6)   NULL,
        CUSTO_ENT_DOC       DECIMAL(19,6)   NULL,

        USUARIO             VARCHAR(100)    NULL,
        ORIGEM              VARCHAR(100)    NULL,

        ARQUIVO_ORIGEM      NVARCHAR(260)   NOT NULL,
        LINHA_ORIGEM        INT             NOT NULL,

        DATA_IMPORTACAO     DATETIME2(0)    NOT NULL
                            CONSTRAINT DF_ENTRADA_NFS_DATA_IMPORTACAO
                            DEFAULT SYSDATETIME(),

        DATA_ATUALIZACAO    DATETIME2(0)    NULL
    );

    CREATE UNIQUE INDEX UX_ENTRADA_NFS_ARQUIVO_LINHA
        ON dbo.ENTRADA_NFS(ARQUIVO_ORIGEM, LINHA_ORIGEM);

    CREATE INDEX IX_ENTRADA_NFS_DATA
        ON dbo.ENTRADA_NFS(DATA);

    CREATE INDEX IX_ENTRADA_NFS_FILIAL
        ON dbo.ENTRADA_NFS(FILIAL);

    CREATE INDEX IX_ENTRADA_NFS_DOC_ENTRADA
        ON dbo.ENTRADA_NFS(DOC_ENTRADA);

    CREATE INDEX IX_ENTRADA_NFS_CODIGO_PROTHEUS
        ON dbo.ENTRADA_NFS(CODIGO_PROTHEUS);
END;

IF OBJECT_ID('dbo.ENTRADA_NFS_ARQUIVOS', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ENTRADA_NFS_ARQUIVOS
    (
        ID                  BIGINT IDENTITY(1,1) NOT NULL
                            CONSTRAINT PK_ENTRADA_NFS_ARQUIVOS PRIMARY KEY,

        ARQUIVO_ORIGEM      NVARCHAR(260) NOT NULL,
        TAMANHO_BYTES       BIGINT NOT NULL,
        DATA_MODIFICACAO    DATETIME2(3) NOT NULL,
        DATA_PROCESSAMENTO  DATETIME2(0) NOT NULL
                            CONSTRAINT DF_ENTRADA_NFS_ARQUIVOS_PROCESSAMENTO
                            DEFAULT SYSDATETIME(),

        REGISTROS           INT NULL,
        STATUS              VARCHAR(20) NOT NULL,
        ERRO                NVARCHAR(2000) NULL,

        CONSTRAINT UQ_ENTRADA_NFS_ARQUIVOS UNIQUE (ARQUIVO_ORIGEM)
    );
END;
"""


SQL_INSERT = r"""
INSERT INTO dbo.ENTRADA_NFS
(
    CODIGO_PROTHEUS,
    FILIAL,
    DESCRICAO,
    TIPO,
    CUSTO_ATUAL,
    DATA,
    ARMAZEM,
    SALDO_ATUAL,
    QTD_ENTRADA,
    DOC_ENTRADA,
    FORNECEDOR,
    CUSTO_ANTERIOR,
    CUSTO_ENT_DOC,
    USUARIO,
    ORIGEM,
    ARQUIVO_ORIGEM,
    LINHA_ORIGEM
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


SQL_CONTROLE_UPSERT = r"""
MERGE dbo.ENTRADA_NFS_ARQUIVOS AS destino
USING
(
    SELECT
        CAST(? AS NVARCHAR(260)) AS ARQUIVO_ORIGEM,
        CAST(? AS BIGINT) AS TAMANHO_BYTES,
        CAST(? AS DATETIME2(3)) AS DATA_MODIFICACAO,
        CAST(? AS INT) AS REGISTROS,
        CAST(? AS VARCHAR(20)) AS STATUS,
        CAST(? AS NVARCHAR(2000)) AS ERRO
) AS origem
ON destino.ARQUIVO_ORIGEM = origem.ARQUIVO_ORIGEM

WHEN MATCHED THEN
    UPDATE SET
        destino.TAMANHO_BYTES = origem.TAMANHO_BYTES,
        destino.DATA_MODIFICACAO = origem.DATA_MODIFICACAO,
        destino.DATA_PROCESSAMENTO = SYSDATETIME(),
        destino.REGISTROS = origem.REGISTROS,
        destino.STATUS = origem.STATUS,
        destino.ERRO = origem.ERRO

WHEN NOT MATCHED THEN
    INSERT
    (
        ARQUIVO_ORIGEM,
        TAMANHO_BYTES,
        DATA_MODIFICACAO,
        DATA_PROCESSAMENTO,
        REGISTROS,
        STATUS,
        ERRO
    )
    VALUES
    (
        origem.ARQUIVO_ORIGEM,
        origem.TAMANHO_BYTES,
        origem.DATA_MODIFICACAO,
        SYSDATETIME(),
        origem.REGISTROS,
        origem.STATUS,
        origem.ERRO
    );
"""


# ============================================================
# CABEÇALHOS
# ============================================================

# ============================================================
# CABEÇALHOS / ALIASES
# ============================================================

# Nome interno -> possíveis nomes encontrados nos relatórios.
# A normalização remove acentos, pontuação, quebras de linha e espaços extras.
ALIASES_CABECALHOS = {
    "CODIGO_PROTHEUS": {
        "CODIGO PROTHEUS", "COD PROTHEUS", "COD. PROTHEUS",
        "CODIGO", "COD PRODUTO", "CODIGO PRODUTO", "COD ITEM",
        "CODIGO ITEM", "PRODUTO"
    },
    "FILIAL": {
        "FILIAL", "COD FILIAL", "CODIGO FILIAL"
    },
    "DESCRICAO": {
        "DESCRICAO", "DESC", "DESCRICAO PRODUTO", "DESCRICAO ITEM"
    },
    "TIPO": {
        "TIPO", "TP", "TIPO PRODUTO", "TIPO ITEM"
    },
    "CUSTO_ATUAL": {
        "CUSTO ATUAL", "CUSTO", "CUSTO MEDIO", "CUSTO MEDIO ATUAL",
        "CUSTO ATUAL R$", "CUSTO UNITARIO"
    },
    "DATA": {
        "DATA", "DT", "DATA ENTRADA", "DT ENTRADA",
        "DATA MOVIMENTO", "DATA MOVIMENTACAO", "DT MOVIMENTO"
    },
    "ARMAZEM": {
        "ARMAZEM", "ALMOXARIFADO", "LOCAL", "LOCAL ESTOQUE"
    },
    "SALDO_ATUAL": {
        "SALDO ATUAL", "SALDO", "ESTOQUE ATUAL", "QTD SALDO",
        "QUANTIDADE SALDO"
    },
    "QTD_ENTRADA": {
        "QTD ENTRADA", "QTDE ENTRADA", "QUANTIDADE ENTRADA",
        "QTD. ENTRADA", "ENTRADA", "QUANTIDADE"
    },
    "DOC_ENTRADA": {
        "DOC ENTRADA", "DOCUMENTO ENTRADA", "DOC. ENTRADA",
        "DOCUMENTO", "NUM DOC", "NUMERO DOCUMENTO", "NF", "NOTA"
    },
    "FORNECEDOR": {
        "FORNECEDOR", "NOME FORNECEDOR", "RAZAO SOCIAL",
        "RAZAO SOCIAL FORNECEDOR"
    },
    "CUSTO_ANTERIOR": {
        "CUSTO ANTERIOR", "CUSTO ANT", "CUSTO MEDIO ANTERIOR",
        "CUSTO ANT."
    },
    "CUSTO_ENT_DOC": {
        "CUSTO ENT DOC", "CUSTO ENTRADA DOC", "CUSTO DOCUMENTO",
        "CUSTO DO DOCUMENTO", "CUSTO NF", "CUSTO ENTRADA"
    },
    "USUARIO": {
        "USUARIO", "USER", "USUARIO INCLUSAO", "USUARIO MOVIMENTO"
    },
    "ORIGEM": {
        "ORIGEM", "ORIGEM MOVIMENTO", "ORIGEM MOVIMENTACAO"
    },
}

# Ordem padrão do relatório. É usada somente como fallback quando o arquivo
# tem os mesmos 15 campos, mas os nomes dos cabeçalhos foram alterados.
ORDEM_PADRAO_COLUNAS = [
    "CODIGO_PROTHEUS",
    "FILIAL",
    "DESCRICAO",
    "TIPO",
    "CUSTO_ATUAL",
    "DATA",
    "ARMAZEM",
    "SALDO_ATUAL",
    "QTD_ENTRADA",
    "DOC_ENTRADA",
    "FORNECEDOR",
    "CUSTO_ANTERIOR",
    "CUSTO_ENT_DOC",
    "USUARIO",
    "ORIGEM",
]

# Campos fundamentais para considerar que uma linha parece ser cabeçalho.
CAMPOS_CHAVE_CABECALHO = {
    "FILIAL", "DESCRICAO", "TIPO", "ARMAZEM",
    "CODIGO_PROTHEUS", "DATA", "DOC_ENTRADA"
}



# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def localizar_driver_sql():
    drivers = pyodbc.drivers()

    preferidos = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]

    for driver in preferidos:
        if driver in drivers:
            return driver

    raise RuntimeError(
        "Nenhum driver ODBC do SQL Server foi encontrado.\n\n"
        "Instale o Microsoft ODBC Driver 17 ou 18 for SQL Server."
    )


def normalizar_cabecalho(valor):
    if valor is None:
        return ""

    s = str(valor).strip().upper()

    trocas = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A", "Ä": "A",
        "É": "E", "Ê": "E", "È": "E", "Ë": "E",
        "Í": "I", "Ì": "I", "Î": "I", "Ï": "I",
        "Ó": "O", "Ô": "O", "Õ": "O", "Ò": "O", "Ö": "O",
        "Ú": "U", "Ù": "U", "Û": "U", "Ü": "U",
        "Ç": "C",
    }

    for a, b in trocas.items():
        s = s.replace(a, b)

    # Padroniza pontuação, quebras de linha, tabs, barras etc. como espaço.
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return " ".join(s.split())


def criar_indice_aliases():
    indice = {}
    for nome_interno, aliases in ALIASES_CABECALHOS.items():
        for alias in aliases:
            indice[normalizar_cabecalho(alias)] = nome_interno
    return indice


INDICE_ALIASES = criar_indice_aliases()


def data_do_nome_arquivo(caminho):
    """
    Reconhece nomes como:
        02.09.2026.xlsx
        02-09-2026.xlsx
        02_09_2026.xlsx
    """
    nome = Path(caminho).stem
    m = re.search(r"(?<!\d)(\d{1,2})[._-](\d{1,2})[._-](\d{4})(?!\d)", nome)
    if not m:
        return None

    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def decimal_sql(valor):
    if valor is None or valor == "":
        return None

    if isinstance(valor, Decimal):
        return valor

    if isinstance(valor, (int, float)):
        return Decimal(str(valor))

    s = str(valor).strip()
    if not s:
        return None

    if "," in s:
        s = s.replace(".", "").replace(",", ".")

    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def data_sql(valor):
    if valor is None or valor == "":
        return None

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, date):
        return valor

    s = str(valor).strip()

    formatos = (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
    )

    for formato in formatos:
        try:
            return datetime.strptime(s, formato).date()
        except ValueError:
            pass

    return None


def texto_generico(valor):
    if valor is None:
        return None

    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)

    s = str(valor).strip()
    return s if s else None


def texto_preservando_zeros(cell):
    """
    Se o valor estiver gravado como número, tenta aproveitar a máscara
    numérica do Excel. Exemplo:
        valor = 902
        formato = 0000
        retorno = 0902
    """
    valor = cell.value

    if valor is None:
        return None

    if isinstance(valor, str):
        s = valor.strip()
        return s if s else None

    if isinstance(valor, bool):
        return str(valor)

    if isinstance(valor, (int, float)):
        fmt = str(cell.number_format or "").strip()

        # Máscara simples composta somente por zeros.
        # Exemplos: 0000 / 000000000
        if fmt and set(fmt) <= {"0"}:
            try:
                inteiro = int(valor)
                return f"{inteiro:0{len(fmt)}d}"
            except Exception:
                pass

        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))

        return str(valor).strip()

    return str(valor).strip()


def datetime_arquivo(timestamp):
    return datetime.fromtimestamp(timestamp)


# ============================================================
# CLASSE PRINCIPAL
# ============================================================

class ImportadorEntradaNFs:
    def __init__(self, root):
        self.root = root
        self.root.title("FTECH - Importador Entrada de NFs")
        self.root.geometry("1050x720")
        self.root.minsize(900, 620)

        self.fila_ui = queue.Queue()
        self.stop_event = threading.Event()
        self.sync_lock = threading.Lock()
        self.monitor_thread = None

        self.total_importados = 0
        self.total_arquivos_processados = 0
        self.total_erros = 0

        self.criar_variaveis()
        self.carregar_config()
        self.criar_interface()

        self.root.after(150, self.processar_fila_ui)
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)

    # --------------------------------------------------------
    # Variáveis
    # --------------------------------------------------------

    def criar_variaveis(self):
        self.var_pasta = tk.StringVar(value=PASTA_PADRAO)
        self.var_intervalo = tk.StringVar(value=str(INTERVALO_PADRAO_SEGUNDOS))

        self.var_status = tk.StringVar(value="Parado")
        self.var_ultimo_ciclo = tk.StringVar(value="-")
        self.var_arquivos = tk.StringVar(value="0")
        self.var_registros = tk.StringVar(value="0")
        self.var_erros = tk.StringVar(value="0")

    # --------------------------------------------------------
    # Interface
    # --------------------------------------------------------

    def criar_interface(self):
        frame_principal = ttk.Frame(self.root, padding=12)
        frame_principal.pack(fill="both", expand=True)

        # SQL
        sql_frame = ttk.LabelFrame(frame_principal, text="Conexão SQL Server", padding=10)
        sql_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(sql_frame, text="Servidor:").grid(row=0, column=0, sticky="w")
        ttk.Label(sql_frame, text=SQL_SERVER).grid(row=0, column=1, sticky="w", padx=(5, 25))

        ttk.Label(sql_frame, text="Banco:").grid(row=0, column=2, sticky="w")
        ttk.Label(sql_frame, text=SQL_DATABASE).grid(row=0, column=3, sticky="w", padx=(5, 25))

        ttk.Label(sql_frame, text="Usuário SQL:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(sql_frame, text=SQL_USUARIO).grid(row=1, column=1, sticky="w", padx=(5, 25), pady=(8, 0))

        ttk.Label(sql_frame, text="Autenticação:").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Label(sql_frame, text="SQL Login (credenciais no código)").grid(row=1, column=3, sticky="w", padx=(5, 25), pady=(8, 0))

        ttk.Button(
            sql_frame,
            text="Testar conexão",
            command=self.testar_conexao_async
        ).grid(row=0, column=4, rowspan=2, padx=(10, 0), sticky="nsew")

        sql_frame.columnconfigure(3, weight=1)

        # Pasta
        pasta_frame = ttk.LabelFrame(frame_principal, text="Monitoramento", padding=10)
        pasta_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(pasta_frame, text="Pasta:").grid(row=0, column=0, sticky="w")
        ttk.Entry(pasta_frame, textvariable=self.var_pasta).grid(
            row=0, column=1, padx=5, sticky="ew"
        )
        ttk.Button(
            pasta_frame,
            text="Selecionar...",
            command=self.selecionar_pasta
        ).grid(row=0, column=2, padx=(5, 0))

        ttk.Label(pasta_frame, text="Verificar a cada:").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        spin = ttk.Spinbox(
            pasta_frame,
            from_=5,
            to=3600,
            increment=5,
            textvariable=self.var_intervalo,
            width=8
        )
        spin.grid(row=1, column=1, sticky="w", padx=5, pady=(8, 0))

        ttk.Label(pasta_frame, text="segundos").grid(
            row=1, column=1, sticky="w", padx=(80, 0), pady=(8, 0)
        )

        pasta_frame.columnconfigure(1, weight=1)

        # Botões
        botoes_frame = ttk.Frame(frame_principal)
        botoes_frame.pack(fill="x", pady=(0, 8))

        self.btn_sync = ttk.Button(
            botoes_frame,
            text="Sincronizar agora",
            command=self.sincronizar_agora
        )
        self.btn_sync.pack(side="left", padx=(0, 5))

        self.btn_iniciar = ttk.Button(
            botoes_frame,
            text="Iniciar monitoramento",
            command=self.iniciar_monitoramento
        )
        self.btn_iniciar.pack(side="left", padx=5)

        self.btn_parar = ttk.Button(
            botoes_frame,
            text="Parar monitoramento",
            command=self.parar_monitoramento,
            state="disabled"
        )
        self.btn_parar.pack(side="left", padx=5)

        ttk.Button(
            botoes_frame,
            text="Abrir pasta de logs",
            command=self.abrir_pasta_logs
        ).pack(side="right")

        # Status
        status_frame = ttk.LabelFrame(frame_principal, text="Status", padding=10)
        status_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(status_frame, text="Monitor:").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.var_status).grid(
            row=0, column=1, sticky="w", padx=(5, 30)
        )

        ttk.Label(status_frame, text="Último ciclo:").grid(row=0, column=2, sticky="w")
        ttk.Label(status_frame, textvariable=self.var_ultimo_ciclo).grid(
            row=0, column=3, sticky="w", padx=(5, 30)
        )

        ttk.Label(status_frame, text="Arquivos processados:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self.var_arquivos).grid(row=1, column=1, sticky="w", padx=(5, 30), pady=(8, 0))

        ttk.Label(status_frame, text="Registros importados:").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self.var_registros).grid(row=1, column=3, sticky="w", padx=(5, 30), pady=(8, 0))

        ttk.Label(status_frame, text="Erros:").grid(row=1, column=4, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self.var_erros).grid(row=1, column=5, sticky="w", padx=5, pady=(8, 0))

        # Log
        log_frame = ttk.LabelFrame(frame_principal, text="Log de execução", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.txt_log = tk.Text(
            log_frame,
            wrap="word",
            height=20,
            state="disabled"
        )
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)

        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.alternar_auth()

        self.log_ui("Aplicativo iniciado.")
        self.log_ui(
            "SQL Login carregado diretamente das credenciais configuradas no código."
        )

    # --------------------------------------------------------
    # UI helpers
    # --------------------------------------------------------

    def alternar_auth(self):
        pass

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.var_pasta.get() or None)
        if pasta:
            self.var_pasta.set(pasta)
            self.salvar_config()

    def abrir_pasta_logs(self):
        try:
            os.startfile(str(BASE_DIR))
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def log_ui(self, mensagem):
        self.fila_ui.put(("log", mensagem))

    def atualizar_contadores_ui(self):
        self.fila_ui.put((
            "contadores",
            self.total_arquivos_processados,
            self.total_importados,
            self.total_erros
        ))

    def processar_fila_ui(self):
        try:
            while True:
                item = self.fila_ui.get_nowait()

                if item[0] == "log":
                    mensagem = item[1]
                    texto = f"[{datetime.now():%d/%m/%Y %H:%M:%S}] {mensagem}"

                    self.txt_log.configure(state="normal")
                    self.txt_log.insert("end", texto + "\n")
                    self.txt_log.see("end")
                    self.txt_log.configure(state="disabled")

                    try:
                        with ARQUIVO_LOG.open("a", encoding="utf-8") as f:
                            f.write(texto + "\n")
                    except Exception:
                        pass

                elif item[0] == "contadores":
                    self.var_arquivos.set(str(item[1]))
                    self.var_registros.set(str(item[2]))
                    self.var_erros.set(str(item[3]))

                elif item[0] == "status":
                    self.var_status.set(item[1])

                elif item[0] == "ultimo_ciclo":
                    self.var_ultimo_ciclo.set(item[1])

                elif item[0] == "msg_info":
                    messagebox.showinfo(item[1], item[2])

                elif item[0] == "msg_erro":
                    messagebox.showerror(item[1], item[2])

        except queue.Empty:
            pass

        self.root.after(150, self.processar_fila_ui)

    # --------------------------------------------------------
    # Config
    # --------------------------------------------------------

    def carregar_config(self):
        if not ARQUIVO_CONFIG.exists():
            return

        try:
            dados = json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))

            self.var_pasta.set(dados.get("pasta", PASTA_PADRAO))
            self.var_intervalo.set(str(dados.get("intervalo", INTERVALO_PADRAO_SEGUNDOS)))
        except Exception:
            pass

    def salvar_config(self):
        try:
            dados = {
                "pasta": self.var_pasta.get().strip(),
                "intervalo": self.obter_intervalo(),
            }

            ARQUIVO_CONFIG.write_text(
                json.dumps(dados, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    def obter_conexao(self):
        driver = localizar_driver_sql()

        if not SQL_SERVER.strip():
            raise ValueError("SQL_SERVER não foi configurado no código.")
        if not SQL_DATABASE.strip():
            raise ValueError("SQL_DATABASE não foi configurado no código.")
        if not SQL_USUARIO.strip() or SQL_USUARIO == "SEU_USUARIO_SQL":
            raise ValueError(
                "Configure SQL_USUARIO no início do arquivo importador_entrada_nfs.py."
            )
        if not SQL_SENHA or SQL_SENHA == "SUA_SENHA_SQL":
            raise ValueError(
                "Configure SQL_SENHA no início do arquivo importador_entrada_nfs.py."
            )

        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USUARIO};"
            f"PWD={SQL_SENHA};"
            "TrustServerCertificate=yes;"
        )

        return pyodbc.connect(
            conn_str,
            timeout=15,
            autocommit=False
        )

    def criar_tabelas(self, conn):
        cursor = conn.cursor()
        cursor.execute(SQL_CRIAR_TABELAS)
        conn.commit()

    def testar_conexao_async(self):
        self.salvar_config()

        def tarefa():
            try:
                conn = self.obter_conexao()
                try:
                    self.criar_tabelas(conn)
                    cursor = conn.cursor()
                    cursor.execute("SELECT @@SERVERNAME, DB_NAME();")
                    linha = cursor.fetchone()

                    self.log_ui(
                        f"Conexão SQL OK. Servidor: {linha[0]} | Banco: {linha[1]}"
                    )

                    self.fila_ui.put((
                        "msg_info",
                        "Conexão",
                        "Conexão com o SQL Server realizada com sucesso."
                    ))
                finally:
                    conn.close()

            except Exception as e:
                self.log_ui(f"Erro de conexão SQL: {e}")
                self.fila_ui.put((
                    "msg_erro",
                    "Erro de conexão",
                    self.mensagem_erro_conexao(e)
                ))

        threading.Thread(target=tarefa, daemon=True).start()

    @staticmethod
    def mensagem_erro_conexao(e):
        texto = str(e)

        if "18452" in texto or "domínio não confiável" in texto.lower():
            return (
                "O SQL Server recusou a autenticação integrada do Windows "
                "(erro 18452: domínio não confiável).\n\n"
                "A versão atual usa SQL Login. Verifique SQL_USUARIO e SQL_SENHA "
                "configurados no início do código."
            )

        if "18456" in texto:
            return (
                "O SQL Server recusou o usuário ou a senha (erro 18456).\n\n"
                "Verifique o login SQL informado e se o SQL Server está "
                "configurado para modo de autenticação mista."
            )

        return texto

    # --------------------------------------------------------
    # Excel
    # --------------------------------------------------------

    def montar_mapa_colunas(self, ws):
        """
        Localiza automaticamente a linha de cabeçalho nos primeiros 30 registros.

        Estratégias:
        1. Nome exato/alias dos cabeçalhos.
        2. Se houver pelo menos alguns campos reconhecidos e exatamente 15
           colunas úteis, usa a ordem padrão A:O como fallback.
        """

        if ws.max_row is None or ws.max_column is None:
            try:
                ws.calculate_dimension(force=True)
            except TypeError:
                ws.calculate_dimension()

        max_row = ws.max_row
        max_col = ws.max_column

        if not max_row or not max_col:
            raise ValueError("Planilha vazia ou sem dimensão utilizável.")

        melhor_linha = None
        melhor_mapa = {}
        melhor_score = -1
        melhor_headers = []

        limite_linhas = min(max_row, 30)

        for linha in range(1, limite_linhas + 1):
            mapa = {}
            headers = []
            colunas_preenchidas = []

            for col in range(1, max_col + 1):
                valor = ws.cell(row=linha, column=col).value
                cab = normalizar_cabecalho(valor)

                if cab:
                    colunas_preenchidas.append(col)
                    headers.append((col, cab))

                nome_interno = INDICE_ALIASES.get(cab)
                if nome_interno and nome_interno not in mapa:
                    mapa[nome_interno] = col

            score = len(mapa)

            # Prefere linhas que tenham campos-chave reconhecidos.
            score += sum(
                1 for campo in CAMPOS_CHAVE_CABECALHO if campo in mapa
            )

            if score > melhor_score:
                melhor_score = score
                melhor_linha = linha
                melhor_mapa = mapa
                melhor_headers = headers

        # Caso normal: todos os 15 cabeçalhos foram identificados.
        if len(melhor_mapa) == len(ORDEM_PADRAO_COLUNAS):
            return melhor_mapa, melhor_linha, "CABECALHO"

        # Fallback para relatórios do mesmo Protheus com nomes de cabeçalho
        # alterados: se a melhor linha tem 15 colunas preenchidas e reconhecemos
        # pelo menos 3 campos, usamos a posição padrão das 15 colunas.
        colunas_preenchidas = [col for col, cab in melhor_headers if cab]

        if (
            len(colunas_preenchidas) >= 15
            and len(melhor_mapa) >= 3
        ):
            # Usa as primeiras 15 colunas preenchidas mantendo a ordem visual.
            colunas_preenchidas = colunas_preenchidas[:15]
            mapa_posicional = {
                nome: colunas_preenchidas[i]
                for i, nome in enumerate(ORDEM_PADRAO_COLUNAS)
            }

            self.log_ui(
                f"Cabeçalho diferente detectado na linha {melhor_linha}; "
                f"usando mapeamento por posição das 15 colunas."
            )
            return mapa_posicional, melhor_linha, "POSICAO"

        faltando = [
            nome for nome in ORDEM_PADRAO_COLUNAS
            if nome not in melhor_mapa
        ]

        encontrados = ", ".join(
            f"{col}:{cab}" for col, cab in melhor_headers[:25]
        )

        raise ValueError(
            "Não foi possível mapear o relatório. "
            f"Melhor linha de cabeçalho encontrada: {melhor_linha}. "
            f"Campos reconhecidos: {len(melhor_mapa)}/15. "
            f"Colunas faltantes: {', '.join(faltando)}. "
            f"Cabeçalhos encontrados: {encontrados}"
        )

    @staticmethod
    def celula(ws, linha, mapa, nome):
        col = mapa.get(nome)
        if col is None:
            return None
        return ws.cell(row=linha, column=col)

    def ler_arquivo(self, caminho):
        wb = openpyxl.load_workbook(
            caminho,
            read_only=True,
            data_only=True
        )

        try:
            # Procura uma planilha que contenha o relatório, em vez de assumir
            # cegamente que a primeira aba é sempre a correta.
            erros_abas = []
            ws_escolhida = None
            mapa = None
            linha_cabecalho = None
            modo_mapeamento = None

            for ws in wb.worksheets:
                try:
                    mapa_temp, linha_temp, modo_temp = self.montar_mapa_colunas(ws)
                    ws_escolhida = ws
                    mapa = mapa_temp
                    linha_cabecalho = linha_temp
                    modo_mapeamento = modo_temp
                    break
                except Exception as e:
                    erros_abas.append(f"{ws.title}: {e}")

            if ws_escolhida is None:
                raise ValueError(
                    "Nenhuma aba compatível encontrada. " + " | ".join(erros_abas)
                )

            ws = ws_escolhida

            self.log_ui(
                f"{caminho.name}: aba '{ws.title}', cabeçalho na linha "
                f"{linha_cabecalho}, modo {modo_mapeamento}."
            )

            registros = []

            # A data do nome é usada SOMENTE se a coluna DATA existir,
            # mas a célula daquela linha vier vazia/ilegível.
            data_arquivo = data_do_nome_arquivo(caminho)

            for linha in range(linha_cabecalho + 1, ws.max_row + 1):
                c_codigo = self.celula(ws, linha, mapa, "CODIGO_PROTHEUS")
                c_filial = self.celula(ws, linha, mapa, "FILIAL")
                c_descricao = self.celula(ws, linha, mapa, "DESCRICAO")
                c_tipo = self.celula(ws, linha, mapa, "TIPO")
                c_custo_atual = self.celula(ws, linha, mapa, "CUSTO_ATUAL")
                c_data = self.celula(ws, linha, mapa, "DATA")
                c_armazem = self.celula(ws, linha, mapa, "ARMAZEM")
                c_saldo_atual = self.celula(ws, linha, mapa, "SALDO_ATUAL")
                c_qtd = self.celula(ws, linha, mapa, "QTD_ENTRADA")
                c_doc = self.celula(ws, linha, mapa, "DOC_ENTRADA")
                c_fornecedor = self.celula(ws, linha, mapa, "FORNECEDOR")
                c_custo_anterior = self.celula(ws, linha, mapa, "CUSTO_ANTERIOR")
                c_custo_doc = self.celula(ws, linha, mapa, "CUSTO_ENT_DOC")
                c_usuario = self.celula(ws, linha, mapa, "USUARIO")
                c_origem = self.celula(ws, linha, mapa, "ORIGEM")

                codigo = texto_preservando_zeros(c_codigo) if c_codigo else None
                filial = texto_preservando_zeros(c_filial) if c_filial else None
                descricao = texto_generico(c_descricao.value) if c_descricao else None
                tipo = texto_generico(c_tipo.value) if c_tipo else None
                custo_atual = decimal_sql(c_custo_atual.value) if c_custo_atual else None

                data_mov = data_sql(c_data.value) if c_data else None
                if data_mov is None:
                    data_mov = data_arquivo

                # Importar somente registros de 01/01/2026 em diante.
                if data_mov is None or data_mov < DATA_MINIMA_IMPORTACAO:
                    continue

                armazem = texto_preservando_zeros(c_armazem) if c_armazem else None
                saldo_atual = decimal_sql(c_saldo_atual.value) if c_saldo_atual else None
                qtd_entrada = decimal_sql(c_qtd.value) if c_qtd else None
                doc_entrada = texto_preservando_zeros(c_doc) if c_doc else None
                fornecedor = texto_generico(c_fornecedor.value) if c_fornecedor else None
                custo_anterior = decimal_sql(c_custo_anterior.value) if c_custo_anterior else None
                custo_ent_doc = decimal_sql(c_custo_doc.value) if c_custo_doc else None
                usuario = texto_generico(c_usuario.value) if c_usuario else None
                origem = texto_generico(c_origem.value) if c_origem else None

                valores = [
                    codigo, filial, descricao, tipo, custo_atual, data_mov,
                    armazem, saldo_atual, qtd_entrada, doc_entrada,
                    fornecedor, custo_anterior, custo_ent_doc, usuario, origem
                ]

                if not any(v is not None and v != "" for v in valores):
                    continue

                registros.append((
                    codigo,
                    filial,
                    descricao,
                    tipo,
                    custo_atual,
                    data_mov,
                    armazem,
                    saldo_atual,
                    qtd_entrada,
                    doc_entrada,
                    fornecedor,
                    custo_anterior,
                    custo_ent_doc,
                    usuario,
                    origem,
                    caminho.name,
                    linha
                ))

            return registros

        finally:
            wb.close()

    # --------------------------------------------------------
    # Controle de arquivos
    # --------------------------------------------------------

    def listar_arquivos(self):
        pasta = Path(self.var_pasta.get().strip())

        if not pasta.exists():
            raise FileNotFoundError(
                f"A pasta não foi encontrada ou não está acessível:\n{pasta}"
            )

        arquivos = []

        for item in pasta.iterdir():
            if (
                item.is_file()
                and item.suffix.lower() in EXTENSOES
                and not item.name.startswith("~$")
            ):
                data_nome = data_do_nome_arquivo(item)

                # Se o nome contém uma data válida e ela é anterior à data mínima,
                # nem abre o arquivo. Ex.: 09.07.2025.xlsx.
                if data_nome is not None and data_nome < DATA_MINIMA_IMPORTACAO:
                    continue

                arquivos.append(item)

        return sorted(arquivos, key=lambda p: p.name.lower())

    @staticmethod
    def obter_estado_arquivo(caminho):
        stat = caminho.stat()
        return stat.st_size, stat.st_mtime

    def buscar_controle_arquivo(self, conn, nome):
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                TAMANHO_BYTES,
                DATA_MODIFICACAO,
                STATUS
            FROM dbo.ENTRADA_NFS_ARQUIVOS
            WHERE ARQUIVO_ORIGEM = ?;
            """,
            nome
        )
        return cursor.fetchone()

    def arquivo_precisa_importar(self, conn, caminho):
        tamanho, mtime = self.obter_estado_arquivo(caminho)
        controle = self.buscar_controle_arquivo(conn, caminho.name)

        if controle is None:
            return True

        tamanho_sql = int(controle[0])
        data_sql_controle = controle[1]
        status = str(controle[2] or "")

        data_atual = datetime_arquivo(mtime)

        # Tolerância pequena por diferenças de precisão do filesystem / SQL.
        diff_segundos = abs((data_atual - data_sql_controle).total_seconds())

        if status != "OK":
            return True

        if tamanho != tamanho_sql:
            return True

        if diff_segundos > 0.01:
            return True

        return False

    def aguardar_arquivo_estavel(self, caminho, timeout=60):
        """
        Para evitar importar enquanto outro processo ainda está salvando:
        considera estável quando tamanho e mtime permanecem iguais em
        duas verificações consecutivas.
        """
        inicio = time.time()
        anterior = None
        iguais = 0

        while time.time() - inicio < timeout:
            if self.stop_event.is_set():
                return False

            try:
                atual = self.obter_estado_arquivo(caminho)

                if atual == anterior:
                    iguais += 1
                else:
                    iguais = 0

                if iguais >= 2:
                    return True

                anterior = atual
            except OSError:
                iguais = 0

            time.sleep(1)

        return False

    def gravar_controle(self, conn, caminho, registros, status, erro=None):
        tamanho, mtime = self.obter_estado_arquivo(caminho)
        data_mod = datetime_arquivo(mtime)

        if erro:
            erro = str(erro)[:2000]

        cursor = conn.cursor()
        cursor.execute(
            SQL_CONTROLE_UPSERT,
            caminho.name,
            tamanho,
            data_mod,
            registros,
            status,
            erro
        )

    # --------------------------------------------------------
    # Importação
    # --------------------------------------------------------

    def importar_um_arquivo(self, conn, caminho):
        self.log_ui(f"Detectado arquivo novo/alterado: {caminho.name}")

        if not self.aguardar_arquivo_estavel(caminho):
            self.log_ui(
                f"Arquivo não ficou estável a tempo, será tentado novamente: "
                f"{caminho.name}"
            )
            return 0

        registros = self.ler_arquivo(caminho)

        cursor = conn.cursor()

        try:
            # Arquivo alterado = substituir totalmente os dados daquele arquivo.
            cursor.execute(
                "DELETE FROM dbo.ENTRADA_NFS WHERE ARQUIVO_ORIGEM = ?;",
                caminho.name
            )

            if registros:
                # fast_executemany acelera bastante inserções em lote.
                try:
                    cursor.fast_executemany = True
                except Exception:
                    pass

                cursor.executemany(SQL_INSERT, registros)

            self.gravar_controle(
                conn,
                caminho,
                len(registros),
                "OK",
                None
            )

            conn.commit()

            self.total_importados += len(registros)
            self.total_arquivos_processados += 1
            self.atualizar_contadores_ui()

            self.log_ui(
                f"Importado com sucesso: {caminho.name} | "
                f"{len(registros)} registro(s)"
            )

            return len(registros)

        except Exception as e:
            conn.rollback()

            # Tenta registrar o erro em nova transação.
            try:
                self.gravar_controle(
                    conn,
                    caminho,
                    0,
                    "ERRO",
                    str(e)
                )
                conn.commit()
            except Exception:
                conn.rollback()

            self.total_erros += 1
            self.atualizar_contadores_ui()

            raise

    # --------------------------------------------------------
    # Sincronização
    # --------------------------------------------------------

    def obter_intervalo(self):
        try:
            valor = int(self.var_intervalo.get().strip())
            return max(5, valor)
        except Exception:
            return INTERVALO_PADRAO_SEGUNDOS

    def executar_ciclo(self):
        if not self.sync_lock.acquire(blocking=False):
            self.log_ui("Já existe uma sincronização em andamento.")
            return

        conn = None

        try:
            self.salvar_config()
            self.fila_ui.put(("status", "Sincronizando..."))

            arquivos = self.listar_arquivos()
            self.log_ui(f"Verificando {len(arquivos)} arquivo(s) na pasta.")

            conn = self.obter_conexao()
            self.criar_tabelas(conn)

            pendentes = []

            for arquivo in arquivos:
                if self.stop_event.is_set():
                    break

                try:
                    if self.arquivo_precisa_importar(conn, arquivo):
                        pendentes.append(arquivo)
                except Exception as e:
                    self.log_ui(
                        f"Não foi possível verificar {arquivo.name}: {e}"
                    )

            if not pendentes:
                self.log_ui("Nenhum arquivo novo ou alterado.")
            else:
                self.log_ui(
                    f"{len(pendentes)} arquivo(s) novo(s)/alterado(s) para importar."
                )

                for arquivo in pendentes:
                    if self.stop_event.is_set():
                        break

                    try:
                        self.importar_um_arquivo(conn, arquivo)
                    except PermissionError:
                        self.log_ui(
                            f"Arquivo em uso, será tentado novamente no próximo ciclo: "
                            f"{arquivo.name}"
                        )
                    except Exception as e:
                        self.log_ui(f"ERRO ao importar {arquivo.name}: {e}")
                        self.log_ui(traceback.format_exc())

            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.fila_ui.put(("ultimo_ciclo", agora))

            if self.monitor_thread and self.monitor_thread.is_alive():
                self.fila_ui.put(("status", "Monitorando"))
            else:
                self.fila_ui.put(("status", "Parado"))

        except Exception as e:
            self.total_erros += 1
            self.atualizar_contadores_ui()

            self.log_ui(f"ERRO no ciclo de sincronização: {e}")

            msg = self.mensagem_erro_conexao(e)

            # Não abre MessageBox em todo ciclo automático.
            if not (self.monitor_thread and self.monitor_thread.is_alive()):
                self.fila_ui.put(("msg_erro", "Erro", msg))

            if self.monitor_thread and self.monitor_thread.is_alive():
                self.fila_ui.put(("status", "Monitorando - erro"))

        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

            self.sync_lock.release()

    def sincronizar_agora(self):
        self.stop_event.clear()

        threading.Thread(
            target=self.executar_ciclo,
            daemon=True
        ).start()

    # --------------------------------------------------------
    # Monitor
    # --------------------------------------------------------

    def iniciar_monitoramento(self):
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        # Validação antecipada das credenciais embutidas no código.
        if (
            not SQL_USUARIO.strip()
            or SQL_USUARIO == "SEU_USUARIO_SQL"
            or not SQL_SENHA
            or SQL_SENHA == "SUA_SENHA_SQL"
        ):
            messagebox.showwarning(
                "Credenciais SQL",
                "Configure SQL_USUARIO e SQL_SENHA no início do código antes de iniciar."
            )
            return

        self.salvar_config()
        self.stop_event.clear()

        self.btn_iniciar.configure(state="disabled")
        self.btn_parar.configure(state="normal")
        self.fila_ui.put(("status", "Monitorando"))

        self.monitor_thread = threading.Thread(
            target=self.loop_monitoramento,
            daemon=True
        )
        self.monitor_thread.start()

        self.log_ui(
            f"Monitoramento iniciado. Intervalo: "
            f"{self.obter_intervalo()} segundos."
        )

    def loop_monitoramento(self):
        # Executa imediatamente ao iniciar.
        while not self.stop_event.is_set():
            self.executar_ciclo()

            intervalo = self.obter_intervalo()

            # Espera de forma interrompível.
            if self.stop_event.wait(intervalo):
                break

        self.fila_ui.put(("status", "Parado"))

    def parar_monitoramento(self):
        self.stop_event.set()
        self.btn_iniciar.configure(state="normal")
        self.btn_parar.configure(state="disabled")
        self.fila_ui.put(("status", "Parando..."))
        self.log_ui("Solicitado encerramento do monitoramento.")

    # --------------------------------------------------------
    # Fechar
    # --------------------------------------------------------

    def fechar(self):
        self.salvar_config()
        self.stop_event.set()
        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main():
    root = tk.Tk()
    app = ImportadorEntradaNFs(root)
    root.mainloop()


if __name__ == "__main__":
    main()
