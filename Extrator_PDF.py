import os
import PyPDF2
import pdfplumber
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import re


def sanitize_filename(name):
    # Substituir caracteres inválidos para nomes de arquivos por sublinhado
    return re.sub(r'[\\/*?:"<>|]', '_', name)


def extract_employee_name(page_text):
    # Função para extrair o nome do funcionário do texto da página.
    lines = page_text.split('\n')
    for i, line in enumerate(lines):
        if 'Funcionário' in line:
            if i + 1 < len(lines):
                return lines[i + 1].strip()
    return None


def split_pdf_by_pages(input_pdf_path, output_dir, status_label, progress_bar):
    # Certifique-se de que o diretório de saída existe
    os.makedirs(output_dir, exist_ok=True)

    with open(input_pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)

        progress_bar["maximum"] = num_pages

        with pdfplumber.open(input_pdf_path) as pdf:
            for page_number in range(num_pages):
                page = pdf.pages[page_number]
                page_text = page.extract_text()
                employee_name = extract_employee_name(page_text)

                if employee_name:
                    sanitized_employee_name = sanitize_filename(employee_name)
                    output_filename = f"{sanitized_employee_name}.pdf"
                    output_path = os.path.join(output_dir, output_filename)

                    pdf_writer = PyPDF2.PdfWriter()
                    pdf_writer.add_page(pdf_reader.pages[page_number])

                    with open(output_path, 'wb') as output_pdf:
                        pdf_writer.write(output_pdf)
                    status_label.config(text=f"Página {page_number + 1} salva como {output_filename}.")
                else:
                    status_label.config(text=f"Nome do funcionário não encontrado na página {page_number + 1}.")

                progress_bar["value"] = page_number + 1
                root.update_idletasks()

    messagebox.showinfo("Concluído", "Divisão do PDF concluída com sucesso!")
    status_label.config(text="Processo concluído!")


def select_input_file():
    input_pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    input_entry.delete(0, tk.END)
    input_entry.insert(0, input_pdf_path)


def select_output_dir():
    output_dir = filedialog.askdirectory()
    output_entry.delete(0, tk.END)
    output_entry.insert(0, output_dir)


def process_pdf():
    input_pdf_path = input_entry.get()
    output_dir = output_entry.get()

    if not input_pdf_path or not output_dir:
        messagebox.showerror("Erro", "Por favor, selecione o arquivo PDF de entrada e o diretório de saída.")
        return

    split_pdf_by_pages(input_pdf_path, output_dir, status_label, progress_bar)


# Configurar a interface gráfica
root = tk.Tk()
root.title("Dividir PDF por Página")

tk.Label(root, text="Selecione o arquivo PDF de entrada:").grid(row=0, column=0, padx=10, pady=10)
input_entry = tk.Entry(root, width=50)
input_entry.grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="Procurar", command=select_input_file).grid(row=0, column=2, padx=10, pady=10)

tk.Label(root, text="Selecione o diretório de saída:").grid(row=1, column=0, padx=10, pady=10)
output_entry = tk.Entry(root, width=50)
output_entry.grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="Procurar", command=select_output_dir).grid(row=1, column=2, padx=10, pady=10)

tk.Button(root, text="Dividir PDF", command=process_pdf).grid(row=2, column=0, columnspan=3, padx=10, pady=20)

status_label = tk.Label(root, text="")
status_label.grid(row=3, column=0, columnspan=3, padx=10, pady=10)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
progress_bar.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

root.mainloop()
