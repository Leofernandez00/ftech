import pyuac

# Solicita permissões de administrador se não tiver
pyuac.runAsAdmin()

# Seu código principal aqui
# Exemplo:
import psutil
import pygetwindow as gw
import tkinter as tk
from tkinter import messagebox, simpledialog, Listbox, Scrollbar, Toplevel
from threading import Thread
import json
import os
import time

# Caminho para salvar configurações
CONFIG_PATH = os.path.expanduser("~/.config_bloqueio_janelas.json")


# Função para carregar configurações
def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"blocked_keywords": [], "blocked_programs": []}
    with open(CONFIG_PATH, "r") as file:
        return json.load(file)


# Função para salvar configurações
def save_config(config):
    with open(CONFIG_PATH, "w") as file:
        json.dump(config, file)


# Função para monitorar e fechar janelas com palavras-chave bloqueadas
def monitor_windows(config):
    while True:
        windows = gw.getAllTitles()
        for window in windows:
            for keyword in config["blocked_keywords"]:
                if keyword.lower() in window.lower():
                    try:
                        # Procura e fecha o processo relacionado
                        for proc in psutil.process_iter(attrs=["pid", "name", "username", "cmdline"]):
                            # Verifica se o nome do processo ou sua linha de comando contém a palavra-chave
                            if keyword.lower() in " ".join(proc.info.get("cmdline", [])).lower():
                                proc.kill()
                                print(f"Fechou janela contendo '{keyword}': {proc.info['name']}")
                    except psutil.NoSuchProcess:
                        pass
        time.sleep(1)  # Evita alto consumo de CPU


# Função para monitorar e fechar programas bloqueados
def monitor_programs(config):
    while True:
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                if proc.info["name"] in config["blocked_programs"]:
                    proc.kill()
                    print(f"Fechou programa bloqueado: {proc.info['name']}")
            except psutil.NoSuchProcess:
                pass
        time.sleep(1)  # Evita alto consumo de CPU


# Função para criar a interface gráfica
def create_gui():
    config = load_config()

    def add_blocked_keyword():
        keyword = simpledialog.askstring("Bloquear Palavra", "Digite a palavra-chave para bloquear:")
        if keyword:
            config["blocked_keywords"].append(keyword)
            config["blocked_keywords"] = list(set(config["blocked_keywords"]))
            save_config(config)
            messagebox.showinfo("Sucesso", f"Palavra-chave bloqueada: {keyword}")

    def add_blocked_program():
        program = simpledialog.askstring("Bloquear Programa", "Digite o nome do programa (ex: chrome.exe):")
        if program:
            config["blocked_programs"].append(program)
            config["blocked_programs"] = list(set(config["blocked_programs"]))
            save_config(config)
            messagebox.showinfo("Sucesso", f"Programa bloqueado: {program}")

    def show_blocked_keywords():
        window = Toplevel()
        window.title("Palavras-chave Bloqueadas")
        window.geometry("400x300")

        listbox = Listbox(window)
        listbox.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        scrollbar = Scrollbar(window)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)

        for keyword in config["blocked_keywords"]:
            listbox.insert("end", keyword)

        def unblock_keyword():
            selected = listbox.curselection()
            if selected:
                keyword = listbox.get(selected[0])
                config["blocked_keywords"].remove(keyword)
                save_config(config)
                listbox.delete(selected[0])
                messagebox.showinfo("Sucesso", f"Palavra-chave desbloqueada: {keyword}")

        tk.Button(window, text="Desbloquear Palavra", command=unblock_keyword).pack(pady=10)
        tk.Button(window, text="Fechar", command=window.destroy).pack(pady=10)

    def show_blocked_programs():
        window = Toplevel()
        window.title("Programas Bloqueados")
        window.geometry("400x300")

        listbox = Listbox(window)
        listbox.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        scrollbar = Scrollbar(window)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)

        for program in config["blocked_programs"]:
            listbox.insert("end", program)

        def unblock_program():
            selected = listbox.curselection()
            if selected:
                program = listbox.get(selected[0])
                config["blocked_programs"].remove(program)
                save_config(config)
                listbox.delete(selected[0])
                messagebox.showinfo("Sucesso", f"Programa desbloqueado: {program}")

        tk.Button(window, text="Desbloquear Programa", command=unblock_program).pack(pady=10)
        tk.Button(window, text="Fechar", command=window.destroy).pack(pady=10)

    # Criar threads para monitorar janelas e programas
    Thread(target=monitor_windows, args=(config,), daemon=True).start()
    Thread(target=monitor_programs, args=(config,), daemon=True).start()

    # Criar janela principal
    window = tk.Tk()
    window.title("Gerenciador de Bloqueios")
    window.geometry("400x400")

    # Botões
    tk.Button(window, text="Adicionar Palavra-chave", command=add_blocked_keyword, width=20).pack(pady=10)
    tk.Button(window, text="Visualizar Palavras Bloqueadas", command=show_blocked_keywords, width=20).pack(pady=10)
    tk.Button(window, text="Adicionar Programa", command=add_blocked_program, width=20).pack(pady=10)
    tk.Button(window, text="Visualizar Programas Bloqueados", command=show_blocked_programs, width=20).pack(pady=10)
    tk.Button(window, text="Sair", command=window.quit, width=20).pack(pady=10)

    window.mainloop()


if __name__ == "__main__":
    create_gui()
