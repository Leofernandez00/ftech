# -*- coding: utf-8 -*-
"""
FTECH Compras - Desktop para Solicitantes
Alta Paulista Equipamentos Agrícolas Ltda.

Requisitos:
    pip install PySide6 pyodbc pywin32 argon2-cffi

Este arquivo usa as procedures dbo.usp_APP_* já instaladas no banco FTECH.
A senha do login técnico é lida de:
C:\ProgramData\Alta Paulista\FTECH Compras\sql.secret
"""
import sys, os, json, uuid, socket
from pathlib import Path
from datetime import datetime, date
from xml.etree.ElementTree import Element, SubElement, tostring

import pyodbc
import win32crypt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QPushButton, QMessageBox, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QSpinBox,
    QTextEdit, QGroupBox, QSplitter, QAbstractItemView, QInputDialog,
    QListWidget, QListWidgetItem, QCheckBox, QStackedWidget, QFrame, QSizePolicy, QGridLayout
)

APP_NAME = "FTECH Compras"
APP_VERSION = "1.0.0"
SERVER = "188.220.168.222"
PORT = 1433
DB = "FTECH"
USER = "FTECH_COMPRAS_APP"
DRIVER = "ODBC Driver 17 for SQL Server"
SECRET = Path(os.environ.get("PROGRAMDATA", str(Path.home()))) / "Alta Paulista" / "FTECH Compras" / "sql.secret"
ENTROPY = b"AltaPaulista.FTECHCompras.v1"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Alta Paulista" / "FTECH Compras"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)

GRANTS = (
    "CREATE", "VIEW_OWN", "VIEW_SECTOR", "VIEW_BRANCH", "EDIT_SUBMITTED",
    "DELETE_SUBMITTED", "MANAGE_USERS", "MANAGE_PERMISSIONS", "VIEW_AUDIT", "ADMIN"
)

STYLE = """
* { font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QDialog, QWidget { background: #f5f7fb; color: #1f2937; }
QFrame#Sidebar { background: #172033; border: none; }
QLabel#Brand { color: white; font-size: 22px; font-weight: 700; padding: 6px; }
QLabel#BrandSub { color: #9fb0c8; font-size: 11px; padding: 0 6px 18px 6px; }
QPushButton#NavButton {
    background: transparent; color: #dbe5f3; border: none; border-radius: 7px;
    text-align: left; padding: 11px 14px; font-size: 14px;
}
QPushButton#NavButton:hover { background: #24324b; }
QPushButton#NavButton:checked { background: #2f5bea; color: white; font-weight: 600; }
QFrame#Topbar { background: white; border-bottom: 1px solid #e5e7eb; }
QLabel#PageTitle { font-size: 23px; font-weight: 700; color: #172033; }
QLabel#PageSub { color: #6b7280; }
QFrame#Card, QGroupBox {
    background: white; border: 1px solid #e4e8ef; border-radius: 10px;
}
QGroupBox { margin-top: 12px; padding: 18px 12px 12px 12px; font-weight: 650; color:#26344d; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QLineEdit, QComboBox, QTextEdit, QSpinBox, QListWidget, QTableWidget {
    background: white; color:#1f2937; border: 1px solid #d6dbe5; border-radius: 6px; padding: 7px;
    selection-background-color: #dce6ff; selection-color:#172033;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus { border: 1px solid #2f5bea; }
QPushButton {
    background:#eef1f6; color:#26344d; border:1px solid #d6dbe5; border-radius:7px;
    padding:8px 13px; font-weight:600;
}
QPushButton:hover { background:#e3e8f1; }
QPushButton#Primary { background:#2f5bea; color:white; border:none; }
QPushButton#Primary:hover { background:#244bc8; }
QPushButton#Danger { background:#fff1f1; color:#b42318; border:1px solid #ffd1d1; }
QHeaderView::section {
    background:#f1f4f9; color:#344054; padding:8px; border:0; border-bottom:1px solid #dce1e8; font-weight:600;
}
QTableWidget { gridline-color:#edf0f4; alternate-background-color:#fafbfc; }
QStatusBar { background:white; color:#667085; border-top:1px solid #e5e7eb; }
"""

def sql_password():
    if not SECRET.exists():
        raise RuntimeError("Credencial SQL não encontrada. Execute provisionar_credencial.py primeiro.")
    blob = SECRET.read_bytes()
    # Assinatura confirmada no Python/pywin32 do ambiente do usuário.
    result = win32crypt.CryptUnprotectData(blob, ENTROPY, None, None, 0)
    data = result[1] if isinstance(result, tuple) else result
    if not isinstance(data, (bytes, bytearray)):
        raise RuntimeError("Retorno inválido do Windows DPAPI.")
    return bytes(data).decode("utf-8")

def connect():
    cs = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER},{PORT};DATABASE={DB};UID={USER};"
        f"PWD={sql_password()};Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=15;"
    )
    return pyodbc.connect(cs)

def execute(sql, *params, commit=True):
    cn = connect()
    try:
        cur = cn.cursor()
        cur.execute(sql, *params)
        cols, rows = [], []
        # Procedures podem emitir rowcount antes do SELECT.
        while True:
            if cur.description:
                cols = [c[0] for c in cur.description]
                rows = [tuple(r) for r in cur.fetchall()]
                break
            if not cur.nextset():
                break
        if commit:
            cn.commit()
        return cols, rows
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()

def rows_as_dicts(sql, *params):
    cols, rows = execute(sql, *params)
    return [dict(zip(cols, r)) for r in rows]

def computer_name():
    return os.environ.get("COMPUTERNAME") or socket.gethostname()

