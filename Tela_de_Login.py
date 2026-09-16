import sqlite3
from tkinter import messagebox, Tk, Label, Entry, Button

class Banco:
    def __init__(self):
        self.conexao = sqlite3.connect('usuarios.db')
        self.createTable()

    def createTable(self):
        c = self.conexao.cursor()

        c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     usuario TEXT NOT NULL,
                     senha TEXT NOT NULL)""")
        self.conexao.commit()
        c.close()

class TelaLogin:
    def __init__(self, master):
        self.master = master
        self.master.title("Login")

        self.label_usuario = Label(master, text="Usuário:")
        self.label_usuario.grid(row=0, column=0, padx=10, pady=10)

        self.entry_usuario = Entry(master)
        self.entry_usuario.grid(row=0, column=1)

        self.label_senha = Label(master, text="Senha:")
        self.label_senha.grid(row=1, column=0, padx=10, pady=10)

        self.entry_senha = Entry(master, show="*")
        self.entry_senha.grid(row=1, column=1)

        self.botao_login = Button(master, text="Login", command=self.login)
        self.botao_login.grid(row=2, columnspan=2, pady=10)

        self.banco = Banco()

    def login(self):
        usuario = self.entry_usuario.get()
        senha = self.entry_senha.get()

        if usuario == "" or senha == "":
            messagebox.showerror("Erro", "Por favor, preencha todos os campos.")
            return

        if self.autenticar(usuario, senha):
            messagebox.showinfo("Sucesso", "Login bem sucedido!")
        else:
            messagebox.showerror("Erro", "Usuário ou senha incorretos.")

    def autenticar(self, usuario, senha):
        c = self.banco.conexao.cursor()
        c.execute("SELECT * FROM usuarios WHERE usuario = ? AND senha = ?", (usuario, senha))
        usuario_encontrado = c.fetchone()
        c.close()
        return usuario_encontrado is not None

root = Tk()
tela_login = TelaLogin(root)
root.mainloop()
