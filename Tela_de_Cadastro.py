import sqlite3
from tkinter import messagebox, Tk, Label, Entry, Button, Listbox

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

    def insertUser(self, usuario, senha):
        c = self.conexao.cursor()
        c.execute("INSERT INTO usuarios (usuario, senha) VALUES (?, ?)", (usuario, senha))
        self.conexao.commit()
        c.close()

    def updateUser(self, id, usuario, senha):
        c = self.conexao.cursor()
        c.execute("UPDATE usuarios SET usuario = ?, senha = ? WHERE id = ?", (usuario, senha, id))
        self.conexao.commit()
        c.close()

    def deleteUser(self, id):
        c = self.conexao.cursor()
        c.execute("DELETE FROM usuarios WHERE id = ?", (id,))
        self.conexao.commit()
        c.close()

    def listarUsuarios(self):
        c = self.conexao.cursor()
        c.execute("SELECT id, usuario FROM usuarios")
        usuarios = c.fetchall()
        c.close()
        return usuarios

class TelaCadastro:
    def __init__(self, master):
        self.master = master
        self.master.title("Cadastro de Usuário")
        self.banco = Banco()  # Inicializa o atributo banco

        self.label_usuario = Label(master, text="Usuário:")
        self.label_usuario.grid(row=0, column=0, padx=10, pady=10)

        self.entry_usuario = Entry(master)
        self.entry_usuario.grid(row=0, column=1)

        self.label_senha = Label(master, text="Senha:")
        self.label_senha.grid(row=1, column=0, padx=10, pady=10)

        self.entry_senha = Entry(master, show="*")
        self.entry_senha.grid(row=1, column=1)

        self.botao_cadastrar = Button(master, text="Cadastrar", command=self.cadastrar)
        self.botao_cadastrar.grid(row=2, column=0, padx=10, pady=10)

        self.botao_atualizar = Button(master, text="Atualizar", command=self.atualizar)
        self.botao_atualizar.grid(row=2, column=1, padx=10, pady=10)

        self.botao_excluir = Button(master, text="Excluir", command=self.excluir)
        self.botao_excluir.grid(row=2, column=2, padx=10, pady=10)

        self.lista_usuarios = Listbox(master)
        self.lista_usuarios.grid(row=3, columnspan=3, padx=10, pady=10)
        self.carregar_usuarios()

    def cadastrar(self):
        usuario = self.entry_usuario.get()
        senha = self.entry_senha.get()

        if usuario == "" or senha == "":
            messagebox.showerror("Erro", "Por favor, preencha todos os campos.")
            return

        usuarios = [user[1] for user in self.banco.listarUsuarios()]
        if usuario in usuarios:
            messagebox.showerror("Erro", "Usuário já cadastrado.")
            return

        try:
            self.banco.insertUser(usuario, senha)
            messagebox.showinfo("Sucesso", "Usuário cadastrado com sucesso!")
            self.entry_usuario.delete(0, 'end')
            self.entry_senha.delete(0, 'end')
            self.carregar_usuarios()
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao cadastrar o usuário: {e}")

    def atualizar(self):
        usuario = self.entry_usuario.get()
        senha = self.entry_senha.get()

        if usuario == "" or senha == "":
            messagebox.showerror("Erro", "Por favor, preencha todos os campos.")
            return

        usuarios = [user[1] for user in self.banco.listarUsuarios()]
        if usuario not in usuarios:
            messagebox.showerror("Erro", "Usuário não encontrado.")
            return

        try:
            # Obtem o ID do usuário selecionado para atualização
            id = 1  # Aqui você deve inserir o ID do usuário selecionado (pode ser obtido de uma lista de usuários cadastrados)
            self.banco.updateUser(id, usuario, senha)
            messagebox.showinfo("Sucesso", "Usuário atualizado com sucesso!")
            self.entry_usuario.delete(0, 'end')
            self.entry_senha.delete(0, 'end')
            self.carregar_usuarios()
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao atualizar o usuário: {e}")

    def excluir(self):
        usuario = self.entry_usuario.get()

        if usuario == "":
            messagebox.showerror("Erro", "Por favor, preencha todos os campos.")
            return

        usuarios = [user[1] for user in self.banco.listarUsuarios()]
        if usuario not in usuarios:
            messagebox.showerror("Erro", "Usuário não encontrado.")
            return

        try:
            # Obtem o ID do usuário selecionado para exclusão
            id = 1  # Aqui você deve inserir o ID do usuário selecionado (pode ser obtido de uma lista de usuários cadastrados)
            self.banco.deleteUser(id)
            messagebox.showinfo("Sucesso", "Usuário excluído com sucesso!")
            self.entry_usuario.delete(0, 'end')
            self.entry_senha.delete(0, 'end')
            self.carregar_usuarios()
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao excluir o usuário: {e}")

    def carregar_usuarios(self):
        self.lista_usuarios.delete(0, 'end')  # Limpa a lista de usuários
        usuarios = self.banco.listarUsuarios()
        for user in usuarios:
            self.lista_usuarios.insert('end', f"ID: {user[0]} - Usuário: {user[1]}")


if __name__ == "__main__":
    root = Tk()
    tela_cadastro = TelaCadastro(root)
    root.mainloop()