def norm(v):
    return "" if v is None else str(v)

def first(d, *names, default=""):
    keys = {str(k).upper(): k for k in d}
    for n in names:
        if n.upper() in keys:
            return d[keys[n.upper()]]
    return default

def safe_proc(proc, params=()):
    placeholders = ",".join("?" for _ in params)
    return rows_as_dicts(f"EXEC dbo.{proc} {placeholders}", *params)

def draft_path(user_id):
    return DATA_DIR / f"rascunho_{user_id}.json"

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.user = None
        self.setWindowTitle(f"{APP_NAME} - Login")
        self.setFixedWidth(460)
        root = QVBoxLayout(self)
        title = QLabel("FTECH COMPRAS")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Solicitação de Compras")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("E-mail")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("E-mail:", self.email)
        form.addRow("Senha:", self.password)
        self.btn = QPushButton("ENTRAR")
        self.btn.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        root.addWidget(title); root.addWidget(sub); root.addSpacing(15); root.addLayout(form); root.addWidget(self.btn)

    def log_attempt(self, email, ok, reason):
        try:
            execute("EXEC dbo.usp_APP_RegistrarTentativa ?,?,?,?", email, int(ok), computer_name(), reason)
        except Exception:
            pass

    def login(self):
        email, pwd = self.email.text().strip().lower(), self.password.text()
        if not email or not pwd:
            QMessageBox.warning(self, "Login", "Informe e-mail e senha."); return
        try:
            data = safe_proc("usp_APP_ObterUsuarioLogin", (email,))
            if not data:
                self.log_attempt(email, False, "USUARIO_NAO_ENCONTRADO")
                raise ValueError("Usuário ou senha inválidos.")
            u = data[0]
            if not bool(first(u, "ATIVO", default=True)):
                raise ValueError("Usuário inativo.")
            blocked = first(u, "BLOQUEADO_ATE", default=None)
            if blocked and isinstance(blocked, datetime) and blocked > datetime.now():
                raise ValueError(f"Usuário bloqueado até {blocked:%d/%m/%Y %H:%M}.")
            try:
                PH.verify(str(first(u, "SENHA_HASH")), pwd)
            except (VerifyMismatchError, InvalidHashError):
                self.log_attempt(email, False, "SENHA_INVALIDA")
                raise ValueError("Usuário ou senha inválidos.")
            self.log_attempt(email, True, "LOGIN_OK")
            try: execute("EXEC dbo.usp_APP_RegistrarAcesso ?", first(u, "ID"))
            except Exception: pass
            self.user = u
            if bool(first(u, "TROCAR_SENHA", default=False)):
                dlg = ChangePasswordDialog(u, self, forced=True)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    self.user = None
                    QMessageBox.warning(self, "Primeiro acesso", "A troca da senha é obrigatória para continuar.")
                    return
                self.user["TROCAR_SENHA"] = False
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

class ItemDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.result_item = None
        self.products = []
        self.clients = []
        self.setWindowTitle("Item da Solicitação")
        self.resize(720, 520)
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.search_product = QLineEdit()
        self.search_product.setPlaceholderText("Digite código ou descrição e clique Buscar")
        bp = QPushButton("Buscar produto")
        bp.clicked.connect(self.find_products)
        hp = QHBoxLayout(); hp.addWidget(self.search_product); hp.addWidget(bp)
        self.product = QComboBox()
        self.product.setEditable(False)
        self.original = QLineEdit()
        self.qty = QSpinBox(); self.qty.setRange(1, 999999); self.qty.setValue(1)

        self.search_client = QLineEdit()
        self.search_client.setPlaceholderText("Opcional - código, CNPJ ou nome")
        bc = QPushButton("Buscar cliente"); bc.clicked.connect(self.find_clients)
        hc = QHBoxLayout(); hc.addWidget(self.search_client); hc.addWidget(bc)
        self.client = QComboBox()
        self.client.addItem("(Sem cliente)", None)
        self.obs = QTextEdit(); self.obs.setMaximumHeight(100)

        form.addRow("Buscar produto:", hp)
        form.addRow("Produto:", self.product)
        form.addRow("Código original:", self.original)
        form.addRow("Quantidade:", self.qty)
        form.addRow("Buscar cliente:", hc)
        form.addRow("Cliente:", self.client)
        form.addRow("Observação:", self.obs)
        root.addLayout(form)
        buttons = QHBoxLayout()
        save = QPushButton("Salvar item"); cancel = QPushButton("Cancelar")
        save.clicked.connect(self.save); cancel.clicked.connect(self.reject)
        buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)

        if existing:
            self.original.setText(existing.get("CODIGOORIGINAL",""))
            self.qty.setValue(int(float(existing.get("QUANTIDADE",1) or 1)))
            self.obs.setPlainText(existing.get("OBSERVACAO",""))
            self.product.addItem(f'{existing.get("CODIGOTOTVS","")} - {existing.get("DESCRICAO","")}', existing)
            self.client.addItem(existing.get("CLIENTE",""), existing.get("CLIENTE",""))
            self.client.setCurrentIndex(1)

    def find_products(self):
        q = self.search_product.text().strip()
        try:
            data = safe_proc("usp_APP_BuscarProdutos", (q, 50))
            self.product.clear(); self.products = data
            for d in data:
                code = norm(first(d, "CODIGO_TOTVS", "CODIGO"))
                desc = norm(first(d, "PRODUTO", "DESCRICAO", "TOTVS_DESCRICAO"))
                self.product.addItem(f"{code} - {desc}", d)
            if not data: QMessageBox.information(self, "Produto", "Nenhum produto encontrado.")
        except Exception as e: QMessageBox.critical(self, "Produto", str(e))

    def find_clients(self):
        q = self.search_client.text().strip()
        try:
            data = safe_proc("usp_APP_BuscarClientes", (q, 50))
            self.client.clear(); self.client.addItem("(Sem cliente)", None); self.clients = data
            for d in data:
                code = norm(first(d, "CODIGO", "ID"))
                loja = norm(first(d, "LOJA"))
                name = norm(first(d, "NOME", "N_FANTASIA"))
                value = f"{code}/{loja} - {name}" if loja else f"{code} - {name}"
                self.client.addItem(value, value)
        except Exception as e: QMessageBox.critical(self, "Cliente", str(e))

    def save(self):
        p = self.product.currentData()
        if not p:
            QMessageBox.warning(self, "Item", "Selecione um produto."); return
        code = norm(first(p, "CODIGO_TOTVS", "CODIGO"))
        desc = norm(first(p, "PRODUTO", "DESCRICAO", "TOTVS_DESCRICAO"))
        self.result_item = {
            "CODIGOTOTVS": code, "CODIGOORIGINAL": self.original.text().strip(),
            "DESCRICAO": desc, "QUANTIDADE": str(self.qty.value()),
            "CLIENTE": norm(self.client.currentData()), "OBSERVACAO": self.obs.toPlainText().strip()
        }
        self.accept()

class NewRequestPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.items = []
        self.employee_data = None
        self.idempotency = str(uuid.uuid4())
        root = QVBoxLayout(self); root.setContentsMargins(26,22,26,22); root.setSpacing(14)

        head = QGroupBox("Dados da solicitação")
        form = QFormLayout(head)
        sr = QHBoxLayout()
        self.employee_search = QLineEdit(); self.employee_search.setPlaceholderText("Nome do funcionário")
        b = QPushButton("Buscar"); b.clicked.connect(self.find_employees)
        sr.addWidget(self.employee_search); sr.addWidget(b)
        self.employee = QComboBox(); self.employee.currentIndexChanged.connect(self.employee_changed)
        self.branch = QLineEdit(); self.branch.setReadOnly(True)
        self.sector = QLineEdit(); self.sector.setReadOnly(True)
        form.addRow("Buscar funcionário:", sr); form.addRow("Funcionário:", self.employee)
        form.addRow("Filial:", self.branch); form.addRow("Setor:", self.sector)
        root.addWidget(head)

        item_box = QGroupBox("Itens solicitados")
        iv = QVBoxLayout(item_box)
        actions = QHBoxLayout()
        self.add_btn = QPushButton("+ Adicionar item"); self.add_btn.setObjectName("Primary"); self.edit_btn = QPushButton("Editar item"); self.remove_btn = QPushButton("Remover item")
        self.add_btn.clicked.connect(self.add_item); self.edit_btn.clicked.connect(self.edit_item); self.remove_btn.clicked.connect(self.remove_item)
        actions.addWidget(self.add_btn); actions.addWidget(self.edit_btn); actions.addWidget(self.remove_btn); actions.addStretch()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Código TOTVS","Descrição","Código original","Qtd.","Cliente","Observação"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        iv.addLayout(actions); iv.addWidget(self.table); root.addWidget(item_box)

        foot = QHBoxLayout()
        self.save_btn = QPushButton("Salvar rascunho"); self.clear_btn = QPushButton("Limpar")
        self.submit_btn = QPushButton("ENVIAR SOLICITAÇÃO"); self.submit_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self.save_draft); self.clear_btn.clicked.connect(self.clear_draft); self.submit_btn.clicked.connect(self.submit)
        foot.addWidget(self.save_btn); foot.addWidget(self.clear_btn); foot.addStretch(); foot.addWidget(self.submit_btn)
        root.addLayout(foot)
        self.load_draft()

    def find_employees(self):
        q = self.employee_search.text().strip()
        try:
            # Procedure criada para busca do cadastro Quark.
            data = safe_proc("usp_APP_BuscarColaboradores", (q, 100))
            self.employee.clear()
            for d in data:
                name = norm(first(d, "pessoa_nome", "PESSOA_NOME", "NOME"))
                branch = norm(first(d, "filial", "FILIAL", "unidade_nome"))
                sector = norm(first(d, "equipe_denominacao", "EQUIPE_DENOMINACAO", "SETOR"))
                self.employee.addItem(f"{name} | {branch} | {sector}", d)
            if not data: QMessageBox.information(self, "Funcionários", "Nenhum funcionário encontrado.")
        except Exception as e: QMessageBox.critical(self, "Funcionários", str(e))

    def employee_changed(self):
        d = self.employee.currentData()
        self.employee_data = d
        if d:
            self.branch.setText(norm(first(d, "filial","FILIAL","unidade_nome")))
            self.sector.setText(norm(first(d, "equipe_denominacao","EQUIPE_DENOMINACAO","SETOR")))

    def refresh_items(self):
        self.table.setRowCount(len(self.items))
        keys = ("CODIGOTOTVS","DESCRICAO","CODIGOORIGINAL","QUANTIDADE","CLIENTE","OBSERVACAO")
        for r,d in enumerate(self.items):
            for c,k in enumerate(keys): self.table.setItem(r,c,QTableWidgetItem(norm(d.get(k))))

    def add_item(self):
        d=ItemDialog(self)
        if d.exec()==QDialog.DialogCode.Accepted:
            self.items.append(d.result_item); self.refresh_items(); self.save_draft(silent=True)

    def edit_item(self):
        r=self.table.currentRow()
        if r<0: QMessageBox.information(self,"Item","Selecione um item."); return
        d=ItemDialog(self,self.items[r])
        if d.exec()==QDialog.DialogCode.Accepted:
            self.items[r]=d.result_item; self.refresh_items(); self.save_draft(silent=True)

    def remove_item(self):
        r=self.table.currentRow()
        if r>=0 and QMessageBox.question(self,"Remover","Remover o item selecionado?")==QMessageBox.StandardButton.Yes:
            self.items.pop(r); self.refresh_items(); self.save_draft(silent=True)

    def payload(self):
        e=self.employee_data or {}
        return {
            "idempotency":self.idempotency,
            "employee_id": first(e,"id","ID"),
            "employee_name":norm(first(e,"pessoa_nome","PESSOA_NOME","NOME")),
            "branch":self.branch.text(),"sector":self.sector.text(),"items":self.items
        }

    def save_draft(self, silent=False):
        try:
            p=draft_path(first(self.main.user,"ID"))
            tmp=p.with_suffix(".tmp"); tmp.write_text(json.dumps(self.payload(),ensure_ascii=False,default=str,indent=2),encoding="utf-8"); os.replace(tmp,p)
            if not silent: QMessageBox.information(self,"Rascunho","Rascunho salvo neste computador.")
        except Exception as e:
            if not silent: QMessageBox.critical(self,"Rascunho",str(e))

    def load_draft(self):
        p=draft_path(first(self.main.user,"ID"))
        if not p.exists(): return
        try:
            d=json.loads(p.read_text(encoding="utf-8")); self.idempotency=d.get("idempotency") or str(uuid.uuid4()); self.items=d.get("items",[])
            self.branch.setText(d.get("branch","")); self.sector.setText(d.get("sector",""))
            if d.get("employee_name"):
                ed={"id":d.get("employee_id"),"pessoa_nome":d.get("employee_name"),"filial":d.get("branch"),"equipe_denominacao":d.get("sector")}
                self.employee.addItem(d["employee_name"],ed); self.employee_data=ed
            self.refresh_items()
        except Exception: pass

    def clear_draft(self):
        if QMessageBox.question(self,"Limpar","Descartar o rascunho atual?")==QMessageBox.StandardButton.Yes:
            self.items=[]; self.employee.clear(); self.employee_data=None; self.branch.clear(); self.sector.clear()
            self.idempotency=str(uuid.uuid4()); self.refresh_items()
            try: draft_path(first(self.main.user,"ID")).unlink(missing_ok=True)
            except Exception: pass

    def items_xml(self):
        root=Element("Itens")
        for item in self.items:
            x=SubElement(root,"Item")
            for k,v in item.items():
                SubElement(x,k).text=norm(v)
        return tostring(root,encoding="unicode")

    def submit(self):
        if not self.employee_data: QMessageBox.warning(self,"Enviar","Selecione o funcionário."); return
        if not self.items: QMessageBox.warning(self,"Enviar","Inclua ao menos um item."); return
        if QMessageBox.question(self,"Confirmar envio",f"Enviar solicitação com {len(self.items)} item(ns)?\n\nApós o envio ela ficará bloqueada para alteração.") != QMessageBox.StandardButton.Yes: return
        try:
            uid=first(self.main.user,"ID"); cid=first(self.employee_data,"id","ID")
            data=safe_proc("usp_APP_CriarSolicitacao",(uid,cid,self.idempotency,self.items_xml()))
            idf=norm(first(data[0],"IDFTECH","ID",default="")) if data else ""
            try: draft_path(uid).unlink(missing_ok=True)
            except Exception: pass
            QMessageBox.information(self,"Solicitação enviada",f"Solicitação enviada com sucesso.{chr(10)+chr(10)+'ID: '+idf if idf else ''}")
            self.items=[]; self.employee.clear(); self.employee_data=None; self.branch.clear(); self.sector.clear(); self.idempotency=str(uuid.uuid4()); self.refresh_items()
            self.main.tracking.refresh()
        except Exception as e:
            QMessageBox.critical(self,"Falha no envio",f"A solicitação não pôde ser enviada.\n\n{e}\n\nO rascunho foi mantido.")
            self.save_draft(silent=True)


