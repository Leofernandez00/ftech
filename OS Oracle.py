import xlrd
import subprocess
import os

ARQUIVO_EXCEL = r"C:\Users\Alta Paulista\Desktop\Import_OS.xls"
ABA_EXCEL = "SQL Results"

ORACLE_USER = "ASSISTE"
ORACLE_PASSWORD = "terceiro"
ORACLE_CONEXAO = "XE"

TABELA_DESTINO = "TEMP_OSRESUM"

SQL_GERADO = r"C:\Users\Alta Paulista\Desktop\import_temp_osresum.sql"

SQLPLUS_EXE = r"\\SERVER\oraclexe\app\oracle\product\10.2.0\server\bin\sqlplus.exe"


def valor_sql(valor, tipo, book):
    if tipo == xlrd.XL_CELL_EMPTY or valor == "":
        return "NULL"

    if tipo == xlrd.XL_CELL_DATE:
        data = xlrd.xldate_as_datetime(valor, book.datemode)
        return "TO_DATE('{}','YYYY-MM-DD HH24:MI:SS')".format(data.strftime("%Y-%m-%d %H:%M:%S"))

    if tipo == xlrd.XL_CELL_NUMBER:
        if float(valor).is_integer():
            return str(int(valor))
        return str(valor).replace(",", ".")

    texto = str(valor).replace("'", "''")
    return "'" + texto + "'"


if not os.path.exists(SQLPLUS_EXE):
    SQLPLUS_EXE = r"C:\oraclexe\app\oracle\product\10.2.0\server\bin\sqlplus.exe"

if not os.path.exists(SQLPLUS_EXE):
    raise Exception("sqlplus.exe não encontrado. Verifique o caminho do Oracle XE.")


book = xlrd.open_workbook(ARQUIVO_EXCEL)
sheet = book.sheet_by_name(ABA_EXCEL)

colunas = []

for col in range(sheet.ncols):
    nome = str(sheet.cell_value(0, col)).strip().upper()
    if nome not in ["", "ROWID"]:
        colunas.append((col, nome))

with open(SQL_GERADO, "w", encoding="utf-8") as f:
    f.write("WHENEVER SQLERROR EXIT SQL.SQLCODE;\n")
    f.write("SET DEFINE OFF;\n")
    f.write("SET FEEDBACK ON;\n\n")

    nomes_colunas = ", ".join([nome for _, nome in colunas])

    for row in range(1, sheet.nrows):
        valores = []

        for col_idx, nome_coluna in colunas:
            cell = sheet.cell(row, col_idx)
            valores.append(valor_sql(cell.value, cell.ctype, book))

        if all(v == "NULL" for v in valores):
            continue

        valores_sql = ", ".join(valores)
        f.write(f"INSERT INTO {TABELA_DESTINO} ({nomes_colunas}) VALUES ({valores_sql});\n")

    f.write("\nCOMMIT;\nEXIT;\n")

print("SQL gerado em:", SQL_GERADO)

subprocess.run([
    SQLPLUS_EXE,
    f"{ORACLE_USER}/{ORACLE_PASSWORD}@{ORACLE_CONEXAO}",
    f"@{SQL_GERADO}"
], check=True)

print("IMPORTAÇÃO FINALIZADA COM SUCESSO")