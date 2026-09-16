import os
import sys
import re
import json
import hmac
import time
import socket
import hashlib
import secrets
import tempfile
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import pyodbc
import requests
import webview
from dotenv import load_dotenv
from packaging.version import Version, InvalidVersion
from PIL import Image, ImageTk

load_dotenv()

APP_NAME = "FTECH Estoque"
APP_VERSION = os.getenv("APP_VERSION", "1.0.1").strip()
SQL_SERVER = os.getenv("SQL_SERVER", "").strip()
SQL_DATABASE = os.getenv("SQL_DATABASE", "").strip()
SQL_USER = os.getenv("SQL_USER", "").strip()
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "").strip()
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server").strip()
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))
MAX_TENTATIVAS = 5

APPSHEET_URL_PADRAO = (
    "https://www.appsheet.com/start/"
    "c13b307f-7eb9-4566-ae95-90c7711e3f7b"
)

ZOOM_JS = r"""
(function () {
    function instalarZoom() {
        if (!document.body) {
            setTimeout(instalarZoom, 300);
            return;
        }
        if (window.__zoomInstalled) return;
        window.__zoomInstalled = true;

        let zoomSalvo = parseFloat(localStorage.getItem('ftech_zoom'));
        let zoomInicial = __FTECH_INITIAL_ZOOM__;
        let zoom = Number.isFinite(zoomSalvo) ? zoomSalvo : zoomInicial;

        function limitarZoom(valor) {
            return Math.min(Math.max(valor, 0.5), 3.0);
        }
        function applyZoom() {
            zoom = limitarZoom(zoom);
            document.body.style.zoom = String(zoom);
            localStorage.setItem('ftech_zoom', String(zoom));
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.salvar_zoom(zoom).catch(function () {});
            }
        }
        applyZoom();

        window.addEventListener('wheel', function (e) {
            if (!e.ctrlKey) return;
            e.preventDefault();
            zoom += e.deltaY < 0 ? 0.1 : -0.1;
            zoom = Math.round(zoom * 10) / 10;
            applyZoom();
        }, { passive: false });

        const container = document.createElement('div');
        container.id = 'ftech-zoom-container';
        container.style.position = 'fixed';
        container.style.right = '15px';
        container.style.bottom = '15px';
        container.style.zIndex = '2147483647';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '6px';

        function makeButton(text, onclick, titulo) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.innerText = text;
            btn.title = titulo;
            btn.style.width = '42px';
            btn.style.height = '42px';
            btn.style.fontSize = '22px';
            btn.style.fontWeight = 'bold';
            btn.style.cursor = 'pointer';
            btn.style.borderRadius = '8px';
            btn.style.border = 'none';
            btn.style.background = '#33e60b';
            btn.style.color = '#030303';
            btn.style.boxShadow = '0 2px 8px rgba(0,0,0,.25)';
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                onclick();
            });
            return btn;
        }

        container.appendChild(makeButton('+', function () {
            zoom = Math.round(Math.min(zoom + 0.1, 3.0) * 10) / 10;
            applyZoom();
        }, 'Aumentar zoom'));

        container.appendChild(makeButton('−', function () {
            zoom = Math.round(Math.max(zoom - 0.1, 0.5) * 10) / 10;
            applyZoom();
        }, 'Diminuir zoom'));

        document.body.appendChild(container);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', instalarZoom, { once: true });
    } else {
        instalarZoom();
    }
})();
"""

THEME_JS = r"""
(function () {
    function instalarTema() {
        if (!document.body) {
            setTimeout(instalarTema, 300);
            return;
        }
        if (window.__ftechThemeInstalled) return;
        window.__ftechThemeInstalled = true;

        const temaSalvo = localStorage.getItem('ftech_tema');
        let temaEscuro = temaSalvo === null
            ? __FTECH_INITIAL_DARK__
            : temaSalvo === 'escuro';

        const style = document.createElement('style');
        style.id = 'ftech-theme-style';
        style.textContent = `
            html.ftech-dark-theme {
                background: #202124 !important;
                filter: invert(0.88) hue-rotate(180deg) !important;
            }
            html.ftech-dark-theme img,
            html.ftech-dark-theme video,
            html.ftech-dark-theme canvas,
            html.ftech-dark-theme svg,
            html.ftech-dark-theme [style*="background-image"] {
                filter: invert(1) hue-rotate(180deg) !important;
            }
            #ftech-theme-button {
                position: fixed !important;
                right: 68px !important;
                bottom: 15px !important;
                z-index: 2147483647 !important;
                height: 42px !important;
                min-width: 105px !important;
                padding: 0 12px !important;
                border: none !important;
                border-radius: 8px !important;
                background: #1f4e78 !important;
                color: white !important;
                font: bold 13px 'Segoe UI', sans-serif !important;
                cursor: pointer !important;
                box-shadow: 0 2px 8px rgba(0,0,0,.25) !important;
                filter: none !important;
            }
            html.ftech-dark-theme #ftech-theme-button {
                filter: invert(1) hue-rotate(180deg) !important;
            }
        `;
        document.head.appendChild(style);

        const button = document.createElement('button');
        button.id = 'ftech-theme-button';
        button.type = 'button';
        button.title = 'Alternar tema claro ou escuro';

        function aplicarTema() {
            document.documentElement.classList.toggle(
                'ftech-dark-theme', temaEscuro
            );
            button.textContent = temaEscuro ? '☀ Claro' : '🌙 Escuro';
            localStorage.setItem(
                'ftech_tema', temaEscuro ? 'escuro' : 'claro'
            );
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.salvar_tema(
                    temaEscuro ? 'escuro' : 'claro'
                ).catch(function () {});
            }
        }

        button.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            temaEscuro = !temaEscuro;
            aplicarTema();
        });

        document.body.appendChild(button);
        aplicarTema();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', instalarTema, { once: true });
    } else {
        instalarTema();
    }
})();
"""


