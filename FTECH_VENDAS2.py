
import os
import socket
from pathlib import Path

import webview


# ============================================================
# CONFIGURAÇÕES FTECH
# ============================================================

APPSHEET_URL = (
    "https://www.appsheet.com/start/"
    "5f2a6d8b-6bac-42bc-8df7-86ca0408a96d"
)

APP_NOME = "FTECH | Módulo Vendas"
EMPRESA = "Alta Paulista"

# Perfil persistente: evita novo login em toda execução
LOCAL_APPDATA = os.environ.get(
    "LOCALAPPDATA",
    str(Path.home() / "AppData" / "Local")
)

DATA_DIR = os.path.join(
    LOCAL_APPDATA,
    "FTECH",
    "Vendas"
)


# ============================================================
# IDENTIFICAÇÃO DO COMPUTADOR
# ============================================================

def get_machine_name():
    try:
        return socket.gethostname()
    except OSError:
        return "Desconhecido"


# ============================================================
# CONTROLE DE ZOOM
# ============================================================

ZOOM_JS = r"""
(function () {
    if (window.__ftechZoomInstalled) return;
    if (!document.body) return;

    window.__ftechZoomInstalled = true;

    const STORAGE_KEY = "ftech_zoom";

    let zoom = parseFloat(
        localStorage.getItem(STORAGE_KEY) || "1"
    );

    if (!Number.isFinite(zoom)) {
        zoom = 1;
    }

    function limitarZoom(valor) {
        return Math.min(3, Math.max(0.5, valor));
    }

    function aplicarZoom(salvar = false) {
        zoom = Math.round(limitarZoom(zoom) * 10) / 10;

        document.body.style.zoom = String(zoom);

        if (salvar) {
            try {
                localStorage.setItem(STORAGE_KEY, String(zoom));
            } catch (e) {}
        }
    }

    aplicarZoom();

    // CTRL + RODA DO MOUSE
    window.addEventListener(
        "wheel",
        function (e) {
            if (!e.ctrlKey) return;

            e.preventDefault();

            zoom += e.deltaY < 0 ? 0.1 : -0.1;

            aplicarZoom(true);
        },
        { passive: false }
    );

    // CONTAINER DOS BOTÕES
    const container = document.createElement("div");

    container.id = "ftech-zoom-controls";

    Object.assign(container.style, {
        position: "fixed",
        right: "15px",
        bottom: "15px",
        zIndex: "2147483647",
        display: "flex",
        flexDirection: "column",
        gap: "6px"
    });

    function criarBotao(texto, variacao) {
        const btn = document.createElement("button");

        btn.type = "button";
        btn.textContent = texto;

        Object.assign(btn.style, {
            width: "42px",
            height: "42px",
            fontSize: "22px",
            cursor: "pointer",
            borderRadius: "8px",
            border: "none",
            background: "#33e60b",
            color: "#030303"
        });

        btn.addEventListener("click", function () {
            zoom += variacao;
            aplicarZoom(true);
        });

        return btn;
    }

    container.appendChild(criarBotao("+", 0.1));
    container.appendChild(criarBotao("-", -0.1));

    document.body.appendChild(container);
})();
"""


# ============================================================
# APLICATIVO PRINCIPAL
# ============================================================

def main():

    os.makedirs(DATA_DIR, exist_ok=True)

    # Permitir downloads do AppSheet
    webview.settings["ALLOW_DOWNLOADS"] = True

    # Desativar ferramentas de desenvolvimento
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False

    computador = get_machine_name()

    titulo = (
        f"{APP_NOME} | "
        f"Empresa: {EMPRESA} | "
        f"Login: {computador}"
    )

    window = webview.create_window(
        title=titulo,
        url=APPSHEET_URL,
        width=1200,
        height=800,
        resizable=True,
        background_color="#FFFFFF"
    )

    # Executa o zoom após cada carregamento
    def on_loaded():
        try:
            window.run_js(ZOOM_JS)
        except Exception:
            pass

    window.events.loaded += on_loaded

    # Inicialização enxuta
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=DATA_DIR,
        http_server=False
    )


if __name__ == "__main__":
    main()
