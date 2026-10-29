from code import interact
import datetime
import discord
import json
import random

from discord import app_commands
from discord import ui
from discord.ext import commands

from typing import Callable

from utils.data import DataFiles, CanonesDict, get_config
from utils.recursos import Bot, contar, expand_bible_verse
from utils.permissoes import permissao

class RecusarSolicitacaoModal(ui.Modal, title="Recusar Solicitação de Sacerdócio"):
	motivo = ui.TextInput(
		label="Motivo da recusa",
		style=discord.TextStyle.paragraph,
		placeholder="Explique o motivo da recusa da solicitação.",
		required=True,
		max_length=500,
	)

	def __init__(
		self, bot: Bot, usuario: discord.Member, disable_all: Callable[..., None]
	):
		super().__init__()
		self.bot = bot
		self.usuario = usuario
		self.disable_all = disable_all

	async def on_submit(self, interaction: discord.Interaction):
		motivo = self.motivo.value.strip()
		motivo_txt = f"**Motivo da recusa:** {motivo}" if motivo else ""

		mensagem = (
			"Sua solicitação para ingressar no sacerdócio foi analisada pelo Conclave e, "
			"neste momento, **não pôde ser aprovada**.\n\n"
			f"{motivo_txt}\n\n"
			"Você continua sendo bem-vindo à comunidade e poderá solicitar novamente no futuro."
		)

		try:
			await self.usuario.send(mensagem)
		except discord.Forbidden:
			pass

		await interaction.response.send_message(
			f"A solicitação de {self.usuario.mention} foi recusada com sucesso.",
			ephemeral=True,
		)

		await self.disable_all()

		await self.usuario.remove_roles(
			interaction.guild.get_role(
				self.bot.config["cargos"]["membros"]["Noviço"]["id"]
			)
		)


class SolicitacaoSacerdocioView(ui.View):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.bot = bot

	async def extract_info(self, interaction: discord.Interaction):
		embed = interaction.message.embeds[0]
		usuario = (
			embed.fields[0]
			.value.replace("<@", "")
			.replace(">", "")
			.replace("!", "")
			.split(" ")[0]
		)
		usuario = interaction.guild.get_member(int(usuario))
		return usuario

	async def disable_all_buttons(self, interaction: discord.Interaction):
		for item in self.children:
			if isinstance(item, ui.Button):
				item.disabled = True

		if interaction.response.is_done():
			return await interaction.message.edit(view=self)
		await interaction.response.edit_message(view=self)

	@ui.button(
		label="Recusar Solicitação",
		style=discord.ButtonStyle.danger,
		custom_id="recusar_solicitacao_sacerdocio",
		emoji="❌",
	)
	async def recusar_solicitacao_button(
		self, interaction: discord.Interaction, button: ui.Button
	):
		usuario = await self.extract_info(interaction)
		if usuario is not None:
			if any(
				interaction.guild.get_role(r.get("id")) in usuario.roles
				for r in self.bot.config["cargos"]["sacerdotes"].values()
			):
				await self.disable_all_buttons(interaction)
				return await interaction.followup.send(
					"Este usuário já é um sacerdote e não pode ter sua solicitação recusada.",
					ephemeral=True,
				)

			if not any(
				r.id == self.bot.config["cargos"]["membros"]["Noviço"]["id"]
				for r in usuario.roles
			):
				await self.disable_all_buttons(interaction)
				return await interaction.followup.send(
					"Este usuário não é um noviço e não pode ter sua solicitação recusada.",
					ephemeral=True,
				)

			async def func_da():
				await self.disable_all_buttons(interaction)

			return await interaction.response.send_modal(
				RecusarSolicitacaoModal(
					bot=self.bot, usuario=usuario, disable_all=func_da
				)
			)

		await self.disable_all_buttons(interaction)

		return await interaction.followup.send(
			"Não foi possível encontrar o usuário da solicitação.", ephemeral=True
		)


async def enviar_link_formulario(
	bot: Bot, interaction: discord.Interaction, tipo: str
):
	view = ui.View()
	view.add_item(
		ui.Button(
			label="Abrir formulário",
			style=discord.ButtonStyle.link,
			url=bot.config["forms"][tipo],
			emoji="📩",
		)
	)
	await interaction.response.send_message(
		"Acesse o formulário pelo botão abaixo.", view=view, ephemeral=True
	)