class MetricCard(QFrame):
    def __init__(self, title, value="—", subtitle=""):
        super().__init__()
        self.setObjectName("Card")
        self.setMinimumHeight(120)
        lay = QVBoxLayout(self)
        t = QLabel(title); t.setStyleSheet("color:#667085;font-weight:600;")
        self.value = QLabel(value); self.value.setStyleSheet("font-size:28px;font-weight:750;color:#172033;")
        s = QLabel(subtitle); s.setStyleSheet("color:#98a2b3;font-size:11px;")
        lay.addWidget(t); lay.addWidget(self.value); lay.addWidget(s); lay.addStretch()

class DashboardPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main
        root = QVBoxLayout(self); root.setContentsMargins(26,22,26,22); root.setSpacing(18)
        hello = QLabel(f"Olá, {norm(first(main.user,'NOME')).split(' ')[0] or 'usuário'}")
        hello.setObjectName("PageTitle")
        sub = QLabel("Acompanhe suas solicitações e abra novos pedidos de compra.")
        sub.setObjectName("PageSub")
        root.addWidget(hello); root.addWidget(sub)

        cards = QGridLayout(); cards.setSpacing(14)
        self.total = MetricCard("Solicitações visíveis", "—", "Conforme suas permissões")
        self.pending = MetricCard("Em andamento", "—", "Aguardando conclusão")
        self.bought = MetricCard("Com pedido TOTVS", "—", "Pedido já informado")
        self.received = MetricCard("Com NF / recebimento", "—", "Informação disponível")
        for i,c in enumerate((self.total,self.pending,self.bought,self.received)):
            cards.addWidget(c,0,i)
        root.addLayout(cards)

        actions = QFrame(); actions.setObjectName("Card"); al = QVBoxLayout(actions)
        at = QLabel("Ações rápidas"); at.setStyleSheet("font-size:17px;font-weight:700;color:#172033;")
        al.addWidget(at)
        row=QHBoxLayout()
        if main.has("CREATE"):
            b=QPushButton("＋ Nova solicitação"); b.setObjectName("Primary")
            b.clicked.connect(lambda: main.go("new"))
            row.addWidget(b)
        b2=QPushButton("Consultar solicitações"); b2.clicked.connect(lambda: main.go("tracking")); row.addWidget(b2)
        row.addStretch(); al.addLayout(row); root.addWidget(actions)
        root.addStretch()
        QTimer.singleShot(250,self.refresh)

    def refresh(self):
        try:
            data=safe_proc("usp_APP_ListarSolicitacoes",(first(self.main.user,"ID"),))
            self.total.value.setText(str(len(data)))
            pend=pedido=nf=0
            for d in data:
                st=norm(first(d,"SITUACAO","STATUS","STATUS_SOLICITANTE")).upper()
                if "RECEB" in st or "ESTOQUE" in st: nf+=1
                elif "COMPR" in st: pedido+=1
                else: pend+=1
            self.pending.value.setText(str(pend)); self.bought.value.setText(str(pedido)); self.received.value.setText(str(nf))
        except Exception:
            self.total.value.setText("—"); self.pending.value.setText("—"); self.bought.value.setText("—"); self.received.value.setText("—")

class TrackingPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main=main; self.rows=[]
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,22); root.setSpacing(12)

        filters=QHBoxLayout()
        self.search=QLineEdit(); self.search.setPlaceholderText("Pesquisar ID, funcionário, filial ou setor...")
        self.status=QComboBox(); self.status.addItems(["Todos","EM PROCESSO DE COMPRA","COMPRADO","RECEBIDO"])
        self.branch=QComboBox(); self.branch.addItem("Todas as filiais")
        self.sector=QComboBox(); self.sector.addItem("Todos os setores")
        b=QPushButton("Atualizar"); b.setObjectName("Primary"); b.clicked.connect(self.refresh)
        filters.addWidget(self.search,2); filters.addWidget(self.status); filters.addWidget(self.branch); filters.addWidget(self.sector); filters.addWidget(b)
        root.addLayout(filters)

        self.table=QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(["ID FTECH","Data","Funcionário","Filial","Setor","Situação"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.detail)
        root.addWidget(self.table,1)

        bottom=QHBoxLayout()
        self.counter=QLabel("0 registro(s)"); self.counter.setStyleSheet("color:#667085;")
        detail=QPushButton("Ver detalhes"); detail.clicked.connect(self.detail)
        bottom.addWidget(self.counter); bottom.addStretch(); bottom.addWidget(detail)
        root.addLayout(bottom)

        self.search.textChanged.connect(self.apply_filter)
        self.status.currentTextChanged.connect(self.apply_filter)
        self.branch.currentTextChanged.connect(self.apply_filter)
        self.sector.currentTextChanged.connect(self.apply_filter)

    def refresh(self):
        try:
            self.rows=safe_proc("usp_APP_ListarSolicitacoes",(first(self.main.user,"ID"),))
            branches=sorted({norm(first(x,"FILIAL")) for x in self.rows if norm(first(x,"FILIAL"))})
            sectors=sorted({norm(first(x,"SETOR")) for x in self.rows if norm(first(x,"SETOR"))})
            cb=self.branch.currentText(); cs=self.sector.currentText()
            self.branch.blockSignals(True); self.sector.blockSignals(True)
            self.branch.clear(); self.branch.addItem("Todas as filiais"); self.branch.addItems(branches)
            self.sector.clear(); self.sector.addItem("Todos os setores"); self.sector.addItems(sectors)
            if cb in branches:self.branch.setCurrentText(cb)
            if cs in sectors:self.sector.setCurrentText(cs)
            self.branch.blockSignals(False); self.sector.blockSignals(False)
            self.apply_filter()
        except Exception as e: QMessageBox.critical(self,"Acompanhamento",str(e))

    def apply_filter(self):
        q=self.search.text().strip().casefold()
        st=self.status.currentText().upper()
        br=self.branch.currentText()
        sec=self.sector.currentText()
        data=[]
        for d in self.rows:
            hay=" ".join(norm(first(d,k)) for k in ("IDFTECH","FUNCIONARIO","FILIAL","SETOR","SITUACAO")).casefold()
            dst=norm(first(d,"SITUACAO","STATUS")).upper()
            if q and q not in hay: continue
            if st!="TODOS" and st not in dst: continue
            if br!="Todas as filiais" and norm(first(d,"FILIAL"))!=br: continue
            if sec!="Todos os setores" and norm(first(d,"SETOR"))!=sec: continue
            data.append(d)
        self.render(data)

    def render(self,data):
        self.table.setRowCount(len(data))
        for r,d in enumerate(data):
            vals=[first(d,"IDFTECH"),first(d,"DATAATUAL"),first(d,"FUNCIONARIO"),first(d,"FILIAL"),first(d,"SETOR"),first(d,"SITUACAO","STATUS")]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(norm(v)))
        self.counter.setText(f"{len(data)} registro(s)")

    def detail(self):
        r=self.table.currentRow()
        if r<0: QMessageBox.information(self,"Detalhes","Selecione uma solicitação."); return
        idf=self.table.item(r,0).text()
        try:
            items=safe_proc("usp_APP_AcompanharItens",(first(self.main.user,"ID"),idf))
            if not items:
                try: items=safe_proc("usp_APP_ObterSolicitacao",(first(self.main.user,"ID"),idf))
                except Exception: pass
            TableDialog(f"Solicitação {idf} — somente leitura",items,self).exec()
        except Exception as e: QMessageBox.critical(self,"Detalhes",str(e))

class AdminPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main=main; self.users=[]
        root=QVBoxLayout(self); root.setContentsMargins(26,22,26,22); root.setSpacing(12)
        top=QHBoxLayout()
        for label,fn in [("Atualizar",self.refresh),("+ Novo usuário",self.new_user),("Ativar/Inativar",self.toggle_active),
                         ("Bloquear",self.block),("Desbloquear",self.unblock),("Redefinir senha",self.reset_password),("Acessos",self.accesses)]:
            b=QPushButton(label); b.clicked.connect(fn); top.addWidget(b)
        top.addStretch(); root.addLayout(top)
        self.table=QTableWidget(); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table)
        if self.main.has("VIEW_AUDIT") or self.main.has("ADMIN"):
            ba=QPushButton("Consultar auditoria"); ba.clicked.connect(self.audit); root.addWidget(ba)
        QTimer.singleShot(100,self.refresh)

    def actor(self): return first(self.main.user,"ID")
    def selected(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.users): QMessageBox.information(self,"Administração","Selecione um usuário."); return None
        return self.users[r]

    def refresh(self):
        try:
            self.users=safe_proc("usp_APP_AdminListarUsuarios",(self.actor(),))
        except Exception:
            try: self.users=safe_proc("usp_APP_AdminListarUsuarios",())
            except Exception as e: QMessageBox.critical(self,"Administração",str(e)); return
        self.table.clear()
        if not self.users: return
        cols=[k for k in self.users[0] if "SENHA" not in k.upper() and "HASH" not in k.upper()]
        self.table.setColumnCount(len(cols)); self.table.setHorizontalHeaderLabels(cols); self.table.setRowCount(len(self.users))
        for r,d in enumerate(self.users):
            for c,k in enumerate(cols): self.table.setItem(r,c,QTableWidgetItem(norm(d[k])))

    def new_user(self):
        name,ok=QInputDialog.getText(self,"Novo usuário","Nome:");
        if not ok or not name.strip(): return
        email,ok=QInputDialog.getText(self,"Novo usuário","E-mail:")
        if not ok or not email.strip(): return
        pwd,ok=QInputDialog.getText(self,"Novo usuário","Senha temporária:",QLineEdit.EchoMode.Password)
        if not ok or not pwd: return
        h=PH.hash(pwd)
        try:
            safe_proc("usp_APP_AdminCriarUsuario",(self.actor(),name.strip(),email.strip().lower(),h))
            QMessageBox.information(self,"Administração","Usuário criado. A troca da senha será exigida no primeiro acesso."); self.refresh()
        except Exception as e: QMessageBox.critical(self,"Administração",str(e))

    def edit_user(self):
        u=self.selected()
        if not u:return
        dlg=QDialog(self); dlg.setWindowTitle("Editar usuário"); form=QFormLayout(dlg)
        name=QLineEdit(norm(first(u,"NOME"))); email=QLineEdit(norm(first(u,"EMAIL")))
        ok=QPushButton("Salvar alterações"); ok.setObjectName("Primary")
        form.addRow("Nome:",name); form.addRow("E-mail:",email); form.addRow(ok)
        def save():
            if not name.text().strip() or not email.text().strip():
                QMessageBox.warning(dlg,"Usuário","Informe nome e e-mail."); return
            try:
                safe_proc("usp_APP_AdminAlterarUsuario",(self.actor(),first(u,"ID"),name.text().strip(),email.text().strip().lower()))
                dlg.accept(); self.refresh()
            except Exception as e: QMessageBox.critical(dlg,"Usuário",str(e))
        ok.clicked.connect(save); dlg.exec()

    def toggle_active(self):
        u=self.selected()
        if not u:return
        active=bool(first(u,"ATIVO",default=True))
        try: safe_proc("usp_APP_AdminDefinirAtivo",(self.actor(),first(u,"ID"),0 if active else 1)); self.refresh()
        except Exception as e: QMessageBox.critical(self,"Administração",str(e))

    def block(self):
        u=self.selected()
        if not u:return
        reason,ok=QInputDialog.getText(self,"Bloquear","Justificativa:")
        if not ok or not reason.strip():return
        try: safe_proc("usp_APP_AdminBloquearUsuario",(self.actor(),first(u,"ID"),reason.strip())); self.refresh()
        except Exception as e: QMessageBox.critical(self,"Administração",str(e))

    def unblock(self):
        u=self.selected()
        if not u:return
        try: safe_proc("usp_APP_AdminDesbloquearUsuario",(self.actor(),first(u,"ID"))); self.refresh()
        except Exception as e: QMessageBox.critical(self,"Administração",str(e))

    def reset_password(self):
        u=self.selected()
        if not u:return
        pwd,ok=QInputDialog.getText(self,"Redefinir senha","Nova senha temporária:",QLineEdit.EchoMode.Password)
        if not ok or not pwd:return
        try: safe_proc("usp_APP_AdminResetarSenha",(self.actor(),first(u,"ID"),PH.hash(pwd))); QMessageBox.information(self,"Senha","Senha redefinida.")
        except Exception as e: QMessageBox.critical(self,"Administração",str(e))

    def accesses(self):
        u=self.selected()
        if not u:return
        dlg=AccessDialog(self,self.actor(),first(u,"ID"))
        dlg.exec()

    def audit(self):
        try:
            data=safe_proc("usp_APP_AdminListarAuditoria",(self.actor(),))
            dlg=TableDialog("Auditoria",data,self); dlg.exec()
        except Exception as e: QMessageBox.critical(self,"Auditoria",str(e))

