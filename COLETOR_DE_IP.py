import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import tkinter as tk
import threading
import schedule
import time

# Função para obter o IP público
def get_public_ip():
    response = requests.get('https://api.ipify.org')
    return response.text

# Função para enviar email
def send_email(ip):
    sender_email = "sistemas@altapaulistapecas.com.br"
    receiver_email = "sistemas@altapaulistapecas.com.br"
    password = "aX24mn8?"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "IP Público do Dia - Filial Assis Loja"

    body = f"Segue IP público da filial de Assis Loja: {ip}"
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('mail.altapaulistapecas.com.br', 587)
    server.starttls()
    server.login(sender_email, password)
    text = msg.as_string()
    server.sendmail(sender_email, receiver_email, text)
    server.quit()

# Função para criar janela com Tkinter
def show_ip_window(ip):
    def send_ip_now():
        send_email(ip)
        result_label.config(text="IP enviado com sucesso!")

    root = tk.Tk()
    root.title("IP Público")
    label = tk.Label(root, text=f"Seu IP público é: {ip}")
    label.pack(pady=20)

    send_button = tk.Button(root, text="Enviar IP Agora", command=send_ip_now)
    send_button.pack(pady=10)

    result_label = tk.Label(root, text="")
    result_label.pack(pady=10)

    root.mainloop()

# Função a ser agendada para envio de email
def job():
    ip = get_public_ip()
    send_email(ip)

# Função para rodar o agendador em segundo plano
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Obtém o IP e mostra na janela
    ip = get_public_ip()
    threading.Thread(target=show_ip_window, args=(ip,)).start()

    # Agenda o envio de email para uma vez ao dia
    schedule.every().day.at("08:01").do(job)

    # Inicia o loop do agendador em uma thread separada
    threading.Thread(target=run_schedule).start()
