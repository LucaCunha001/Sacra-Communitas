import os

from dotenv import load_dotenv

from utils.console import (
	command,
	reinstall_requirements,
	upgrade_pip
)
from utils.recursos import (
	Bot,
	get_config
)

load_dotenv()
TOKEN = os.getenv('TOKEN')

config = get_config()
bot = Bot()

if __name__ == "__main__":
	upgrade_pip()
	reinstall_requirements()
	command("clear")

	bot.run(TOKEN)