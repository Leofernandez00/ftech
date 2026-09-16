import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)

    def acceptNavigationRequest(self, url, navigation_type, is_redirect):
        # Permite navegação da página principal
        if navigation_type == QWebEnginePage.NavigationType.NavigationTypeMainFrame:
            return True
        return False

class Navegador(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Navegador Restrito")
        self.setGeometry(100, 100, 1024, 768)

        self.webview = QWebEngineView(self)
        self.setCentralWidget(self.webview)

        page = CustomWebEnginePage(self)
        self.webview.setPage(page)

        self.webview.setUrl(QUrl("https://ap.lhftech.com.br"))

        self.webview.page().profile().downloadRequested.connect(self.on_download_requested)

    def on_download_requested(self, download):
        options = QFileDialog.Options()
        suggested_filename = download.suggestedFileName()

        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo", suggested_filename, "Todos os Arquivos (*)",
                                                   options=options)

        if file_path:
            download.setPath(file_path)
            download.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = Navegador()
    janela.show()
    sys.exit(app.exec())
