import pandas as pd
import urllib
from sqlalchemy import create_engine, text

SERVER = "10.0.0.254"
DATABASE = "FTECH"
USERNAME = "ftech"
PASSWORD = "ftech@1975"
TABELA = "CLIENTES_TOTVS"

arquivo = r"C:\Users\Alta Paulista\Desktop\CLIENTES_TOTVS.xlsx"

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=10.0.0.254;"
    "Database=FTECH;"
    "UID=ftech;"
    "PWD=ftech@1975;"
    "TrustServerCertificate=yes;"
)

params = urllib.parse.quote_plus(conn_str)

engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    fast_executemany=True
)

df = pd.read_excel(arquivo, dtype=str)

df.columns = df.columns.str.strip()

df = df.rename(columns={
    "CNPJ/CPF": "CNPJ_CPF",
    "N Fantasia": "N_Fantasia",
    "Ins. Estad.": "Ins_Estad",
    "C. Contabil": "C_Contabil",
    "Grp.Clientes": "Grp_Clientes",
    "E-Mail": "E_Mail",
    "Cod.Segmento": "Cod_Segmento",
    "Cod. Abics": "Cod_Abics",
    "Dt Fim Vincu": "Dt_Fim_Vincu",
    "Reg.Paraiba": "Reg_Paraiba",
    "Usa DDA": "Usa_DDA",
    "Opt. Simples": "Opt_Simples",
    "Cod.Mun.SIAF": "Cod_Mun_SIAF",
    "Rg. Simp. MT": "Rg_Simp_MT",
    "P. Carga Med": "P_Carga_Med",
    "End.Not.Form": "End_Not_Form",
    "Contr TARE ?": "Contr_TARE",
    "Aliq. Fixa": "Aliq_Fixa",
    "Destaca IE": "Destaca_IE",
    "Opt Simp Nac": "Opt_Simp_Nac",
    "Inc. Cultura": "Inc_Cultura",
    "Fil. Transf.": "Fil_Transf",
    "URL.Img.uMov": "URL_Img_uMov",
    "Tipo Camp": "Tipo_Camp",
    "Codigo.1": "Codigo_1",
    "Inovar Auto": "Inovar_Auto",
    "Desc. Membro": "Desc_Membro",
    "Outros Mun.": "Outros_Mun",
    "Cod. Terr.": "Cod_Terr",
    "Nome Territ.": "Nome_Territ",
    "Desc. Camp.": "Desc_Camp",
    "Recolhe IRRF": "Recolhe_IRRF"
})

colunas_sql = [
    "Codigo", "Loja", "CNPJ_CPF", "Nome", "N_Fantasia", "Tipo", "Municipio",
    "Regiao", "DDI", "Ins_Estad", "C_Contabil", "Grp_Clientes", "E_Mail",
    "Cod_Segmento", "Descricao", "Cod_Abics", "Dt_Fim_Vincu", "Reg_Paraiba",
    "Usa_DDA", "Opt_Simples", "Cod_Mun_SIAF", "Rg_Simp_MT", "P_Carga_Med",
    "End_Not_Form", "Contr_TARE", "Aliq_Fixa", "Destaca_IE", "Opt_Simp_Nac",
    "Inc_Cultura", "Fil_Transf", "URL_Img_uMov", "Tipo_Camp", "Codigo_1",
    "Inovar_Auto", "TPJ", "Desc_Membro", "Outros_Mun", "Cod_Terr", "Membro",
    "Nome_Territ", "Desc_Camp", "Contribuinte", "TDA", "Recolhe_IRRF"
]

for coluna in colunas_sql:
    if coluna not in df.columns:
        df[coluna] = None

df = df[colunas_sql]

df = df.where(pd.notnull(df), None)

with engine.begin() as conn:
    conn.execute(text(f"TRUNCATE TABLE dbo.{TABELA}"))

df.to_sql(
    TABELA,
    con=engine,
    schema="dbo",
    if_exists="append",
    index=False,
    chunksize=1000
)

print("Importação concluída com sucesso!")
print(f"Total de registros importados: {len(df)}")