class AccessDialog(QDialog):
    def __init__(self,parent,actor,user_id):
        super().__init__(parent); self.actor=actor; self.user_id=user_id
        self.setWindowTitle("Filiais, setores e permissões"); self.resize(800,600)
        root=QVBoxLayout(self); cols=QHBoxLayout()
        self.branches=QListWidget(); self.sectors=QListWidget(); self.grants=QListWidget()
        for title,w in [("Filiais",self.branches),("Setores",self.sectors),("Permissões",self.grants)]:
            box=QGroupBox(title); l=QVBoxLayout(box); l.addWidget(w); cols.addWidget(box)
        root.addLayout(cols); save=QPushButton("Salvar acessos"); save.clicked.connect(self.save); root.addWidget(save)
        self.load()

    def fill_checks(self,w,values,selected):
        w.clear()
        sel={norm(x).casefold() for x in selected}
        for v in values:
            s=norm(v); it=QListWidgetItem(s); it.setFlags(it.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if s.casefold() in sel else Qt.CheckState.Unchecked); w.addItem(it)

    def checked(self,w):
        return [w.item(i).text() for i in range(w.count()) if w.item(i).checkState()==Qt.CheckState.Checked]

    def load(self):
        try:
            acc=safe_proc("usp_APP_AdminObterAcessos",(self.actor,self.user_id))
            # Se a procedure retorna conjuntos múltiplos, a versão simples pode não trazer todos.
            current_br=[]; current_sec=[]; current_gr=[]
            for d in acc:
                typ=norm(first(d,"TIPO","TIPO_ACESSO")).upper(); val=first(d,"VALOR","FILIAL","SETOR","PERMISSAO")
                if typ=="FILIAL":current_br.append(val)
                elif typ=="SETOR":current_sec.append(val)
                elif typ in ("PERMISSAO","GRANT"):current_gr.append(val)
            br=safe_proc("usp_APP_AdminListarFiliais",(self.actor,))
            sec=safe_proc("usp_APP_AdminListarSetores",(self.actor,))
            self.fill_checks(self.branches,[first(x,"FILIAL","NOME") for x in br],current_br)
            self.fill_checks(self.sectors,[first(x,"SETOR","NOME") for x in sec],current_sec)
            self.fill_checks(self.grants,GRANTS,current_gr)
        except Exception as e: QMessageBox.critical(self,"Acessos",str(e))

    def save(self):
        # Procedures de substituição recebem JSON com o conjunto completo.
        try:
            safe_proc("usp_APP_AdminSalvarFiliais",(self.actor,self.user_id,json.dumps(self.checked(self.branches),ensure_ascii=False)))
            safe_proc("usp_APP_AdminSalvarSetores",(self.actor,self.user_id,json.dumps(self.checked(self.sectors),ensure_ascii=False)))
            safe_proc("usp_APP_AdminSalvarPermissoes",(self.actor,self.user_id,json.dumps(self.checked(self.grants),ensure_ascii=False)))
            QMessageBox.information(self,"Acessos","Acessos salvos."); self.accept()
        except Exception as e: QMessageBox.critical(self,"Acessos",str(e))

class TableDialog(QDialog):
    def __init__(self,title,data,parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.resize(1100,650)
        l=QVBoxLayout(self); t=QTableWidget(); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); l.addWidget(t)
        if data:
            cols=list(data[0]); t.setColumnCount(len(cols)); t.setHorizontalHeaderLabels(cols); t.setRowCount(len(data))
            for r,d in enumerate(data):
                for c,k in enumerate(cols):t.setItem(r,c,QTableWidgetItem(norm(d[k])))
            t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

