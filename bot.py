import discord
import os
import traceback

from discord import app_commands, ui

from utils.console import (
	command,
	reinstall_requirements,
	upgrade_pip
)
from utils.recursos import (
	Bot,
	get_config
)
from utils.permissoes import FaltaPermissaoSacerdotal

config = get_config()
bot = Bot()

def get_command_name(interaction: discord.Interaction) -> str:
	parts = []

	parent = getattr(interaction.command, "parent", None)
	if parent:
		parts.append(parent.name)

	parts.append(getattr(interaction.command, "name", "desconhecido"))

	if hasattr(interaction.command, "parameters"):
		for p in interaction.command.parameters:
			value = getattr(interaction.namespace, p.name, None)

			if p.required:
				parts.append(f"({p.name}={value})")
			else:
				parts.append(f"[{p.name}={value} {{default={p.default}}}]")

	return " ".join(parts)


def unwrap_app_command_error(error: Exception) -> Exception:
	if isinstance(error, app_commands.CommandInvokeError) and error.original:
		return error.original
	return error


def walk_exception_tree(err: Exception, seen=None):
	if seen is None:
		seen = set()

	if err in seen:
		return

	seen.add(err)
	yield err

	if err.__cause__:
		yield from walk_exception_tree(err.__cause__, seen)

	if err.__context__ and not err.__suppress_context__:
		yield from walk_exception_tree(err.__context__, seen)

def user_error_message(
	interaction: discord.Interaction,
	error: app_commands.AppCommandError
) -> str:
	cmd = get_command_name(interaction)
	error = unwrap_app_command_error(error)

	if isinstance(error, FaltaPermissaoSacerdotal):
		return (
			f"{error.role.name} não possui autoridade para executar "
			f"o comando `{cmd}`: {error.permissao.replace('_', ' ')}."
		)

	if isinstance(error, app_commands.MissingPermissions):
		perms = ", ".join(error.missing_permissions).replace("_", " ")
		return f"Você não tem permissão para executar `{cmd}`: {perms}."

	if isinstance(error, app_commands.BotMissingPermissions):
		perms = ", ".join(error.missing_permissions).replace("_", " ")
		return f"Eu não tenho permissão para executar `{cmd}`: {perms}."

	if isinstance(error, app_commands.CommandOnCooldown):
		return f"⏳ Aguarde {error.retry_after:.2f}s para usar `{cmd}` novamente."

	return f"Ocorreu um erro ao executar o comando `{cmd}`."

PROJECT_ROOT = os.getcwd().replace("\\", "/")

def format_full_traceback(error: Exception) -> str:
	error = unwrap_app_command_error(error)

	lines = traceback.format_exception(
		type(error),
		error,
		error.__traceback__
	)

	text = "".join(lines)

	return text.replace("```", "`\u200b``")

def chunk_text(text: str, size: int = 900):
	for i in range(0, len(text), size):
		yield text[i:i + size]

def build_log_view(
	interaction: discord.Interaction,
	error: Exception
) -> ui.LayoutView:
	error = unwrap_app_command_error(error)

	view = ui.LayoutView()

	container = ui.Container(
		accent_color=0xff0000
	)

	container.add_item(
		ui.TextDisplay(content="## Erro em App Command")
	)

	texto = (
		f"> ### Comando: `{get_command_name(interaction)}`\n"
		f"> ### Usuário: {interaction.user} ({interaction.user.id})\n"
	)

	if interaction.guild:
		texto += f"> ### Servidor: {interaction.guild.name} ({interaction.guild.id})\n"

	container.add_item(
		ui.TextDisplay(
			content=texto
		)
	)

	error_text = format_full_traceback(error)

	container.add_item(
		ui.Separator(spacing=discord.SeparatorSpacing.large)
	)

	container.add_item(
		ui.TextDisplay(content="### Traceback completo:")
	)

	for chunk in chunk_text(error_text):
		container.add_item(
			ui.TextDisplay(
				content=f"```py\n{chunk}\n```"
			)
		)

	view.add_item(container)
	return view

@bot.tree.error
async def on_app_command_error(
	interaction: discord.Interaction,
	error: app_commands.AppCommandError
):
	error = unwrap_app_command_error(error)

	traceback.print_exception(
		type(error),
		error,
		error.__traceback__
	)

	user_embed = discord.Embed(
		title="Erro ao executar comando",
		description=user_error_message(interaction, error),
		color=0xFF0000
	)

	if interaction.response.is_done():
		await interaction.followup.send(embed=user_embed, ephemeral=True)
	else:
		await interaction.response.send_message(embed=user_embed, ephemeral=True)

	await bot.send_to_console(view=build_log_view(interaction, error))

if __name__ == "__main__":
	upgrade_pip()
	reinstall_requirements()
	command("clear")
	bot.run(config['TOKEN'])