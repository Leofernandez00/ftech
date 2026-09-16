import json
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import pyodbc


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# LocalDB do Fiscal Monitor
LOCALDB_CONNECTION_STRING = (
    r"DRIVER={ODBC Driver 17 for SQL Server};"
    r"SERVER=(localdb)\MSSQLLocalDB;"
    r"DATABASE=fiscaliodba;"
    r"Trusted_Connection=Yes;"
    r"APP=FiscalLocalDBSync;"
    r"Connection Timeout=2;"
)

# SQL Server de destino
# >>> PREENCHA SERVIDOR, USUÁRIO E SENHA <<<
SQLSERVER_CONNECTION_STRING = (
    r"DRIVER={ODBC Driver 17 for SQL Server};"
    r"SERVER=188.220.168.222;"
    r"DATABASE=FTECH;"
    r"UID=ftech;"
    r"PWD=ftech@1975;"
    r"TrustServerCertificate=Yes;"
    r"Connection Timeout=10;"
)

TABLES = [
    "document",
    "docitem",
    "docstatus",
    "objectchange",
    "docheadtext",
    "event",
]

PRIMARY_KEYS = {
    "document": ["filial", "chave"],
    "docitem": ["chave", "nitem"],
    "docstatus": ["filial", "chave", "status"],
    "objectchange": ["ucguid", "ucobject"],
    "docheadtext": ["chave"],
    "event": ["chave", "tpevento", "nseqevento"],
}

# Quantos registros são lidos do LocalDB por vez.
BATCH_SIZE = 50000

# Durante a carga inicial, continua rapidamente lote a lote.
ACTIVE_LOOP_PAUSE_SECONDS = 0.25

# Depois que TODAS as tabelas chegam ao fim da varredura,
# aguarda 30 minutos antes de começar nova varredura completa.
FULL_RESCAN_INTERVAL_SECONDS = 30 * 60

# Em caso de erro, aguarda antes de tentar novamente.
ERROR_RETRY_SECONDS = 30

# Segurança: desativa pooling ODBC.
# Assim conn.close() realmente libera a conexão com o LocalDB.
pyodbc.pooling = False


# ============================================================
# LOG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "fiscal_sync.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

log = logging.getLogger("FiscalLocalDBSync")


# ============================================================
# UTILITÁRIOS SQL
# ============================================================

def q(identifier: str) -> str:
    return "[" + identifier.replace("]", "]]") + "]"


def connect_localdb():
    """
    Conexão curta com LocalDB.
    Nunca deve permanecer aberta durante gravações no SQL Server remoto.
    """
    return pyodbc.connect(
        LOCALDB_CONNECTION_STRING,
        autocommit=True
    )


def connect_sqlserver():
    return pyodbc.connect(
        SQLSERVER_CONNECTION_STRING,
        autocommit=False
    )


def ensure_state_table():
    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        cur.execute("""
        IF OBJECT_ID(N'dbo.FISCAL_SYNC_STATE', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.FISCAL_SYNC_STATE
            (
                table_name sysname NOT NULL PRIMARY KEY,
                last_pk_json nvarchar(max) NULL,
                scan_round bigint NOT NULL DEFAULT(0),
                last_batch_rows int NOT NULL DEFAULT(0),
                last_sync_at datetime2(0) NULL,
                next_scan_at datetime2(0) NULL,
                last_error nvarchar(2000) NULL
            );
        END;
        """)

        conn.commit()
        cur.close()

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()


def get_columns_from_localdb(table: str):
    conn = None

    try:
        conn = connect_localdb()
        cur = conn.cursor()

        cur.execute("SET LOCK_TIMEOUT 500;")
        cur.execute("SET DEADLOCK_PRIORITY LOW;")

        cur.execute("""
            SELECT c.name
            FROM sys.tables t
            INNER JOIN sys.schemas s
                ON s.schema_id = t.schema_id
            INNER JOIN sys.columns c
                ON c.object_id = t.object_id
            WHERE s.name = 'dbo'
              AND t.name = ?
            ORDER BY c.column_id;
        """, table)

        result = [row[0] for row in cur.fetchall()]
        cur.close()

        return result

    finally:
        if conn is not None:
            conn.close()


def get_columns_from_sqlserver(table: str):
    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        cur.execute("""
            SELECT c.name
            FROM sys.tables t
            INNER JOIN sys.schemas s
                ON s.schema_id = t.schema_id
            INNER JOIN sys.columns c
                ON c.object_id = t.object_id
            WHERE s.name = 'dbo'
              AND t.name = ?
            ORDER BY c.column_id;
        """, table)

        result = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.rollback()

        return result

    finally:
        if conn is not None:
            conn.close()


