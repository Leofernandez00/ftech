import sys
import os
import subprocess
import importlib.util
from pathlib import Path

def check_virtualenv():
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Ambiente virtual ATIVADO")
    else:
        print("⚠️ Nenhum ambiente virtual detectado!")

def check_python_version():
    print(f"✅ Python versão: {sys.version}")

def check_pyqt6_installation():
    spec = importlib.util.find_spec("PyQt6")
    if spec is None:
        print("❌ PyQt6 NÃO está instalado.")
    else:
        print("✅ PyQt6 encontrado.")
        try:
            import PyQt6
            print(f"✅ PyQt6 versão: {PyQt6.__version__}")
            print(f"📂 Local de instalação: {Path(PyQt6.__file__).parent}")
        except Exception as e:
            print(f"❌ Erro ao importar PyQt6: {e}")

def check_dll_block(pydir):
    print("\n🔍 Verificando DLLs bloqueadas...")
    blocked = False
    for file in Path(pydir).glob("*.pyd"):
        props = subprocess.run(['powershell', '-Command', f"(Get-Item '{file}').Attributes"], capture_output=True, text=True)
        if "Blocked" in props.stdout:
            print(f"⚠️ Arquivo bloqueado: {file}")
            blocked = True
    if not blocked:
        print("✅ Nenhum arquivo bloqueado encontrado.")

def check_pip_path():
    print("\n✅ PIP está usando: ")
    subprocess.run([sys.executable, '-m', 'pip', '--version'])

def check_where_python():
    print("\n✅ Localizações do Python:")
    subprocess.run(['where', 'python'], shell=True)

def check_environment():
    print("\n✅ PATH atual:")
    print(os.environ.get('PATH'))

if __name__ == "__main__":
    print("🔧 Iniciando diagnóstico do ambiente PyQt6...\n")
    check_virtualenv()
    check_python_version()
    check_pyqt6_installation()
    check_pip_path()
    check_where_python()
    check_environment()

    try:
        import PyQt6
        check_dll_block(Path(PyQt6.__file__).parent)
    except:
        print("❌ PyQt6 não importado. Pulando verificação de bloqueio de DLLs.")
