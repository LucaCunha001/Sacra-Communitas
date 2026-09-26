import discord
from discord import app_commands

from utils.recursos import Bot
from cogs._helpers.ticket_views import (
	AprovarIntencao,
	OpenTicketView,
	TicketView,
	TipoPedidoView,
	TicketsCommands,
)


async def setup(bot: Bot) -> None:
	tickets_commands = TicketsCommands()
	try:
		bot.tree.add_command(tickets_commands)
	except Exception:
		bot.tree.remove_command("ticket")
		bot.tree.add_command(tickets_commands)

	for channel in bot.get_ticket_channels():
		bot.add_view(TicketView(bot=bot, user=bot.get_user(int(channel.topic))))

	bot.add_view(OpenTicketView(bot=bot))
	bot.add_view(TipoPedidoView())
	bot.add_view(AprovarIntencao())
