import psycopg2

try:
    conn = psycopg2.connect(
        dbname="restricoes",
        user="postgres",
        password="postgres",
        host="187.17.206.167",
        port="5432"
    )
    print("Conexão bem-sucedida!")
    conn.close()
except Exception as e:
    print(f"Erro ao conectar: {e}")
