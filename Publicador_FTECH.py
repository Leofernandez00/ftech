import os
import re
import sys
import shutil
import hashlib
import subprocess
import threading
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

import pyodbc
from dotenv import load_dotenv
from packaging.version import Version

APP_TITLE = "Publicador FTECH"
BASE_DIR = Path(__file__).resolve().parent
GITIGNORE_ENTRIES = [
    ".env", "venv/", ".venv/", "build/", "dist/", "__pycache__/",
    "*.pyc", "*.spec", "webview_profile/", "webview_profiles/", "*.download",
    "FTECH_PUBLICACAO/", "credentials.json", "credentials*.json",
    "client_secret*.json", "token.json", "token*.json", "*.exe",
]
load_dotenv(BASE_DIR / ".env")


def run_process(command, cwd):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    lines = []
    for line in iter(process.stdout.readline, ""):
        if not line and process.poll() is not None:
            break
        if line:
            lines.append(line.rstrip())
    process.wait()
    return process.returncode, lines


def normalize_version(text):
    value = str(text).strip()
    if value.lower().startswith("v"):
        value = value[1:]
    return str(Version(value))


def next_patch(text):
    version = Version(normalize_version(text))
    return f"{version.major}.{version.minor}.{version.micro + 1}"


def calculate_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def read_current_version(source_path):
    content = source_path.read_text(encoding="utf-8")
    patterns = [
        r'APP_VERSION\s*=\s*os\.getenv\(\s*["\']APP_VERSION["\']\s*,\s*["\']([^"\']+)["\']\s*\)\.strip\(\)',
        r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return normalize_version(match.group(1))
    return "1.0.0"


def update_source_version(source_path, version):
    content = source_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(APP_VERSION\s*=\s*os\.getenv\(\s*["\']APP_VERSION["\']\s*,\s*["\'])'
        r'([^"\']+)'
        r'(["\']\s*\)\.strip\(\))'
    )
    updated, count = pattern.subn(
        lambda m: f"{m.group(1)}{version}{m.group(3)}", content, count=1
    )
    if count == 0:
        pattern = re.compile(r'(APP_VERSION\s*=\s*["\'])([^"\']+)(["\'])')
        updated, count = pattern.subn(
            lambda m: f"{m.group(1)}{version}{m.group(3)}", content, count=1
        )
    if count == 0:
        raise RuntimeError("Não encontrei APP_VERSION no código principal.")
    source_path.write_text(updated, encoding="utf-8")


def ensure_gitignore(project_dir):
    path = project_dir / ".gitignore"
    existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    lines = {line.strip() for line in existing.splitlines()}
    additions = [entry for entry in GITIGNORE_ENTRIES if entry not in lines]
    if additions:
        with path.open("a", encoding="utf-8") as file:
            if existing and not existing.endswith("\n"):
                file.write("\n")
            file.write("\n# Publicador FTECH\n")
            for entry in additions:
                file.write(entry + "\n")


def get_current_git_branch(git, project):
    """Retorna a branch local ativa, sem presumir que seja main ou master."""
    code, output = run_process([git, "branch", "--show-current"], project)
    branch = "\n".join(output).strip()
    if code != 0 or not branch:
        raise RuntimeError(
            "Não foi possível identificar a branch Git atual. "
            "Verifique se o repositório possui uma branch ativa."
        )
    return branch


def sql_connection():
    values = {
        "SQL_SERVER": os.getenv("SQL_SERVER", "").strip(),
        "SQL_DATABASE": os.getenv("SQL_DATABASE", "").strip(),
        "SQL_USER": os.getenv("SQL_USER", "").strip(),
        "SQL_PASSWORD": os.getenv("SQL_PASSWORD", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Faltam no .env: " + ", ".join(missing))
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server").strip()
    connection_string = (
        f"DRIVER={{{driver}}};SERVER={values['SQL_SERVER']};"
        f"DATABASE={values['SQL_DATABASE']};UID={values['SQL_USER']};"
        f"PWD={values['SQL_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "Connection Timeout=20;"
    )
    return pyodbc.connect(connection_string)


def update_sql(version, url, sha256, notes):
    with sql_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            IF OBJECT_ID('dbo.FTECH_APP_VERSAO', 'U') IS NULL
                THROW 50001, 'A tabela dbo.FTECH_APP_VERSAO não existe.', 1;
            """
        )
        cursor.execute("UPDATE dbo.FTECH_APP_VERSAO SET ATIVA = 0 WHERE ATIVA = 1;")
        cursor.execute(
            """
            IF EXISTS (SELECT 1 FROM dbo.FTECH_APP_VERSAO WHERE VERSAO = ?)
            BEGIN
                UPDATE dbo.FTECH_APP_VERSAO
                SET URL_DOWNLOAD=?, SHA256=?, OBRIGATORIA=1, OBSERVACAO=?,
                    DATA_PUBLICACAO=SYSDATETIME(), ATIVA=1
                WHERE VERSAO=?;
            END
            ELSE
            BEGIN
                INSERT INTO dbo.FTECH_APP_VERSAO
                (VERSAO, URL_DOWNLOAD, SHA256, OBRIGATORIA, OBSERVACAO, DATA_PUBLICACAO, ATIVA)
                VALUES (?, ?, ?, 1, ?, SYSDATETIME(), 1);
            END
            """,
            version, url, sha256, notes, version,
            version, url, sha256, notes,
        )
        connection.commit()


class PublisherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("920x730")
        self.root.minsize(840, 650)
        self.running = False
        self.build_ui()
        self.load_defaults()

    def build_ui(self):
        header = tk.Frame(self.root, bg="#1f4e78", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="PUBLICADOR FTECH", bg="#1f4e78", fg="white",
                 font=("Segoe UI", 20, "bold")).pack(pady=(13, 0))
        tk.Label(header, text="Build, GitHub Release e SQL Server", bg="#1f4e78",
                 fg="white", font=("Segoe UI", 10)).pack()

        body = ttk.Frame(self.root, padding=14)
        body.pack(fill="both", expand=True)
        frame = ttk.LabelFrame(body, text="Configuração", padding=10)
        frame.pack(fill="x")

        self.project = tk.StringVar(value=str(BASE_DIR))
        self.source = tk.StringVar(value="FTECH_2.py")
        self.icon = tk.StringVar(value="icone.ico")
        self.exe_name = tk.StringVar(value="FTECH")
        self.repository = tk.StringVar(value="Leofernandez00/ftech")
        self.version = tk.StringVar(value="1.0.1")
        self.release_title = tk.StringVar(value="FTECH 2.0.1")

        fields = [
            ("Pasta do projeto", self.project, self.choose_project),
            ("Código principal", self.source, self.choose_source),
            ("Ícone", self.icon, self.choose_icon),
            ("Nome do EXE", self.exe_name, None),
            ("Repositório", self.repository, None),
            ("Nova versão", self.version, None),
            ("Título da Release", self.release_title, None),
        ]
        for row, (label, variable, command) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=variable).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=4
            )
            if command:
                ttk.Button(frame, text="Selecionar", command=command).grid(
                    row=row, column=2, padx=(8, 0), pady=4
                )
        frame.columnconfigure(1, weight=1)

        notes_frame = ttk.LabelFrame(body, text="Notas da versão", padding=8)
        notes_frame.pack(fill="x", pady=(10, 0))
        self.notes = tk.Text(notes_frame, height=5, font=("Segoe UI", 10), wrap="word")
        self.notes.pack(fill="x")
        self.notes.insert("1.0", "- Correções e melhorias no FTECH App.\n- Ajustes de estabilidade.")

        options = ttk.LabelFrame(body, text="Etapas", padding=8)
        options.pack(fill="x", pady=(10, 0))
        self.do_build = tk.BooleanVar(value=True)
        self.do_git = tk.BooleanVar(value=True)
        self.do_release = tk.BooleanVar(value=True)
        self.do_sql = tk.BooleanVar(value=True)
        for text, variable in [
            ("Gerar EXE", self.do_build),
            ("Commit/push do código", self.do_git),
            ("Criar Release", self.do_release),
            ("Atualizar SQL", self.do_sql),
        ]:
            ttk.Checkbutton(options, text=text, variable=variable).pack(side="left", padx=(0, 18))

        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=10)
        self.publish_button = ttk.Button(actions, text="PUBLICAR NOVA VERSÃO", command=self.start)
        self.publish_button.pack(side="left")
        ttk.Button(actions, text="Verificar pré-requisitos", command=self.start_check).pack(side="left", padx=8)
        ttk.Button(actions, text="Incrementar revisão", command=self.increment).pack(side="left")
        self.progress = ttk.Progressbar(actions, maximum=100)
        self.progress.pack(side="right", fill="x", expand=True, padx=(15, 0))

        log_frame = ttk.LabelFrame(body, text="Log", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log_widget = tk.Text(log_frame, bg="#101820", fg="#e8e8e8",
                                  font=("Consolas", 9), state="disabled", wrap="word")
        scroll = ttk.Scrollbar(log_frame, command=self.log_widget.yview)
        self.log_widget.configure(yscrollcommand=scroll.set)
        self.log_widget.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def load_defaults(self):
        source = BASE_DIR / self.source.get()
        if source.exists():
            current = read_current_version(source)
            new = next_patch(current)
            self.version.set(new)
            self.release_title.set(f"FTECH App {new}")

    def choose_project(self):
        selected = filedialog.askdirectory(initialdir=self.project.get())
        if selected:
            self.project.set(selected)

    def choose_source(self):
        selected = filedialog.askopenfilename(
            initialdir=self.project.get(), filetypes=[("Python", "*.py")]
        )
        if selected:
            self.source.set(selected)

    def choose_icon(self):
        selected = filedialog.askopenfilename(
            initialdir=self.project.get(), filetypes=[("Ícone", "*.ico")]
        )
        if selected:
            self.icon.set(selected)

    def increment(self):
        try:
            new = next_patch(self.version.get())
            self.version.set(new)
            self.release_title.set(f"FTECH App {new}")
        except Exception as error:
            messagebox.showerror("Versão inválida", str(error), parent=self.root)

    def log(self, text):
        self.root.after(0, lambda: self._log(text))

    def _log(self, text):
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", str(text) + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def set_progress(self, value):
        self.root.after(0, lambda: self.progress.configure(value=value))

    def set_running(self, value):
        self.running = value
        self.root.after(0, lambda: self.publish_button.configure(
            state="disabled" if value else "normal"
        ))

    def paths(self):
        project = Path(self.project.get()).expanduser().resolve()
        source = Path(self.source.get())
        icon = Path(self.icon.get())
        if not source.is_absolute():
            source = project / source
        if not icon.is_absolute():
            icon = project / icon
        repository = self.repository.get().strip()
        version = normalize_version(self.version.get())
        exe_name = self.exe_name.get().strip()
        if not project.is_dir():
            raise RuntimeError(f"Pasta não encontrada: {project}")
        if not source.is_file():
            raise RuntimeError(f"Código principal não encontrado: {source}")
        if not icon.is_file():
            raise RuntimeError(f"Ícone não encontrado: {icon}")
        if "/" not in repository:
            raise RuntimeError("Use USUARIO/REPOSITORIO no campo Repositório.")
        return project, source, icon, repository, version, exe_name

    def check_tools(self):
        git = shutil.which("git")
        gh = shutil.which("gh")
        if not git:
            raise RuntimeError("Git não encontrado. Instale o Git for Windows.")
        self.log(f"Git: {git}")
        if self.do_release.get():
            if not gh:
                raise RuntimeError("GitHub CLI não encontrado. Instale o gh e execute: gh auth login")
            self.log(f"GitHub CLI: {gh}")
            code, output = run_process([gh, "auth", "status"], BASE_DIR)
            for line in output:
                self.log(line)
            if code != 0:
                raise RuntimeError("GitHub CLI não autenticado. Execute: gh auth login")
        return git, gh

    def start_check(self):
        if self.running:
            return
        threading.Thread(target=self.check_only, daemon=True).start()

    def check_only(self):
        self.set_running(True)
        try:
            self.paths()
            self.check_tools()
            self.log("Pré-requisitos verificados com sucesso.")
        except Exception as error:
            self.log(f"ERRO: {error}")
            self.root.after(0, lambda e=error: messagebox.showerror("Erro", str(e), parent=self.root))
        finally:
            self.set_running(False)

    def start(self):
        if self.running:
            return
        if not messagebox.askyesno("Confirmar", "Publicar a nova versão agora?", parent=self.root):
            return
        threading.Thread(target=self.publish, daemon=True).start()

    def publish(self):
        self.set_running(True)
        self.set_progress(0)
        try:
            project, source, icon, repository, version, exe_name = self.paths()
            notes = self.notes.get("1.0", "end").strip() or "Nova versão do FTECH App."
            tag = f"v{version}"
            title = self.release_title.get().strip() or f"FTECH App {version}"
            git, gh = self.check_tools()

            self.log("=" * 65)
            self.log(f"PUBLICANDO VERSÃO {version}")
            update_source_version(source, version)
            ensure_gitignore(project)
            self.set_progress(12)

            dist = project / "dist" / f"{exe_name}.exe"
            if self.do_build.get():
                self.build_exe(project, source, icon, exe_name)
            elif not dist.exists():
                raise RuntimeError(f"EXE não encontrado: {dist}")
            self.set_progress(55)

            sha256 = calculate_sha256(dist)
            self.log(f"SHA-256: {sha256}")
            self.log(f"Tamanho: {dist.stat().st_size / 1024 / 1024:.2f} MB")

            git_branch = None
            if self.do_git.get():
                git_branch = self.git_push(project, repository, version, git)
            self.set_progress(72)

            if self.do_release.get():
                if not git_branch:
                    git_branch = get_current_git_branch(git, project)
                self.release(
                    project, repository, tag, title, notes, dist, gh, git_branch
                )
            self.set_progress(88)

            url = f"https://github.com/{repository}/releases/download/{tag}/{dist.name}"
            self.log(f"URL direta: {url}")
            if self.do_sql.get():
                update_sql(version, url, sha256, notes)
                self.log("SQL Server atualizado.")

            self.set_progress(100)
            self.log("PUBLICAÇÃO CONCLUÍDA COM SUCESSO.")
            self.root.after(0, lambda: messagebox.showinfo(
                "Concluído", f"Versão {version} publicada.\n\n{url}", parent=self.root
            ))
        except Exception as error:
            self.log(f"ERRO: {error}")
            self.root.after(0, lambda e=error: messagebox.showerror("Falha", str(e), parent=self.root))
        finally:
            self.set_running(False)

    def build_exe(self, project, source, icon, exe_name):
        self.log("Limpando build/dist/spec...")
        for name in ("build", "dist"):
            folder = project / name
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
        spec = project / f"{exe_name}.spec"
        if spec.exists():
            spec.unlink()

        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--windowed", "--name", exe_name,
            f"--icon={icon}", f"--add-data={icon}{os.pathsep}.",
            "--hidden-import=pyodbc", "--hidden-import=requests",
            "--hidden-import=dotenv", "--hidden-import=packaging.version",
            "--hidden-import=PIL", "--hidden-import=PIL.Image",
            "--hidden-import=PIL.ImageTk", "--hidden-import=webview",
            "--hidden-import=webview.platforms.edgechromium", "--hidden-import=clr",
            "--collect-all=webview", "--collect-all=pythonnet",
            "--collect-all=PIL", "--collect-all=packaging", str(source),
        ]
        self.command(command, project)
        dist = project / "dist" / f"{exe_name}.exe"
        if not dist.exists():
            raise RuntimeError(f"PyInstaller terminou sem criar: {dist}")
        self.log(f"EXE criado: {dist}")

    def git_push(self, project, repository, version, git):
        if not (project / ".git").exists():
            self.command([git, "init"], project)
        branch = get_current_git_branch(git, project)
        self.log(f"Branch Git detectada: {branch}")
        remote_url = f"https://github.com/{repository}.git"
        code, output = run_process([git, "remote", "get-url", "origin"], project)
        if code != 0:
            self.command([git, "remote", "add", "origin", remote_url], project)
        elif "\n".join(output).strip() != remote_url:
            self.command([git, "remote", "set-url", "origin", remote_url], project)
        # Remove somente do índice uma eventual inclusão antiga do repositório
        # interno. Os arquivos permanecem normalmente no computador.
        self.command(
            [
                git, "rm", "-r", "--cached", "--ignore-unmatch", "--",
                "FTECH_PUBLICACAO", "credentials.json", "token.json",
                ":(glob)**/*.exe",
            ],
            project,
        )
        self.command([git, "add", "."], project)
        code, changes = run_process([git, "status", "--porcelain"], project)
        if code != 0:
            raise RuntimeError("Erro ao consultar git status.")
        if changes:
            self.command([git, "commit", "-m", f"Versão {version}"], project)
        else:
            self.log("Sem alterações para commit.")
        self.command([git, "push", "-u", "origin", branch], project)
        return branch

    def release(self, project, repository, tag, title, notes, dist, gh, branch):
        code, _ = run_process([gh, "release", "view", tag, "--repo", repository], project)
        notes_file = Path(tempfile.gettempdir()) / f"ftech_notes_{os.getpid()}.txt"
        notes_file.write_text(notes, encoding="utf-8")
        try:
            if code == 0:
                self.command([gh, "release", "upload", tag, str(dist), "--clobber", "--repo", repository], project)
                self.command([gh, "release", "edit", tag, "--title", title,
                              "--notes-file", str(notes_file), "--latest", "--repo", repository], project)
            else:
                self.command([gh, "release", "create", tag, str(dist), "--title", title,
                              "--notes-file", str(notes_file), "--target", branch,
                              "--latest", "--repo", repository], project)
        finally:
            try:
                notes_file.unlink()
            except OSError:
                pass

    def command(self, command, cwd):
        self.log("> " + " ".join(f'"{part}"' if " " in part else part for part in command))
        code, output = run_process(command, cwd)
        for line in output:
            self.log(line)
        if code != 0:
            raise RuntimeError("Comando falhou. Consulte o log acima.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PublisherApp().run()