def resource_path(relative_path):
    """Retorna o caminho correto no Python e no EXE criado pelo PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", get_application_directory())
    return os.path.join(base_path, relative_path)


def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() - width) // 2
    y = (window.winfo_screenheight() - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def get_machine_name():
    try:
        return socket.gethostname()
    except Exception:
        return "Desconhecido"


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "Desconhecido"


def sanitize_username(username):
    return re.sub(r"[^a-zA-Z0-9._-]", "_", username.strip().lower())


def get_application_directory():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_executable_path():
    return os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)


class PreferenciasWeb:
    """Salva tema e zoom fora do navegador para persistirem entre execuções."""

    def __init__(self, caminho):
        self.caminho = caminho
        self.lock = threading.Lock()
        self.dados = {"tema": "claro", "zoom": 1.0}
        self._carregar()

    def _carregar(self):
        try:
            with open(self.caminho, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            if dados.get("tema") in ("claro", "escuro"):
                self.dados["tema"] = dados["tema"]
            zoom = float(dados.get("zoom", 1.0))
            self.dados["zoom"] = min(max(zoom, 0.5), 3.0)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def _salvar(self):
        os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
        temporario = self.caminho + ".tmp"
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(self.dados, arquivo, ensure_ascii=False, indent=2)
        os.replace(temporario, self.caminho)

    def salvar_zoom(self, zoom):
        try:
            valor = min(max(float(zoom), 0.5), 3.0)
            with self.lock:
                self.dados["zoom"] = valor
                self._salvar()
            return True
        except (OSError, ValueError, TypeError):
            return False

    def salvar_tema(self, tema):
        if tema not in ("claro", "escuro"):
            return False
        try:
            with self.lock:
                self.dados["tema"] = tema
                self._salvar()
            return True
        except OSError:
            return False


def get_sql_connection():
    missing = [
        name for name, value in (
            ("SQL_SERVER", SQL_SERVER),
            ("SQL_DATABASE", SQL_DATABASE),
            ("SQL_USER", SQL_USER),
            ("SQL_PASSWORD", SQL_PASSWORD),
        ) if not value
    ]
    if missing:
        raise RuntimeError("Configurações ausentes no .env: " + ", ".join(missing))

    conn_str = (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=15;"
    )
    return pyodbc.connect(conn_str)


def generate_password_hash(password):
    salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return digest.hex(), salt.hex()


def verify_password(password, stored_hash, stored_salt):
    try:
        salt = bytes.fromhex(stored_salt)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, 600_000
        ).hex()
        return hmac.compare_digest(digest, stored_hash)
    except Exception:
        return False


def register_login_log(usuario, sucesso, motivo, id_usuario=None):
    try:
        with get_sql_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO dbo.FTECH_USUARIOS_APP_LOG
                (ID_USUARIO, USUARIO_INFORMADO, COMPUTADOR, IP_LOCAL, SUCESSO, MOTIVO)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                id_usuario, usuario, get_machine_name(), get_local_ip(),
                1 if sucesso else 0, motivo,
            )
            connection.commit()
    except Exception as error:
        print(f"Erro ao registrar log: {error}")


def authenticate_user(username, password):
    username = username.strip().lower()
    if not username or not password:
        return None, "Informe o usuário e a senha."

    try:
        with get_sql_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT ID_USUARIO, USUARIO, NOME_COMPLETO, SENHA_HASH, SENHA_SALT,
                       PROVEDOR_LOGIN, EMAIL_APPSHEET, APPSHEET_URL, ATIVO,
                       BLOQUEADO, TENTATIVAS_LOGIN,
                       TROCAR_SENHA_PROXIMO_LOGIN
                FROM dbo.FTECH_USUARIOS_APP
                WHERE LOWER(USUARIO) = LOWER(?)
                """,
                username,
            )
            row = cursor.fetchone()

            if not row:
                register_login_log(username, False, "Usuário não encontrado.")
                return None, "Usuário ou senha inválidos."

            user = {
                "id_usuario": row.ID_USUARIO,
                "usuario": row.USUARIO,
                "nome_completo": row.NOME_COMPLETO,
                "senha_hash": row.SENHA_HASH,
                "senha_salt": row.SENHA_SALT,
                "provedor": row.PROVEDOR_LOGIN,
                "email_appsheet": row.EMAIL_APPSHEET,
                "appsheet_url": row.APPSHEET_URL,
                "ativo": bool(row.ATIVO),
                "bloqueado": bool(row.BLOQUEADO),
                "tentativas": int(row.TENTATIVAS_LOGIN or 0),
                "trocar_senha": bool(row.TROCAR_SENHA_PROXIMO_LOGIN),
            }

            if not user["ativo"]:
                return None, "Este usuário está desativado."
            if user["bloqueado"]:
                return None, "Este usuário está bloqueado. Procure o administrador."

            if not verify_password(password, user["senha_hash"], user["senha_salt"]):
                tentativas = user["tentativas"] + 1
                bloquear = tentativas >= MAX_TENTATIVAS
                cursor.execute(
                    """
                    UPDATE dbo.FTECH_USUARIOS_APP
                    SET TENTATIVAS_LOGIN = ?, BLOQUEADO = ?,
                        DATA_ALTERACAO = SYSDATETIME()
                    WHERE ID_USUARIO = ?
                    """,
                    tentativas, 1 if bloquear else 0, user["id_usuario"],
                )
                connection.commit()
                register_login_log(
                    username, False,
                    f"Senha inválida. Tentativa {tentativas} de {MAX_TENTATIVAS}.",
                    user["id_usuario"],
                )
                if bloquear:
                    return None, "Usuário bloqueado após várias tentativas inválidas."
                return None, "Usuário ou senha inválidos."

            cursor.execute(
                """
                UPDATE dbo.FTECH_USUARIOS_APP
                SET TENTATIVAS_LOGIN = 0, BLOQUEADO = 0,
                    ULTIMO_LOGIN = SYSDATETIME(), ULTIMO_COMPUTADOR = ?,
                    DATA_ALTERACAO = SYSDATETIME()
                WHERE ID_USUARIO = ?
                """,
                get_machine_name(), user["id_usuario"],
            )
            connection.commit()
            register_login_log(username, True, "Login realizado com sucesso.", user["id_usuario"])
            return user, None

    except Exception as error:
        return None, f"Não foi possível validar o usuário.\n\nDetalhes: {error}"


