import cv2
import smtplib
import os
from datetime import datetime, time
import tkinter as tk
from tkinter import filedialog, messagebox
from threading import Thread


class SecurityApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Segurança com Webcam")

        # Variáveis de controle
        self.diretorio_videos = ""
        self.horario_inicio = time(8, 0)
        self.horario_fim = time(18, 0)
        self.gravando = False
        self.movimento_detectado = False

        # Interface
        self.create_widgets()

        # Variáveis da webcam
        self.cap = None
        self.out = None
        self.detector_ativado = False

    def create_widgets(self):
        # Configuração do diretório
        self.btn_diretorio = tk.Button(self.root, text="Escolher Diretório", command=self.escolher_diretorio)
        self.btn_diretorio.pack(pady=10)

        # Configuração do horário
        self.lbl_horario = tk.Label(self.root, text="Horário de Monitoramento (Ex: 08:00 - 18:00)")
        self.lbl_horario.pack(pady=5)

        self.txt_horario_inicio = tk.Entry(self.root)
        self.txt_horario_inicio.insert(0, "08:00")
        self.txt_horario_inicio.pack(pady=5)

        self.txt_horario_fim = tk.Entry(self.root)
        self.txt_horario_fim.insert(0, "18:00")
        self.txt_horario_fim.pack(pady=5)

        # Botões de controle
        self.btn_iniciar = tk.Button(self.root, text="Iniciar Monitoramento", command=self.iniciar_monitoramento)
        self.btn_iniciar.pack(pady=10)

        self.btn_parar = tk.Button(self.root, text="Parar Monitoramento", command=self.parar_monitoramento)
        self.btn_parar.pack(pady=10)

        # Área para exibir a webcam
        self.lbl_video = tk.Label(self.root)
        self.lbl_video.pack(pady=10)

    def escolher_diretorio(self):
        self.diretorio_videos = filedialog.askdirectory()
        if not self.diretorio_videos:
            messagebox.showwarning("Aviso", "Selecione um diretório válido!")

    def iniciar_monitoramento(self):
        # Verificar horário configurado
        horario_inicio = self.txt_horario_inicio.get()
        horario_fim = self.txt_horario_fim.get()
        try:
            self.horario_inicio = datetime.strptime(horario_inicio, "%H:%M").time()
            self.horario_fim = datetime.strptime(horario_fim, "%H:%M").time()
        except ValueError:
            messagebox.showerror("Erro", "Horário inválido. Use o formato HH:MM.")
            return

        # Verificar se o diretório foi selecionado
        if not self.diretorio_videos:
            messagebox.showwarning("Aviso", "Selecione um diretório para salvar os vídeos!")
            return

        # Iniciar a captura de vídeo em uma thread separada
        self.cap = cv2.VideoCapture(0)
        self.detector_ativado = True
        self.thread_monitoramento = Thread(target=self.monitorar_movimento)
        self.thread_monitoramento.start()

    def parar_monitoramento(self):
        self.detector_ativado = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

    def monitorar_movimento(self):
        quadro_anterior = None
        while self.detector_ativado:
            ret, frame = self.cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if quadro_anterior is None:
                quadro_anterior = gray
                continue

            frame_diff = cv2.absdiff(quadro_anterior, gray)
            _, threshold = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
            movimento = cv2.dilate(threshold, None, iterations=2)
            contornos, _ = cv2.findContours(movimento, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contorno in contornos:
                if cv2.contourArea(contorno) < 500:
                    continue
                (x, y, w, h) = cv2.boundingRect(contorno)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Gravar vídeo quando o movimento for detectado
                if not self.gravando:
                    horario_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    caminho_arquivo = os.path.join(self.diretorio_videos, f"video_{horario_atual}.avi")
                    self.out = cv2.VideoWriter(caminho_arquivo, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (640, 480))
                    self.gravando = True

                self.out.write(frame)

                # Verificar se o movimento está fora do horário permitido
                horario_atual = datetime.now().time()
                if not (self.horario_inicio <= horario_atual <= self.horario_fim):
                    self.enviar_email()

            quadro_anterior = gray.copy()

            # Exibir a imagem da webcam na interface
            self.mostrar_frame(frame)

        if self.out:
            self.out.release()

    def mostrar_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        cv2.imshow("Webcam", img)

    def enviar_email(self):
        remetente = 'seuemail@example.com'
        destinatario = 'destinatario@example.com'
        senha = 'sua_senha'

        assunto = 'Movimento detectado fora do horário!'
        corpo = f"Movimento detectado às {datetime.now()}."

        mensagem = f'Subject: {assunto}\n\n{corpo}'

        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(remetente, senha)
                server.sendmail(remetente, destinatario, mensagem)
            print("E-mail enviado com sucesso!")
        except Exception as e:
            print(f"Erro ao enviar e-mail: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = SecurityApp(root)
    root.mainloop()

