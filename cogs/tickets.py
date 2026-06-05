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


async def setup(bot: Bot):
    bot.tree.add_command(TicketsCommands())
    bot.add_view(TicketView(bot=bot))
    bot.add_view(OpenTicketView(bot=bot))
    bot.add_view(TipoPedidoView())
    bot.add_view(AprovarIntencao())