def change_user_password(user_id, new_password):
    """Altera a senha interna do FTECH após o primeiro login."""
    if len(new_password) < 6:
        raise ValueError("A nova senha deve ter pelo menos 6 caracteres.")

    password_hash, salt = generate_password_hash(new_password)

    with get_sql_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE dbo.FTECH_USUARIOS_APP
            SET SENHA_HASH = ?,
                SENHA_SALT = ?,
                TROCAR_SENHA_PROXIMO_LOGIN = 0,
                TENTATIVAS_LOGIN = 0,
                BLOQUEADO = 0,
                DATA_ULTIMA_TROCA_SENHA = SYSDATETIME(),
                DATA_ALTERACAO = SYSDATETIME()
            WHERE ID_USUARIO = ?
            """,
            password_hash,
            salt,
            user_id,
        )

        if cursor.rowcount == 0:
            raise RuntimeError("Usuário não encontrado para alteração da senha.")

        connection.commit()


class ForcedPasswordChangeDialog:
    def __init__(self, parent, user, temporary_password):
        self.parent = parent
        self.user = user
        self.temporary_password = temporary_password
        self.changed = False

        self.window = tk.Toplevel(parent)
        self.window.title("FTECH | Alteração obrigatória de senha")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        center_window(self.window, 470, 410)
        self.window.configure(bg="#f4f4f4")

        tk.Label(
            self.window,
            text="Crie sua nova senha",
            font=("Segoe UI", 17, "bold"),
            bg="#1f4e78",
            fg="white",
            pady=18,
        ).pack(fill="x")

        form = tk.Frame(self.window, bg="#f4f4f4", padx=45, pady=22)
        form.pack(fill="both", expand=True)

        tk.Label(
            form,
            text=(
                "A senha utilizada é temporária. Para continuar, "
                "defina uma senha pessoal."
            ),
            font=("Segoe UI", 10),
            bg="#f4f4f4",
            wraplength=370,
            justify="left",
        ).pack(fill="x", pady=(0, 15))

        tk.Label(
            form,
            text="Nova senha",
            font=("Segoe UI", 10, "bold"),
            bg="#f4f4f4",
            anchor="w",
        ).pack(fill="x")

        self.new_password = tk.Entry(
            form,
            show="●",
            font=("Segoe UI", 11),
            relief="solid",
            bd=1,
        )
        self.new_password.pack(fill="x", ipady=6, pady=(4, 12))

        tk.Label(
            form,
            text="Confirmar nova senha",
            font=("Segoe UI", 10, "bold"),
            bg="#f4f4f4",
            anchor="w",
        ).pack(fill="x")

        self.confirm_password = tk.Entry(
            form,
            show="●",
            font=("Segoe UI", 11),
            relief="solid",
            bd=1,
        )
        self.confirm_password.pack(fill="x", ipady=6, pady=(4, 17))

        tk.Button(
            form,
            text="ALTERAR SENHA E CONTINUAR",
            font=("Segoe UI", 14, "bold"),
            bg="#33e60b",
            fg="#030303",
            activebackground="#2dcc0a",
            bd=0,
            cursor="hand2",
            command=self.save,
        ).pack(fill="x", ipady=15)

        self.window.bind("<Return>", lambda _event: self.save())
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.new_password.focus_set()

    def save(self):
        new_password = self.new_password.get()
        confirmation = self.confirm_password.get()

        if not new_password or not confirmation:
            messagebox.showwarning(
                "Campos obrigatórios",
                "Informe e confirme a nova senha.",
                parent=self.window,
            )
            return

        if len(new_password) < 6:
            messagebox.showwarning(
                "Senha inválida",
                "A nova senha deve possuir pelo menos 6 caracteres.",
                parent=self.window,
            )
            return

        if new_password != confirmation:
            messagebox.showwarning(
                "Senhas diferentes",
                "A nova senha e a confirmação não coincidem.",
                parent=self.window,
            )
            return

        if hmac.compare_digest(new_password, self.temporary_password):
            messagebox.showwarning(
                "Senha inválida",
                "A nova senha deve ser diferente da senha temporária.",
                parent=self.window,
            )
            return

        try:
            change_user_password(self.user["id_usuario"], new_password)
            register_login_log(
                self.user["usuario"],
                True,
                "Senha temporária alterada com sucesso.",
                self.user["id_usuario"],
            )
            self.changed = True
            messagebox.showinfo(
                "Senha alterada",
                "Sua senha foi alterada com sucesso.",
                parent=self.window,
            )
            self.window.destroy()
        except Exception as error:
            messagebox.showerror(
                "Erro ao alterar senha",
                str(error),
                parent=self.window,
            )

    def cancel(self):
        self.changed = False
        self.window.destroy()

    def show(self):
        self.parent.wait_window(self.window)
        return self.changed


# ============================================================
# ATUALIZAÇÃO VIA SQL + URL DIRETA
# ============================================================

def normalize_version(value):
    text = str(value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return Version(text)


def check_for_update():
    with get_sql_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT TOP 1 VERSAO, URL_DOWNLOAD, SHA256, OBRIGATORIA, OBSERVACAO
            FROM dbo.FTECH_APP_VERSAO
            WHERE ATIVA = 1
            ORDER BY DATA_PUBLICACAO DESC, ID_VERSAO DESC
            """
        )
        row = cursor.fetchone()

    if not row:
        return None

    latest = normalize_version(row.VERSAO)
    current = normalize_version(APP_VERSION)
    if latest <= current:
        return None

    return {
        "version": str(latest),
        "download_url": str(row.URL_DOWNLOAD or "").strip(),
        "sha256": str(row.SHA256 or "").strip().lower(),
        "mandatory": bool(row.OBRIGATORIA),
        "notes": str(row.OBSERVACAO or "").strip(),
    }