class ChangePasswordDialog(QDialog):
    def __init__(self,user,parent=None,forced=False):
        super().__init__(parent); self.user=user; self.forced=forced
        self.setWindowTitle("Trocar senha" if not forced else "Primeiro acesso — crie sua nova senha")
        self.setModal(True); self.setMinimumWidth(430)
        l=QVBoxLayout(self)
        if forced:
            info=QLabel("Por segurança, a senha temporária precisa ser substituída antes de acessar o sistema.")
            info.setWordWrap(True); info.setStyleSheet("color:#667085;")
            l.addWidget(info)
        f=QFormLayout(); self.a=QLineEdit(); self.b=QLineEdit()
        self.a.setEchoMode(QLineEdit.EchoMode.Password); self.b.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("Nova senha:",self.a); f.addRow("Confirmar:",self.b); l.addLayout(f)
        row=QHBoxLayout(); row.addStretch()
        if not forced:
            cancel=QPushButton("Cancelar"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        ok=QPushButton("ALTERAR SENHA"); ok.setObjectName("Primary"); ok.clicked.connect(self.go); row.addWidget(ok); l.addLayout(row)

    def reject(self):
        if self.forced:return
        super().reject()

    def go(self):
        if len(self.a.text())<8:
            QMessageBox.warning(self,"Senha","Use uma senha com pelo menos 8 caracteres."); return
        if self.a.text()!=self.b.text():
            QMessageBox.warning(self,"Senha","As senhas não coincidem."); return
        try:
            execute("EXEC dbo.usp_APP_AlterarMinhaSenha ?,?",first(self.user,"ID"),PH.hash(self.a.text()))
            QMessageBox.information(self,"Senha","Senha alterada com sucesso."); self.accept()
        except Exception as e: QMessageBox.critical(self,"Senha",str(e))

class MainWindow(QMainWindow):
    def __init__(self,user):
        super().__init__(); self.user=user; self.permissions=set(); self.pages={}; self.nav={}
        self.setWindowTitle(f"{APP_NAME}  •  {APP_VERSION}"); self.resize(1480,880); self.setMinimumSize(1180,720)
        self.load_permissions()

        shell=QWidget(); self.setCentralWidget(shell); outer=QHBoxLayout(shell); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        sidebar=QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(235)
        sl=QVBoxLayout(sidebar); sl.setContentsMargins(14,18,14,18); sl.setSpacing(6)
        brand=QLabel("FTECH Compras"); brand.setObjectName("Brand")
        bsub=QLabel("SOLICITAÇÃO DE COMPRAS"); bsub.setObjectName("BrandSub")
        sl.addWidget(brand); sl.addWidget(bsub)

        content=QWidget(); cl=QVBoxLayout(content); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
        top=QFrame(); top.setObjectName("Topbar"); top.setFixedHeight(70); tl=QHBoxLayout(top); tl.setContentsMargins(24,8,24,8)
        self.page_title=QLabel("Início"); self.page_title.setObjectName("PageTitle")
        userbox=QLabel(f"{first(user,'NOME')}\n{first(user,'EMAIL')}")
        userbox.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        userbox.setStyleSheet("color:#475467;")
        tl.addWidget(self.page_title); tl.addStretch(); tl.addWidget(userbox)
        self.stack=QStackedWidget()
        cl.addWidget(top); cl.addWidget(self.stack,1)
        outer.addWidget(sidebar); outer.addWidget(content,1)

        self.dashboard=DashboardPage(self); self.add_page(sidebar,sl,"home","⌂  Início",self.dashboard)
        if self.has("CREATE"):
            self.new_request=NewRequestPage(self); self.add_page(sidebar,sl,"new","＋  Nova Solicitação",self.new_request)
        self.tracking=TrackingPage(self); self.add_page(sidebar,sl,"tracking","☷  Acompanhamento",self.tracking)
        if any(self.has(x) for x in ("MANAGE_USERS","MANAGE_PERMISSIONS","VIEW_AUDIT","ADMIN")):
            self.admin=AdminPage(self); self.add_page(sidebar,sl,"admin","⚙  Administração",self.admin)

        sl.addStretch()
        change=QPushButton("Alterar minha senha"); change.setObjectName("NavButton")
        change.clicked.connect(lambda:ChangePasswordDialog(self.user,self).exec()); sl.addWidget(change)
        logout=QPushButton("Sair"); logout.setObjectName("NavButton"); logout.clicked.connect(QApplication.quit); sl.addWidget(logout)

        self.statusBar().showMessage("Conectado ao FTECH • acesso conforme permissões do usuário")
        self.last_activity=datetime.now(); self.idle=QTimer(self); self.idle.timeout.connect(self.check_idle); self.idle.start(60_000)
        self.go("home")

    def add_page(self,sidebar,layout,key,label,page):
        self.pages[key]=page; self.stack.addWidget(page)
        b=QPushButton(label); b.setObjectName("NavButton"); b.setCheckable(True)
        b.clicked.connect(lambda checked=False,k=key:self.go(k)); self.nav[key]=b; layout.addWidget(b)

    def go(self,key):
        if key not in self.pages:return
        self.stack.setCurrentWidget(self.pages[key])
        titles={"home":"Início","new":"Nova Solicitação","tracking":"Acompanhamento","admin":"Administração"}
        self.page_title.setText(titles.get(key,key))
        for k,b in self.nav.items(): b.setChecked(k==key)
        if key=="tracking": self.tracking.refresh()
        if key=="home": self.dashboard.refresh()

    def load_permissions(self):
        try:
            data=safe_proc("usp_APP_ListarPermissoes",(first(self.user,"ID"),))
            for d in data:
                p=norm(first(d,"PERMISSAO","GRANT"))
                allowed=first(d,"PERMITIDO","ATIVO",default=True)
                if p and bool(allowed): self.permissions.add(p.upper())
        except Exception: pass

    def has(self,p): return "ADMIN" in self.permissions or p.upper() in self.permissions

    def event(self,e):
        if e.type() in (e.Type.MouseButtonPress,e.Type.KeyPress,e.Type.Wheel):
            self.last_activity=datetime.now()
        return super().event(e)

    def check_idle(self):
        if (datetime.now()-self.last_activity).total_seconds()>=1800:
            QMessageBox.information(self,"Sessão","Sessão encerrada após 30 minutos de inatividade.")
            QApplication.quit()

def main():
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setStyleSheet(STYLE)
    try: sql_password()
    except Exception as e:
        QMessageBox.critical(None,APP_NAME,str(e)); return 2
    login=LoginDialog()
    if login.exec()!=QDialog.DialogCode.Accepted:return 0
    # troca obrigatória antes da janela principal
    if bool(first(login.user,"TROCAR_SENHA",default=False)):
        d=ChangePasswordDialog(login.user)
        if d.exec()!=QDialog.DialogCode.Accepted:return 0
    w=MainWindow(login.user); w.show()
    return app.exec()

if __name__=="__main__":
    raise SystemExit(main())
