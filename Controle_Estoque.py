import tkinter as tk
from tkinter import messagebox
import sqlite3

# Configuração do banco de dados
conn = sqlite3.connect("estoque.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    nivel TEXT NOT NULL CHECK(nivel IN ('admin', 'usuario'))
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    quantidade INTEGER NOT NULL
)
''')

# Criação do usuário admin padrão na primeira execução
cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
if not cursor.fetchone():
    cursor.execute("INSERT INTO usuarios (usuario, senha, nivel) VALUES ('admin', 'admin', 'admin')")
    conn.commit()

# Função para criar um novo usuário
def criar_usuario():
    def salvar_usuario():
        usuario = entry_usuario.get()
        senha = entry_senha.get()
        nivel = combo_nivel.get()

        if usuario and senha and nivel:
            try:
                cursor.execute("INSERT INTO usuarios (usuario, senha, nivel) VALUES (?, ?, ?)", (usuario, senha, nivel))
                conn.commit()
                messagebox.showinfo("Sucesso", "Usuário criado com sucesso.")
                janela_criar_usuario.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Erro", "Usuário já existe.")
        else:
            messagebox.showerror("Erro", "Todos os campos são obrigatórios.")

    janela_criar_usuario = tk.Toplevel()
    janela_criar_usuario.title("Criar Usuário")

    tk.Label(janela_criar_usuario, text="Usuário:").grid(row=0, column=0, pady=5)
    entry_usuario = tk.Entry(janela_criar_usuario)
    entry_usuario.grid(row=0, column=1, pady=5)

    tk.Label(janela_criar_usuario, text="Senha:").grid(row=1, column=0, pady=5)
    entry_senha = tk.Entry(janela_criar_usuario, show="*")
    entry_senha.grid(row=1, column=1, pady=5)

    tk.Label(janela_criar_usuario, text="Nível:").grid(row=2, column=0, pady=5)
    combo_nivel = tk.StringVar()
    tk.OptionMenu(janela_criar_usuario, combo_nivel, "admin", "usuario").grid(row=2, column=1, pady=5)

    tk.Button(janela_criar_usuario, text="Salvar", command=salvar_usuario).grid(row=3, column=0, columnspan=2, pady=10)

# Função para autenticar o usuário
def autenticar():
    usuario = entry_usuario.get()
    senha = entry_senha.get()

    cursor.execute("SELECT nivel FROM usuarios WHERE usuario = ? AND senha = ?", (usuario, senha))
    resultado = cursor.fetchone()

    if resultado:
        nivel = resultado[0]
        janela_login.destroy()
        abrir_menu_principal(nivel)
    else:
        messagebox.showerror("Erro", "Usuário ou senha incorretos.")

# Função para adicionar um novo produto
def adicionar_produto():
    def salvar_produto():
        nome = entry_nome.get()
        quantidade = entry_quantidade.get()

        if nome and quantidade.isdigit():
            cursor.execute("INSERT INTO produtos (nome, quantidade) VALUES (?, ?)", (nome, int(quantidade)))
            conn.commit()
            messagebox.showinfo("Sucesso", "Produto adicionado com sucesso.")
            janela_adicionar_produto.destroy()
        else:
            messagebox.showerror("Erro", "Todos os campos são obrigatórios e quantidade deve ser um número.")

    janela_adicionar_produto = tk.Toplevel()
    janela_adicionar_produto.title("Adicionar Produto")

    tk.Label(janela_adicionar_produto, text="Nome do Produto:").grid(row=0, column=0, pady=5)
    entry_nome = tk.Entry(janela_adicionar_produto)
    entry_nome.grid(row=0, column=1, pady=5)

    tk.Label(janela_adicionar_produto, text="Quantidade:").grid(row=1, column=0, pady=5)
    entry_quantidade = tk.Entry(janela_adicionar_produto)
    entry_quantidade.grid(row=1, column=1, pady=5)

    tk.Button(janela_adicionar_produto, text="Salvar", command=salvar_produto).grid(row=2, column=0, columnspan=2, pady=10)

# Função para visualizar o estoque
def visualizar_estoque():
    janela_estoque = tk.Toplevel()
    janela_estoque.title("Estoque")

    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    texto_estoque = ""
    for produto in produtos:
        texto_estoque += f"ID: {produto[0]}, Nome: {produto[1]}, Quantidade: {produto[2]}\n"

    tk.Label(janela_estoque, text=texto_estoque).pack(padx=10, pady=10)

# Função para abrir o menu principal
def abrir_menu_principal(nivel):
    janela_menu = tk.Tk()
    janela_menu.title("Menu Principal")

    if nivel == "admin":
        tk.Button(janela_menu, text="Criar Usuário", command=criar_usuario).pack(pady=5)

    tk.Button(janela_menu, text="Adicionar Produto", command=adicionar_produto).pack(pady=5)
    tk.Button(janela_menu, text="Visualizar Estoque", command=visualizar_estoque).pack(pady=5)
    tk.Button(janela_menu, text="Sair", command=janela_menu.destroy).pack(pady=10)

    janela_menu.mainloop()

# Janela de login
janela_login = tk.Tk()
janela_login.title("Login")

tk.Label(janela_login, text="Usuário:").grid(row=0, column=0, pady=5)
entry_usuario = tk.Entry(janela_login)
entry_usuario.grid(row=0, column=1, pady=5)

tk.Label(janela_login, text="Senha:").grid(row=1, column=0, pady=5)
entry_senha = tk.Entry(janela_login, show="*")
entry_senha.grid(row=1, column=1, pady=5)

tk.Button(janela_login, text="Login", command=autenticar).grid(row=2, column=0, columnspan=2, pady=10)

janela_login.mainloop()

# Fechando a conexão com o banco de dados
conn.close()