def calculate_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def download_update(update_info, progress_callback=None):
    if not getattr(sys, "frozen", False):
        raise RuntimeError("A substituição automática só funciona no EXE compilado.")

    folder = os.path.join(tempfile.gettempdir(), "FTECH_Update")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, f"FTECH_App_{update_info['version']}.exe.download")

    with requests.get(
        update_info["download_url"],
        stream=True,
        timeout=(20, REQUEST_TIMEOUT),
        allow_redirects=True,
        headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
    ) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with open(target, "wb") as file:
            for block in response.iter_content(1024 * 1024):
                if not block:
                    continue
                file.write(block)
                downloaded += len(block)
                if progress_callback and total:
                    progress_callback(min(100, int(downloaded * 100 / total)))

    if not os.path.isfile(target) or os.path.getsize(target) == 0:
        raise RuntimeError("O arquivo baixado está vazio ou não foi criado.")

    expected = update_info.get("sha256", "")
    if expected:
        received = calculate_sha256(target)
        if received != expected:
            os.remove(target)
            raise RuntimeError(
                "Falha de integridade SHA-256.\n\n"
                f"Esperado: {expected}\nRecebido: {received}"
            )
    return target


def create_updater_script(downloaded_file, current_executable):
    pid = os.getpid()
    updater_path = os.path.join(tempfile.gettempdir(), f"ftech_updater_{pid}.bat")

    lines = [
        "@echo off",
        "setlocal EnableExtensions EnableDelayedExpansion",
        "title Atualizacao do FTECH",
        f'set "PID={pid}"',
        f'set "NOVO_ARQUIVO={os.path.abspath(downloaded_file)}"',
        f'set "ARQUIVO_ATUAL={os.path.abspath(current_executable)}"',
        ":AGUARDAR",
        'tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL',
        "if not errorlevel 1 (",
        "    timeout /t 1 /nobreak >NUL",
        "    goto AGUARDAR",
        ")",
        "rem O PyInstaller --onefile ainda precisa encerrar o bootloader e limpar a pasta _MEI.",
        "timeout /t 8 /nobreak >NUL",
        "set /A TENTATIVAS=0",
        ":SUBSTITUIR",
        'copy /Y "%NOVO_ARQUIVO%" "%ARQUIVO_ATUAL%" >NUL',
        "if errorlevel 1 (",
        "    set /A TENTATIVAS+=1",
        "    if !TENTATIVAS! LSS 20 (",
        "        timeout /t 1 /nobreak >NUL",
        "        goto SUBSTITUIR",
        "    )",
        '    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd.exe -Verb RunAs -Wait -ArgumentList \"/c copy /Y \\\"%NOVO_ARQUIVO%\\\" \\\"%ARQUIVO_ATUAL%\\\"\""',
        "    if errorlevel 1 exit /b 1",
        ")",
        'if not exist "%ARQUIVO_ATUAL%" exit /b 1',
        'del /F /Q "%NOVO_ARQUIVO%" >NUL 2>&1',
        "timeout /t 3 /nobreak >NUL",
        'start "" "%ARQUIVO_ATUAL%"',
        "timeout /t 2 /nobreak >NUL",
        'del /F /Q "%~f0" >NUL 2>&1',
    ]

    with open(updater_path, "w", encoding="cp1252", errors="replace") as file:
        file.write("\r\n".join(lines) + "\r\n")
    return updater_path


