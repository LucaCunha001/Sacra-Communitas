import os
import shlex
import sys
import subprocess

def is_unix() -> bool:
	"""Retorna True se o sistema for Unix (Linux/macOS)."""
	return os.name != "nt"


def convert(cmd: str) -> list[str]:
	"""Converte o comando para o formato adequado ao SO."""
	cmd_parts: list[str] = shlex.split(cmd)
	final_cmd = []

	for part in cmd_parts:
		if part == "clear" and not is_unix():
			part = "cls"
		
		final_cmd.append(part)

	return final_cmd


def command(cmd: str) -> subprocess.Popen | None:
	"""
	Executa um comando de forma não bloqueante.
	Retorna o processo (Popen) ou None se falhar.
	"""
	try:
		converted_cmd = convert(cmd)
		return subprocess.Popen(converted_cmd, shell=True)
	
	except FileNotFoundError:
		print(f"[ERRO] Comando não encontrado: {cmd}")

	except Exception as e:
		print(f"[ERRO] Falha ao executar '{cmd}': {e}")

	return None

def reinstall_requirements():
	"""
	Reinstala os requisitos do código
	"""
	return subprocess.run(
		[sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--root-user-action=ignore"]
	)

def upgrade_pip():
	"""
	Atualiza o pip
	"""
	return subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])