def validate_schema():
    log.info("Validando estrutura das tabelas...")

    for table in TABLES:
        src = get_columns_from_localdb(table)
        dst = get_columns_from_sqlserver(table)

        if not src:
            raise RuntimeError(
                f"Tabela dbo.{table} não encontrada no LocalDB."
            )

        if not dst:
            raise RuntimeError(
                f"Tabela dbo.{table} não encontrada no SQL Server FTECH."
            )

        if src != dst:
            only_src = [c for c in src if c not in dst]
            only_dst = [c for c in dst if c not in src]

            raise RuntimeError(
                f"Estrutura diferente em dbo.{table}. "
                f"Somente LocalDB={only_src}; "
                f"somente destino={only_dst}."
            )

        missing_pk = [
            c for c in PRIMARY_KEYS[table]
            if c not in src
        ]

        if missing_pk:
            raise RuntimeError(
                f"PK configurada incorretamente para {table}: "
                f"{missing_pk}"
            )

        log.info(
            "Estrutura OK: %-13s | %d colunas | PK=%s",
            table,
            len(src),
            "+".join(PRIMARY_KEYS[table])
        )


# ============================================================
# ESTADO DA SINCRONIZAÇÃO
# ============================================================

def get_state(table: str):
    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                last_pk_json,
                scan_round,
                next_scan_at
            FROM dbo.FISCAL_SYNC_STATE
            WHERE table_name = ?;
        """, table)

        row = cur.fetchone()

        cur.close()
        conn.rollback()

        if row is None:
            return {
                "last_pk": None,
                "scan_round": 0,
                "next_scan_at": None,
            }

        return {
            "last_pk":
                json.loads(row[0]) if row[0] else None,
            "scan_round":
                int(row[1] or 0),
            "next_scan_at":
                row[2],
        }

    finally:
        if conn is not None:
            conn.close()


def save_error(table: str, message: str):
    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        cur.execute("""
            IF EXISTS (
                SELECT 1
                FROM dbo.FISCAL_SYNC_STATE
                WHERE table_name = ?
            )
            BEGIN
                UPDATE dbo.FISCAL_SYNC_STATE
                SET last_error = ?,
                    last_sync_at = SYSDATETIME()
                WHERE table_name = ?;
            END
            ELSE
            BEGIN
                INSERT INTO dbo.FISCAL_SYNC_STATE
                (
                    table_name,
                    last_error,
                    last_sync_at
                )
                VALUES (?, ?, SYSDATETIME());
            END
        """,
        table, message[:2000], table,
        table, message[:2000])

        conn.commit()
        cur.close()

    except Exception:
        if conn is not None:
            conn.rollback()
        log.exception(
            "Não foi possível registrar o erro de %s.",
            table
        )

    finally:
        if conn is not None:
            conn.close()


def reset_sync_state():
    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        cur.execute("""
            UPDATE dbo.FISCAL_SYNC_STATE
            SET last_pk_json = NULL,
                next_scan_at = NULL,
                last_error = NULL;
        """)

        conn.commit()
        cur.close()

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()


# ============================================================
# PAGINAÇÃO POR CHAVE PRIMÁRIA
# ============================================================

def build_keyset_where(pk_columns, last_pk):
    if last_pk is None:
        return "", []

    if len(last_pk) != len(pk_columns):
        raise RuntimeError(
            f"Cursor incompatível. "
            f"Esperado={len(pk_columns)}, "
            f"recebido={len(last_pk)}"
        )

    clauses = []
    params = []

    for i, pk in enumerate(pk_columns):
        terms = []

        for j in range(i):
            terms.append(
                f"{q(pk_columns[j])} = ?"
            )
            params.append(last_pk[j])

        terms.append(
            f"{q(pk)} > ?"
        )
        params.append(last_pk[i])

        clauses.append(
            "(" + " AND ".join(terms) + ")"
        )

    return (
        " WHERE " + " OR ".join(clauses),
        params
    )


# ============================================================
# LEITURA DO LOCALDB
# ============================================================

def read_localdb_batch(table: str, columns, last_pk):
    """
    Lê um lote e fecha o LocalDB ANTES de retornar.
    """
    pk_columns = PRIMARY_KEYS[table]

    where_sql, params = build_keyset_where(
        pk_columns,
        last_pk
    )

    column_sql = ", ".join(
        q(c) for c in columns
    )

    order_sql = ", ".join(
        q(c) for c in pk_columns
    )

    sql = f"""
        SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
        SET LOCK_TIMEOUT 500;
        SET DEADLOCK_PRIORITY LOW;

        SELECT TOP ({int(BATCH_SIZE)})
            {column_sql}
        FROM dbo.{q(table)} WITH (NOLOCK)
        {where_sql}
        ORDER BY {order_sql};
    """

    conn = None

    try:
        conn = connect_localdb()
        cur = conn.cursor()

        cur.execute(sql, params)

        rows = [
            tuple(row)
            for row in cur.fetchall()
        ]

        cur.close()

        return rows

    finally:
        # CRÍTICO:
        # a conexão LocalDB é fechada antes do UPSERT remoto.
        if conn is not None:
            conn.close()


# ============================================================
# UPSERT NO SQL SERVER
# ============================================================

def stage_insert(cursor, table, columns, rows):
    cursor.execute(
        f"SELECT TOP (0) * "
        f"INTO #stage "
        f"FROM dbo.{q(table)};"
    )

    cols_sql = ", ".join(
        q(c) for c in columns
    )

    placeholders = ", ".join(
        "?" for _ in columns
    )

    sql = (
        f"INSERT INTO #stage ({cols_sql}) "
        f"VALUES ({placeholders});"
    )

    cursor.fast_executemany = False
    cursor.executemany(sql, rows)


def upsert_and_save_cursor(
    table: str,
    columns,
    rows,
    new_last_pk,
    scan_round: int
):
    pk_columns = PRIMARY_KEYS[table]

    non_pk_columns = [
        c for c in columns
        if c not in pk_columns
    ]

    join_sql = " AND ".join(
        f"T.{q(pk)} = S.{q(pk)}"
        for pk in pk_columns
    )

    cols_sql = ", ".join(
        q(c) for c in columns
    )

    source_cols_sql = ", ".join(
        f"S.{q(c)}"
        for c in columns
    )

    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        stage_insert(
            cur,
            table,
            columns,
            rows
        )

        updated = 0

        if non_pk_columns:
            set_sql = ", ".join(
                f"T.{q(c)} = S.{q(c)}"
                for c in non_pk_columns
            )

            source_compare = ", ".join(
                f"S.{q(c)}"
                for c in non_pk_columns
            )

            target_compare = ", ".join(
                f"T.{q(c)}"
                for c in non_pk_columns
            )

            update_sql = f"""
                UPDATE T
                SET {set_sql}
                FROM dbo.{q(table)} AS T
                INNER JOIN #stage AS S
                    ON {join_sql}
                WHERE EXISTS
                (
                    SELECT {source_compare}
                    EXCEPT
                    SELECT {target_compare}
                );
            """

            cur.execute(update_sql)
            updated = max(cur.rowcount, 0)

        insert_sql = f"""
            INSERT INTO dbo.{q(table)}
            (
                {cols_sql}
            )
            SELECT
                {source_cols_sql}
            FROM #stage AS S
            WHERE NOT EXISTS
            (
                SELECT 1
                FROM dbo.{q(table)} AS T
                WHERE {join_sql}
            );
        """

        cur.execute(insert_sql)
        inserted = max(cur.rowcount, 0)

        last_pk_json = json.dumps(
            list(new_last_pk),
            ensure_ascii=False
        )

        cur.execute("""
            IF EXISTS (
                SELECT 1
                FROM dbo.FISCAL_SYNC_STATE
                WHERE table_name = ?
            )
            BEGIN
                UPDATE dbo.FISCAL_SYNC_STATE
                SET last_pk_json = ?,
                    scan_round = ?,
                    last_batch_rows = ?,
                    last_sync_at = SYSDATETIME(),
                    next_scan_at = NULL,
                    last_error = NULL
                WHERE table_name = ?;
            END
            ELSE
            BEGIN
                INSERT INTO dbo.FISCAL_SYNC_STATE
                (
                    table_name,
                    last_pk_json,
                    scan_round,
                    last_batch_rows,
                    last_sync_at,
                    next_scan_at,
                    last_error
                )
                VALUES
                (
                    ?, ?, ?, ?,
                    SYSDATETIME(),
                    NULL,
                    NULL
                );
            END
        """,
        table,
        last_pk_json,
        scan_round,
        len(rows),
        table,
        table,
        last_pk_json,
        scan_round,
        len(rows))

        conn.commit()
        cur.close()

        return inserted, updated

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()


def mark_scan_complete(
    table: str,
    current_round: int
):
    next_scan = datetime.now() + timedelta(
        seconds=FULL_RESCAN_INTERVAL_SECONDS
    )

    next_round = current_round + 1

    conn = None

    try:
        conn = connect_sqlserver()
        cur = conn.cursor()

        cur.execute("""
            IF EXISTS (
                SELECT 1
                FROM dbo.FISCAL_SYNC_STATE
                WHERE table_name = ?
            )
            BEGIN
                UPDATE dbo.FISCAL_SYNC_STATE
                SET last_pk_json = NULL,
                    scan_round = ?,
                    last_batch_rows = 0,
                    last_sync_at = SYSDATETIME(),
                    next_scan_at = ?,
                    last_error = NULL
                WHERE table_name = ?;
            END
            ELSE
            BEGIN
                INSERT INTO dbo.FISCAL_SYNC_STATE
                (
                    table_name,
                    last_pk_json,
                    scan_round,
                    last_batch_rows,
                    last_sync_at,
                    next_scan_at,
                    last_error
                )
                VALUES
                (
                    ?, NULL, ?, 0,
                    SYSDATETIME(),
                    ?,
                    NULL
                );
            END
        """,
        table,
        next_round,
        next_scan,
        table,
        table,
        next_round,
        next_scan)

        conn.commit()
        cur.close()

        return next_round, next_scan

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()


# ============================================================
# SINCRONIZAÇÃO DE UMA TABELA
# ============================================================

def extract_last_pk(
    table: str,
    columns,
    last_row
):
    index = {
        name: i
        for i, name in enumerate(columns)
    }

    return [
        last_row[index[pk]]
        for pk in PRIMARY_KEYS[table]
    ]


def sync_one_table(
    table: str,
    columns
):
    state = get_state(table)

    # Se esta tabela já terminou a varredura,
    # aguarda o horário da próxima.
    if state["next_scan_at"] is not None:
        if datetime.now() < state["next_scan_at"]:
            return {
                "table": table,
                "skipped": True,
                "rows": 0,
                "inserted": 0,
                "updated": 0,
            }

    # 1) lê LocalDB e fecha
    rows = read_localdb_batch(
        table,
        columns,
        state["last_pk"]
    )

    # 2) só depois grava remotamente
    if not rows:
        new_round, next_scan = mark_scan_complete(
            table,
            state["scan_round"]
        )

        log.info(
            "%-13s | varredura %d concluída | próxima=%s",
            table,
            new_round,
            next_scan.strftime("%d/%m/%Y %H:%M:%S")
        )

        return {
            "table": table,
            "skipped": False,
            "rows": 0,
            "inserted": 0,
            "updated": 0,
        }

    new_last_pk = extract_last_pk(
        table,
        columns,
        rows[-1]
    )

    inserted, updated = upsert_and_save_cursor(
        table,
        columns,
        rows,
        new_last_pk,
        state["scan_round"]
    )

    log.info(
        "%-13s | lidos=%d | inserts=%d | updates=%d",
        table,
        len(rows),
        inserted,
        updated
    )

    return {
        "table": table,
        "skipped": False,
        "rows": len(rows),
        "inserted": inserted,
        "updated": updated,
    }


def load_metadata():
    return {
        table: get_columns_from_localdb(table)
        for table in TABLES
    }


# ============================================================
# LOG PARA INTERFACE
# ============================================================

class QueueLogHandler(logging.Handler):
    def __init__(self, gui_queue):
        super().__init__()
        self.gui_queue = gui_queue

        self.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                "%Y-%m-%d %H:%M:%S"
            )
        )

    def emit(self, record):
        try:
            self.gui_queue.put(
                ("log", self.format(record))
            )
        except Exception:
            pass


# ============================================================
# INTERFACE
# ============================================================

class FiscalSyncApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(
            "Fiscal Sync - LocalDB → SQL Server"
        )
        self.geometry("1150x740")
        self.minsize(980, 650)

        self.gui_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.metadata = None

        self.session_read = 0
        self.session_inserted = 0
        self.session_updated = 0
        self.session_errors = 0

        self.table_stats = {
            table: {
                "read": 0,
                "inserted": 0,
                "updated": 0,
                "status": "Aguardando",
                "last": "-"
            }
            for table in TABLES
        }

        handler = QueueLogHandler(
            self.gui_queue
        )
        log.addHandler(handler)

        self._build_ui()

        self.after(
            150,
            self._process_gui_queue
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self._on_close
        )

        self._set_status(
            "PARADO",
            "Clique em Iniciar sincronização."
        )

    # --------------------------------------------------------
    # Construção visual
    # --------------------------------------------------------

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(
            self,
            padding=(14, 12, 14, 6)
        )
        header.grid(
            row=0,
            column=0,
            sticky="ew"
        )
        header.columnconfigure(1, weight=1)

        ttk.Label(
            header,
            text="Fiscal LocalDB → SQL Server",
            font=("Segoe UI", 17, "bold")
        ).grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.status_var = tk.StringVar()
        self.status_detail_var = tk.StringVar()

        ttk.Label(
            header,
            textvariable=self.status_var,
            font=("Segoe UI", 11, "bold")
        ).grid(
            row=0,
            column=1,
            sticky="e"
        )

        ttk.Label(
            header,
            textvariable=self.status_detail_var,
            font=("Segoe UI", 9)
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(4, 0)
        )

        summary = ttk.LabelFrame(
            self,
            text="Resumo",
            padding=10
        )
        summary.grid(
            row=1,
            column=0,
            padx=14,
            pady=(4, 8),
            sticky="ew"
        )

        for i in range(5):
            summary.columnconfigure(
                i,
                weight=1
            )

        self.read_var = tk.StringVar(value="0")
        self.insert_var = tk.StringVar(value="0")
        self.update_var = tk.StringVar(value="0")
        self.error_var = tk.StringVar(value="0")
        self.next_var = tk.StringVar(value="-")

        self._summary_item(
            summary,
            0,
            "LIDOS",
            self.read_var
        )

        self._summary_item(
            summary,
            1,
            "INSERIDOS",
            self.insert_var
        )

        self._summary_item(
            summary,
            2,
            "ATUALIZADOS",
            self.update_var
        )

        self._summary_item(
            summary,
            3,
            "ERROS",
            self.error_var
        )

        self._summary_item(
            summary,
            4,
            "PRÓXIMA VERIFICAÇÃO",
            self.next_var
        )

        controls = ttk.Frame(
            self,
            padding=(14, 0, 14, 8)
        )
        controls.grid(
            row=2,
            column=0,
            sticky="ew"
        )

        self.start_button = ttk.Button(
            controls,
            text="Iniciar sincronização",
            command=self.start_sync
        )
        self.start_button.pack(
            side="left",
            padx=(0, 8)
        )

        self.stop_button = ttk.Button(
            controls,
            text="Parar",
            command=self.stop_sync,
            state="disabled"
        )
        self.stop_button.pack(
            side="left",
            padx=(0, 8)
        )

        self.once_button = ttk.Button(
            controls,
            text="Executar 1 lote",
            command=self.run_one_cycle
        )
        self.once_button.pack(
            side="left",
            padx=(0, 8)
        )

        self.reset_button = ttk.Button(
            controls,
            text="Reiniciar varredura",
            command=self.reset_state_gui
        )
        self.reset_button.pack(
            side="left",
            padx=(0, 8)
        )

        ttk.Button(
            controls,
            text="Abrir logs",
            command=self.open_logs_folder
        ).pack(
            side="right"
        )

        notebook = ttk.Notebook(self)
        notebook.grid(
            row=3,
            column=0,
            padx=14,
            pady=(0, 14),
            sticky="nsew"
        )

        tables_tab = ttk.Frame(
            notebook,
            padding=10
        )

        logs_tab = ttk.Frame(
            notebook,
            padding=10
        )

        notebook.add(
            tables_tab,
            text="Tabelas"
        )

        notebook.add(
            logs_tab,
            text="Logs"
        )

        tables_tab.columnconfigure(
            0,
            weight=1
        )
        tables_tab.rowconfigure(
            0,
            weight=1
        )

        columns = (
            "table",
            "status",
            "read",
            "inserted",
            "updated",
            "last"
        )

        self.tree = ttk.Treeview(
            tables_tab,
            columns=columns,
            show="headings"
        )

        headings = {
            "table": "Tabela",
            "status": "Status",
            "read": "Lidos",
            "inserted": "Inseridos",
            "updated": "Atualizados",
            "last": "Última execução"
        }

        for col, title in headings.items():
            self.tree.heading(
                col,
                text=title
            )

        self.tree.column(
            "table",
            width=150
        )

        self.tree.column(
            "status",
            width=170,
            anchor="center"
        )

        self.tree.column(
            "read",
            width=100,
            anchor="e"
        )

        self.tree.column(
            "inserted",
            width=100,
            anchor="e"
        )

        self.tree.column(
            "updated",
            width=100,
            anchor="e"
        )

        self.tree.column(
            "last",
            width=165,
            anchor="center"
        )

        scroll = ttk.Scrollbar(
            tables_tab,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(
            yscrollcommand=scroll.set
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scroll.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        for table in TABLES:
            self.tree.insert(
                "",
                "end",
                iid=table,
                values=(
                    table,
                    "Aguardando",
                    0,
                    0,
                    0,
                    "-"
                )
            )

        logs_tab.columnconfigure(
            0,
            weight=1
        )
        logs_tab.rowconfigure(
            0,
            weight=1
        )

        self.log_text = ScrolledText(
            logs_tab,
            wrap="word",
            font=("Consolas", 9),
            state="disabled"
        )

        self.log_text.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        ttk.Button(
            logs_tab,
            text="Limpar visualização",
            command=self.clear_log_view
        ).grid(
            row=1,
            column=0,
            sticky="e",
            pady=(8, 0)
        )

    def _summary_item(
        self,
        parent,
        column,
        label,
        variable
    ):
        frame = ttk.Frame(parent)

        frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=8
        )

        ttk.Label(
            frame,
            text=label,
            font=("Segoe UI", 8)
        ).pack()

        ttk.Label(
            frame,
            textvariable=variable,
            font=("Segoe UI", 13, "bold")
        ).pack(
            pady=(2, 0)
        )

    # --------------------------------------------------------
    # Atualizações GUI
    # --------------------------------------------------------

    def _process_gui_queue(self):
        try:
            while True:
                item = self.gui_queue.get_nowait()
                event = item[0]

                if event == "log":
                    self._append_log(
                        item[1]
                    )

                elif event == "status":
                    self._set_status(
                        item[1],
                        item[2]
                    )

                elif event == "table":
                    self._apply_table_stats(
                        item[1],
                        item[2]
                    )

                elif event == "summary":
                    self._refresh_summary()

                elif event == "buttons":
                    self._set_running_buttons(
                        item[1]
                    )

                elif event == "next":
                    self.next_var.set(
                        item[1]
                    )

                elif event == "error":
                    messagebox.showerror(
                        item[1],
                        item[2]
                    )

                elif event == "info":
                    messagebox.showinfo(
                        item[1],
                        item[2]
                    )

        except queue.Empty:
            pass

        self.after(
            150,
            self._process_gui_queue
        )

    def _append_log(self, message):
        self.log_text.configure(
            state="normal"
        )

        self.log_text.insert(
            "end",
            message + "\n"
        )

        self.log_text.see("end")

        line_count = int(
            self.log_text.index(
                "end-1c"
            ).split(".")[0]
        )

        if line_count > 5000:
            self.log_text.delete(
                "1.0",
                "1000.0"
            )

        self.log_text.configure(
            state="disabled"
        )

    def clear_log_view(self):
        self.log_text.configure(
            state="normal"
        )

        self.log_text.delete(
            "1.0",
            "end"
        )

        self.log_text.configure(
            state="disabled"
        )

    def _set_status(
        self,
        status,
        detail=""
    ):
        self.status_var.set(status)
        self.status_detail_var.set(detail)

    def _set_running_buttons(
        self,
        running
    ):
        if running:
            self.start_button.config(
                state="disabled"
            )

            self.once_button.config(
                state="disabled"
            )

            self.reset_button.config(
                state="disabled"
            )

            self.stop_button.config(
                state="normal"
            )

        else:
            self.start_button.config(
                state="normal"
            )

            self.once_button.config(
                state="normal"
            )

            self.reset_button.config(
                state="normal"
            )

            self.stop_button.config(
                state="disabled"
            )

    def _apply_table_stats(
        self,
        table,
        stats
    ):
        self.table_stats[table].update(
            stats
        )

        s = self.table_stats[table]

        self.tree.item(
            table,
            values=(
                table,
                s["status"],
                f'{s["read"]:,}'.replace(",", "."),
                f'{s["inserted"]:,}'.replace(",", "."),
                f'{s["updated"]:,}'.replace(",", "."),
                s["last"]
            )
        )

    def _refresh_summary(self):
        self.read_var.set(
            f"{self.session_read:,}".replace(",", ".")
        )

        self.insert_var.set(
            f"{self.session_inserted:,}".replace(",", ".")
        )

        self.update_var.set(
            f"{self.session_updated:,}".replace(",", ".")
        )

        self.error_var.set(
            f"{self.session_errors:,}".replace(",", ".")
        )

    # --------------------------------------------------------
    # Preparação
    # --------------------------------------------------------

    def _prepare_sync(self):
        self.gui_queue.put((
            "status",
            "VALIDANDO",
            "Validando LocalDB e SQL Server..."
        ))

        ensure_state_table()
        validate_schema()

        if self.metadata is None:
            self.metadata = load_metadata()

        self.gui_queue.put((
            "status",
            "SINCRONIZANDO",
            "Estruturas validadas. Iniciando..."
        ))

    # --------------------------------------------------------
    # Botões
    # --------------------------------------------------------

    def start_sync(self):
        if (
            self.worker_thread
            and self.worker_thread.is_alive()
        ):
            return

        self.stop_event.clear()

        self._set_running_buttons(
            True
        )

        self.worker_thread = threading.Thread(
            target=self._worker_continuous,
            daemon=True
        )

        self.worker_thread.start()

    def stop_sync(self):
        self.stop_event.set()

        self._set_status(
            "PARANDO",
            "Aguardando o lote atual terminar com segurança..."
        )

        log.info(
            "Solicitação de parada recebida."
        )

    def run_one_cycle(self):
        if (
            self.worker_thread
            and self.worker_thread.is_alive()
        ):
            return

        self.stop_event.clear()
        self._set_running_buttons(True)

        self.worker_thread = threading.Thread(
            target=self._worker_single_cycle,
            daemon=True
        )

        self.worker_thread.start()

    def reset_state_gui(self):
        if (
            self.worker_thread
            and self.worker_thread.is_alive()
        ):
            messagebox.showwarning(
                "Sincronização ativa",
                "Pare a sincronização antes "
                "de reiniciar a varredura."
            )
            return

        answer = messagebox.askyesno(
            "Reiniciar varredura",
            "Isso NÃO apaga dados do SQL Server.\n\n"
            "Apenas zera os cursores para que todas "
            "as tabelas sejam percorridas novamente.\n\n"
            "Deseja continuar?"
        )

        if not answer:
            return

        def worker():
            try:
                ensure_state_table()
                reset_sync_state()

                self.gui_queue.put((
                    "info",
                    "Concluído",
                    "A varredura foi reiniciada.\n"
                    "Nenhum dado foi apagado."
                ))

                log.info(
                    "Cursores zerados manualmente."
                )

            except Exception as exc:
                self.gui_queue.put((
                    "error",
                    "Erro",
                    str(exc)
                ))

        threading.Thread(
            target=worker,
            daemon=True
        ).start()

    # --------------------------------------------------------
    # Execução contínua
    # --------------------------------------------------------

    def _worker_continuous(self):
        failed = False

        try:
            self._prepare_sync()

            log.info(
                "Modo contínuo iniciado. "
                "Após a carga/varredura completa, "
                "nova verificação ocorrerá a cada 30 minutos."
            )

            while not self.stop_event.is_set():
                did_work = False
                had_error = False

                for table in TABLES:
                    if self.stop_event.is_set():
                        break

                    try:
                        self.gui_queue.put((
                            "table",
                            table,
                            {
                                "status": "Lendo...",
                                "last":
                                    datetime.now().strftime(
                                        "%d/%m/%Y %H:%M:%S"
                                    )
                            }
                        ))

                        result = sync_one_table(
                            table,
                            self.metadata[table]
                        )

                        if result["skipped"]:
                            self.gui_queue.put((
                                "table",
                                table,
                                {
                                    "status":
                                        "Aguardando 30 min"
                                }
                            ))
                            continue

                        if result["rows"] > 0:
                            did_work = True

                        self.session_read += (
                            result["rows"]
                        )

                        self.session_inserted += (
                            result["inserted"]
                        )

                        self.session_updated += (
                            result["updated"]
                        )

                        current = (
                            self.table_stats[table]
                        )

                        self.gui_queue.put((
                            "table",
                            table,
                            {
                                "read":
                                    current["read"]
                                    + result["rows"],

                                "inserted":
                                    current["inserted"]
                                    + result["inserted"],

                                "updated":
                                    current["updated"]
                                    + result["updated"],

                                "status":
                                    (
                                        "Sincronizando"
                                        if result["rows"] > 0
                                        else "Varredura concluída"
                                    ),

                                "last":
                                    datetime.now().strftime(
                                        "%d/%m/%Y %H:%M:%S"
                                    )
                            }
                        ))

                        self.gui_queue.put((
                            "summary",
                        ))

                    except Exception as exc:
                        had_error = True
                        self.session_errors += 1

                        self.gui_queue.put((
                            "summary",
                        ))

                        msg = (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        )

                        try:
                            save_error(
                                table,
                                msg
                            )
                        except Exception:
                            pass

                        log.exception(
                            "%s | erro de sincronização",
                            table
                        )

                        self.gui_queue.put((
                            "table",
                            table,
                            {
                                "status": "ERRO",
                                "last":
                                    datetime.now().strftime(
                                        "%d/%m/%Y %H:%M:%S"
                                    )
                            }
                        ))

                if self.stop_event.is_set():
                    break

                # Ainda há dados sendo percorridos:
                # segue rapidamente para o próximo lote.
                if did_work:
                    self.gui_queue.put((
                        "status",
                        "SINCRONIZANDO",
                        "Carga/varredura em andamento..."
                    ))

                    self._interruptible_wait(
                        ACTIVE_LOOP_PAUSE_SECONDS
                    )

                    continue

                # Todas chegaram ao fim.
                next_seconds = (
                    self._seconds_until_next_scan()
                )

                if (
                    had_error
                    and next_seconds <= 0
                ):
                    next_seconds = (
                        ERROR_RETRY_SECONDS
                    )

                if next_seconds <= 0:
                    next_seconds = 1

                self.gui_queue.put((
                    "status",
                    "MONITORANDO",
                    "Carga concluída. "
                    "Próxima verificação em até 30 minutos."
                ))

                self._countdown_wait(
                    next_seconds
                )

        except Exception as exc:
            failed = True

            log.exception(
                "Falha ao iniciar o sincronizador."
            )

            self.gui_queue.put((
                "status",
                "ERRO",
                str(exc)
            ))

            self.gui_queue.put((
                "error",
                "Erro ao iniciar",
                str(exc)
            ))

        finally:
            self.gui_queue.put((
                "buttons",
                False
            ))

            self.gui_queue.put((
                "next",
                "-"
            ))

            if self.stop_event.is_set():
                self.gui_queue.put((
                    "status",
                    "PARADO",
                    "Sincronização interrompida."
                ))

            elif not failed:
                self.gui_queue.put((
                    "status",
                    "PARADO",
                    "Sincronização encerrada."
                ))

    # --------------------------------------------------------
    # Um lote
    # --------------------------------------------------------

    def _worker_single_cycle(self):
        try:
            self._prepare_sync()

            for table in TABLES:
                if self.stop_event.is_set():
                    break

                result = sync_one_table(
                    table,
                    self.metadata[table]
                )

                self.session_read += (
                    result["rows"]
                )

                self.session_inserted += (
                    result["inserted"]
                )

                self.session_updated += (
                    result["updated"]
                )

                current = (
                    self.table_stats[table]
                )

                self.gui_queue.put((
                    "table",
                    table,
                    {
                        "read":
                            current["read"]
                            + result["rows"],

                        "inserted":
                            current["inserted"]
                            + result["inserted"],

                        "updated":
                            current["updated"]
                            + result["updated"],

                        "status":
                            (
                                "Aguardando"
                                if result["skipped"]
                                else "Lote executado"
                            ),

                        "last":
                            datetime.now().strftime(
                                "%d/%m/%Y %H:%M:%S"
                            )
                    }
                ))

                self.gui_queue.put((
                    "summary",
                ))

            self.gui_queue.put((
                "status",
                "PARADO",
                "Execução de 1 lote concluída."
            ))

        except Exception as exc:
            self.session_errors += 1

            self.gui_queue.put((
                "summary",
            ))

            log.exception(
                "Erro na execução manual."
            )

            self.gui_queue.put((
                "status",
                "ERRO",
                str(exc)
            ))

            self.gui_queue.put((
                "error",
                "Erro",
                str(exc)
            ))

        finally:
            self.gui_queue.put((
                "buttons",
                False
            ))

    # --------------------------------------------------------
    # Próxima execução
    # --------------------------------------------------------

    def _seconds_until_next_scan(self):
        next_times = []

        for table in TABLES:
            try:
                state = get_state(table)

                dt = state.get(
                    "next_scan_at"
                )

                if dt is not None:
                    next_times.append(dt)

            except Exception:
                pass

        if not next_times:
            return 1

        earliest = min(next_times)

        seconds = int(
            (
                earliest
                - datetime.now()
            ).total_seconds()
        )

        return max(
            seconds,
            0
        )

    def _interruptible_wait(
        self,
        seconds
    ):
        end = (
            time.time()
            + max(seconds, 0)
        )

        while time.time() < end:
            if self.stop_event.is_set():
                return

            remaining = end - time.time()

            time.sleep(
                min(
                    0.2,
                    max(remaining, 0)
                )
            )

    def _countdown_wait(
        self,
        seconds
    ):
        end = (
            time.time()
            + seconds
        )

        while time.time() < end:
            if self.stop_event.is_set():
                return

            remaining = max(
                0,
                int(end - time.time())
            )

            minutes, secs = divmod(
                remaining,
                60
            )

            self.gui_queue.put((
                "next",
                f"{minutes:02d}:{secs:02d}"
            ))

            time.sleep(1)

        self.gui_queue.put((
            "next",
            "agora"
        ))

    # --------------------------------------------------------
    # Utilitários
    # --------------------------------------------------------

    def open_logs_folder(self):
        os.makedirs(
            LOG_DIR,
            exist_ok=True
        )

        try:
            os.startfile(
                LOG_DIR
            )

        except Exception as exc:
            messagebox.showerror(
                "Erro",
                f"Não foi possível abrir "
                f"a pasta de logs:\n{exc}"
            )

    def _on_close(self):
        if (
            self.worker_thread
            and self.worker_thread.is_alive()
        ):
            answer = messagebox.askyesno(
                "Sincronização ativa",
                "A sincronização está em andamento.\n\n"
                "Deseja parar e fechar?"
            )

            if not answer:
                return

            self.stop_event.set()

        self.destroy()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    app = FiscalSyncApp()
    app.mainloop()
