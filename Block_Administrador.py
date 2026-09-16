import sqlite3
import tkinter as tk
from tkinter import messagebox
from threading import Thread
import socket
import json

# Configuração global do servidor
servidor_ativo = False
servidor_socket = None
clientes_conectados = []


# Configurando o banco de dados SQLite
def configurar_bd():
    conn = sqlite3.connect('configuracoes_administrador.db')
    cursor = conn.cursor()

    # Criar tabela de clientes
    cursor.execute('''CREATE TABLE IF NOT EXISTS Clientes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT,
                        ip TEXT,
                        porta INTEGER
                      )''')

    # Criar tabela de configurações
    cursor.execute('''CREATE TABLE IF NOT EXISTS Configuracoes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cliente_id INTEGER,
                        bloquear_sites BOOLEAN,
                        sites_bloqueados TEXT,
                        bloquear_ips BOOLEAN,
                        bloquear_cmd BOOLEAN,
                        bloquear_registro BOOLEAN,
                        bloquear_gerenciador BOOLEAN,
                        bloquear_rede BOOLEAN,
                        bloquear_vbs BOOLEAN,
                        bloquear_powershell BOOLEAN,
                        FOREIGN KEY (cliente_id) REFERENCES Clientes(id)
                      )''')
    conn.commit()
    conn.close()


