import pyodbc
import tkinter as tk
from tkinter import messagebox, ttk
import subprocess

# =========================
# CONEXÃO COM SQL SERVER
# =========================
def conectar():
    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=tcp:10.0.0.254,1433;"
        "Database=FTECH;"
        "UID=ftech;"
        "PWD=ftech@1975;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


# =========================
# ESTILO PADRÃO
# =========================
BG_GERAL = "#f2f2f2"
BG_CARD = "#ffffff"
COR_PRIMARIA = "#0A6ED1"   # Azul corporativo
FONTE_TITULO = ("Segoe UI", 14, "bold")
FONTE_LABEL = ("Segoe UI", 10)
FONTE_INPUT = ("Segoe UI", 10)
FONTE_BOTAO = ("Segoe UI", 10, "bold")


# =========================
# TELA 2 - FILIAL / MÓDULO
# =========================
def tela_selecao(usuario_id):
    win = tk.Tk()
    win.title("Seleção de Ambiente")
    win.geometry("520x360")
    win.resizable(False, False)
    win.configure(bg=BG_GERAL)

    card = tk.Frame(win, bg=BG_CARD, padx=40, pady=30)
    card.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(
        card,
        text="Seleção de Ambiente",
        font=FONTE_TITULO,
        bg=BG_CARD,
        fg=COR_PRIMARIA
    ).pack(pady=(0, 25))

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT CODIGO, DESCRICAO FROM FILIAIS")
        filiais = cursor.fetchall()

        cursor.execute("""
            SELECT MODULO, CAMINHO_EXE
            FROM USUARIO_MODULO
            WHERE USUARIO_ID = ?
        """, usuario_id)
        modulos = cursor.fetchall()

        conn.close()

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao carregar dados:\n{e}")
        win.destroy()
        return

    tk.Label(card, text="Filial", font=FONTE_LABEL, bg=BG_CARD).pack(anchor="w")
    filial_cb = ttk.Combobox(
        card,
        values=[f"{f[0]} - {f[1]}" for f in filiais],
        state="readonly",
        width=38
    )
    filial_cb.pack(pady=(5, 20))

    tk.Label(card, text="Módulo", font=FONTE_LABEL, bg=BG_CARD).pack(anchor="w")
    modulo_cb = ttk.Combobox(
        card,
        values=[m[0] for m in modulos],
        state="readonly",
        width=38
    )
    modulo_cb.pack(pady=(5, 30))

    def abrir_modulo():
        modulo_selecionado = modulo_cb.get()

        if not modulo_selecionado:
            messagebox.showwarning("Atenção", "Selecione um módulo")
            return

        for modulo, caminho in modulos:
            if modulo == modulo_selecionado:
                try:
                    subprocess.Popen(caminho)
                    win.destroy()
                except Exception as e:
                    messagebox.showerror("Erro", f"Não foi possível abrir o módulo:\n{e}")

    tk.Button(
        card,
        text="Entrar",
        font=FONTE_BOTAO,
        bg=COR_PRIMARIA,
        fg="white",
        activebackground="#085caf",
        activeforeground="white",
        width=22,
        height=2,
        bd=0,
        command=abrir_modulo
    ).pack()

    win.mainloop()


# =========================
# TELA 1 - LOGIN
# =========================
def tela_login():
    def autenticar():
        usuario = entry_usuario.get().strip()
        senha = entry_senha.get().strip()

        if not usuario or not senha:
            messagebox.showwarning("Atenção", "Informe usuário e senha")
            return

        try:
            conn = conectar()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ID
                FROM USUARIOS
                WHERE LOGIN = ?
                  AND SENHA = ?
                  AND ATIVO = 1
            """, usuario, senha)

            row = cursor.fetchone()
            conn.close()

            if row:
                root.destroy()
                tela_selecao(row[0])
            else:
                messagebox.showerror("Erro", "Usuário ou senha inválidos")

        except Exception as e:
            messagebox.showerror("Erro de conexão", str(e))

    global root
    root = tk.Tk()
    root.title("Login - FTECH")
    root.geometry("420x320")
    root.resizable(False, False)
    root.configure(bg=BG_GERAL)

    card = tk.Frame(root, bg=BG_CARD, padx=40, pady=35)
    card.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(
        card,
        text="Acesso ao Sistema",
        font=FONTE_TITULO,
        bg=BG_CARD,
        fg=COR_PRIMARIA
    ).pack(pady=(0, 25))

    tk.Label(card, text="Usuário", font=FONTE_LABEL, bg=BG_CARD).pack(anchor="w")
    entry_usuario = tk.Entry(card, font=FONTE_INPUT, width=32)
    entry_usuario.pack(pady=(5, 15))

    tk.Label(card, text="Senha", font=FONTE_LABEL, bg=BG_CARD).pack(anchor="w")
    entry_senha = tk.Entry(card, font=FONTE_INPUT, show="*", width=32)
    entry_senha.pack(pady=(5, 25))

    tk.Button(
        card,
        text="Entrar",
        font=FONTE_BOTAO,
        bg=COR_PRIMARIA,
        fg="white",
        activebackground="#085caf",
        activeforeground="white",
        width=22,
        height=2,
        bd=0,
        command=autenticar
    ).pack()

    root.mainloop()


# =========================
# START DO SISTEMA
# =========================
if __name__ == "__main__":
    tela_login()
