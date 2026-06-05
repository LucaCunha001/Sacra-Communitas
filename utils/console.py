import os
import subprocess
import sys


def is_unix() -> bool:
	"""Retorna True se o sistema for Unix (Linux/macOS)."""
	return os.name != "nt"


def clear_console() -> None:
	"""Limpa o terminal para o sistema operacional atual."""
	command = "clear" if is_unix() else "cls"
	subprocess.run(command, shell=True)


def command(cmd: str) -> subprocess.CompletedProcess | None:
	"""Executa um comando no shell e retorna o resultado."""
	try:
		return subprocess.run(cmd, shell=True, check=True)
	except FileNotFoundError:
		print(f"[ERRO] Comando não encontrado: {cmd}")
	except subprocess.CalledProcessError as error:
		print(f"[ERRO] Comando falhou ({cmd}): {error}")
	except Exception as e:
		print(f"[ERRO] Falha ao executar '{cmd}': {e}")

	return None

def reinstall_requirements() -> subprocess.CompletedProcess:
	"""Instala ou atualiza as dependências do projeto."""
	return subprocess.run(
		[sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--root-user-action=ignore"],
		check=True,
	)

def upgrade_pip() -> int:
	"""
	Atualiza o pip
	"""
	return subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])