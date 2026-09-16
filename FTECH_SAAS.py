import os
import requests
import webview
import socket

APPSHEET_URL = (
    "https://www.appsheet.com/start/"
    "8a8b91d3-535d-4517-bb03-1e9f015a419d"

#https://www.appsheet.com/start/8a8b91d3-535d-4517-bb03-1e9f015a419d
#https://www.appsheet.com/start/c13b307f-7eb9-4566-ae95-90c7711e3f7b

#FTECH VENDAS
    #https://www.appsheet.com/start/5f2a6d8b-6bac-42bc-8df7-86ca0408a96d
#FTECH COMPLETO
#    "8a8b91d3-535d-4517-bb03-1e9f015a419d"
#    "?platform=desktop"
#    "#viewStack[0][identifier][Type]=Control"
#    "&viewStack[0][identifier][Name]=P%C3%A1gina%20Inicial"
#    "&appName=ControlesAltaPaulista-639513597"
)


def get_machine_name():
    try:
        return socket.gethostname()
    except Exception as e:
        print(f"Erro ao obter nome da máquina: {e}")
        return "Desconhecido"

# JavaScript injetado para controle de zoom
ZOOM_JS = r"""
(function () {
    if (window.__zoomInstalled) return;
    window.__zoomInstalled = true;

    let zoom = parseFloat(localStorage.getItem('ftech_zoom')) || 1.0;

    function applyZoom() {
        document.body.style.zoom = zoom;
        localStorage.setItem('ftech_zoom', zoom);
    }

    applyZoom();

    // Ctrl + Scroll
    window.addEventListener('wheel', function (e) {
        if (e.ctrlKey) {
            e.preventDefault();

            if (e.deltaY < 0) {
                zoom += 0.1;
            } else {
                zoom -= 0.1;
            }

            zoom = Math.min(Math.max(zoom, 0.5), 3.0);
            applyZoom();
        }
    }, { passive: false });

    // Botões flutuantes
    const container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.right = '15px';
    container.style.bottom = '15px';
    container.style.zIndex = '99999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '6px';

    function makeButton(text, onclick) {
        const btn = document.createElement('button');
        btn.innerText = text;
        btn.style.width = '42px';
        btn.style.height = '42px';
        btn.style.fontSize = '22px';
        btn.style.cursor = 'pointer';
        btn.style.borderRadius = '8px';
        btn.style.border = 'none';
        btn.style.background = '#33e60b';
        btn.style.color = '#030303';
        btn.onclick = onclick;
        return btn;
    }

    const zoomIn = makeButton('+', () => {
        zoom = Math.min(zoom + 0.1, 3.0);
        applyZoom();
    });

    const zoomOut = makeButton('-', () => {
        zoom = Math.max(zoom - 0.1, 0.5);
        applyZoom();
    });

    container.appendChild(zoomIn);
    container.appendChild(zoomOut);
    document.body.appendChild(container);
})();
"""

if __name__ == "__main__":
    ip = get_machine_name()

    DATA_DIR = os.path.join(os.getcwd(), "webview_profile")
    os.makedirs(DATA_DIR, exist_ok=True)

    webview.settings["ALLOW_DOWNLOADS"] = True

    window = webview.create_window(
        title=f"FTECH | Módulo Vendas | Empresa: Alta Paulista | Login: {ip}",
        url=APPSHEET_URL,
        width=1200,
        height=800,
        resizable=True
    )

    def on_loaded():
        window.evaluate_js(ZOOM_JS)

    window.events.loaded += on_loaded

    webview.start(
        gui="edgechromium",
        private_mode=False,
        storage_path=DATA_DIR,
        debug=True
    )

