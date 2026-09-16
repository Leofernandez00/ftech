import tkinter as tk
import subprocess

def open_program(program_path):
    subprocess.Popen(program_path)

def create_button(text, program_path):
    return tk.Button(root, text=text, command=lambda: open_program(program_path))

root = tk.Tk()
root.title("Abrir Programas")

# Criando os botões e associando-os aos caminhos dos programas
button_dracena = create_button("DRACENA", r"C:\DIMEP\Alta Dracena\ExemploREP.exe")
button_nova_andradina = create_button("NOVA ANDRADINA", r"C:\DIMEP\Nova Andradina\ExemploREP.exe")
button_aracatuba = create_button("ARAÇATUBA", r"C:\DIMEP\Araçatuba\ExemploREP.exe")
button_daniele = create_button("DANIELE", r"C:\DIMEP\Daniele\ExemploREP.exe")

# Posicionando os botões na tela
button_dracena.pack()
button_nova_andradina.pack()
button_aracatuba.pack()
button_daniele.pack()

root.mainloop()
