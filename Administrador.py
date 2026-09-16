import tkinter as tk
from tkinter import messagebox

class AdminApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Administração de Bloqueios")
        self.master.geometry("600x500")

        # Exemplo de lista de clientes conectados
        self.clients_label = tk.Label(master, text="Clientes Conectados")
        self.clients_label.pack()

        self.clients_listbox = tk.Listbox(master, height=6, selectmode=tk.SINGLE)
        self.clients_listbox.pack()

        self.refresh_button = tk.Button(master, text="Atualizar Lista", command=self.refresh_clients)
        self.refresh_button.pack()

        # Botão para visualizar logs
        self.view_logs_button = tk.Button(master, text="Visualizar Logs", command=self.view_logs)
        self.view_logs_button.pack()

        # Opções de bloqueios
        self.block_usb_button = tk.Button(master, text="Bloquear USB", command=self.block_usb)
        self.block_usb_button.pack()

        self.block_cmd_button = tk.Button(master, text="Bloquear CMD", command=self.block_cmd)
        self.block_cmd_button.pack()

        self.block_registry_button = tk.Button(master, text="Bloquear Editor de Registro", command=self.block_registry)
        self.block_registry_button.pack()

        self.block_user_manager_button = tk.Button(master, text="Bloquear Gerenciador de Usuários", command=self.block_user_manager)
        self.block_user_manager_button.pack()

        self.block_network_button = tk.Button(master, text="Bloquear Acesso à Rede", command=self.block_network)
        self.block_network_button.pack()

        self.block_powershell_button = tk.Button(master, text="Bloquear PowerShell", command=self.block_powershell)
        self.block_powershell_button.pack()

        self.block_vbs_button = tk.Button(master, text="Bloquear Execução de VBS", command=self.block_vbs)
        self.block_vbs_button.pack()

    def refresh_clients(self):
        # Aqui você pode colocar código para pegar a lista de clientes conectados
        # e mostrar na interface. Por enquanto, vamos simular:
        self.clients_listbox.delete(0, tk.END)
        self.clients_listbox.insert(tk.END, "Cliente 1 - Conectado")
        self.clients_listbox.insert(tk.END, "Cliente 2 - Conectado")

    def view_logs(self):
        # Aqui você pode adicionar uma função para visualizar os logs dos clientes.
        messagebox.showinfo("Logs", "Exibindo logs das atividades")

    def block_usb(self):
        # Ações para bloquear o USB
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio USB", f"USB foi bloqueado para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

    def block_cmd(self):
        # Ações para bloquear o CMD
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio CMD", f"CMD foi bloqueado para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

    def block_registry(self):
        # Ações para bloquear o editor de registro
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio Editor de Registro", f"Editor de Registro foi bloqueado para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

    def block_user_manager(self):
        # Ações para bloquear o gerenciador de usuários
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio Gerenciador de Usuários", f"Gerenciador de Usuários foi bloqueado para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

    def block_network(self):
        # Ações para bloquear o acesso à rede
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio Rede", f"Acesso à rede foi bloqueado para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

    def block_powershell(self):
        # Ações para bloquear o PowerShell
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio PowerShell", f"PowerShell foi bloqueado para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

    def block_vbs(self):
        # Ações para bloquear o VBS
        selected_client = self.clients_listbox.curselection()
        if selected_client:
            client = self.clients_listbox.get(selected_client)
            messagebox.showinfo("Bloqueio VBS", f"Execução de VBS foi bloqueada para o {client}!")
        else:
            messagebox.showwarning("Aviso", "Selecione um cliente!")

if __name__ == "__main__":
    root = tk.Tk()
    app = AdminApp(root)
    root.mainloop()

