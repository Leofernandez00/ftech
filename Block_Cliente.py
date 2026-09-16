import socket
import tkinter as tk
from tkinter import messagebox
import subprocess

# Função para obter o IP do cliente automaticamente
def obter_ip_cliente():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Conecta ao DNS do Google para pegar o IP local
        ip_cliente = s.getsockname()[0]
        s.close()
        return ip_cliente
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao obter o IP: {str(e)}")
        return None

# Função para abrir a porta no firewall do Windows
def liberar_porta_firewall(porta):
    try:
        subprocess.run(f"netsh advfirewall firewall add rule name=\"Liberar Porta {porta}\" dir=in action=allow protocol=TCP localport={porta}", check=True, shell=True)
        subprocess.run(f"netsh advfirewall firewall add rule name=\"Liberar Porta {porta}\" dir=out action=allow protocol=TCP localport={porta}", check=True, shell=True)
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao liberar a porta no firewall: {str(e)}")

# Função para realizar a conexão com o Administrador
def conectar_administrador(ip, porta):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((ip, int(porta)))
        return client_socket
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao conectar: {str(e)}")
        return None

# Função que realiza ações com base no comando recebido
def executar_comando(comando):
    if comando == "bloquear_sites":
        return "Sites bloqueados!"
    elif comando == "desbloquear_sites":
        return "Sites desbloqueados!"
    elif comando == "bloquear_cmd":
        return "CMD bloqueado!"
    elif comando == "desbloquear_cmd":
        return "CMD desbloqueado!"
    elif comando == "obter_status":
        return "Sites: Desbloqueados, CMD: Bloqueado"
    else:
        return "Comando desconhecido"

# Função para iniciar o cliente e conectar ao administrador
def iniciar_cliente():
    nome_cliente = entry_nome.get()
    porta_cliente = entry_porta_cliente.get()
    ip_administrador = entry_ip_admin.get()
    porta_administrador = entry_porta_admin.get()

    if not nome_cliente or not porta_cliente or not ip_administrador or not porta_administrador:
        messagebox.showwarning("Aviso", "Por favor, preencha todas as informações.")
        return

    try:
        # Libera a porta no firewall
        liberar_porta_firewall(porta_cliente)

        # Inicia o socket do cliente
        servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor_socket.bind(("0.0.0.0", int(porta_cliente)))
        servidor_socket.listen(1)

        messagebox.showinfo("Cliente", f"Cliente {nome_cliente} aguardando comandos do administrador...")

        while True:
            client_socket, addr = servidor_socket.accept()
            comando = client_socket.recv(1024).decode()
            resposta = executar_comando(comando)
            client_socket.send(resposta.encode())
            client_socket.close()

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao iniciar cliente: {str(e)}")

# Interface gráfica para coletar informações do cliente e administrador
janela = tk.Tk()
janela.title("Configuração do Cliente")

# Obter IP do cliente automaticamente
ip_cliente = obter_ip_cliente()

# Exibir IP do Cliente na tela
tk.Label(janela, text="IP do Cliente:").pack(pady=5)
entry_ip_cliente = tk.Entry(janela)
entry_ip_cliente.pack(pady=5)
entry_ip_cliente.insert(0, ip_cliente)
entry_ip_cliente.config(state="disabled")  # IP não pode ser editado

# Campo para o nome do cliente
tk.Label(janela, text="Nome do Cliente:").pack(pady=5)
entry_nome = tk.Entry(janela)
entry_nome.pack(pady=5)

# Campo para a porta do cliente
tk.Label(janela, text="Porta do Cliente:").pack(pady=5)
entry_porta_cliente = tk.Entry(janela)
entry_porta_cliente.pack(pady=5)

# Campo para o IP do Administrador
tk.Label(janela, text="IP do Administrador:").pack(pady=5)
entry_ip_admin = tk.Entry(janela)
entry_ip_admin.pack(pady=5)

# Campo para a porta do Administrador
tk.Label(janela, text="Porta do Administrador:").pack(pady=5)
entry_porta_admin = tk.Entry(janela)
entry_porta_admin.pack(pady=5)

# Botão para iniciar o cliente
tk.Button(janela, text="Iniciar Cliente", command=iniciar_cliente).pack(pady=10)

janela.mainloop()
