import fitz  # PyMuPDF
import pytesseract
from docx import Document
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from PIL import Image
import io


def select_pdf():
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    pdf_entry.delete(0, tk.END)
    pdf_entry.insert(0, pdf_path)


def select_save_path():
    save_path = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("DOCX files", "*.docx")])
    save_entry.delete(0, tk.END)
    save_entry.insert(0, save_path)


def convert_pdf_to_docx():
    pdf_path = pdf_entry.get()
    save_path = save_entry.get()

    if not pdf_path or not save_path:
        messagebox.showerror("Error", "Please select both a PDF file and a save path.")
        return

    try:
        doc = Document()
        pdf_document = fitz.open(pdf_path)

        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes("ppm")))
            text = pytesseract.image_to_string(img, lang="eng")
            doc.add_paragraph(text)

        doc.save(save_path)
        messagebox.showinfo("Success", "PDF successfully converted to DOCX.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# GUI
root = tk.Tk()
root.title("PDF to DOCX Converter")

tk.Label(root, text="Select PDF file:").grid(row=0, column=0, padx=10, pady=10)
pdf_entry = tk.Entry(root, width=50)
pdf_entry.grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="Browse", command=select_pdf).grid(row=0, column=2, padx=10, pady=10)

tk.Label(root, text="Select save path:").grid(row=1, column=0, padx=10, pady=10)
save_entry = tk.Entry(root, width=50)
save_entry.grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="Browse", command=select_save_path).grid(row=1, column=2, padx=10, pady=10)

tk.Button(root, text="Convert", command=convert_pdf_to_docx).grid(row=2, column=0, columnspan=3, pady=20)

root.mainloop()

