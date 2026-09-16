import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import pandas as pd
import tabula
from PyPDF2 import PdfReader
import os
import threading
import time


# Função para selecionar o arquivo PDF de origem
def select_pdf_file():
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    pdf_entry.delete(0, tk.END)
    pdf_entry.insert(0, file_path)


# Função para selecionar o local onde salvar o arquivo Excel
def select_excel_location():
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
    excel_entry.delete(0, tk.END)
    excel_entry.insert(0, file_path)


# Função para extrair a informação "Func.:" do PDF
def extract_func_info(pdf_path):
    with open(pdf_path, 'rb') as f:
        pdf = PdfReader(f)
        num_pages = len(pdf.pages)
        func_info = []

        for page_num in range(num_pages):
            page = pdf.pages[page_num]
            text = page.extract_text()
            lines = text.split('\n')
            for line in lines:
                if line.startswith("Func.:"):
                    func_info.append(line)
                    break
            else:
                func_info.append("Func.: Não Encontrado")

    return func_info


# Função para extrair tabelas do PDF usando tabula
def extract_tables_from_pdf(pdf_path):
    tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
    return tables


# Função para atualizar a barra de progresso e a porcentagem
def update_progress(progress, label, value):
    progress['value'] = value
    label.config(text=f'{value}%')
    root.update_idletasks()


# Função para converter PDF em Excel com mais informações
def pdf_to_excel(pdf_path, excel_path):
    if pdf_path and excel_path:
        # Atualizar a barra de progresso
        update_progress(progress, progress_label, 10)

        # Extrair a informação "Func.:" de cada página
        func_info = extract_func_info(pdf_path)
        update_progress(progress, progress_label, 30)

        # Extrair tabelas do PDF
        tables = extract_tables_from_pdf(pdf_path)
        update_progress(progress, progress_label, 60)

        # Inicializar uma lista para armazenar todas as tabelas e separadores
        combined_data = []

        # Combinar todas as tabelas e adicionar a informação "Func.:" entre elas
        for i, table in enumerate(tables):
            if i < len(func_info):
                combined_data.append(pd.DataFrame([[func_info[i]]], columns=["Func. Info"]))
            combined_data.append(pd.DataFrame(table))

        # Concatenar todas as tabelas e informações em um único DataFrame
        combined_df = pd.concat(combined_data, ignore_index=True)
        update_progress(progress, progress_label, 80)

        # Salvar como arquivo Excel
        combined_df.to_excel(excel_path, index=False)
        update_progress(progress, progress_label, 100)

        result_label.config(text=f'PDF convertido para Excel em:\n{excel_path}')

        # Habilitar o botão de abrir arquivo
        open_button.config(state=tk.NORMAL)
    else:
        result_label.config(text='Por favor, selecione o arquivo PDF e o local de salvamento.')


# Função para iniciar a conversão em um thread separado
def start_conversion():
    # Iniciar o contador de tempo
    start_time = time.time()
    update_timer(start_time)

    pdf_path = pdf_entry.get()
    excel_path = excel_entry.get()
    conversion_thread = threading.Thread(target=pdf_to_excel, args=(pdf_path, excel_path))
    conversion_thread.start()


# Função para atualizar o timer
def update_timer(start_time):
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    timer_label.config(text=f"Tempo decorrido: {minutes:02d}:{seconds:02d}")
    root.after(1000, update_timer, start_time)


# Função para abrir o arquivo Excel convertido
def open_excel_file():
    excel_path = excel_entry.get()
    if os.path.exists(excel_path):
        os.startfile(excel_path)


# Configuração da interface gráfica usando tkinter
root = tk.Tk()
root.title("Conversor PDF para Excel")

# Interface para seleção do arquivo PDF
tk.Label(root, text="PDF de origem:").grid(row=0, column=0, padx=10, pady=10)
pdf_entry = tk.Entry(root, width=50)
pdf_entry.grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="Selecionar PDF", command=select_pdf_file).grid(row=0, column=2, padx=10, pady=10)

# Interface para seleção do local de salvamento do Excel
tk.Label(root, text="Salvar como Excel:").grid(row=1, column=0, padx=10, pady=10)
excel_entry = tk.Entry(root, width=50)
excel_entry.grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="Selecionar local", command=select_excel_location).grid(row=1, column=2, padx=10, pady=10)

# Botão para iniciar a conversão
tk.Button(root, text="Converter PDF para Excel", command=start_conversion).grid(row=2, column=1, padx=10, pady=20)

# Barra de progresso
progress = ttk.Progressbar(root, orient=tk.HORIZONTAL, length=400, mode='determinate')
progress.grid(row=3, column=1, padx=10, pady=10)

# Rótulo para a porcentagem
progress_label = tk.Label(root, text="0%")
progress_label.grid(row=3, column=2, padx=10, pady=10)

# Rótulo para o timer
timer_label = tk.Label(root, text="Tempo decorrido: 00:00")
timer_label.grid(row=4, column=1, padx=10, pady=10)

# Resultado da operação
result_label = tk.Label(root, text="", wraplength=400)
result_label.grid(row=5, column=1, padx=10, pady=10)

# Botão para abrir o arquivo Excel
open_button = tk.Button(root, text="Abrir Excel", command=open_excel_file, state=tk.DISABLED)
open_button.grid(row=6, column=1, padx=10, pady=10)

root.mainloop()
