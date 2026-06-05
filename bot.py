import logging
import os
import sys

from dotenv import load_dotenv
from utils.console import clear_console
from utils.logger import setup_logging
from utils.recursos import Bot

load_dotenv()
setup_logging(os.getenv("LOG_LEVEL", "INFO"))

if __name__ == "__main__":
	clear_console()

	token = os.getenv("TOKEN")
	if not token:
		logging.error("Token não encontrado. Verifique o arquivo .env")
		sys.exit(1)

	bot = Bot()
	try:
		bot.run(token)
	except Exception as error:
		logging.exception("Falha ao iniciar o bot")
		sys.exit(1)
