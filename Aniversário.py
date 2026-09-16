import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pyodbc
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formataddr

# Função para conectar ao SQL Server
def connect_db():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};'
                          'SERVER=SERVER\\SQL2017;'
                          'DATABASE=AltaPaulista;'
                          'UID=sa;'
                          'PWD=Sonoda455b')
    return conn

# Função para cadastrar funcionário
def cadastrar_funcionario(nome, email, data_nascimento, imagem):
    conn = connect_db()
    cursor = conn.cursor()
    data_nascimento_sql = datetime.strptime(data_nascimento, "%d/%m/%Y").strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO Funcionarios (nome, email, data_nascimento, imagem) VALUES (?, ?, ?, ?)",
                   (nome, email, data_nascimento_sql, imagem))
    conn.commit()
    conn.close()

# Função para atualizar funcionário
def atualizar_funcionario(id, nome, email, data_nascimento, imagem):
    conn = connect_db()
    cursor = conn.cursor()
    data_nascimento_sql = datetime.strptime(data_nascimento, "%d/%m/%Y").strftime("%Y-%m-%d")
    cursor.execute("""
        UPDATE Funcionarios
        SET nome = ?, email = ?, data_nascimento = ?, imagem = ?
        WHERE id = ?
    """, (nome, email, data_nascimento_sql, imagem, id))
    conn.commit()
    conn.close()

