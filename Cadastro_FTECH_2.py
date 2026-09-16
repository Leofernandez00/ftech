import os
import hashlib
import secrets
import string
import tkinter as tk
from tkinter import ttk, messagebox

import pyodbc
from dotenv import load_dotenv

load_dotenv()

SQL_SERVER = os.getenv("SQL_SERVER", "").strip()
SQL_DATABASE = os.getenv("SQL_DATABASE", "").strip()
SQL_USER = os.getenv("SQL_USER", "").strip()
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "").strip()
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server").strip()


def get_connection():
    connection_string = (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=15;"
    )
    return pyodbc.connect(connection_string)


def generate_password_hash(password):
    salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return digest.hex(), salt.hex()


def generate_temporary_password(length=12):
    """Gera uma senha temporária com letras maiúsculas, minúsculas e números."""
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)):
            return password


class UserAdminApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FTECH | Cadastro de usuários")
        self.root.geometry("1050x650")
        self.root.minsize(900, 580)
        self.selected_user_id = None
        self.build_interface()
        self.load_users()

    def build_interface(self):
        header = tk.Frame(self.root, bg="#1f4e78", height=75)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Administração de usuários FTECH",
            bg="#1f4e78",
            fg="white",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=20)

        body = tk.Frame(self.root, padx=18, pady=15)
        body.pack(fill="both", expand=True)

        form = ttk.LabelFrame(body, text="Cadastro / edição", padding=12)
        form.pack(fill="x")

        self.usuario = tk.StringVar()
        self.nome = tk.StringVar()
        self.senha = tk.StringVar()
        self.confirmacao = tk.StringVar()
        self.provedor = tk.StringVar(value="GOOGLE")
        self.email = tk.StringVar()
        self.appsheet_senha = tk.StringVar()
        self.url = tk.StringVar(value=(
            "https://www.appsheet.com/start/"
            "8a8b91d3-535d-4517-bb03-1e9f015a419d"
        ))
        self.ativo = tk.BooleanVar(value=True)
        self.trocar_senha = tk.BooleanVar(value=True)

        fields = [
            ("Usuário", self.usuario, ""),
            ("Nome completo", self.nome, ""),
            ("Senha", self.senha, "●"),
            ("Confirmar senha", self.confirmacao, "●"),
            ("E-mail AppSheet", self.email, ""),
            ("Senha AppSheet", self.appsheet_senha, "●"),
            ("URL AppSheet", self.url, ""),
        ]

        for index, (label, variable, show) in enumerate(fields):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(form, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=6)
            ttk.Entry(form, textvariable=variable, show=show).grid(
                row=row, column=col + 1, sticky="ew", padx=(0, 16), pady=6
            )

        ttk.Label(form, text="Provedor").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Combobox(
            form,
            textvariable=self.provedor,
            values=("GOOGLE", "MICROSOFT"),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", padx=(0, 16), pady=6)

        ttk.Checkbutton(form, text="Usuário ativo", variable=self.ativo).grid(
            row=4, column=2, sticky="w", pady=6
        )

        ttk.Checkbutton(
            form,
            text="Exigir troca de senha no próximo login",
            variable=self.trocar_senha,
        ).grid(row=4, column=3, sticky="w", pady=6)

        ttk.Button(
            form,
            text="Gerar senha temporária",
            command=self.generate_temp_password,
        ).grid(row=5, column=1, sticky="w", pady=(8, 0))

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        buttons = tk.Frame(body)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="Novo / limpar", command=self.clear_form).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Salvar", command=self.save_user).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Desbloquear", command=self.unlock_user).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Ativar / desativar", command=self.toggle_active).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Excluir", command=self.delete_user).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Atualizar lista", command=self.load_users).pack(side="right")

        frame = ttk.LabelFrame(body, text="Usuários cadastrados", padding=8)
        frame.pack(fill="both", expand=True)

        columns = ("id", "usuario", "nome", "provedor", "email", "ativo", "trocar_senha", "bloqueado", "tentativas", "ultimo_login")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")

        headings = {
            "id": "ID", "usuario": "Usuário", "nome": "Nome", "provedor": "Provedor",
            "email": "E-mail", "ativo": "Ativo", "trocar_senha": "Trocar senha", "bloqueado": "Bloqueado",
            "tentativas": "Tentativas", "ultimo_login": "Último login",
        }
        widths = {
            "id": 55, "usuario": 120, "nome": 180, "provedor": 90,
            "email": 210, "ativo": 60, "trocar_senha": 90, "bloqueado": 80,
            "tentativas": 75, "ultimo_login": 140,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="center")

        sy = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def generate_temp_password(self):
        password = generate_temporary_password()
        self.senha.set(password)
        self.confirmacao.set(password)
        self.trocar_senha.set(True)

        self.root.clipboard_clear()
        self.root.clipboard_append(password)
        self.root.update()

        messagebox.showinfo(
            "Senha temporária",
            "Senha temporária gerada e copiada para a área de transferência:\n\n"
            f"{password}\n\n"
            "O usuário deverá alterá-la no próximo login.",
            parent=self.root,
        )

    def clear_form(self):
        self.selected_user_id = None
        self.usuario.set("")
        self.nome.set("")
        self.senha.set("")
        self.confirmacao.set("")
        self.provedor.set("GOOGLE")
        self.email.set("")
        self.appsheet_senha.set("")
        self.url.set("https://www.appsheet.com/start/8a8b91d3-535d-4517-bb03-1e9f015a419d")
        self.ativo.set(True)
        self.trocar_senha.set(True)

    def load_users(self):
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT ID_USUARIO, USUARIO, NOME_COMPLETO, PROVEDOR_LOGIN,
                           EMAIL_APPSHEET, ATIVO, TROCAR_SENHA_PROXIMO_LOGIN,
                           BLOQUEADO, TENTATIVAS_LOGIN, ULTIMO_LOGIN
                    FROM dbo.FTECH_USUARIOS_APP
                    ORDER BY NOME_COMPLETO
                    """
                )
                rows = cursor.fetchall()

            self.tree.delete(*self.tree.get_children())
            for row in rows:
                last_login = row.ULTIMO_LOGIN.strftime("%d/%m/%Y %H:%M") if row.ULTIMO_LOGIN else ""
                self.tree.insert("", "end", iid=str(row.ID_USUARIO), values=(
                    row.ID_USUARIO, row.USUARIO, row.NOME_COMPLETO, row.PROVEDOR_LOGIN,
                    row.EMAIL_APPSHEET, "Sim" if row.ATIVO else "Não",
                    "Sim" if row.TROCAR_SENHA_PROXIMO_LOGIN else "Não",
                    "Sim" if row.BLOQUEADO else "Não", row.TENTATIVAS_LOGIN, last_login,
                ))
        except Exception as error:
            messagebox.showerror("Erro", f"Não foi possível carregar os usuários.\n\n{error}")

    def on_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        self.selected_user_id = int(selected[0])
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT USUARIO, NOME_COMPLETO, PROVEDOR_LOGIN,
                       EMAIL_APPSHEET, APPSHEET_SENHA, APPSHEET_URL, ATIVO,
                       TROCAR_SENHA_PROXIMO_LOGIN
                FROM dbo.FTECH_USUARIOS_APP
                WHERE ID_USUARIO = ?
                """,
                self.selected_user_id,
            )
            row = cursor.fetchone()

        self.usuario.set(row.USUARIO)
        self.nome.set(row.NOME_COMPLETO)
        self.senha.set("")
        self.confirmacao.set("")
        self.provedor.set(row.PROVEDOR_LOGIN)
        self.email.set(row.EMAIL_APPSHEET)
        self.appsheet_senha.set(row.APPSHEET_SENHA or "")
        self.url.set(row.APPSHEET_URL)
        self.ativo.set(bool(row.ATIVO))
        self.trocar_senha.set(bool(row.TROCAR_SENHA_PROXIMO_LOGIN))

    def validate(self):
        usuario = self.usuario.get().strip().lower()
        nome = self.nome.get().strip()
        senha = self.senha.get()
        confirmacao = self.confirmacao.get()
        provedor = self.provedor.get().strip().upper()
        email = self.email.get().strip().lower()
        appsheet_senha = self.appsheet_senha.get()
        url = self.url.get().strip()

        if not usuario or not nome or not email or not url:
            raise ValueError("Preencha usuário, nome, e-mail e URL do AppSheet.")
        if self.selected_user_id is None and not senha:
            raise ValueError("Informe uma senha para o novo usuário.")
        if senha and senha != confirmacao:
            raise ValueError("A senha e a confirmação não coincidem.")
        if senha and len(senha) < 6:
            raise ValueError("A senha deve ter pelo menos 6 caracteres.")
        return usuario, nome, senha, provedor, email, appsheet_senha, url

    def save_user(self):
        try:
            usuario, nome, senha, provedor, email, appsheet_senha, url = self.validate()
            ativo = 1 if self.ativo.get() else 0
            trocar_senha = 1 if self.trocar_senha.get() else 0

            with get_connection() as connection:
                cursor = connection.cursor()
                if self.selected_user_id is None:
                    password_hash, salt = generate_password_hash(senha)
                    cursor.execute(
                        """
                        INSERT INTO dbo.FTECH_USUARIOS_APP
                        (USUARIO, NOME_COMPLETO, SENHA_HASH, SENHA_SALT,
                         PROVEDOR_LOGIN, EMAIL_APPSHEET, APPSHEET_SENHA, APPSHEET_URL,
                         ATIVO, TROCAR_SENHA_PROXIMO_LOGIN,
                         BLOQUEADO, TENTATIVAS_LOGIN)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                        """,
                        usuario, nome, password_hash, salt, provedor, email, appsheet_senha, url,
                        ativo, trocar_senha,
                    )
                elif senha:
                    password_hash, salt = generate_password_hash(senha)
                    cursor.execute(
                        """
                        UPDATE dbo.FTECH_USUARIOS_APP
                        SET USUARIO=?, NOME_COMPLETO=?, SENHA_HASH=?, SENHA_SALT=?,
                            PROVEDOR_LOGIN=?, EMAIL_APPSHEET=?, APPSHEET_SENHA=?, APPSHEET_URL=?, ATIVO=?,
                            TROCAR_SENHA_PROXIMO_LOGIN=?,
                            DATA_ALTERACAO=SYSDATETIME()
                        WHERE ID_USUARIO=?
                        """,
                        usuario, nome, password_hash, salt, provedor, email, appsheet_senha, url,
                        ativo, trocar_senha, self.selected_user_id,
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE dbo.FTECH_USUARIOS_APP
                        SET USUARIO=?, NOME_COMPLETO=?, PROVEDOR_LOGIN=?,
                            EMAIL_APPSHEET=?, APPSHEET_SENHA=?, APPSHEET_URL=?, ATIVO=?,
                            TROCAR_SENHA_PROXIMO_LOGIN=?,
                            DATA_ALTERACAO=SYSDATETIME()
                        WHERE ID_USUARIO=?
                        """,
                        usuario, nome, provedor, email, appsheet_senha, url, ativo,
                        trocar_senha, self.selected_user_id,
                    )
                connection.commit()

            messagebox.showinfo("Sucesso", "Usuário salvo com sucesso.")
            self.clear_form()
            self.load_users()
        except pyodbc.IntegrityError:
            messagebox.showerror("Erro", "Já existe um usuário com esse nome.")
        except Exception as error:
            messagebox.showerror("Erro", str(error))

    def require_selection(self):
        if self.selected_user_id is None:
            messagebox.showwarning("Seleção", "Selecione um usuário na lista.")
            return False
        return True

    def unlock_user(self):
        if not self.require_selection():
            return
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE dbo.FTECH_USUARIOS_APP SET BLOQUEADO=0, TENTATIVAS_LOGIN=0 WHERE ID_USUARIO=?",
                self.selected_user_id,
            )
            connection.commit()
        self.load_users()

    def toggle_active(self):
        if not self.require_selection():
            return
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE dbo.FTECH_USUARIOS_APP SET ATIVO=CASE WHEN ATIVO=1 THEN 0 ELSE 1 END WHERE ID_USUARIO=?",
                self.selected_user_id,
            )
            connection.commit()
        self.load_users()

    def delete_user(self):
        if not self.require_selection():
            return
        if not messagebox.askyesno("Confirmar", "Excluir o usuário selecionado e seus logs?"):
            return
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM dbo.FTECH_USUARIOS_APP_LOG WHERE ID_USUARIO=?", self.selected_user_id)
            cursor.execute("DELETE FROM dbo.FTECH_USUARIOS_APP WHERE ID_USUARIO=?", self.selected_user_id)
            connection.commit()
        self.clear_form()
        self.load_users()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    UserAdminApp().run()
