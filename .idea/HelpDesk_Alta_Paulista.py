import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl


class Browser(QMainWindow):
    def __init__(self, url):
        super().__init__()
        self.setWindowTitle('FTECH - Cliente:Alta Paulista')

        # Cria o widget de visualização do navegador
        self.browser = QWebEngineView()

        # Converte a string da URL para um objeto QUrl
        qurl = QUrl(url)

        # Define a URL do navegador
        self.browser.setUrl(qurl)
        self.setCentralWidget(self.browser)

        # Obtém o cookie store da página do navegador
        cookie_store = self.browser.page().profile().cookieStore()

        # Permite o redimensionamento e a adição de botões padrão da janela
        self.setWindowFlags(
            Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        # Abre a janela maximizada
        self.showMaximized()


def open_url_in_background(url):
    app = QApplication(sys.argv)
    browser = Browser(url)
    browser.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    url = 'https://altapaulista.tomticket.com/helpdesk'
    open_url_in_background(url)