# Função para excluir funcionário
def excluir_funcionario(id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Funcionarios WHERE id = ?", (id,))
    conn.commit()
    conn.close()

# Função para enviar um e-mail
def send_email(name, to_email, cc_email, image_path):
    from_email = "marketing@altapaulistapecas.com.br"
    password = "Tog14$098*"

    msg = MIMEMultipart('related')
    msg['From'] = formataddr(('Alta Paulista', from_email))
    msg['To'] = to_email
    if cc_email:
        msg['Cc'] = cc_email
    msg['Subject'] = f"Feliz Aniversário, {name}!"

    body = f"""
    <html>
    <body>
        <p></p>
        <img src="cid:birthday_image">
    </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        with open(image_path, 'rb') as f:
            img = MIMEImage(f.read())
            img.add_header('Content-ID', '<birthday_image>')
            msg.attach(img)
    except Exception as e:
        print(f"Erro ao abrir imagem: {e}")
        return

    try:
        # Conectar ao servidor SMTP usando SSL diretamente
        server = smtplib.SMTP_SSL('smtp.dreamhost.com', 465)
        server.login(from_email, password)
        server.sendmail(from_email, [to_email] + ([cc_email] if cc_email else []), msg.as_string())
        server.quit()
        print(f"E-mail enviado para {name} ({to_email})")
    except smtplib.SMTPException as e:
        print(f"Erro no SMTP: {e}")
    except Exception as e:
        print(f"Erro ao enviar e-mail para {name} ({to_email}): {e}")

# Função para selecionar a imagem do funcionário
def selecionar_imagem(entry):
    filepath = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
    entry.delete(0, tk.END)
    entry.insert(0, filepath)

# Função para visualizar e-mails antes de enviar
def visualizar_email(nome, to_email, image_path):
    try:
        visualizar_window = tk.Toplevel()
        visualizar_window.title("Visualizar E-mail")

        tk.Label(visualizar_window, text=f"Para: {to_email}").pack()
        tk.Label(visualizar_window, text=f"Assunto: Feliz Aniversário, {nome}").pack()
        tk.Label(visualizar_window, text="Corpo do E-mail:").pack()

        preview_text = f"""
        <html>
        <body>
            <p></p>
            <img src="cid:birthday_image">
        </body>
        </html>
        """
        body_preview = tk.Text(visualizar_window, height=10, width=50)
        body_preview.insert(tk.END, preview_text)
        body_preview.config(state=tk.DISABLED)
        body_preview.pack()

        tk.Label(visualizar_window, text="CC:").pack()
        cc_entry = tk.Entry(visualizar_window, width=50)
        cc_entry.pack()

        def enviar():
            cc_email = cc_entry.get()
            send_email(nome, to_email, cc_email, image_path)
            visualizar_window.destroy()

        tk.Button(visualizar_window, text="Enviar", command=enviar).pack()

    except Exception as e:
        print(f"Erro ao visualizar e-mail: {e}")

# Função para mostrar destinatários e permitir visualização e envio de e-mail
def mostrar_destinatarios():
    try:
        enviar_window = tk.Toplevel()
        enviar_window.title("Enviar E-mails de Aniversário")

        tree = ttk.Treeview(enviar_window, columns=("nome", "email", "data_nascimento", "imagem"), show="headings")
        tree.heading("nome", text="Nome")
        tree.heading("email", text="E-mail")
        tree.heading("data_nascimento", text="Data de Nascimento")
        tree.heading("imagem", text="Imagem")

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nome, email, data_nascimento, imagem FROM Funcionarios")
        rows = cursor.fetchall()
        today = datetime.now().strftime("%d/%m")

        for row in rows:
            birthday = row[2].strftime("%d/%m")
            if birthday == today:
                tree.insert("", "end", values=(row[0], row[1], row[2].strftime("%d/%m/%Y"), row[3]))

        conn.close()

        tree.pack()

        tk.Label(enviar_window, text="CC:").pack()
        cc_entry = tk.Entry(enviar_window, width=50)
        cc_entry.pack()

        def visualizar_e_enviar():
            try:
                selected_item = tree.selection()
                if not selected_item:
                    messagebox.showwarning("Aviso", "Nenhum funcionário selecionado.")
                    return

                item = tree.item(selected_item)
                values = item["values"]
                nome = values[0]
                email = values[1]
                imagem = values[3]

                visualizar_email(nome, email, imagem)
                print(f"Visualização de e-mail para {nome} ({email}) aberta.")

            except Exception as e:
                print(f"Erro ao visualizar e enviar: {e}")

        tk.Button(enviar_window, text="Visualizar e Enviar", command=visualizar_e_enviar).pack()

    except Exception as e:
        print(f"Erro ao mostrar destinatários: {e}")

# Interface gráfica para gerenciar funcionários
class CadastroFuncionarioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerenciar Funcionários")

        tk.Label(root, text="Nome:").grid(row=0, column=0)
        self.nome_entry = tk.Entry(root)
        self.nome_entry.grid(row=0, column=1)

        tk.Label(root, text="E-mail:").grid(row=1, column=0)
        self.email_entry = tk.Entry(root)
        self.email_entry.grid(row=1, column=1)

        tk.Label(root, text="Data de Nascimento (dd/mm/yyyy):").grid(row=2, column=0)
        self.data_entry = tk.Entry(root)
        self.data_entry.grid(row=2, column=1)

        tk.Label(root, text="Imagem:").grid(row=3, column=0)
        self.imagem_entry = tk.Entry(root)
        self.imagem_entry.grid(row=3, column=1)
        self.imagem_button = tk.Button(root, text="Selecionar Imagem", command=lambda: selecionar_imagem(self.imagem_entry))
        self.imagem_button.grid(row=3, column=2)

        self.cadastrar_button = tk.Button(root, text="Cadastrar", command=self.cadastrar)
        self.cadastrar_button.grid(row=4, columnspan=3)

        self.atualizar_button = tk.Button(root, text="Atualizar", command=self.atualizar)
        self.atualizar_button.grid(row=5, columnspan=3)

        self.excluir_button = tk.Button(root, text="Excluir", command=self.excluir)
        self.excluir_button.grid(row=6, columnspan=3)

        self.enviar_email_button = tk.Button(root, text="Enviar E-mails de Aniversário", command=mostrar_destinatarios)
        self.enviar_email_button.grid(row=7, columnspan=3)

        self.id_funcionario = None

    def cadastrar(self):
        nome = self.nome_entry.get()
        email = self.email_entry.get()
        data_nascimento = self.data_entry.get()
        imagem = self.imagem_entry.get()
        cadastrar_funcionario(nome, email, data_nascimento, imagem)
        messagebox.showinfo("Sucesso", "Funcionário cadastrado com sucesso.")

    def atualizar(self):
        if self.id_funcionario is None:
            messagebox.showwarning("Aviso", "Nenhum funcionário selecionado.")
            return

        nome = self.nome_entry.get()
        email = self.email_entry.get()
        data_nascimento = self.data_entry.get()
        imagem = self.imagem_entry.get()
        atualizar_funcionario(self.id_funcionario, nome, email, data_nascimento, imagem)
        messagebox.showinfo("Sucesso", "Funcionário atualizado com sucesso.")

    def excluir(self):
        if self.id_funcionario is None:
            messagebox.showwarning("Aviso", "Nenhum funcionário selecionado.")
            return

        excluir_funcionario(self.id_funcionario)
        messagebox.showinfo("Sucesso", "Funcionário excluído com sucesso.")
        self.id_funcionario = None

if __name__ == "__main__":
    root = tk.Tk()
    app = CadastroFuncionarioApp(root)
    root.mainloop()
