import os
import time
import threading
import logging
import requests
import pyodbc
import tkinter as tk

from tkinter import ttk, messagebox
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv


load_dotenv()

API_KEY = (os.getenv("MOBI7_API_KEY") or "").strip()
BASE_URL = "https://developer.mobi7.io"

SQL_SERVER = (os.getenv("SQL_SERVER") or "").strip()
SQL_PORT = (os.getenv("SQL_PORT") or "1433").strip()
SQL_DATABASE = (os.getenv("SQL_DATABASE") or "FTECH").strip()
SQL_USER = (os.getenv("SQL_USER") or "").strip()
SQL_PASSWORD = (os.getenv("SQL_PASSWORD") or "").strip()

INTERVALO_HORAS = int(os.getenv("INTERVALO_HORAS", "2"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "100"))

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=f"logs/mobi7_{datetime.now().strftime('%Y%m%d')}.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def utc_iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(value):
    if not value:
        return None
    return str(value).replace("T", " ").replace("Z", "").split(".")[0]


def get_conn():
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SQL_SERVER},{SQL_PORT};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=no;"
        "TrustServerCertificate=yes;",
        timeout=20
    )


def api_get(endpoint, params=None):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "api-key": API_KEY
    }

    response = requests.get(
        BASE_URL + endpoint,
        headers=headers,
        params=params or {},
        timeout=60
    )

    if response.status_code in (401, 403):
        raise Exception(f"API não autorizada. Status {response.status_code}: {response.text}")

    if response.status_code == 404:
        return None

    if response.status_code >= 500:
        raise Exception(
            f"Erro {response.status_code} na API Mobi7. "
            f"URL: {response.url}. Resposta: {response.text}"
        )

    response.raise_for_status()
    return response.json()


def get_paginated(endpoint, params=None):
    page = 1
    todos = []

    while True:
        parametros = dict(params or {})
        parametros["pageSize"] = PAGE_SIZE
        parametros["pageNumber"] = page

        dados = api_get(endpoint, parametros)

        if not dados:
            break

        items = dados.get("items", [])

        if not items:
            break

        todos.extend(items)

        total = dados.get("total", len(todos))

        if len(todos) >= total:
            break

        page += 1

    return todos


