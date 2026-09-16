import tkinter as tk
from tkinter import messagebox
import psycopg2

class ClienteApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Configuração do Cliente")
        self.master.geometry("400x300")

        # Campos de configuração
        self.host_label = tk.Label(master, text="Endereço IP do servidor")
        self.host_label.pack()

        self.host_entry = tk.Entry(master)
        self.host_entry.pack()

        self.port_label = tk.Label(master, text="Porta do servidor")
        self.port_label.pack()

        self.port_entry = tk.Entry(master)
        self.port_entry.insert(0, "5432")  # valor padrão
        self.port_entry.pack()

        self.db_label = tk.Label(master, text="Nome do banco de dados")
        self.db_label.pack()

        self.db_entry = tk.Entry(master)
        self.db_entry.insert(0, "restricoes")  # valor padrão
        self.db_entry.pack()

        self.user_label = tk.Label(master, text="Usuário")
        self.user_label.pack()

        self.user_entry = tk.Entry(master)
        self.user_entry.insert(0, "postgres")  # valor padrão
        self.user_entry.pack()

        self.password_label = tk.Label(master, text="Senha")
        self.password_label.pack()

        self.password_entry = tk.Entry(master, show="*")
        self.password_entry.pack()

        # Botão de conexão
        self.connect_button = tk.Button(master, text="Conectar", command=self.connect_to_db)
        self.connect_button.pack()

    def connect_to_db(self):
        try:
            # Tentando a conexão com os dados inseridos
            conn = psycopg2.connect(
                dbname=self.db_entry.get(),
                user=self.user_entry.get(),
                password=self.password_entry.get(),
                host=self.host_entry.get(),
                port=self.port_entry.get()
            )
            messagebox.showinfo("Conexão", "Conexão bem-sucedida!")
            conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao conectar: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ClienteApp(root)
    root.mainloop()
