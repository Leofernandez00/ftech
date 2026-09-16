"""
Arquiva dados antigos do Fiscal.io LocalDB no SQL Server.

Modos:
  diagnosticar  - testa conexoes, mostra quantidades e nao altera dados
  arquivar      - cria fiscal_archive e copia registros antigos sem apagar
  limpar        - copia, valida e depois apaga do LocalDB

Dependencia:
  py -m pip install pyodbc
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pyodbc

CORE_API_VERSION = 2


SOURCE_SERVER = r"(LocalDB)\MSSQLLocalDB"
SOURCE_DATABASE = "fiscaliodba"
TARGET_SERVER = "SERVERVPS1"
TARGET_DATABASE = "FTECH"
TARGET_USER = "ftech"
TARGET_PASSWORD = "ftech@1975"
TARGET_SCHEMA = "fiscal_archive"
TABLES = (
    "document",
    "event",
    "docitem",
    "docstatus",
    "objectchange",
    "docheadtext",
)
BATCH_SIZE = 1000
DELETE_BATCH_SIZE = 5000


def qident(value: str) -> str:
    return "[" + value.replace("]", "]]") + "]"


def choose_driver() -> str:
    available = list(pyodbc.drivers())
    for candidate in (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
    ):
        if candidate in available:
            return candidate
    raise RuntimeError(
        "Nenhum driver ODBC do SQL Server foi encontrado. "
        "Instale o Microsoft ODBC Driver 17 ou 18 for SQL Server."
    )


def source_connection(driver: str) -> pyodbc.Connection:
    text = (
        f"DRIVER={{{driver}}};"
        f"SERVER={SOURCE_SERVER};"
        f"DATABASE={SOURCE_DATABASE};"
        "Trusted_Connection=yes;"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(text, autocommit=False)


def target_connection(driver: str, password: str) -> pyodbc.Connection:
    text = (
        f"DRIVER={{{driver}}};"
        f"SERVER={TARGET_SERVER};"
        f"DATABASE={TARGET_DATABASE};"
        f"UID={TARGET_USER};"
        f"PWD={password};"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(text, autocommit=False)


def first_day_current_month() -> str:
    today = date.today()
    return f"{today.year:04d}.{today.month:02d}.01"


def date_expression(column: str) -> str:
    col = column
    return (
        "COALESCE("
        f"TRY_CONVERT(date, REPLACE(LEFT({col}, 10), '.', '-'), 23),"
        f"TRY_CONVERT(date, LEFT({col}, 10), 103),"
        f"TRY_CONVERT(date, LEFT({col}, 10), 120)"
        ")"
    )


def source_filter(table: str, alias: str = "s") -> tuple[str, list[Any]]:
    cutoff = first_day_current_month()
    doc_date = date_expression("d.dtemi")

    if table == "document":
        return f"{date_expression(f'{alias}.dtemi')} < CONVERT(date, ?, 102)", [cutoff]
    if table == "event":
        return f"{date_expression(f'{alias}.dtemi')} < CONVERT(date, ?, 102)", [cutoff]
    if table == "objectchange":
        return f"{date_expression(f'{alias}.ucdttime')} < CONVERT(date, ?, 102)", [cutoff]
    if table == "docstatus":
        return (
            "EXISTS (SELECT 1 FROM dbo.document AS d "
            f"WHERE d.chave = {alias}.chave "
            f"AND d.filial = {alias}.filial "
            f"AND {doc_date} < CONVERT(date, ?, 102))",
            [cutoff],
        )
    if table in {"docitem", "docheadtext"}:
        return (
            "EXISTS (SELECT 1 FROM dbo.document AS d "
            f"WHERE d.chave = {alias}.chave "
            f"AND {doc_date} < CONVERT(date, ?, 102))",
            [cutoff],
        )
    raise ValueError(f"Tabela sem regra de arquivamento: {table}")


def get_columns(source: pyodbc.Connection, table: str) -> list[dict[str, Any]]:
    sql = """
    SELECT
        c.column_id,
        c.name,
        ty.name AS type_name,
        c.max_length,
        c.precision,
        c.scale,
        c.is_nullable,
        c.is_identity,
        c.is_computed
    FROM sys.columns AS c
    INNER JOIN sys.types AS ty
        ON ty.user_type_id = c.user_type_id
    WHERE c.object_id = OBJECT_ID(?)
    ORDER BY c.column_id;
    """
    rows = source.cursor().execute(sql, f"dbo.{table}").fetchall()
    names = [item[0] for item in source.cursor().execute(sql, f"dbo.{table}").description]
    result = [dict(zip(names, row)) for row in rows]
    if not result:
        raise RuntimeError(f"Tabela dbo.{table} nao encontrada no LocalDB.")
    computed = [x["name"] for x in result if x["is_computed"]]
    if computed:
        raise RuntimeError(
            f"A tabela dbo.{table} possui colunas calculadas nao suportadas: {computed}"
        )
    return result


def get_primary_key(source: pyodbc.Connection, table: str) -> list[str]:
    sql = """
    SELECT c.name
    FROM sys.indexes AS i
    INNER JOIN sys.index_columns AS ic
        ON ic.object_id = i.object_id
       AND ic.index_id = i.index_id
    INNER JOIN sys.columns AS c
        ON c.object_id = ic.object_id
       AND c.column_id = ic.column_id
    WHERE i.object_id = OBJECT_ID(?)
      AND i.is_primary_key = 1
    ORDER BY ic.key_ordinal;
    """
    rows = source.cursor().execute(sql, f"dbo.{table}").fetchall()
    keys = [row[0] for row in rows]
    if not keys:
        raise RuntimeError(f"A tabela dbo.{table} nao possui chave primaria.")
    return keys


def sql_type(column: dict[str, Any]) -> str:
    name = str(column["type_name"]).lower()
    max_length = int(column["max_length"])
    precision = int(column["precision"])
    scale = int(column["scale"])

    if name in {"varchar", "char", "varbinary", "binary"}:
        size = "MAX" if max_length == -1 else str(max_length)
        return f"{name}({size})"
    if name in {"nvarchar", "nchar"}:
        size = "MAX" if max_length == -1 else str(max_length // 2)
        return f"{name}({size})"
    if name in {"decimal", "numeric"}:
        return f"{name}({precision},{scale})"
    if name in {"datetime2", "datetimeoffset", "time"}:
        return f"{name}({scale})"
    if name in {
        "bigint", "int", "smallint", "tinyint", "bit", "money", "smallmoney",
        "float", "real", "date", "datetime", "smalldatetime", "uniqueidentifier",
        "text", "ntext", "image", "xml", "sql_variant",
    }:
        return name
    if name in {"timestamp", "rowversion"}:
        raise RuntimeError("Colunas timestamp/rowversion nao sao suportadas.")
    raise RuntimeError(f"Tipo SQL nao suportado automaticamente: {name}")


def ensure_schema(target: pyodbc.Connection) -> None:
    target.cursor().execute(
        f"""
        IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = ?)
            EXEC('CREATE SCHEMA {qident(TARGET_SCHEMA)} AUTHORIZATION dbo');
        """,
        TARGET_SCHEMA,
    )
    target.commit()


def ensure_target_table(
    source: pyodbc.Connection,
    target: pyodbc.Connection,
    table: str,
) -> tuple[list[str], list[str], bool]:
    columns = get_columns(source, table)
    keys = get_primary_key(source, table)
    exists = target.cursor().execute(
        """
        SELECT COUNT(*)
        FROM sys.tables AS t
        INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        WHERE s.name = ? AND t.name = ?;
        """,
        TARGET_SCHEMA,
        table,
    ).fetchval()

    column_names = [str(x["name"]) for x in columns]
    has_identity = any(bool(x["is_identity"]) for x in columns)

    if not exists:
        definitions: list[str] = []
        for col in columns:
            identity = " IDENTITY(1,1)" if col["is_identity"] else ""
            nullable = " NULL" if col["is_nullable"] else " NOT NULL"
            definitions.append(
                f"{qident(str(col['name']))} {sql_type(col)}{identity}{nullable}"
            )
        pk_name = f"PK_fiscal_archive_{table}"
        definitions.append(
            f"CONSTRAINT {qident(pk_name)} PRIMARY KEY "
            f"({', '.join(qident(x) for x in keys)})"
        )
        create_sql = (
            f"CREATE TABLE {qident(TARGET_SCHEMA)}.{qident(table)} (\n  "
            + ",\n  ".join(definitions)
            + "\n);"
        )
        target.cursor().execute(create_sql)
        target.commit()
        logging.info("Criada tabela %s.%s.", TARGET_SCHEMA, table)
    else:
        target_columns = [
            row[0]
            for row in target.cursor().execute(
                """
                SELECT c.name
                FROM sys.columns AS c
                INNER JOIN sys.tables AS t ON t.object_id = c.object_id
                INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
                WHERE s.name = ? AND t.name = ?
                ORDER BY c.column_id;
                """,
                TARGET_SCHEMA,
                table,
            ).fetchall()
        ]
        if target_columns != column_names:
            raise RuntimeError(
                f"Estrutura divergente em {TARGET_SCHEMA}.{table}. "
                f"Origem={column_names}; destino={target_columns}"
            )
    return column_names, keys, has_identity


def candidate_count(source: pyodbc.Connection, table: str) -> int:
    where, params = source_filter(table)
    return int(
        source.cursor().execute(
            f"SELECT COUNT_BIG(*) FROM dbo.{qident(table)} AS s WHERE {where};",
            *params,
        ).fetchval()
    )


def chunks(cursor: pyodbc.Cursor, size: int) -> Iterable[list[Any]]:
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            return
        yield rows


def archive_table(
    source: pyodbc.Connection,
    target: pyodbc.Connection,
    table: str,
    all_rows: bool = False,
) -> tuple[int, int]:
    columns, keys, has_identity = ensure_target_table(source, target, table)
    cols_sql = ", ".join(qident(x) for x in columns)
    if all_rows:
        where, params = "1 = 1", []
    else:
        where, params = source_filter(table)
    source_cursor = source.cursor()
    source_cursor.execute(
        f"SELECT {cols_sql} FROM dbo.{qident(table)} AS s WHERE {where};",
        *params,
    )

    target_cursor = target.cursor()
    target_cursor.execute(
        "IF OBJECT_ID('tempdb..#stage') IS NOT NULL DROP TABLE #stage;"
    )
    target_cursor.execute(
        f"SELECT TOP (0) {cols_sql} INTO #stage FROM "
        f"{qident(TARGET_SCHEMA)}.{qident(table)};"
    )
    placeholders = ", ".join("?" for _ in columns)
    insert_stage = f"INSERT INTO #stage ({cols_sql}) VALUES ({placeholders});"
    key_match = " AND ".join(
        f"t.{qident(key)} = s.{qident(key)}" for key in keys
    )
    update_columns = [name for name in columns if name not in keys]
    update_set = ", ".join(
        f"t.{qident(name)} = s.{qident(name)}" for name in update_columns
    )

    read_total = 0
    inserted_total = 0
    for rows in chunks(source_cursor, BATCH_SIZE):
        target_cursor.execute("TRUNCATE TABLE #stage;")
        # O modo fast_executemany do ODBC 18 pode calcular buffers menores
        # para alguns campos varchar extensos do Fiscal.io e gerar HY000
        # "String data, right truncation". O modo convencional e mais lento,
        # mas preserva integralmente esses textos.
        target_cursor.fast_executemany = False
        target_cursor.executemany(insert_stage, rows)

        # Sincroniza alteracoes feitas pelo Fiscal.io em registros que ja
        # existem no arquivo historico.
        if update_set:
            target_cursor.execute(
                f"""
                UPDATE t
                SET {update_set}
                FROM {qident(TARGET_SCHEMA)}.{qident(table)} AS t
                INNER JOIN #stage AS s ON {key_match};
                """
            )

        if has_identity:
            target_cursor.execute(
                f"SET IDENTITY_INSERT {qident(TARGET_SCHEMA)}.{qident(table)} ON;"
            )
        target_cursor.execute(
            f"""
            INSERT INTO {qident(TARGET_SCHEMA)}.{qident(table)} ({cols_sql})
            SELECT {', '.join('s.' + qident(x) for x in columns)}
            FROM #stage AS s
            WHERE NOT EXISTS (
                SELECT 1
                FROM {qident(TARGET_SCHEMA)}.{qident(table)} AS t
                WHERE {key_match}
            );
            """
        )
        # rowcount deve ser lido imediatamente. Alguns drivers ODBC nao
        # expõem corretamente um SELECT @@ROWCOUNT enviado no mesmo lote.
        inserted = max(int(target_cursor.rowcount), 0)
        if has_identity:
            target_cursor.execute(
                f"SET IDENTITY_INSERT {qident(TARGET_SCHEMA)}.{qident(table)} OFF;"
            )

        missing = int(
            target_cursor.execute(
                f"""
                SELECT COUNT_BIG(*)
                FROM #stage AS s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM {qident(TARGET_SCHEMA)}.{qident(table)} AS t
                    WHERE {key_match}
                );
                """
            ).fetchval()
        )
        if missing:
            target.rollback()
            raise RuntimeError(
                f"Validacao falhou em {table}: {missing} linhas do lote "
                "nao foram encontradas no destino."
            )
        target.commit()
        read_total += len(rows)
        inserted_total += inserted
        logging.info(
            "%s: %s lidas, %s novas no destino.",
            table,
            f"{read_total:,}",
            f"{inserted_total:,}",
        )

    target_cursor.execute(
        "IF OBJECT_ID('tempdb..#stage') IS NOT NULL DROP TABLE #stage;"
    )
    target.commit()
    return read_total, inserted_total


def invalid_date_count(source: pyodbc.Connection, table: str) -> int:
    if table == "document":
        column = "dtemi"
    elif table == "event":
        column = "dtemi"
    elif table == "objectchange":
        column = "ucdttime"
    else:
        return 0
    expression = date_expression(qident(column))
    return int(
        source.cursor().execute(
            f"""
            SELECT COUNT_BIG(*)
            FROM dbo.{qident(table)}
            WHERE {qident(column)} IS NOT NULL
              AND LTRIM(RTRIM({qident(column)})) <> ''
              AND {expression} IS NULL;
            """
        ).fetchval()
    )


def diagnose(source: pyodbc.Connection, target: pyodbc.Connection) -> None:
    source_version = source.cursor().execute("SELECT @@VERSION;").fetchval()
    target_version = target.cursor().execute("SELECT @@VERSION;").fetchval()
    logging.info("Origem conectada: %s", str(source_version).splitlines()[0])
    logging.info("Destino conectado: %s", str(target_version).splitlines()[0])
    logging.info("Corte: tudo anterior a %s", first_day_current_month())
    ensure_schema(target)

    for table in TABLES:
        ensure_target_table(source, target, table)
        total = candidate_count(source, table)
        invalid = invalid_date_count(source, table)
        logging.info(
            "%-15s candidatos=%s datas_invalidas=%s",
            table,
            f"{total:,}",
            f"{invalid:,}",
        )


def delete_table(source: pyodbc.Connection, table: str) -> int:
    where, params = source_filter(table)
    deleted_total = 0
    while True:
        cursor = source.cursor()
        cursor.execute(
            f"""
            DELETE TOP ({DELETE_BATCH_SIZE}) s
            FROM dbo.{qident(table)} AS s
            WHERE {where};
            """,
            *params,
        )
        # Leia diretamente o total afetado para evitar o problema de múltiplos
        # resultados do ODBC 18 observado durante a etapa de cópia.
        deleted = max(int(cursor.rowcount), 0)
        source.commit()
        deleted_total += deleted
        if deleted:
            logging.info("%s: %s removidas.", table, f"{deleted_total:,}")
        if deleted == 0:
            break
    return deleted_total


def shrink_source(source: pyodbc.Connection, target_mb: int) -> None:
    logical_name = source.cursor().execute(
        "SELECT name FROM sys.database_files WHERE type_desc = 'ROWS';"
    ).fetchval()
    source.cursor().execute("CHECKPOINT;")
    source.commit()
    source.cursor().execute(
        f"DBCC SHRINKFILE ({qident(str(logical_name))}, {int(target_mb)});"
    )
    source.commit()
    size = source.cursor().execute(
        """
        SELECT CAST(size * 8.0 / 1024 AS decimal(18,2))
        FROM sys.database_files
        WHERE type_desc = 'ROWS';
        """
    ).fetchval()
    logging.info("Tamanho final do MDF: %s MB.", size)


def archive_all(
    source: pyodbc.Connection,
    target: pyodbc.Connection,
    start_table: str | None = None,
    all_rows: bool = False,
) -> dict[str, tuple[int, int]]:
    ensure_schema(target)
    summary: dict[str, tuple[int, int]] = {}
    selected_tables = list(TABLES)
    if start_table:
        selected_tables = selected_tables[selected_tables.index(start_table):]
        logging.info("Retomando o arquivamento a partir de %s.", start_table)
    for table in selected_tables:
        logging.info("Arquivando %s...", table)
        summary[table] = archive_table(
            source, target, table, all_rows=all_rows
        )
    return summary


def configure_logging() -> Path:
    folder = Path(__file__).resolve().parent / "logs"
    folder.mkdir(exist_ok=True)
    path = folder / f"arquivar_fiscalio_{date.today():%Y%m%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arquiva dados antigos do Fiscal.io no SQL Server."
    )
    parser.add_argument(
        "modo",
        choices=("diagnosticar", "arquivar", "limpar"),
        help="Operacao que sera executada.",
    )
    parser.add_argument(
        "--shrink",
        type=int,
        metavar="MB",
        help="Depois da limpeza, tenta reduzir o MDF para este tamanho.",
    )
    parser.add_argument(
        "--iniciar-em",
        choices=TABLES,
        help="No modo arquivar, retoma a copia a partir desta tabela.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log_path = configure_logging()
    # A variavel de ambiente, quando configurada, tem prioridade sobre a
    # senha salva abaixo. Isso permite trocar a senha sem editar o arquivo.
    password = os.environ.get("FTECH_SQL_PASSWORD", TARGET_PASSWORD)

    driver = choose_driver()
    logging.info("Driver: %s", driver)
    logging.info("Log: %s", log_path)

    source = source_connection(driver)
    target = target_connection(driver, password)
    try:
        if args.modo == "diagnosticar":
            diagnose(source, target)
            logging.info("Diagnostico concluido. Nenhum dado foi apagado.")
            return 0

        if args.iniciar_em and args.modo != "arquivar":
            raise RuntimeError(
                "--iniciar-em somente pode ser usado no modo arquivar."
            )
        summary = archive_all(source, target, args.iniciar_em)
        logging.info("Copia e validacao concluidas:")
        for table, (read_count, inserted_count) in summary.items():
            logging.info(
                "  %-15s lidas=%s novas=%s",
                table,
                f"{read_count:,}",
                f"{inserted_count:,}",
            )

        if args.modo == "arquivar":
            logging.info("Modo arquivar: nenhum registro foi apagado do LocalDB.")
            return 0

        print()
        print("ATENCAO: a proxima etapa apagara do LocalDB os dados ja arquivados.")
        print("O Fiscal.io deve estar completamente fechado.")
        confirmation = input('Digite exatamente "CONFIRMO A LIMPEZA": ').strip()
        if confirmation != "CONFIRMO A LIMPEZA":
            logging.warning("Limpeza cancelada pelo usuario.")
            return 2

        # Filhas logicas primeiro; document sempre por ultimo.
        delete_order = (
            "docheadtext",
            "docitem",
            "docstatus",
            "event",
            "objectchange",
            "document",
        )
        for table in delete_order:
            logging.info("Removendo dados antigos de %s...", table)
            delete_table(source, table)

        if args.shrink:
            shrink_source(source, args.shrink)
        logging.info("Arquivamento e limpeza concluidos.")
        return 0
    except Exception:
        source.rollback()
        target.rollback()
        logging.exception("Falha na execucao.")
        return 1
    finally:
        target.close()
        source.close()



# ================= INTERFACE VISUAL =================

import logging
import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

class QueueLogHandler(logging.Handler):
    def __init__(self, output_queue: queue.Queue[str]) -> None:
        super().__init__()
        self.output_queue = output_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.output_queue.put_nowait(self.format(record))
        except Exception:
            pass


class FiscalArchiveApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fiscal.io - Arquivamento SQL Server")
        self.geometry("980x650")
        self.minsize(820, 520)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker_active = False
        self.auto_enabled = False
        self.next_run: datetime | None = None
        self.after_id: str | None = None

        self.interval_var = tk.IntVar(value=15)
        self.status_var = tk.StringVar(value="Parado")
        self.next_var = tk.StringVar(value="Próxima execução: não agendada")

        self._build_ui()
        self._configure_logging()
        self.after(150, self._drain_logs)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logging.info("Aplicativo iniciado.")
        logging.info(
            "Origem: %s / %s", SOURCE_SERVER, SOURCE_DATABASE
        )
        logging.info(
            "Destino: %s / %s / esquema %s",
            TARGET_SERVER,
            TARGET_DATABASE,
            TARGET_SCHEMA,
        )

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")

        ttk.Label(
            header,
            text="Fiscal.io → SQL Server",
            font=("Segoe UI", 17, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                "Sincroniza as 6 tabelas a cada ciclo. "
                "A limpeza de meses anteriores é separada."
            ),
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(3, 10))

        ttk.Label(header, text="Intervalo (minutos):").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Spinbox(
            header,
            from_=1,
            to=1440,
            width=7,
            textvariable=self.interval_var,
        ).grid(row=2, column=1, sticky="w", padx=(6, 18))

        self.start_button = ttk.Button(
            header, text="Iniciar automático", command=self._start_auto
        )
        self.start_button.grid(row=2, column=2, padx=4)

        self.stop_button = ttk.Button(
            header,
            text="Parar automático",
            command=self._stop_auto,
            state="disabled",
        )
        self.stop_button.grid(row=2, column=3, padx=4)

        self.sync_button = ttk.Button(
            header, text="Sincronizar agora", command=self._sync_now
        )
        self.sync_button.grid(row=2, column=4, padx=4)

        self.diag_button = ttk.Button(
            header, text="Diagnóstico", command=self._diagnose
        )
        self.diag_button.grid(row=2, column=5, padx=4)

        info = ttk.LabelFrame(self, text="Status", padding=10)
        info.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(
            info, textvariable=self.status_var, font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        ttk.Label(info, textvariable=self.next_var).pack(side="right")

        actions = ttk.Frame(self, padding=(12, 0, 12, 8))
        actions.pack(fill="x")
        self.clean_button = ttk.Button(
            actions,
            text="Arquivar e limpar meses anteriores",
            command=self._clean_old,
        )
        self.clean_button.pack(side="left")
        ttk.Label(
            actions,
            text=(
                "Esta ação mantém no LocalDB somente o mês corrente "
                "e tenta reduzir o MDF para 90 MB."
            ),
        ).pack(side="left", padx=12)

        log_frame = ttk.LabelFrame(self, text="Log de execução", padding=8)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

    def _configure_logging(self) -> None:
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
        queue_handler = QueueLogHandler(self.log_queue)
        queue_handler.setFormatter(formatter)
        root.addHandler(queue_handler)

        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / f"fiscalio_gui_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    def _drain_logs(self) -> None:
        changed = False
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.configure(state="disabled")
            changed = True
        if changed:
            self.log_text.see("end")
        self.after(150, self._drain_logs)

    def _set_busy(self, busy: bool, status: str = "Parado") -> None:
        self.worker_active = busy
        self.status_var.set(status)
        normal_state = "disabled" if busy else "normal"
        self.sync_button.configure(state=normal_state)
        self.diag_button.configure(state=normal_state)
        self.clean_button.configure(state=normal_state)

    def _connections(self):
        driver = choose_driver()
        logging.info("Driver: %s", driver)
        source = source_connection(driver)
        target = target_connection(driver, TARGET_PASSWORD)
        return source, target

    def _run_worker(self, action: str) -> None:
        if self.worker_active:
            return
        self._set_busy(True, f"Executando: {action}")
        threading.Thread(
            target=self._worker_body, args=(action,), daemon=True
        ).start()

    def _worker_body(self, action: str) -> None:
        source = target = None
        success = False
        try:
            source, target = self._connections()
            if action == "diagnóstico":
                diagnose(source, target)
                logging.info("Diagnóstico concluído.")
            elif action == "sincronização":
                logging.info("Iniciando sincronização completa...")
                summary = archive_all(
                    source, target, all_rows=True
                )
                for table, (read_count, inserted_count) in summary.items():
                    logging.info(
                        "%-15s lidas=%s novas=%s",
                        table,
                        f"{read_count:,}",
                        f"{inserted_count:,}",
                    )
                logging.info("Sincronização concluída e validada.")
            elif action == "limpeza":
                logging.info(
                    "Sincronizando tudo antes de iniciar a limpeza..."
                )
                archive_all(source, target, all_rows=True)
                for table in (
                    "docheadtext",
                    "docitem",
                    "docstatus",
                    "event",
                    "objectchange",
                    "document",
                ):
                    logging.info("Limpando dados antigos de %s...", table)
                    delete_table(source, table)
                shrink_source(source, 90)
                logging.info("Limpeza concluída.")
            success = True
        except Exception:
            if source is not None:
                source.rollback()
            if target is not None:
                target.rollback()
            logging.exception("Falha na operação %s.", action)
        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()
            self.after(0, self._worker_finished, action, success)

    def _worker_finished(self, action: str, success: bool) -> None:
        self._set_busy(False, "Concluído" if success else "Erro")
        if action == "limpeza":
            message = (
                "Arquivamento e limpeza concluídos."
                if success
                else "A limpeza apresentou erro. Consulte o log."
            )
            (messagebox.showinfo if success else messagebox.showerror)(
                "Fiscal.io", message
            )
        if self.auto_enabled:
            self._schedule_next()

    def _diagnose(self) -> None:
        self._run_worker("diagnóstico")

    def _sync_now(self) -> None:
        self._run_worker("sincronização")

    def _clean_old(self) -> None:
        if self.worker_active:
            return
        confirmed = messagebox.askyesno(
            "Confirmar limpeza",
            (
                "O Fiscal.io deve estar fechado.\n\n"
                "O programa sincronizará e validará os dados antes de "
                "excluir do LocalDB tudo que for anterior ao mês atual.\n\n"
                "Deseja continuar?"
            ),
            icon="warning",
        )
        if confirmed:
            self._run_worker("limpeza")

    def _start_auto(self) -> None:
        try:
            interval = int(self.interval_var.get())
            if interval < 1:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror(
                "Intervalo inválido", "Informe pelo menos 1 minuto."
            )
            return
        self.auto_enabled = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        logging.info("Modo automático iniciado: intervalo de %s minutos.", interval)
        self._run_worker("sincronização")

    def _stop_auto(self) -> None:
        self.auto_enabled = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.next_run = None
        self.next_var.set("Próxima execução: não agendada")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        logging.info("Modo automático parado.")

    def _schedule_next(self) -> None:
        if not self.auto_enabled:
            return
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        interval = max(int(self.interval_var.get()), 1)
        self.next_run = datetime.now() + timedelta(minutes=interval)
        self.next_var.set(
            f"Próxima execução: {self.next_run:%d/%m/%Y %H:%M:%S}"
        )
        self.after_id = self.after(
            interval * 60 * 1000, self._automatic_tick
        )

    def _automatic_tick(self) -> None:
        self.after_id = None
        if self.auto_enabled:
            self._run_worker("sincronização")

    def _on_close(self) -> None:
        if self.worker_active:
            messagebox.showwarning(
                "Operação em andamento",
                "Aguarde a operação terminar antes de fechar o programa.",
            )
            return
        self.destroy()


if __name__ == "__main__":
    FiscalArchiveApp().mainloop()