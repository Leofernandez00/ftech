import os
import pyautogui
import time
from tkinter import Tk, filedialog

def select_files():
    root = Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(title='Selecione os arquivos XLSX', filetypes=[('Excel files', '*.xlsx')])
    return root.tk.splitlist(file_paths)

def select_output_folder():
    root = Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory(title='Selecione a pasta de destino para os PDFs')
    return folder_path

def main():
    files = select_files()
    output_folder = select_output_folder()

    for file in files:
        # Abrir o arquivo XLSX
        os.startfile(file)
        time.sleep(2)  # Aguardar 2 segundos para o Excel abrir completamente

        # Selecionar a área A1:V57
        pyautogui.hotkey('ctrl', 'shift', 'right')
        pyautogui.hotkey('ctrl', 'shift', 'down')

        # Esperar um momento para a seleção ser processada
        time.sleep(1)

        # Abrir o menu "Salvar Como"
        pyautogui.hotkey('alt', 'f')
        pyautogui.press('a')
        pyautogui.press('v')

        # Esperar pela janela "Salvar Como" aparecer
        time.sleep(1)

        # Selecionar "PDF" na lista de formatos de arquivo
        pyautogui.typewrite('pdf')
        pyautogui.press('enter')

        # Esperar um momento para o Excel processar a mudança de formato
        time.sleep(1)

        # Digitar o nome do arquivo e selecionar a pasta de destino
        filename = os.path.splitext(os.path.basename(file))[0] + '.pdf'
        pdf_path = os.path.join(output_folder, filename)
        pyautogui.typewrite(pdf_path)

        # Confirmar a ação
        pyautogui.press('enter')

if __name__ == "__main__":
    main()