def install_update(update_info, progress_callback=None):
    downloaded = download_update(update_info, progress_callback)
    script = create_updater_script(downloaded, get_executable_path())
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(["cmd.exe", "/c", script], creationflags=flags, close_fds=True)
    return True


class UpdateWindow:
    def __init__(self, update_info):
        self.update_info = update_info
        self.success = False
        self.root = tk.Tk()
        self.root.title("Atualização do FTECH")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        center_window(self.root, 520, 290)

        tk.Label(self.root, text="Nova versão disponível", font=("Segoe UI", 16, "bold")).pack(pady=(25, 8))
        tk.Label(
            self.root,
            text=f"Versão instalada: {APP_VERSION}\nNova versão: {update_info['version']}\n\n{update_info.get('notes') or 'Sem observações.'}",
            font=("Segoe UI", 10), justify="center", wraplength=460,
        ).pack(pady=5)

        self.status = tk.Label(self.root, text="Preparando atualização...", font=("Segoe UI", 10))
        self.status.pack(pady=(12, 5))
        self.progress = ttk.Progressbar(self.root, maximum=100, length=410)
        self.progress.pack(pady=5)
        self.percent = tk.Label(self.root, text="0%", font=("Segoe UI", 10, "bold"))
        self.percent.pack()

    def update_progress(self, value):
        self.root.after(0, lambda: self._set_progress(value))

    def _set_progress(self, value):
        self.progress["value"] = value
        self.percent.config(text=f"{value}%")

    def worker(self):
        try:
            self.root.after(0, lambda: self.status.config(text="Baixando atualização..."))
            install_update(self.update_info, self.update_progress)
            self.success = True
            self.root.after(0, lambda: self.status.config(text="Atualização pronta. Reiniciando..."))
            time.sleep(1)
            self.root.after(0, self.root.destroy)
        except Exception as error:
            self.root.after(0, lambda e=error: self.show_error(e))

    def show_error(self, error):
        messagebox.showerror("Erro na atualização", str(error), parent=self.root)
        self.root.destroy()

    def show(self):
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.mainloop()
        return self.success


def verify_and_install_update():
    try:
        update_info = check_for_update()
        if not update_info:
            return False
        if not getattr(sys, "frozen", False):
            print(f"Nova versão encontrada: {update_info['version']}. Atualização automática apenas no EXE.")
            return False
        return UpdateWindow(update_info).show()
    except InvalidVersion as error:
        print(f"Versão inválida: {error}")
        return False
    except Exception as error:
        print(f"Erro ao verificar atualização: {error}")
        return False


