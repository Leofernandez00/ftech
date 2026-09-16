import os
import pyodbc
import tkinter as tk
from lxml import etree
from datetime import datetime
import threading

XML_DIR = r"\\SERVER\xml_eventos"

DB_CONFIG = {
    "SERVER": "10.0.0.254",
    "DATABASE": "FTECH",
    "UID": "ftech",
    "PWD": "ftech@1975"
}

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

INTERVALO_IMPORTACAO = 60 * 60 * 1000  # 1 hora em milissegundos
importando = False


def get_connection():
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"UID={DB_CONFIG['UID']};"
        f"PWD={DB_CONFIG['PWD']};"
        f"TrustServerCertificate=yes;"
    )


def log(log_box, msg):
    log_box.insert(tk.END, msg + "\n")
    log_box.see(tk.END)
    log_box.update_idletasks()


def converter_data(valor):
    if not valor:
        return None

    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except Exception:
        return None


def buscar_arquivos_ja_importados(cursor):
    cursor.execute("SELECT Arquivo FROM dbo.NF_Evento WHERE Arquivo IS NOT NULL")
    return {row[0] for row in cursor.fetchall()}


def extrair_xml(file):
    path = os.path.join(XML_DIR, file)

    tree = etree.parse(path)
    root_tag = tree.getroot().tag

    if "procEventoNFe" not in root_tag:
        return None

    cOrgao = tree.findtext(".//nfe:infEvento/nfe:cOrgao", namespaces=NS)
    tpAmb = tree.findtext(".//nfe:infEvento/nfe:tpAmb", namespaces=NS)
    CNPJ = tree.findtext(".//nfe:infEvento/nfe:CNPJ", namespaces=NS)
    chNFe = tree.findtext(".//nfe:infEvento/nfe:chNFe", namespaces=NS)
    dhEvento = converter_data(tree.findtext(".//nfe:infEvento/nfe:dhEvento", namespaces=NS))
    tpEvento = tree.findtext(".//nfe:infEvento/nfe:tpEvento", namespaces=NS)
    nSeqEvento = tree.findtext(".//nfe:infEvento/nfe:nSeqEvento", namespaces=NS)
    verEvento = tree.findtext(".//nfe:infEvento/nfe:verEvento", namespaces=NS)
    descEvento = tree.findtext(".//nfe:infEvento/nfe:detEvento/nfe:descEvento", namespaces=NS)
    nProt = tree.findtext(".//nfe:infEvento/nfe:detEvento/nfe:nProt", namespaces=NS)
    xJust = tree.findtext(".//nfe:infEvento/nfe:detEvento/nfe:xJust", namespaces=NS)

    cStat = tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:cStat", namespaces=NS)
    xMotivo = tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:xMotivo", namespaces=NS)
    xEvento = tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:xEvento", namespaces=NS)
    CNPJDest = tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:CNPJDest", namespaces=NS)
    emailDest = tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:emailDest", namespaces=NS)
    dhRegEvento = converter_data(tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:dhRegEvento", namespaces=NS))
    nProtRet = tree.findtext(".//nfe:retEvento/nfe:infEvento/nfe:nProt", namespaces=NS)

    return (
        file,
        cOrgao,
        tpAmb,
        CNPJ,
        chNFe,
        dhEvento,
        tpEvento,
        nSeqEvento,
        verEvento,
        descEvento,
        nProt,
        xJust,
        cStat,
        xMotivo,
        xEvento,
        CNPJDest,
        emailDest,
        dhRegEvento,
        nProtRet
    )


def import_xmls(log_box):
    global importando

    if importando:
        log(log_box, "[AVISO] Já existe uma importação em andamento. A nova execução foi ignorada.")
        return

    importando = True

    try:
        log(log_box, "")
        log(log_box, f"Iniciando importação automática/manual em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        log(log_box, "Conectando ao banco de dados...")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = False

        log(log_box, "Verificando arquivos já importados...")
        arquivos_importados = buscar_arquivos_ja_importados(cursor)

        arquivos_xml = [
            f for f in os.listdir(XML_DIR)
            if f.lower().endswith(".xml")
        ]

        novos_registros = []
        ignorados = 0
        duplicados = 0
        erros = 0

        log(log_box, f"Total de XMLs encontrados na pasta: {len(arquivos_xml)}")

        for file in arquivos_xml:
            if file in arquivos_importados:
                duplicados += 1
                continue

            try:
                dados = extrair_xml(file)

                if dados is None:
                    ignorados += 1
                    log(log_box, f"[IGNORADO] {file} não é evento de NF-e.")
                    continue

                novos_registros.append(dados)

            except Exception as e:
                erros += 1
                log(log_box, f"[ERRO] {file} - {e}")

        if novos_registros:
            log(log_box, f"Inserindo {len(novos_registros)} novos eventos no banco...")

            cursor.executemany("""
                INSERT INTO dbo.NF_Evento
                (
                    Arquivo,
                    cOrgao,
                    tpAmb,
                    CNPJ,
                    chNFe,
                    dhEvento,
                    tpEvento,
                    nSeqEvento,
                    verEvento,
                    descEvento,
                    nProt,
                    xJust,
                    cStat,
                    xMotivo,
                    xEvento,
                    CNPJDest,
                    emailDest,
                    dhRegEvento,
                    nProtRet
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, novos_registros)

            conn.commit()
            log(log_box, "[OK] Importação concluída com sucesso.")
        else:
            log(log_box, "Nenhum novo XML para importar.")

        log(log_box, "----------------------------------------")
        log(log_box, f"Novos importados: {len(novos_registros)}")
        log(log_box, f"Já existentes ignorados: {duplicados}")
        log(log_box, f"XMLs não-evento ignorados: {ignorados}")
        log(log_box, f"Erros: {erros}")
        log(log_box, "----------------------------------------")

        conn.close()

    except Exception as e:
        log(log_box, f"[ERRO GERAL] {e}")

    finally:
        importando = False


def run_import(log_box):
    threading.Thread(target=import_xmls, args=(log_box,), daemon=True).start()


def iniciar_importacao_automatica(root, log_box):
    run_import(log_box)

    proxima = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    log(log_box, f"Próxima verificação automática em 1 hora.")

    root.after(
        INTERVALO_IMPORTACAO,
        lambda: iniciar_importacao_automatica(root, log_box)
    )


def main():
    root = tk.Tk()
    root.title("Importador de Eventos NFe - Otimizado")

    frame = tk.Frame(root)
    frame.pack(padx=10, pady=10)

    log_box = tk.Text(frame, width=110, height=28)
    log_box.pack()

    import_btn = tk.Button(
        frame,
        text="Importar XMLs Agora",
        command=lambda: run_import(log_box),
        width=30
    )
    import_btn.pack(pady=5)

    log(log_box, "Sistema iniciado.")
    log(log_box, "A importação será executada automaticamente a cada 1 hora.")

    iniciar_importacao_automatica(root, log_box)

    root.mainloop()


if __name__ == "__main__":
    main()