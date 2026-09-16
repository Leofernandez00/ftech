import sys
import psutil
import platform
import socket
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import uuid
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl


class Browser(QMainWindow):
    def __init__(self, url):
        super().__init__()
        self.setWindowTitle('HelpDesk - Alta Paulista')
        self.url = url
        self.confirmation_dialog()

    def confirmation_dialog(self):
        # Exibe a mensagem de confirmação
        reply = QMessageBox.question(self, 'Confirmar Envio',
                                     "Deseja enviar informações do sistema para agilizar o atendimento pelo suporte?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            system_info = self.get_system_info()
            self.send_email(system_info)

        # Abra o navegador em ambos os casos
        self.open_browser()

    def open_browser(self):
        # Cria o widget de visualização do navegador
        self.browser = QWebEngineView()

        # Converte a string da URL para um objeto QUrl
        qurl = QUrl(self.url)

        # Define a URL do navegador
        self.browser.setUrl(qurl)
        self.setCentralWidget(self.browser)

        # Permite o redimensionamento e a adição de botões padrão da janela
        self.setWindowFlags(
            Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        # Abre a janela maximizada
        self.showMaximized()

    def get_system_info(self):
        # Informações do sistema
        system_info = {
            'Processor': platform.processor(),
            'Memory': self.get_memory_info(),
            'Storage': self.get_disk_info(),
            'Screen Resolution': str(QApplication.desktop().screenGeometry()),
            'Logged User': psutil.users()[0].name,
            'Network IP': self.get_ip_address(),
            'MAC Address': self.get_mac_address(),
        }
        return system_info

    def get_memory_info(self):
        # Informações de memória RAM
        mem = psutil.virtual_memory()
        return f"{mem.total / (1024 ** 3):.2f} GB"

    def get_disk_info(self):
        # Informações de armazenamento
        partitions = psutil.disk_partitions()
        disk_info = {}
        for partition in partitions:
            if os.name == 'nt':
                if 'fixed' in partition.opts:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info[
                        partition.device] = f"Total: {usage.total / (1024 ** 3):.2f} GB, Free: {usage.free / (1024 ** 3):.2f} GB"
            else:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info[
                    partition.device] = f"Total: {usage.total / (1024 ** 3):.2f} GB, Free: {usage.free / (1024 ** 3):.2f} GB"
        return disk_info

    def get_ip_address(self):
        # IP da rede
        return socket.gethostbyname(socket.gethostname())

    def get_mac_address(self):
        # MAC Address do adaptador
        return ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)])

    def send_email(self, system_info):
        # Configurações do e-mail
        email_sender = 'suporte@altapaulistapecas.com.br'  # Insira seu e-mail
        email_receiver = 'suporte@altapaulistapecas.com.br;cyberbackupdracena@gmail.com'  # E-mail de destino
        password = 'aX24mn8?'  # Senha do seu e-mail

        # Construindo o corpo do e-mail
        msg = MIMEMultipart()
        msg['From'] = email_sender
        msg['To'] = email_receiver
        msg['Subject'] = 'Relatório do Sistema'

        # Corpo da mensagem
        body = "Relatório do Sistema:\n\n"
        for key, value in system_info.items():
            body += f"{key}: {value}\n"
        msg.attach(MIMEText(body, 'plain'))

        # Anexa o arquivo system.conf se existir
        attachment_path = r'C:\Users\Alta Paulista\AppData\Roaming\AnyDesk\system.conf'
        if os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as file:
                attachment = MIMEText(file.read().decode(), 'plain')  # Corrigido aqui para decodificar os bytes
                attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                msg.attach(attachment)

        # Conecta ao servidor SMTP do DreamHost usando SSL na porta 465
        server = smtplib.SMTP_SSL('smtp.dreamhost.com', 465)
        # Login
        server.login(email_sender, password)
        # Envia e-mail
        text = msg.as_string()
        server.sendmail(email_sender, email_receiver, text)
        # Encerra a conexão
        server.quit()


def open_url_in_background(url):
    app = QApplication(sys.argv)
    browser = Browser(url)
    sys.exit(app.exec_())


if __name__ == "__main__":
    url = 'https://altapaulista.tomticket.com/helpdesk'
    open_url_in_background(url)