def criar_tabelas(conn):
    cursor = conn.cursor()

    cursor.execute("""
    IF OBJECT_ID('dbo.MOBI7_VEICULOS', 'U') IS NULL
    CREATE TABLE dbo.MOBI7_VEICULOS (
        id NVARCHAR(100) NOT NULL PRIMARY KEY,
        plate NVARCHAR(30),
        vin NVARCHAR(100),
        nickname NVARCHAR(255),
        description NVARCHAR(500),
        driver NVARCHAR(255),
        brand NVARCHAR(100),
        color NVARCHAR(100),
        model NVARCHAR(100),
        situation NVARCHAR(100),
        data_importacao DATETIME2 DEFAULT SYSDATETIME()
    )
    """)

    cursor.execute("""
    IF OBJECT_ID('dbo.MOBI7_VEICULOS_GRUPOS', 'U') IS NULL
    CREATE TABLE dbo.MOBI7_VEICULOS_GRUPOS (
        vehicle_id NVARCHAR(100) NOT NULL,
        group_id NVARCHAR(100) NOT NULL,
        group_name NVARCHAR(255),
        data_importacao DATETIME2 DEFAULT SYSDATETIME(),
        CONSTRAINT PK_MOBI7_VEICULOS_GRUPOS PRIMARY KEY (vehicle_id, group_id)
    )
    """)

    cursor.execute("""
    IF OBJECT_ID('dbo.MOBI7_PERCURSOS', 'U') IS NULL
    CREATE TABLE dbo.MOBI7_PERCURSOS (
        vehicle_id NVARCHAR(100) NOT NULL,
        driver_name NVARCHAR(255),
        driver_ibutton NVARCHAR(100),
        distance FLOAT,
        totalTime INT,
        maxSpeed INT,
        lastProcessed DATETIME2,
        start_date DATETIME2 NOT NULL,
        start_lat FLOAT,
        start_lng FLOAT,
        start_odometer FLOAT,
        end_date DATETIME2 NOT NULL,
        end_lat FLOAT,
        end_lng FLOAT,
        end_odometer FLOAT,
        data_importacao DATETIME2 DEFAULT SYSDATETIME(),
        CONSTRAINT PK_MOBI7_PERCURSOS PRIMARY KEY (vehicle_id, start_date, end_date)
    )
    """)

    cursor.execute("""
    IF OBJECT_ID('dbo.MOBI7_OFENSAS', 'U') IS NULL
    CREATE TABLE dbo.MOBI7_OFENSAS (
        vehicle_id NVARCHAR(100) NOT NULL,
        drivername NVARCHAR(255),
        type NVARCHAR(100) NOT NULL,
        speed INT,
        duration INT,
        start_date DATETIME2 NOT NULL,
        start_lat FLOAT,
        start_lng FLOAT,
        data_importacao DATETIME2 DEFAULT SYSDATETIME(),
        CONSTRAINT PK_MOBI7_OFENSAS PRIMARY KEY (vehicle_id, type, start_date)
    )
    """)

    cursor.execute("""
    IF OBJECT_ID('dbo.MOBI7_ULTIMA_POSICAO', 'U') IS NULL
    CREATE TABLE dbo.MOBI7_ULTIMA_POSICAO (
        vehicle_id NVARCHAR(100) NOT NULL PRIMARY KEY,
        iButton NVARCHAR(100),
        date DATETIME2,
        arrivalDate DATETIME2,
        speed INT,
        ignition BIT,
        block BIT,
        odometer FLOAT,
        hourmeter FLOAT,
        vehicleBattery FLOAT,
        lat FLOAT,
        lng FLOAT,
        direction INT,
        data_importacao DATETIME2 DEFAULT SYSDATETIME()
    )
    """)

    cursor.execute("""
    IF OBJECT_ID('dbo.MOBI7_HISTORICO_POSICOES', 'U') IS NULL
    CREATE TABLE dbo.MOBI7_HISTORICO_POSICOES (
        vehicle_id NVARCHAR(100) NOT NULL,
        iButton NVARCHAR(100),
        date DATETIME2 NOT NULL,
        arrivalDate DATETIME2,
        speed INT,
        ignition BIT,
        block BIT,
        odometer FLOAT,
        hourmeter FLOAT,
        vehicleBattery FLOAT,
        lat FLOAT,
        lng FLOAT,
        direction INT,
        data_importacao DATETIME2 DEFAULT SYSDATETIME(),
        CONSTRAINT PK_MOBI7_HISTORICO_POSICOES PRIMARY KEY (vehicle_id, date)
    )
    """)

    conn.commit()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Importador Mobi7 → SQL Server")
        self.root.geometry("1000x700")

        self.executando = False
        self.proxima_execucao = datetime.now() + timedelta(seconds=10)

        ttk.Label(root, text="Importador Mobi7 → SQL Server", font=("Arial", 14, "bold")).pack(pady=8)

        self.lbl_api = ttk.Label(root, text="API: Aguardando")
        self.lbl_api.pack(anchor="w", padx=10)

        self.lbl_sql = ttk.Label(root, text="SQL Server: Aguardando")
        self.lbl_sql.pack(anchor="w", padx=10)

        self.lbl_ultima = ttk.Label(root, text="Última sincronização: Nunca")
        self.lbl_ultima.pack(anchor="w", padx=10)

        self.lbl_proxima = ttk.Label(root, text="Próxima sincronização: -")
        self.lbl_proxima.pack(anchor="w", padx=10)

        self.progress = ttk.Progressbar(root, orient="horizontal", length=960, mode="determinate")
        self.progress.pack(padx=10, pady=10)

        frame = ttk.Frame(root)
        frame.pack(pady=5)

        self.btn_sinc = ttk.Button(frame, text="Sincronizar Agora", command=self.sincronizar_manual)
        self.btn_sinc.grid(row=0, column=0, padx=5)

        self.btn_teste = ttk.Button(frame, text="Testar Conexões", command=self.testar_conexoes)
        self.btn_teste.grid(row=0, column=1, padx=5)

        self.btn_sair = ttk.Button(frame, text="Sair", command=self.sair)
        self.btn_sair.grid(row=0, column=2, padx=5)

        self.log_text = tk.Text(root, height=32)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.log("Sistema iniciado.")
        self.log(f"PAGE_SIZE configurado: {PAGE_SIZE}")
        self.log(f"Intervalo automático: {INTERVALO_HORAS} hora(s).")

        threading.Thread(target=self.loop_automatico, daemon=True).start()

    def log(self, msg):
        linha = f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} - {msg}"
        self.log_text.insert(tk.END, linha + "\n")
        self.log_text.see(tk.END)
        logging.info(msg)
        self.root.update_idletasks()

    def progresso(self, valor):
        self.progress["value"] = valor
        self.root.update_idletasks()

    def testar_conexoes(self):
        threading.Thread(target=self._testar_conexoes, daemon=True).start()

    def _testar_conexoes(self):
        try:
            self.log("Testando API...")
            teste = api_get("/vehicles/v1", {"pageSize": 1, "pageNumber": 1})
            total = teste.get("total", 0)
            self.lbl_api.config(text=f"API: Conectada - veículos encontrados: {total}")
            self.log(f"API conectada. Total de veículos: {total}")
        except Exception as e:
            self.lbl_api.config(text="API: Erro")
            self.log(f"Erro API: {e}")

        try:
            self.log("Testando SQL Server...")
            conn = get_conn()
            criar_tabelas(conn)
            conn.close()
            self.lbl_sql.config(text="SQL Server: Conectado")
            self.log("SQL Server conectado e tabelas verificadas.")
        except Exception as e:
            self.lbl_sql.config(text="SQL Server: Erro")
            self.log(f"Erro SQL Server: {e}")

    def importar_veiculos(self, conn):
        self.log("Importando veículos...")
        veiculos = get_paginated("/vehicles/v1")

        cursor = conn.cursor()

        for v in veiculos:
            cursor.execute("""
                MERGE dbo.MOBI7_VEICULOS AS T
                USING (SELECT ? AS id) AS S
                ON T.id = S.id
                WHEN MATCHED THEN UPDATE SET
                    plate=?, vin=?, nickname=?, description=?, driver=?,
                    brand=?, color=?, model=?, situation=?,
                    data_importacao=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (id, plate, vin, nickname, description, driver, brand, color, model, situation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            v.get("id"),
            v.get("plate"), v.get("vin"), v.get("nickname"), v.get("description"),
            v.get("driver"), v.get("brand"), v.get("color"), v.get("model"), v.get("situation"),
            v.get("id"), v.get("plate"), v.get("vin"), v.get("nickname"), v.get("description"),
            v.get("driver"), v.get("brand"), v.get("color"), v.get("model"), v.get("situation"))

            for g in v.get("groups", []) or []:
                cursor.execute("""
                    MERGE dbo.MOBI7_VEICULOS_GRUPOS AS T
                    USING (SELECT ? AS vehicle_id, ? AS group_id) AS S
                    ON T.vehicle_id = S.vehicle_id AND T.group_id = S.group_id
                    WHEN MATCHED THEN UPDATE SET
                        group_name=?, data_importacao=SYSDATETIME()
                    WHEN NOT MATCHED THEN INSERT
                        (vehicle_id, group_id, group_name)
                    VALUES (?, ?, ?);
                """,
                v.get("id"), g.get("id"),
                g.get("name"),
                v.get("id"), g.get("id"), g.get("name"))

        conn.commit()
        self.log(f"Veículos importados: {len(veiculos)}")
        return veiculos

    def importar_percursos(self, conn, vehicle_id, inicio, fim):
        items = get_paginated(
            f"/trips/v1/vehicles/{vehicle_id}",
            {
                "startDate": utc_iso(inicio),
                "endDate": utc_iso(fim)
            }
        )

        cursor = conn.cursor()

        for item in items:
            driver = item.get("driver") or {}
            start = item.get("startPosition") or {}
            end = item.get("endPosition") or {}

            start_date = parse_date(start.get("date"))
            end_date = parse_date(end.get("date"))

            if not start_date or not end_date:
                continue

            cursor.execute("""
                MERGE dbo.MOBI7_PERCURSOS AS T
                USING (SELECT ? AS vehicle_id, ? AS start_date, ? AS end_date) AS S
                ON T.vehicle_id = S.vehicle_id
                AND T.start_date = S.start_date
                AND T.end_date = S.end_date
                WHEN MATCHED THEN UPDATE SET
                    driver_name=?, driver_ibutton=?, distance=?, totalTime=?, maxSpeed=?,
                    lastProcessed=?, start_lat=?, start_lng=?, start_odometer=?,
                    end_lat=?, end_lng=?, end_odometer=?, data_importacao=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (vehicle_id, driver_name, driver_ibutton, distance, totalTime, maxSpeed,
                     lastProcessed, start_date, start_lat, start_lng, start_odometer,
                     end_date, end_lat, end_lng, end_odometer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            vehicle_id, start_date, end_date,
            driver.get("name"), driver.get("iButton"), item.get("distance"),
            item.get("totalTime"), item.get("maxSpeed"), parse_date(item.get("lastProcessed")),
            start.get("lat"), start.get("lng"), start.get("odometer"),
            end.get("lat"), end.get("lng"), end.get("odometer"),
            vehicle_id, driver.get("name"), driver.get("iButton"), item.get("distance"),
            item.get("totalTime"), item.get("maxSpeed"), parse_date(item.get("lastProcessed")),
            start_date, start.get("lat"), start.get("lng"), start.get("odometer"),
            end_date, end.get("lat"), end.get("lng"), end.get("odometer"))

        conn.commit()
        return len(items)

    def importar_ofensas(self, conn, vehicle_id, inicio, fim):
        items = get_paginated(
            f"/behaviors/v1/vehicles/{vehicle_id}",
            {
                "startDate": utc_iso(inicio),
                "endDate": utc_iso(fim)
            }
        )

        cursor = conn.cursor()

        for item in items:
            start = item.get("startPosition") or {}
            start_date = parse_date(start.get("date"))

            if not start_date or not item.get("type"):
                continue

            cursor.execute("""
                MERGE dbo.MOBI7_OFENSAS AS T
                USING (SELECT ? AS vehicle_id, ? AS type, ? AS start_date) AS S
                ON T.vehicle_id = S.vehicle_id
                AND T.type = S.type
                AND T.start_date = S.start_date
                WHEN MATCHED THEN UPDATE SET
                    drivername=?, speed=?, duration=?, start_lat=?, start_lng=?,
                    data_importacao=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (vehicle_id, drivername, type, speed, duration, start_date, start_lat, start_lng)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            vehicle_id, item.get("type"), start_date,
            item.get("drivername"), item.get("speed"), item.get("duration"),
            start.get("lat"), start.get("lng"),
            vehicle_id, item.get("drivername"), item.get("type"), item.get("speed"),
            item.get("duration"), start_date, start.get("lat"), start.get("lng"))

        conn.commit()
        return len(items)

    def importar_ultima_posicao(self, conn, vehicle_id):
        item = api_get(f"/positions/v1/vehicles/{vehicle_id}/last")

        if not item:
            return 0

        coord = item.get("coordinate") or {}
        cursor = conn.cursor()

        cursor.execute("""
            MERGE dbo.MOBI7_ULTIMA_POSICAO AS T
            USING (SELECT ? AS vehicle_id) AS S
            ON T.vehicle_id = S.vehicle_id
            WHEN MATCHED THEN UPDATE SET
                iButton=?, date=?, arrivalDate=?, speed=?, ignition=?, block=?,
                odometer=?, hourmeter=?, vehicleBattery=?, lat=?, lng=?, direction=?,
                data_importacao=SYSDATETIME()
            WHEN NOT MATCHED THEN INSERT
                (vehicle_id, iButton, date, arrivalDate, speed, ignition, block,
                 odometer, hourmeter, vehicleBattery, lat, lng, direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        vehicle_id,
        item.get("iButton"), parse_date(item.get("date")), parse_date(item.get("arrivalDate")),
        item.get("speed"), item.get("ignition"), item.get("block"),
        item.get("odometer"), item.get("hourmeter"), item.get("vehicleBattery"),
        coord.get("lat"), coord.get("lng"), item.get("direction"),
        vehicle_id,
        item.get("iButton"), parse_date(item.get("date")), parse_date(item.get("arrivalDate")),
        item.get("speed"), item.get("ignition"), item.get("block"),
        item.get("odometer"), item.get("hourmeter"), item.get("vehicleBattery"),
        coord.get("lat"), coord.get("lng"), item.get("direction"))

        conn.commit()
        return 1

    def importar_historico(self, conn, vehicle_id, inicio, fim):
        items = get_paginated(
            f"/positions/v1/vehicles/{vehicle_id}/history",
            {
                "startDate": utc_iso(inicio),
                "endDate": utc_iso(fim)
            }
        )

        cursor = conn.cursor()

        for item in items:
            coord = item.get("coordinate") or {}
            data_posicao = parse_date(item.get("date"))

            if not data_posicao:
                continue

            cursor.execute("""
                MERGE dbo.MOBI7_HISTORICO_POSICOES AS T
                USING (SELECT ? AS vehicle_id, ? AS date) AS S
                ON T.vehicle_id = S.vehicle_id AND T.date = S.date
                WHEN MATCHED THEN UPDATE SET
                    iButton=?, arrivalDate=?, speed=?, ignition=?, block=?,
                    odometer=?, hourmeter=?, vehicleBattery=?, lat=?, lng=?, direction=?,
                    data_importacao=SYSDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (vehicle_id, iButton, date, arrivalDate, speed, ignition, block,
                     odometer, hourmeter, vehicleBattery, lat, lng, direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            vehicle_id, data_posicao,
            item.get("iButton"), parse_date(item.get("arrivalDate")),
            item.get("speed"), item.get("ignition"), item.get("block"),
            item.get("odometer"), item.get("hourmeter"), item.get("vehicleBattery"),
            coord.get("lat"), coord.get("lng"), item.get("direction"),
            vehicle_id, item.get("iButton"), data_posicao,
            parse_date(item.get("arrivalDate")), item.get("speed"),
            item.get("ignition"), item.get("block"), item.get("odometer"),
            item.get("hourmeter"), item.get("vehicleBattery"),
            coord.get("lat"), coord.get("lng"), item.get("direction"))

        conn.commit()
        return len(items)

    def sincronizar_manual(self):
        if self.executando:
            messagebox.showinfo("Aguarde", "Já existe uma sincronização em andamento.")
            return

        threading.Thread(target=self.executar_sincronizacao, daemon=True).start()

    def executar_sincronizacao(self):
        self.executando = True
        self.btn_sinc.config(state="disabled")
        self.progresso(0)

        try:
            self.log("Iniciando sincronização Mobi7...")

            fim = datetime.now(timezone.utc)
            inicio = fim - timedelta(hours=3)

            conn = get_conn()
            criar_tabelas(conn)

            self.lbl_sql.config(text="SQL Server: Conectado")
            self.lbl_api.config(text="API: Conectada")

            self.progresso(5)

            veiculos = self.importar_veiculos(conn)

            total_veiculos = len(veiculos)
            total_percursos = 0
            total_ofensas = 0
            total_ultimas = 0
            total_historico = 0

            for index, v in enumerate(veiculos, start=1):
                vehicle_id = v.get("id")
                placa = v.get("plate")

                self.log(f"Veículo {index}/{total_veiculos}: {placa} - {vehicle_id}")

                try:
                    total_percursos += self.importar_percursos(conn, vehicle_id, inicio, fim)
                except Exception as e:
                    self.log(f"Erro percursos {placa}: {e}")

                try:
                    total_ofensas += self.importar_ofensas(conn, vehicle_id, inicio, fim)
                except Exception as e:
                    self.log(f"Erro ofensas {placa}: {e}")

                try:
                    total_ultimas += self.importar_ultima_posicao(conn, vehicle_id)
                except Exception as e:
                    self.log(f"Erro última posição {placa}: {e}")

                try:
                    total_historico += self.importar_historico(conn, vehicle_id, inicio, fim)
                except Exception as e:
                    self.log(f"Erro histórico {placa}: {e}")

                progresso_atual = 5 + int((index / max(total_veiculos, 1)) * 95)
                self.progresso(progresso_atual)

            conn.close()

            agora = datetime.now()
            self.lbl_ultima.config(text=f"Última sincronização: {agora.strftime('%d/%m/%Y %H:%M:%S')}")

            self.proxima_execucao = agora + timedelta(hours=INTERVALO_HORAS)
            self.lbl_proxima.config(text=f"Próxima sincronização: {self.proxima_execucao.strftime('%d/%m/%Y %H:%M:%S')}")

            self.log("Sincronização finalizada.")
            self.log(f"Veículos: {total_veiculos}")
            self.log(f"Percursos: {total_percursos}")
            self.log(f"Ofensas: {total_ofensas}")
            self.log(f"Últimas posições: {total_ultimas}")
            self.log(f"Histórico posições: {total_historico}")

            self.progresso(100)

        except Exception as e:
            self.log(f"ERRO GERAL: {e}")
            messagebox.showerror("Erro", str(e))

        finally:
            self.executando = False
            self.btn_sinc.config(state="normal")

    def loop_automatico(self):
        while True:
            if self.proxima_execucao:
                self.lbl_proxima.config(
                    text=f"Próxima sincronização: {self.proxima_execucao.strftime('%d/%m/%Y %H:%M:%S')}"
                )

            if not self.executando and datetime.now() >= self.proxima_execucao:
                self.executar_sincronizacao()

            time.sleep(5)

    def sair(self):
        if messagebox.askyesno("Sair", "Deseja encerrar o importador?"):
            self.root.destroy()


if __name__ == "__main__":
    if not API_KEY:
        raise Exception("MOBI7_API_KEY não encontrada no .env")

    root = tk.Tk()
    app = App(root)
    root.mainloop()