# Função para salvar as configurações no banco de dados
def salvar_configuracoes():
    cliente_id = cliente_selecionado.get()
    bloquear_sites = var_sites.get()
    sites = entry_sites.get() if bloquear_sites else None
    bloquear_ips = var_ips.get()
    bloquear_cmd = var_cmd.get()
    bloquear_registro = var_registro.get()
    bloquear_gerenciador = var_gerenciador.get()
    bloquear_rede = var_rede.get()
    bloquear_vbs = var_vbs.get()
    bloquear_powershell = var_powershell.get()

    conn = sqlite3.connect('configuracoes_administrador.db')
    cursor = conn.cursor()

    cursor.execute('''INSERT INTO Configuracoes (cliente_id, bloquear_sites, sites_bloqueados, bloquear_ips, bloquear_cmd, 
                    bloquear_registro, bloquear_gerenciador, bloquear_rede, bloquear_vbs, bloquear_powershell)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (cliente_id, bloquear_sites, sites, bloquear_ips, bloquear_cmd, bloquear_registro,
                    bloquear_gerenciador, bloquear_rede, bloquear_vbs, bloquear_powershell))

    conn.commit()
    conn.close()
    messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")


# Funções para controle do servidor
def iniciar_servidor():
    global servidor_ativo, servidor_socket
    if not servidor_ativo:
        servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor_socket.bind(('0.0.0.0', int(entry_porta_servidor.get())))
        servidor_socket.listen(5)
        servidor_ativo = True
        atualizar_status_servidor()
        Thread(target=aceitar_conexoes).start()


def aceitar_conexoes():
    while servidor_ativo:
        cliente, endereco = servidor_socket.accept()
        print(f"Conectado com {endereco}")
        clientes_conectados.append(cliente)  # Adiciona o cliente à lista
        Thread(target=gerenciar_cliente, args=(cliente,)).start()


def gerenciar_cliente(cliente_socket):
    while servidor_ativo:
        try:
            mensagem = cliente_socket.recv(1024)
            if not mensagem:
                break
            print(f"Mensagem recebida: {mensagem.decode('utf-8')}")
        except Exception as e:
            print(f"Erro na comunicação: {e}")
            break

    cliente_socket.close()


def parar_servidor():
    global servidor_ativo, servidor_socket
    if servidor_ativo:
        servidor_ativo = False
        servidor_socket.close()
        for cliente in clientes_conectados:
            cliente.close()
        atualizar_status_servidor()


def atualizar_status_servidor():
    if servidor_ativo:
        lbl_status.config(text="Servidor Ativo", bg="green")
    else:
        lbl_status.config(text="Servidor Parado", bg="red")


# Função para cadastrar cliente
def cadastrar_cliente():
    nome = entry_nome_cliente.get()
    ip = entry_ip_cliente.get()
    porta = entry_porta_cliente.get()

    if nome and ip and porta.isdigit():
        conn = sqlite3.connect('configuracoes_administrador.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Clientes (nome, ip, porta) VALUES (?, ?, ?)", (nome, ip, int(porta)))
        conn.commit()
        conn.close()
        messagebox.showinfo("Sucesso", "Cliente cadastrado com sucesso!")
        atualizar_lista_clientes()
    else:
        messagebox.showwarning("Erro", "Preencha todos os campos corretamente.")


# Atualiza a lista de clientes
def atualizar_lista_clientes():
    conn = sqlite3.connect('configuracoes_administrador.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM Clientes")
    clientes = cursor.fetchall()
    conn.close()

    cliente_selecionado.set(clientes[0][1] if clientes else "Nenhum cliente cadastrado")
    clientes_nomes = [f"{cliente[1]}" for cliente in clientes] if clientes else ["Nenhum cliente cadastrado"]

    cliente_menu['menu'].delete(0, 'end')  # Limpar o menu
    for nome in clientes_nomes:
        cliente_menu['menu'].add_command(label=nome, command=tk._setit(cliente_selecionado, nome))


# Função para enviar as configurações ao cliente
def enviar_configuracoes_para_cliente():
    cliente_id = cliente_selecionado.get()

    if cliente_id == "Nenhum cliente cadastrado":
        messagebox.showwarning("Erro", "Selecione um cliente primeiro.")
        return

    # Obter as configurações do cliente selecionado
    conn = sqlite3.connect('configuracoes_administrador.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Configuracoes WHERE cliente_id = ?", (cliente_id,))
    configuracoes = cursor.fetchone()
    conn.close()

    if configuracoes:
        # Preparar as configurações para enviar
        dados_configuracoes = {
            "bloquear_sites": configuracoes[2],
            "sites_bloqueados": configuracoes[3],
            "bloquear_ips": configuracoes[4],
            "bloquear_cmd": configuracoes[5],
            "bloquear_registro": configuracoes[6],
            "bloquear_gerenciador": configuracoes[7],
            "bloquear_rede": configuracoes[8],
            "bloquear_vbs": configuracoes[9],
            "bloquear_powershell": configuracoes[10]
        }

        # Enviar as configurações para todos os clientes conectados
        for cliente in clientes_conectados:
            try:
                cliente.sendall(json.dumps(dados_configuracoes).encode('utf-8'))
                messagebox.showinfo("Sucesso", "Configurações enviadas ao cliente!")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível enviar as configurações: {e}")


# Interface gráfica
def criar_interface():
    global cliente_selecionado, var_sites, var_ips, var_cmd, var_registro, var_gerenciador, var_rede, var_vbs, var_powershell, entry_sites, lbl_status, entry_porta_servidor
    global entry_nome_cliente, entry_ip_cliente, entry_porta_cliente, cliente_menu

    janela = tk.Tk()
    janela.title("Administrador de Bloqueios")

    # Seção para selecionar o cliente
    tk.Label(janela, text="Selecione o Cliente").pack(pady=5)
    cliente_selecionado = tk.StringVar(janela)

    # Inicializa a lista de clientes
    cliente_menu = tk.OptionMenu(janela, cliente_selecionado, "")
    cliente_menu.pack(pady=5)

    atualizar_lista_clientes()  # Preenche a lista de clientes ao iniciar

    # Configurar porta do servidor
    tk.Label(janela, text="Porta do Servidor").pack(pady=5)
    entry_porta_servidor = tk.Entry(janela)
    entry_porta_servidor.insert(0, "8485")
    entry_porta_servidor.pack(pady=5)

    # Botões de controle do servidor
    btn_iniciar_servidor = tk.Button(janela, text="Iniciar Servidor", command=iniciar_servidor)
    btn_iniciar_servidor.pack(pady=5)

    btn_parar_servidor = tk.Button(janela, text="Parar Servidor", command=parar_servidor)
    btn_parar_servidor.pack(pady=5)

    # Status do servidor
    lbl_status = tk.Label(janela, text="Servidor Parado", bg="red", width=20)
    lbl_status.pack(pady=5)

    # Opções de bloqueios
    var_sites = tk.BooleanVar()
    var_ips = tk.BooleanVar()
    var_cmd = tk.BooleanVar()
    var_registro = tk.BooleanVar()
    var_gerenciador = tk.BooleanVar()
    var_rede = tk.BooleanVar()
    var_vbs = tk.BooleanVar()
    var_powershell = tk.BooleanVar()

    tk.Checkbutton(janela, text="Bloquear Sites", variable=var_sites).pack(pady=5)
    entry_sites = tk.Entry(janela)
    entry_sites.pack(pady=5)
    tk.Label(janela, text="Digite os sites separados por vírgula").pack(pady=5)

    tk.Checkbutton(janela, text="Bloquear IPs", variable=var_ips).pack(pady=5)
    tk.Checkbutton(janela, text="Bloquear CMD", variable=var_cmd).pack(pady=5)
    tk.Checkbutton(janela, text="Bloquear Editor de Registro", variable=var_registro).pack(pady=5)
    tk.Checkbutton(janela, text="Bloquear Gerenciador de Usuários", variable=var_gerenciador).pack(pady=5)
    tk.Checkbutton(janela, text="Bloquear Configurações de Rede", variable=var_rede).pack(pady=5)
    tk.Checkbutton(janela, text="Bloquear VBS", variable=var_vbs).pack(pady=5)
    tk.Checkbutton(janela, text="Bloquear PowerShell", variable=var_powershell).pack(pady=5)

    tk.Button(janela, text="Salvar Configurações", command=salvar_configuracoes).pack(pady=10)
    tk.Button(janela, text="Enviar Configurações ao Cliente", command=enviar_configuracoes_para_cliente).pack(pady=10)

    # Seção para cadastrar cliente
    tk.Label(janela, text="Cadastrar Cliente").pack(pady=10)
    entry_nome_cliente = tk.Entry(janela)
    entry_nome_cliente.pack(pady=5)
    entry_ip_cliente = tk.Entry(janela)
    entry_ip_cliente.pack(pady=5)
    entry_porta_cliente = tk.Entry(janela)
    entry_porta_cliente.pack(pady=5)

    tk.Button(janela, text="Cadastrar Cliente", command=cadastrar_cliente).pack(pady=10)

    janela.mainloop()


if __name__ == "__main__":
    configurar_bd()
    criar_interface()
