import random
import string
import tkinter as tk
from tkinter import messagebox

def gerar_senha():
    comprimento = 12  # Define o tamanho mínimo da senha
    caracteres = string.ascii_letters + string.digits + string.punctuation
    senha = ''.join(random.choice(caracteres) for _ in range(comprimento))
    entrada_senha.delete(0, tk.END)
    entrada_senha.insert(0, senha)

def copiar_senha():
    senha = entrada_senha.get()
    if senha:
        janela.clipboard_clear()
        janela.clipboard_append(senha)
        janela.update()
        messagebox.showinfo("Copiado", "Senha copiada para a área de transferência!")
    else:
        messagebox.showwarning("Aviso", "Nenhuma senha gerada!")

# Criando a interface gráfica
janela = tk.Tk()
janela.title("Gerador de Senhas")
janela.geometry("400x200")
janela.resizable(False, False)

# Criando widgets
label_instrucao = tk.Label(janela, text="Gerador de Senhas Seguras", font=("Arial", 12, "bold"))
label_instrucao.pack(pady=10)

entrada_senha = tk.Entry(janela, font=("Arial", 14), width=30)
entrada_senha.pack(pady=5)

botao_gerar = tk.Button(janela, text="Gerar Senha", command=gerar_senha, font=("Arial", 12), bg="#4CAF50", fg="white")
botao_gerar.pack(pady=5)

botao_copiar = tk.Button(janela, text="Copiar Senha", command=copiar_senha, font=("Arial", 12), bg="#008CBA", fg="white")
botao_copiar.pack(pady=5)

# Iniciar loop da interface gráfica
janela.mainloop()