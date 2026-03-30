import asyncio
import sys
import traceback
from typing import Optional, Callable, Awaitable

import discord
from discord.ext import commands
from discord import app_commands, ui


class ErrorManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._setup_hooks()

    def _setup_hooks(self):
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(self._handle_async_exception)
        sys.excepthook = self._handle_global_exception

    async def handle_error(
        self,
        *,
        origin: str,
        user: Optional[discord.abc.User],
        guild: Optional[discord.Guild],
        command_name: str,
        send_user_feedback: Callable[[str], Awaitable[None]],
        error: Exception
    ):
        error = self._unwrap(error)

        traceback.print_exception(type(error), error, error.__traceback__)

        try:
            await send_user_feedback(self._build_user_message(command_name, error))
        except Exception:
            pass

        try:
            await self.bot.send_to_console(
                view=self._build_log_view(origin, user, guild, command_name, error)
            )
        except Exception:
            traceback.print_exc()

    def _unwrap(self, error: Exception) -> Exception:
        if isinstance(error, app_commands.CommandInvokeError) and error.original:
            return error.original
        return error

    def _build_user_message(self, command: str, error: Exception) -> str:
        if isinstance(error, commands.MissingPermissions):
            return "Você não tem permissão pra isso."

        if isinstance(error, discord.Forbidden):
            return "Eu não tenho permissão pra fazer isso."

        if isinstance(error, app_commands.CommandOnCooldown):
            return f"⏳ Aguarde {error.retry_after:.2f}s para usar `{command}` novamente."

        return f"Ocorreu um erro ao executar `{command}`."

    def _build_log_view(self, origin, user, guild, command, error):
        view = ui.LayoutView()

        container = ui.Container(accent_color=0xFF0000)

        container.add_item(ui.TextDisplay(content="## Erro capturado"))

        info = f"> Origem: {origin}\n> Comando: `{command}`\n"

        if user:
            info += f"> Usuário: {user} ({user.id})\n"

        if guild:
            info += f"> Servidor: {guild.name} ({guild.id})\n"

        container.add_item(ui.TextDisplay(content=info))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(content="### Traceback:"))

        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        tb = tb.replace("```", "`\u200b``")

        for chunk in self._chunk(tb):
            container.add_item(ui.TextDisplay(content=f"```py\n{chunk}\n```"))

        view.add_item(container)
        return view

    def _chunk(self, text: str, size: int = 900):
        for i in range(0, len(text), size):
            yield text[i:i + size]

    def _handle_async_exception(self, loop, context):
        error = context.get("exception") or Exception(context.get("message"))

        asyncio.create_task(self.handle_error(
            origin="asyncio",
            user=None,
            guild=None,
            command_name="task",
            send_user_feedback=lambda msg: asyncio.sleep(0),
            error=error
        ))

    def _handle_global_exception(self, exc_type, exc_value, exc_traceback):
        traceback.print_exception(exc_type, exc_value, exc_traceback)

        try:
            asyncio.run(self.handle_error(
                origin="global",
                user=None,
                guild=None,
                command_name="startup",
                send_user_feedback=lambda msg: asyncio.sleep(0),
                error=exc_value
            ))
        except RuntimeError:
            pass

    def wrap(self, func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await self.handle_error(
                    origin=func.__name__,
                    user=None,
                    guild=None,
                    command_name="internal",
                    send_user_feedback=lambda msg: asyncio.sleep(0),
                    error=e
                )
        return wrapper

def setup_error_manager(bot: commands.Bot) -> ErrorManager:
    manager = ErrorManager(bot)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
        async def responder(msg):
            embed = discord.Embed(title="Erro", description=msg, color=0xFF0000)

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

        await manager.handle_error(
            origin="slash",
            user=interaction.user,
            guild=interaction.guild,
            command_name=interaction.command.name if interaction.command else "unknown",
            send_user_feedback=responder,
            error=error
        )

    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception):
        await manager.handle_error(
            origin="prefix",
            user=ctx.author,
            guild=ctx.guild,
            command_name=ctx.command.qualified_name if ctx.command else "unknown",
            send_user_feedback=lambda msg: ctx.send(msg),
            error=error
        )

    @bot.event
    async def on_error(event, *args, **kwargs):
        error = sys.exc_info()[1]

        await manager.handle_error(
            origin=event,
            user=None,
            guild=None,
            command_name="evento",
            send_user_feedback=lambda msg: asyncio.sleep(0),
            error=error
        )

    return manager
