import discord
import json
import io
import os
import subprocess
import sys

from discord import app_commands
from discord.ext import commands
from discord import ui

from utils.data import get_config, save_config
from utils.recursos import Bot

guild_ids = [get_config()["config"]["servidores"]["main"]]

class EscolherChave(ui.View):
	def __init__(self, tipo: str):
		super().__init__(timeout=None)
		self.tipo = tipo

		match tipo:
			case "canais":
				config = get_config()["canais"]

				self.select = ui.Select(
					custom_id="selecao",
					placeholder="Chave a ser configurada",
					options=[
						discord.SelectOption(
							label=chave.capitalize(),
							value=chave,
							description=f"Valor atual: {valor}"
						)
						for chave, valor in config.items()
					]
				)

				self.select_value = ui.ChannelSelect(
					custom_id="selecao_canais",
					channel_types=[discord.ChannelType.text],
					placeholder="Canal a ser selecionado"
				)

			case "cargos":
				config = get_config()["cargos"]["config"]

				self.select = ui.Select(
					custom_id="selecao",
					placeholder="Chave a ser configurada",
					options=[
						discord.SelectOption(
							label=chave.capitalize(),
							value=chave,
							description=f"Valor atual: {valor}"
						)
						for chave, valor in config.items()
					]
				)

				self.select_value = ui.RoleSelect(
					custom_id="selecao_cargos",
					placeholder="Cargo a ser selecionado"
				)

		save_button = ui.Button(
			label="Salvar mudança",
			style=discord.ButtonStyle.green,
			custom_id="save"
		)
		save_button.callback = self.callback

		self.add_item(self.select)
		self.add_item(self.select_value)
		self.add_item(save_button)
	
	async def callback(self, interaction: discord.Interaction):
		chave = self.select.values[0]
		valor = self.select_value.values[0]

		config = get_config()
		if self.tipo == "cargos":
			config["cargos"]["config"][chave] = valor
		else:
			config["canais"][chave] = valor
		
		for i in self.children:
			if isinstance(i, ui.Select) or isinstance(i, ui.RoleSelect) or isinstance(i, ui.ChannelSelect) or isinstance(i, ui.Button):
				i.disabled = True
		
		save_config(config)
		
		await interaction.response.edit_message(view=self)

class ConfigCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	config_gp = app_commands.Group(name="config", description="Comandos de configuração do bot")

	@config_gp.command(name="change", description="Muda a configuração de um canal específico.")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.describe(
		chave="Chave do canal a ser atualizado."
	)
	@app_commands.choices(
		chave=[
			app_commands.Choice(name=k.capitalize(), value=k) for k in ["canais", "cargos"]
		]
	)
	async def set_config(self, interaction: discord.Interaction, chave: str):
		await interaction.response.send_message(view=EscolherChave(chave), ephemeral=True)
	
	@app_commands.command(name="reload", description="Recarrega o bot.")
	@commands.is_owner()
	async def reload_bot(self, interaction: discord.Interaction):

		embed = discord.Embed(
			title="Bot Recarregado",
			description="O bot foi recarregados com sucesso.",
			color=0x00FF00
		)

		await interaction.response.send_message(embed=embed, ephemeral=True)
		
		python = sys.executable
		script = os.path.abspath(r"C:\Users\lcunh\Desktop\Projetos\Discord\bots\outros\Sacra Communitas\bot.py")
		subprocess.Popen([python, script])
		os._exit(0)
	
	@app_commands.command(name="reload_cmd", description="Recarrega os comandos do bot.")
	@app_commands.checks.has_permissions(administrator=True)
	async def reload_commands(self, interaction: discord.Interaction):
		embed = discord.Embed(
			title="Comandos Recarregados",
			description="Os comandos do bot foram recarregados com sucesso.",
			color=0x00FF00
		)

		await interaction.response.send_message(embed=embed, ephemeral=True)
		await self.bot.load_cogs()
	
	@config_gp.command(name="download", description="Baixar arquivos de configuração do bot (Somente ao dono do bot).")
	@commands.is_owner()
	async def download_config(self, interaction: discord.Interaction):
		config = get_config()
		json_str = json.dumps(config, indent=4, ensure_ascii=False)
		file = discord.File(
			fp=io.StringIO(json_str),
			filename="config.json"
		)
		await interaction.response.send_message("Aqui está o arquivo de configuração:", file=file, ephemeral=True)

	@config_gp.command(name="download_members")
	async def download_members(self, interaction: discord.Interaction):
		from utils.data import get_members

		config = get_members()
		json_str = json.dumps(config, indent=4, ensure_ascii=False)
		file = discord.File(
			fp=io.StringIO(json_str),
			filename="config.json"
		)
		await interaction.response.send_message("Aqui está o arquivo de membros:", file=file, ephemeral=True)

	@config_gp.command(name="server", description="Define o tipo de servidor.")
	@commands.is_owner()
	@app_commands.choices(
		tipo=[
			app_commands.Choice(name="Principal", value="main"),
			app_commands.Choice(name="Apelação", value="apel")
		]
	)
	async def set_server(self, interaction: discord.Interaction, tipo: str):
		config = self.bot.config
		config["config"] = config.get("config", {})
		config["config"]["servidores"] = config["config"].get("servidores", {})
		config["config"]["servidores"][tipo] = interaction.guild_id
		save_config(config)
		await interaction.response.send_message("Servidor configurado com sucesso! Recomenda-se reiniciar o bot.", ephemeral=True)

async def setup(bot: Bot):
	await bot.add_cog(ConfigCog(bot))
	bot.add_view(EscolherChave("canais"))
	bot.add_view(EscolherChave("cargos"))