class LoginWindow:
    def __init__(self):
        self.authenticated_user = None
        self.authenticating = False
        self.dark_theme = False
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} | Login")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f4f4")

        self.icon_path = resource_path("icone.ico")
        self.logo_image = None

        try:
            if os.path.isfile(self.icon_path):
                self.root.iconbitmap(self.icon_path)
        except Exception as error:
            print(f"Não foi possível aplicar o ícone da janela: {error}")

        center_window(self.root, 500, 470)
        self.create_widgets()
        self.apply_theme()
        self.root.bind("<Return>", lambda _event: self.start_authentication())

    def create_widgets(self):
        self.header = tk.Frame(self.root, bg="#1f4e78", height=155)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        self.theme_button = tk.Button(
            self.header,
            text="🌙 Escuro",
            font=("Segoe UI", 9, "bold"),
            bg="#1f4e78",
            fg="white",
            activebackground="#173b5c",
            activeforeground="white",
            cursor="hand2",
            bd=0,
            command=self.toggle_theme,
        )
        self.theme_button.place(relx=1.0, x=-12, y=10, anchor="ne")

        try:
            if os.path.isfile(self.icon_path):
                image = Image.open(self.icon_path).convert("RGBA")
                image.thumbnail((72, 72), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(image)
                tk.Label(
                    self.header,
                    image=self.logo_image,
                    bg="#1f4e78",
                    bd=0,
                ).pack(pady=(12, 2))
        except Exception as error:
            print(f"Não foi possível carregar o logo da tela de login: {error}")

        tk.Label(
            self.header,
            text="FTECH",
            font=("Segoe UI", 23, "bold"),
            fg="white",
            bg="#1f4e78",
        ).pack(pady=(0, 0))

        tk.Label(
            self.header,
            text="Alta Paulista",
            font=("Segoe UI", 11),
            fg="white",
            bg="#1f4e78",
        ).pack()

        self.form = tk.Frame(self.root, bg="#f4f4f4")
        self.form.pack(fill="both", expand=True, padx=58, pady=24)

        self.username_label = tk.Label(
            self.form,
            text="Usuário",
            font=("Segoe UI", 10, "bold"),
            bg="#f4f4f4",
            anchor="w",
        )
        self.username_label.pack(fill="x")

        self.username = tk.Entry(
            self.form,
            font=("Segoe UI", 11),
            relief="solid",
            bd=1,
        )
        self.username.pack(fill="x", ipady=7, pady=(5, 15))

        self.password_label = tk.Label(
            self.form,
            text="Senha",
            font=("Segoe UI", 10, "bold"),
            bg="#f4f4f4",
            anchor="w",
        )
        self.password_label.pack(fill="x")

        self.password = tk.Entry(
            self.form,
            font=("Segoe UI", 11),
            show="●",
            relief="solid",
            bd=1,
        )
        self.password.pack(fill="x", ipady=7, pady=(5, 20))

        self.button = tk.Button(
            self.form,
            text="ENTRAR",
            font=("Segoe UI", 11, "bold"),
            bg="#33e60b",
            fg="#030303",
            activebackground="#2dcc0a",
            cursor="hand2",
            bd=0,
            command=self.start_authentication,
        )
        self.button.pack(fill="x", ipady=9)

        self.status = tk.Label(
            self.form,
            text=f"Versão {APP_VERSION}",
            font=("Segoe UI", 9),
            fg="#666666",
            bg="#f4f4f4",
        )
        self.status.pack(pady=(14, 0))
        self.username.focus_set()

    def toggle_theme(self):
        self.dark_theme = not self.dark_theme
        self.apply_theme()

    def apply_theme(self):
        if self.dark_theme:
            background = "#202124"
            foreground = "#f1f3f4"
            field_background = "#303134"
            field_foreground = "#f1f3f4"
            header_background = "#152f45"
            status_foreground = "#bdc1c6"
            theme_text = "☀ Claro"
        else:
            background = "#f4f4f4"
            foreground = "#030303"
            field_background = "white"
            field_foreground = "#030303"
            header_background = "#1f4e78"
            status_foreground = "#666666"
            theme_text = "🌙 Escuro"

        self.root.configure(bg=background)
        self.header.configure(bg=header_background)
        self.form.configure(bg=background)
        self.username_label.configure(bg=background, fg=foreground)
        self.password_label.configure(bg=background, fg=foreground)
        self.username.configure(
            bg=field_background,
            fg=field_foreground,
            insertbackground=field_foreground,
        )
        self.password.configure(
            bg=field_background,
            fg=field_foreground,
            insertbackground=field_foreground,
        )
        self.status.configure(bg=background, fg=status_foreground)
        self.theme_button.configure(
            text=theme_text,
            bg=header_background,
            activebackground=header_background,
        )

        for widget in self.header.winfo_children():
            if isinstance(widget, tk.Label):
                widget.configure(bg=header_background)

    def start_authentication(self):
        if self.authenticating:
            return
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            messagebox.showwarning("Campos obrigatórios", "Informe o usuário e a senha.", parent=self.root)
            return

        self.authenticating = True
        self.button.config(state="disabled", text="VALIDANDO...")
        self.status.config(text="Conectando ao servidor...")
        threading.Thread(target=self.worker, args=(username, password), daemon=True).start()

    def worker(self, username, password):
        user, error = authenticate_user(username, password)
        self.root.after(
            0,
            lambda: self.finished(user, error, password),
        )

    def finished(self, user, error, informed_password):
        self.authenticating = False
        self.button.config(state="normal", text="ENTRAR")
        self.password.delete(0, tk.END)

        if error:
            self.status.config(text="Falha na autenticação.")
            messagebox.showerror("Login não autorizado", error, parent=self.root)
            return

        if user.get("trocar_senha"):
            self.status.config(text="Alteração obrigatória de senha...")
            changed = ForcedPasswordChangeDialog(
                self.root,
                user,
                informed_password,
            ).show()

            informed_password = None

            if not changed:
                self.status.config(
                    text="A senha deve ser alterada para continuar."
                )
                messagebox.showwarning(
                    "Alteração obrigatória",
                    "O acesso não será liberado enquanto a senha temporária "
                    "não for alterada.",
                    parent=self.root,
                )
                return

            user["trocar_senha"] = False

        informed_password = None
        self.authenticated_user = user
        self.root.destroy()

    def show(self):
        self.root.mainloop()
        return self.authenticated_user


def criar_javascript_provedor(provider):
    """Seleciona automaticamente Google ou Microsoft na tela do AppSheet."""
    provider = str(provider or "").upper().strip()

    if provider == "GOOGLE":
        provider_text = "Google"
    elif provider == "MICROSOFT":
        provider_text = "Microsoft"
    else:
        return "(function(){ return 'Provedor não reconhecido'; })();"

    return f"""
    (function () {{
        const PROVIDER = {provider_text!r};

        function visible(element) {{
            if (!element) return false;
            const style = window.getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }}

        function normalizedText(element) {{
            return (element.innerText || element.textContent || '')
                .trim()
                .replace(/\\s+/g, ' ');
        }}

        function findProviderButton() {{
            const elements = document.querySelectorAll(
                'button, a, [role="button"], div[tabindex], div'
            );

            for (const element of elements) {{
                if (!visible(element)) continue;

                const text = normalizedText(element).toLowerCase();
                if (text === PROVIDER.toLowerCase()) {{
                    return element.closest('button, a, [role="button"]') || element;
                }}
            }}
            return null;
        }}

        function clickProvider() {{
            if (window.__ftechProviderClicked) return true;

            const button = findProviderButton();
            if (!button) return false;

            window.__ftechProviderClicked = true;
            button.scrollIntoView({{ block: 'center', inline: 'center' }});
            setTimeout(function () {{ button.click(); }}, 250);
            return true;
        }}

        if (clickProvider()) return 'Provedor selecionado';

        let attempts = 0;
        const timer = setInterval(function () {{
            attempts += 1;
            if (clickProvider() || attempts >= 30) clearInterval(timer);
        }}, 400);

        return 'Aguardando botão do provedor';
    }})();
    """


def criar_javascript_email(email, provider):
    """Preenche somente o e-mail do Google ou Microsoft, sem armazenar senha."""
    email = str(email or "").strip()
    provider = str(provider or "").upper().strip()

    if provider == "GOOGLE":
        selectors = [
            "#identifierId",
            "input[name='identifier']",
            "input[type='email']",
        ]
    else:
        selectors = [
            "#i0116",
            "input[name='loginfmt']",
            "input[type='email']",
        ]

    selectors_js = repr(", ".join(selectors))

    return f"""
    (function () {{
        const EMAIL = {email!r};
        const SELECTORS = {selectors_js};

        function setNativeValue(element, value) {{
            const descriptor = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype,
                'value'
            );

            if (descriptor && descriptor.set) {{
                descriptor.set.call(element, value);
            }} else {{
                element.value = value;
            }}

            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
            element.dispatchEvent(new Event('blur', {{ bubbles: true }}));
            element.focus();
        }}

        function fillEmail() {{
            const field = document.querySelector(SELECTORS);
            if (!field) return false;

            if (!field.value || field.value.trim().toLowerCase() !== EMAIL.toLowerCase()) {{
                setNativeValue(field, EMAIL);
            }}

            return true;
        }}

        if (fillEmail()) return 'E-mail preenchido';

        let attempts = 0;
        const timer = setInterval(function () {{
            attempts += 1;
            if (fillEmail() || attempts >= 30) clearInterval(timer);
        }}, 400);

        return 'Aguardando campo de e-mail';
    }})();
    """


def habilitar_autofill_senhas_webview2():
    """
    Habilita o preenchimento geral e o salvamento de senhas no WebView2.

    O pywebview não expõe essas opções diretamente. Por isso, esta função
    aplica um pequeno ajuste no evento interno de inicialização do WebView2.
    Caso uma propriedade não exista na versão instalada, ela é ignorada.
    """
    try:
        from webview.platforms import edgechromium

        edge_class = edgechromium.EdgeChrome

        if getattr(edge_class, "_ftech_password_patch", False):
            return True

        original_on_webview_ready = edge_class.on_webview_ready

        def on_webview_ready_com_senhas(self, sender, args):
            # Mantém todo o comportamento original do pywebview.
            original_on_webview_ready(self, sender, args)

            try:
                if not args.IsSuccess:
                    return

                core = sender.CoreWebView2
                if core is None:
                    return

                settings = core.Settings

                # Propriedades disponíveis conforme a versão do SDK WebView2.
                for property_name in (
                    "IsGeneralAutofillEnabled",
                    "IsPasswordAutosaveEnabled",
                    "IsPasswordAutofillEnabled",
                ):
                    try:
                        if hasattr(settings, property_name):
                            setattr(settings, property_name, True)
                    except Exception as error:
                        print(
                            f"Não foi possível ativar {property_name} "
                            f"em Settings: {error}"
                        )

                # Algumas versões também expõem as opções no Profile.
                try:
                    profile = core.Profile
                except Exception:
                    profile = None

                if profile is not None:
                    for property_name in (
                        "IsGeneralAutofillEnabled",
                        "IsPasswordAutosaveEnabled",
                    ):
                        try:
                            if hasattr(profile, property_name):
                                setattr(profile, property_name, True)
                        except Exception as error:
                            print(
                                f"Não foi possível ativar {property_name} "
                                f"no Profile: {error}"
                            )

                print(
                    "WebView2: preenchimento automático e salvamento "
                    "de senhas habilitados."
                )

            except Exception as error:
                # Uma falha nessa configuração não deve impedir o AppSheet.
                print(f"Erro ao habilitar o gerenciador de senhas: {error}")

        edge_class.on_webview_ready = on_webview_ready_com_senhas
        edge_class._ftech_password_patch = True
        return True

    except Exception as error:
        print(f"Não foi possível preparar o autofill do WebView2: {error}")
        return False


def open_appsheet(user):
    username = sanitize_username(user["usuario"])
    provider = str(user["provedor"]).upper().strip()
    email_appsheet = str(user.get("email_appsheet") or "").strip()
    appsheet_url = user.get("appsheet_url") or APPSHEET_URL_PADRAO

    base = os.getenv("LOCALAPPDATA") or get_application_directory()
    profile = os.path.join(base, "FTECH", "webview_profiles", provider, username)
    os.makedirs(profile, exist_ok=True)

    preferencias_path = os.path.join(
        base, "FTECH", "preferencias", f"{provider}_{username}.json"
    )
    preferencias = PreferenciasWeb(preferencias_path)

    zoom_js = ZOOM_JS.replace(
        "__FTECH_INITIAL_ZOOM__", repr(preferencias.dados["zoom"])
    )
    theme_js = THEME_JS.replace(
        "__FTECH_INITIAL_DARK__",
        "true" if preferencias.dados["tema"] == "escuro" else "false",
    )

    webview.settings["ALLOW_DOWNLOADS"] = True

    window = webview.create_window(
        title=(
            f"FTECH | Alta Paulista | {user['nome_completo']} | "
            f"{email_appsheet}"
        ),
        url=appsheet_url,
        width=1200,
        height=800,
        min_size=(900, 600),
        resizable=True,
        js_api=preferencias,
    )

    provider_js = criar_javascript_provedor(provider)
    email_js = criar_javascript_email(email_appsheet, provider)

    def on_loaded():
        try:
            current_url = (window.get_current_url() or "").lower()

            # Zoom nas páginas do AppSheet.
            if "appsheet.com" in current_url:
                try:
                    window.evaluate_js(zoom_js)
                except Exception as error:
                    print(f"Erro ao instalar zoom: {error}")

                try:
                    window.evaluate_js(theme_js)
                except Exception as error:
                    print(f"Erro ao instalar seletor de tema: {error}")

                # Na tela de escolha, seleciona automaticamente o provedor.
                try:
                    window.evaluate_js(provider_js)
                except Exception as error:
                    print(f"Erro ao selecionar provedor: {error}")

            # Na página externa do provedor, preenche automaticamente o e-mail.
            if provider == "GOOGLE" and "accounts.google.com" in current_url:
                try:
                    window.evaluate_js(email_js)
                except Exception as error:
                    print(f"Erro ao preencher e-mail Google: {error}")

            elif provider == "MICROSOFT" and (
                "login.microsoftonline.com" in current_url
                or "login.live.com" in current_url
                or "login.microsoft.com" in current_url
            ):
                try:
                    window.evaluate_js(email_js)
                except Exception as error:
                    print(f"Erro ao preencher e-mail Microsoft: {error}")

        except Exception as error:
            print(f"Erro ao tratar página carregada: {error}")

    window.events.loaded += on_loaded

    # Ativa o gerenciador de senhas nativo do WebView2 antes da inicialização.
    habilitar_autofill_senhas_webview2()

    webview.start(
        gui="edgechromium",
        private_mode=False,
        storage_path=profile,
        debug=False,
    )

def main():
    if verify_and_install_update():
        sys.exit(0)

    user = LoginWindow().show()
    if not user:
        sys.exit(0)

    open_appsheet(user)


if __name__ == "__main__":
    main()