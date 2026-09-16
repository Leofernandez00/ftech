import pyodbc
import tkinter as tk
from tkinter import ttk, messagebox

# =========================
# CONEXÃO
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


class AdminApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Administração - FTECH")
        self.root.geometry("900x520")
        self.root.resizable(False, False)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.notebook.add(self.tela_usuarios(), text="Usuários")
        self.notebook.add(self.tela_filiais(), text="Filiais")
        self.notebook.add(self.tela_usuario_modulo(), text="Usuário × Módulo")
        self.notebook.add(self.tela_consulta_acessos(), text="Consulta de Acessos")

        self.root.mainloop()

    # =========================
    # USUÁRIOS
    # =========================
    def tela_usuarios(self):
        frame = ttk.Frame(self.notebook)

        ttk.Label(frame, text="Cadastro de Usuários", font=("Segoe UI", 12, "bold")).pack(pady=10)

        form = ttk.Frame(frame)
        form.pack(pady=10)

        ttk.Label(form, text="Nome").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(form, width=30)
        nome.grid(row=0, column=1, padx=10)

        ttk.Label(form, text="Login").grid(row=1, column=0, sticky="w")
        login = ttk.Entry(form, width=30)
        login.grid(row=1, column=1, padx=10)

        ttk.Label(form, text="Senha").grid(row=2, column=0, sticky="w")
        senha = ttk.Entry(form, width=30, show="*")
        senha.grid(row=2, column=1, padx=10)

        ativo = tk.IntVar(value=1)
        ttk.Checkbutton(form, text="Ativo", variable=ativo).grid(row=3, column=1, sticky="w")

        def salvar():
            if not nome.get() or not login.get() or not senha.get():
                messagebox.showwarning("Atenção", "Preencha todos os campos")
                return

            try:
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO USUARIOS (USUARIO, LOGIN, SENHA, ATIVO)
                    VALUES (?, ?, ?, ?)
                """, nome.get(), login.get().lower(), senha.get(), ativo.get())
                conn.commit()
                conn.close()
                messagebox.showinfo("Sucesso", "Usuário cadastrado")
                nome.delete(0, tk.END)
                login.delete(0, tk.END)
                senha.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Erro", str(e))

        ttk.Button(frame, text="Salvar Usuário", width=25, command=salvar).pack(pady=15)
        return frame

    # =========================
    # FILIAIS
    # =========================
    def tela_filiais(self):
        frame = ttk.Frame(self.notebook)

        ttk.Label(frame, text="Cadastro de Filiais", font=("Segoe UI", 12, "bold")).pack(pady=10)

        form = ttk.Frame(frame)
        form.pack(pady=20)

        codigo = ttk.Entry(form, width=20)
        descricao = ttk.Entry(form, width=30)

        ttk.Label(form, text="Código").grid(row=0, column=0)
        codigo.grid(row=0, column=1, padx=10)

        ttk.Label(form, text="Descrição").grid(row=1, column=0)
        descricao.grid(row=1, column=1, padx=10)

        def salvar():
            if not codigo.get() or not descricao.get():
                messagebox.showwarning("Atenção", "Preencha todos os campos")
                return

            try:
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO FILIAIS (CODIGO, DESCRICAO) VALUES (?, ?)",
                    codigo.get(), descricao.get()
                )
                conn.commit()
                conn.close()
                messagebox.showinfo("Sucesso", "Filial cadastrada")
                codigo.delete(0, tk.END)
                descricao.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Erro", str(e))

        ttk.Button(frame, text="Salvar Filial", width=25, command=salvar).pack(pady=15)
        return frame

    # =========================
    # USUÁRIO × MÓDULO
    # =========================
    def tela_usuario_modulo(self):
        frame = ttk.Frame(self.notebook)

        ttk.Label(frame, text="Vínculo Usuário × Módulo", font=("Segoe UI", 12, "bold")).pack(pady=10)

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, LOGIN FROM USUARIOS WHERE ATIVO = 1")
        usuarios = cursor.fetchall()
        conn.close()

        form = ttk.Frame(frame)
        form.pack(pady=15)

        usuario_cb = ttk.Combobox(
            form,
            values=[f"{u[0]} - {u[1]}" for u in usuarios],
            width=30,
            state="readonly"
        )
        modulo = ttk.Entry(form, width=30)
        caminho = ttk.Entry(form, width=40)

        ttk.Label(form, text="Usuário").grid(row=0, column=0)
        usuario_cb.grid(row=0, column=1, padx=10)

        ttk.Label(form, text="Módulo").grid(row=1, column=0)
        modulo.grid(row=1, column=1, padx=10)

        ttk.Label(form, text="Caminho EXE").grid(row=2, column=0)
        caminho.grid(row=2, column=1, padx=10)

        def salvar():
            usuario_id = int(usuario_cb.get().split(" - ")[0])
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO USUARIO_MODULO (USUARIO_ID, MODULO, CAMINHO_EXE)
                VALUES (?, ?, ?)
            """, usuario_id, modulo.get(), caminho.get())
            conn.commit()
            conn.close()
            messagebox.showinfo("Sucesso", "Módulo vinculado")

        ttk.Button(frame, text="Salvar Vínculo", width=25, command=salvar).pack(pady=20)
        return frame

    # =========================
    # 🔍 CONSULTA DE ACESSOS
    # =========================
    def tela_consulta_acessos(self):
        frame = ttk.Frame(self.notebook)

        ttk.Label(frame, text="Consulta de Acessos por Usuário",
                  font=("Segoe UI", 12, "bold")).pack(pady=10)

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, LOGIN FROM USUARIOS")
        usuarios = cursor.fetchall()
        conn.close()

        usuario_cb = ttk.Combobox(
            frame,
            values=[f"{u[0]} - {u[1]}" for u in usuarios],
            state="readonly",
            width=40
        )
        usuario_cb.pack(pady=10)

        cols = ("Módulo", "Caminho EXE")
        tabela = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        tabela.heading("Módulo", text="Módulo")
        tabela.heading("Caminho EXE", text="Caminho do Executável")
        tabela.column("Módulo", width=200)
        tabela.column("Caminho EXE", width=500)
        tabela.pack(padx=10, pady=10)

        def carregar():
            tabela.delete(*tabela.get_children())
            usuario_id = int(usuario_cb.get().split(" - ")[0])

            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MODULO, CAMINHO_EXE
                FROM USUARIO_MODULO
                WHERE USUARIO_ID = ?
            """, usuario_id)

            for row in cursor.fetchall():
                tabela.insert("", tk.END, values=row)

            conn.close()

        ttk.Button(frame, text="Carregar Acessos", width=25, command=carregar).pack(pady=10)
        return frame


# =========================
# START
# =========================
if __name__ == "__main__":
    AdminApp()