async def enviar_solicitacao(bot: Bot, interaction: discord.Interaction):
	if not any(
		r == role.id
		for role in interaction.user.roles
		for r in [1429972827209207878, 1429973276041412658]
	):
		return await interaction.response.send_message(
			"Precisa ser católico para se tornar um sacerdote!", ephemeral=True
		)

	cargos_sacedotes = bot.config.get("cargos").get("sacerdotes", {})

	if any(
		r.id == bot.config["cargos"]["membros"]["Noviço"]["id"]
		for r in interaction.user.roles
	):
		await interaction.response.send_message(
			"Você já fez a sua solicitação e não pode enviar outra.", ephemeral=True
		)
		return

	if any(
		cargo_dict["id"] in [role.id for role in interaction.user.roles]
		for cargo_dict in cargos_sacedotes.values()
	):
		await interaction.response.send_message(
			"Você já é um sacerdote e não pode enviar outra solicitação.",
			ephemeral=True,
		)
		return

	return await enviar_link_formulario(bot, interaction, "sacerdocio")


class ModalRegras(discord.ui.Modal):
	def __init__(self, i: int):
		super().__init__(
			title="Mudar regra do servidor", timeout=None, custom_id="regras_servidor"
		)
		self.regras = CanonesCog.get_regras()
		self.i = i

		self.add_item(
			discord.ui.TextInput(
				label=f"Regra {contar(i+1)}",
				style=discord.TextStyle.long,
				custom_id=str(i),
				id=i,
				default=self.regras[i] if len(self.regras) > i else None,
				required=True,
				placeholder=f"Regra de número {i+1}",
			)
		)

	async def on_submit(self, interaction: discord.Interaction):
		for item in self.children:
			item: discord.ui.TextInput
			self.regras[item.id] = item.value

		with open(DataFiles.CANONES.value, "r", encoding="utf-8") as f:
			canones = json.load(f)
		canones["Regras"] = self.regras
		with open(DataFiles.CANONES.value, "w", encoding="utf-8") as f:
			json.dump(canones, f, indent=4, ensure_ascii=False)

		await interaction.response.send_message(
			"Regras atualizadas com sucesso!", ephemeral=True
		)


class CanonesCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot

	@staticmethod
	def get_regras() -> list[str]:
		with open(DataFiles.CANONES.value, "r", encoding="utf-8") as f:
			canones = json.load(f)["Regras"]
		return canones

	regras_gp = app_commands.Group(
		name="regras", description="Comandos relacionados as regras do servidor."
	)

	@regras_gp.command(name="listar", description="Mostra as regras do servidor")
	async def regras(self, interaction: discord.Interaction):
		view = self.gerar_regras_view(interaction.guild)

		await interaction.response.send_message(view=view, ephemeral=True)

	@regras_gp.command(name="atualizar", description="Atualiza as regras do servidor")
	@app_commands.checks.has_permissions(administrator=True)
	async def regras_update(self, interaction: discord.Interaction):
		view = self.gerar_regras_view(interaction.guild)

		canal_regras = self.bot.get_channel(self.bot.config["canais"]["regras"])

		msg_regras = await canal_regras.fetch_message(1431339631802056866)
		await msg_regras.edit(view=view)

		await interaction.response.send_message(
			"Regras enviadas com sucesso!", ephemeral=True
		)

	def gerar_regras_view(self, guild: discord.Guild) -> ui.LayoutView:
		regras = self.get_regras()

		view = ui.LayoutView()

		regras_txt = "\n".join(
			f"**{contar(i)}.** {regra}"
			for i, regra in enumerate(regras, start=1)
		)

		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"# Decálogo da {guild.name}"),
				accessory=ui.Thumbnail(
					media=self.bot.guild_icon
				)
			),

			ui.TextDisplay(regras_txt),

			ui.TextDisplay(
				f"*{guild.name} • Decálogo*"
			),

			accent_color=0xFFCC00,
		)

		view.add_item(container)

		return view

	@regras_gp.command(name="definir", description="Defina uma das regras")
	@app_commands.choices(
		numero=[
			app_commands.Choice(name=str(contar(i + 1)), value=i) for i in range(10)
		]
	)
	@app_commands.describe(numero="A posição com a qual a regra situará.")
	@app_commands.checks.has_permissions(administrator=True)
	async def definir(self, interaction: discord.Interaction, numero: int):
		await interaction.response.send_modal(ModalRegras(i=numero))

	def get_canones(self) -> list[CanonesDict]:
		with open(DataFiles.CANONES.value, "r", encoding="utf-8") as f:
			canones = json.load(f)["Cânones"]
		return canones

	canone_gp = app_commands.Group(
		name="canone", description="Comandos relacionados aos cânones da comunidade."
	)

	@canone_gp.command(
		name="setup", description="Envia os cânones dos seus respecitvos canais."
	)
	@app_commands.checks.has_permissions(administrator=True)
	async def setup_canone(self, interaction: discord.Interaction):
		await interaction.response.defer(thinking=True, ephemeral=True)
		canones = self.get_canones()
		contagem_artigos = 0

		embed_codigo = discord.Embed(
			title="Código Canônico",
			description="Preâmbulo: Inspirado no zelo pela ordem, pela caridade e pela comunhão com a Igreja de Cristo, o presente Código estabelece os funcionamentos sacerdotais disciplinares e as normas punitivas aplicáveis a todos os membros da comunidade, a fim de preservar a verdade, a paz e a integridade da fé católica neste espaço.\n\n## Sumário:\n",
			color=0xFFCC00,
		)
		embed_codigo.set_author(
			name=interaction.user.name,
			url=f"https://discord.com/users/{interaction.user.id}",
			icon_url=interaction.user.display_avatar.url,
		)
		embed_codigo.set_footer(
			text=f"{interaction.guild.name} - Código Canônico",
			icon_url=interaction.guild.icon.url,
		)
		embed_codigo.set_thumbnail(url=interaction.guild.icon.url)

		sumario = []

		for c, canone in enumerate(canones):
			embed = discord.Embed(
				title=f"Cânone {contar(c+1)} — {canone['titulo']}",
				description=f"{canone['conteudo']}\n\n",
				colour=0xFFCC00,
			)
			embed.set_author(
				name=interaction.user.name,
				url=f"https://discord.com/users/{interaction.user.id}",
				icon_url=interaction.user.display_avatar.url,
			)
			embed.set_footer(
				text=f"{interaction.guild.name} - Código Canônico",
				icon_url=interaction.guild.icon.url,
			)
			embed.set_thumbnail(url=interaction.guild.icon.url)

			for artigo in canone["artigos"]:

				contagem_artigos += 1
				embed.description += (
					f"**Art. {contar(contagem_artigos)}º** {artigo['texto']}\n"
				)

				for i, inciso in enumerate(artigo.get("incisos", [])):
					embed.description += f"\n**{contar(i+1)} —** {inciso}"
					embed.description += "." if len(artigo["incisos"]) - 1 == i else ";"

				for i, paragrafo in enumerate(artigo.get("paragrafos", [])):
					if i == 0 and len(artigo.get("incisos", [])) > 0:
						embed.description += "\n"

					if len(artigo["paragrafos"]) == 1:
						embed.description += f"\n**Parágrafo único.** {paragrafo}"
					else:
						embed.description += f"\n**§{contar(i+1)}.** {paragrafo}"

				embed.description += (
					"\n"
					if not any(
						len(artigo.get(j, [])) != 0 for j in ["incisos", "paragrafos"]
					)
					else "\n\n"
				)

			canal = self.bot.get_channel(canone["canal"])

			sumario.append(canal.mention)

			await canal.purge(limit=None)

			embed.timestamp = datetime.datetime.now()
			await canal.send(embed=embed)

		for item in sumario:
			embed_codigo.description += f"\n{item}"
		embed_codigo.timestamp = datetime.datetime.now()

		canal_codigo = self.bot.get_channel(self.bot.config["canais"]["codigo"])
		await canal_codigo.send(embed=embed_codigo)

		await interaction.followup.send("Cânones atualizados com sucesso!")

async def setup(bot: Bot) -> None:
	await bot.add_cog(CanonesCog(bot))
	bot.add_view(SolicitacaoSacerdocioView(bot=bot))
