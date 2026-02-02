import aiohttp
import datetime
import discord
import json
import logging
import sys
import random
import re

from discord import app_commands
from discord import ui
from discord.ext import commands, tasks

from typing import Callable

from utils.data import DataFiles, CanonesDict, get_config, save_config
from utils.recursos import Bot, contar, expand_bible_verse
from utils.permissoes import permissao
from utils.embed import criar_embed

from zoneinfo import ZoneInfo

logger = logging.getLogger("liturgia")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

guild_ids = [get_config()["config"]["servidores"]["main"]]

class RecusarSolicitacaoModal(ui.Modal, title="Recusar Solicitação de Sacerdócio"):
	motivo = ui.TextInput(
		label="Motivo da recusa",
		style=discord.TextStyle.paragraph,
		placeholder="Explique o motivo da recusa da solicitação.",
		required=True,
		max_length=500
	)

	def __init__(self, bot: Bot, usuario: discord.Member, disable_all: Callable[..., None]):
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
			ephemeral=True
		)
		
		await self.disable_all()

		await self.usuario.remove_roles(
			interaction.guild.get_role(self.bot.config["cargos"]["membros"]["Noviço"]["id"])
		)

class SolicitacaoSacerdocioView(ui.View):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.bot = bot
	
	async def extract_info(self, interaction: discord.Interaction):
		embed = interaction.message.embeds[0]
		usuario = embed.fields[0].value.replace("<@", "").replace(">", "").replace("!", "").split(" ")[0]
		usuario = interaction.guild.get_member(int(usuario))
		return usuario

	async def disable_all_buttons(self, interaction: discord.Interaction):
		for item in self.children:
			if isinstance(item, ui.Button):
				item.disabled = True

		if interaction.response.is_done():
			return await interaction.message.edit(view=self)
		await interaction.response.edit_message(view=self)

	@ui.button(label="Recusar Solicitação", style=discord.ButtonStyle.danger, custom_id="recusar_solicitacao_sacerdocio", emoji="❌")
	async def recusar_solicitacao_button(self, interaction: discord.Interaction, button: ui.Button):
		usuario = await self.extract_info(interaction)
		if usuario is not None:
			if any(interaction.guild.get_role(r.get("id")) in usuario.roles for r in self.bot.config["cargos"]["sacerdotes"].values()):		
				await self.disable_all_buttons(interaction)
				return await interaction.followup.send(
					"Este usuário já é um sacerdote e não pode ter sua solicitação recusada.",
					ephemeral=True
				)

			if not any(r.id == self.bot.config["cargos"]["membros"]["Noviço"]["id"] for r in usuario.roles):
				await self.disable_all_buttons(interaction)
				return await interaction.followup.send(
					"Este usuário não é um noviço e não pode ter sua solicitação recusada.",
					ephemeral=True
				)
			
			async def func_da():
				await self.disable_all_buttons(interaction)

			return await interaction.response.send_modal(
				RecusarSolicitacaoModal(bot=self.bot, usuario=usuario, disable_all=func_da)
			)

		await self.disable_all_buttons(interaction)

		return await interaction.followup.send(
			"Não foi possível encontrar o usuário da solicitação.", ephemeral=True
		)

class SolicitacaoSacerdocioModal(ui.Modal, title="Solicitação de Sacerdócio"):

	motivo = ui.TextInput(
		label="Motivo",
		style=discord.TextStyle.paragraph,
		placeholder="Explique por que você deseja se tornar um sacerdote.",
		required=True,
		max_length=500
	)

	experiencia = ui.TextInput(
		label="Experiência ou atividades relevantes",
		style=discord.TextStyle.paragraph,
		placeholder="Ex.: já moderei canais, participei de eventos...",
		required=False,
		max_length=300
	)

	pouco_sobre = ui.TextInput(
		label="Conte um pouco sobre você",
		style=discord.TextStyle.paragraph,
		placeholder="Fale um pouco sobre você para que possamos conhecê-lo melhor.",
		required=True,
		max_length=500
	)

	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot

	async def on_submit(self, interaction: discord.Interaction):
		guild = interaction.guild
		user = interaction.user

		novico_cargo = guild.get_role(self.bot.config["cargos"]["membros"]["Noviço"]["id"])
		if novico_cargo in user.roles:
			await interaction.response.send_message(
				"Você já possui o cargo de Noviço.", ephemeral=True
			)
			return

		tempo_no_servidor = discord.utils.format_dt(user.joined_at, style='R')

		embed = discord.Embed(
			title="Nova Solicitação de Sacerdócio",
			color=0xffcc00,
			timestamp=discord.utils.utcnow()
		)
		embed.set_thumbnail(url=user.display_avatar.url)
		embed.add_field(name="Usuário", value=f"{user.mention} (`{user.id}`)", inline=False)
		embed.add_field(name="Motivo:", value=self.motivo, inline=False)
		embed.add_field(name="Tempo no servidor:", value=tempo_no_servidor, inline=True)
		embed.add_field(name="Experiência:", value=self.experiencia or "Não informada", inline=True)
		embed.add_field(name="Sobre o candidato:", value=self.pouco_sobre, inline=False)
		embed.set_footer(text=f"Solicitação enviada por {user.display_name}", icon_url=user.display_avatar.url)

		canal_id = self.bot.config['canais'].get('solicitacoes_sacerdocio')
		canal = guild.get_channel(canal_id)
		if canal:
			await canal.send(embed=embed, view=SolicitacaoSacerdocioView(bot=self.bot))
			
		await user.add_roles(novico_cargo)

		await interaction.response.send_message(
			"Sua solicitação foi enviada com sucesso! Aguarde a análise do Conclave.",
			ephemeral=True
		)

async def enviar_solicitacao(bot: Bot, interaction: discord.Interaction):
	if not any(r == role.id for role in interaction.user.roles for r in [1429972827209207878, 1429973276041412658]):
		return await interaction.response.send_message("Precisa ser católico para se tornar um sacerdote!", ephemeral=True)
	
	canal_id = bot.config['canais'].get('solicitacoes_sacerdocio')
	canal = bot.get_channel(canal_id)

	cargos_sacedotes = bot.config.get('cargos').get('sacerdotes', {})

	if any(r.id == bot.config["cargos"]["membros"]["Noviço"]["id"] for r in interaction.user.roles):
		await interaction.response.send_message("Você já fez a sua solicitação e não pode enviar outra.", ephemeral=True)
		return

	if any(cargo_dict['id'] in [role.id for role in interaction.user.roles] for cargo_dict in cargos_sacedotes.values()):
		await interaction.response.send_message("Você já é um sacerdote e não pode enviar outra solicitação.", ephemeral=True)
		return
	
	async for msg in canal.history(limit=None, oldest_first=False):
		if not msg.embeds:
			continue
		embed = msg.embeds[0]
		if embed.fields and embed.fields[0].value.startswith(interaction.user.mention):
			if msg.created_at < datetime.datetime.now() - datetime.timedelta(days=7):
				return await interaction.response.send_message(
					f"Você já enviou uma solicitação há menos de uma semana e não pode enviar outra { discord.utils.format_dt(msg.created_at + datetime.timedelta(days=7), "R") }.", ephemeral=True
				)
	
	modal = SolicitacaoSacerdocioModal(bot=bot)
	await interaction.response.send_modal(modal)

class SacerdocioNovicoView(ui.View):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.bot = bot
	
	@ui.button(label="Enviar Solicitação", style=discord.ButtonStyle.primary, custom_id="enviar_solicitacao_sacerdocio", emoji="✉️")
	async def enviar_solicitacao_button(self, interaction: discord.Interaction, button: ui.Button):
		await enviar_solicitacao(self.bot, interaction)

class SacerdocioCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot
	
	sacerdocio_group = app_commands.Group(name="sacerdocio", description="Comandos relacionados aos sacerdócios")
	
	@sacerdocio_group.command(name="info", description="Obter informações sobre o sacedócio.")
	async def info(self, interaction: discord.Interaction):
		config = self.bot.config
		cargos_sacedotes = config.get('cargos').get('sacerdotes', {})

		embed = discord.Embed(
			title="Informações do Sacerdócio",
			description="Aqui estão as informações sobre os sacerdócios disponíveis:\n",
			color=0xffcc00
		)
		embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Emblem_of_the_Papacy_SE.svg/250px-Emblem_of_the_Papacy_SE.svg.png")

		for nome, cargo_dict in cargos_sacedotes.items():
			cargo = interaction.guild.get_role(cargo_dict['id'])
			embed.description += f"# **{nome.capitalize()} - {len(cargo.members)}**:\n{cargo.mention} -  {cargo_dict['descricao']}\n\n"
		
		embed.description += "Para enviar uma solicitação para se tornar um sacerdote, use o comando </sacerdocio enviar_solicitacao:1429191602269589596>."

		await interaction.response.send_message(embed=embed)
	

	@sacerdocio_group.command(name="noviços", description="Mostra os noviços do servidor.")
	@permissao(designar_cargos=True)
	async def novicos(self, interaction: discord.Interaction):
		novico_cargo = interaction.guild.get_role(self.bot.config['cargos']['membros']['Noviço']['id'])
		novicos = novico_cargo.members

		if not novicos:
			return await interaction.response.send_message("Não há noviços no momento.", ephemeral=True)

		embed = discord.Embed(
			title="Noviços Atuais",
			description="Aqui estão os membros que atualmente possuem o cargo de Noviço:\n",
			color=0xffcc00
		)
		embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Emblem_of_the_Papacy_SE.svg/250px-Emblem_of_the_Papacy_SE.svg.png")

		for novico in novicos:
			embed.description += f"- {novico.mention}\n"

		await interaction.response.send_message(embed=embed)

	@sacerdocio_group.command(name="solicitacao_msg", description="Envia a mensagem de solicitação de sacerdócio no canal designado.")
	@permissao(gerenciar_comunidade=True)
	async def solicitacao_msg(self, interaction: discord.Interaction):
		canal_id = self.bot.config['canais'].get('solicitacoes_sacerdocio_pub')
		canal: discord.TextChannel = interaction.guild.get_channel(canal_id)
		
		if not canal:
			return await interaction.response.send_message("Canal de solicitações de sacerdócio não encontrado.", ephemeral=True)
		
		await canal.purge(limit=None)

		embed = criar_embed(
			titulo="Torne-se um sacerdote do Sacra Communitas",
			descricao=(
				"Gostaria de servir nossa comunidade em um papel mais profundo e significativo? "
				"Estamos aceitando solicitações para novos sacerdotes que desejam se juntar ao nosso clero dedicado.\n\n"
				"Como sacerdote, você terá a oportunidade de ajudar a cuidar do servidor e de seus membros, "
				"promovendo um ambiente mais acolhedor e seguro para todos da comunidade.\n\n"
				"Ao fazer a sua solicitação, você se compromete a manter uma conduta exemplar, "
				"respeitando as diretrizes e valores da comunidade.\n\n"
				"Ao enviar sua solicitação, ganhará automaticamente o cargo de Noviço, iniciando sua jornada rumo ao sacerdócio.Depois, basta aguardar a análise do Papa, Cardeais e Bispos.\n\n"
				"Clique no botão abaixo para enviar sua solicitação e dar o primeiro passo em direção a essa nobre vocação!"
			),
			cor=0xffcc00,
			footer="Noviços",
			servidor=interaction.guild,
			author=interaction.guild.owner
		)

		await canal.send(embed=embed, view=SacerdocioNovicoView(bot=self.bot))
		await interaction.response.send_message("Mensagem de solicitação enviada com sucesso!", ephemeral=True)

	@sacerdocio_group.command(name="enviar_solicitacao", description="Enviar uma solicitação para se tornar um sacerdote.")
	async def enviar_solicitacao_cmd(self, interaction: discord.Interaction):
		await enviar_solicitacao(self.bot, interaction)
	
	@app_commands.command(name="anjos", description="Obter informações sobre os anjos.")
	async def anjos(self, interaction: discord.Interaction):
		embed = discord.Embed(
			title="Anjos da Sacra Communitas",
			description=(
				"Os Anjos são membros especiais que auxiliam na moderação e organização do servidor. "
				"Eles possuem responsabilidades como:\n"
				"- Ajudar novos membros\n"
				"- Monitorar o chat\n"
				"- Proteger a comunidade\n"
				"- Prestar assistência necessária aos sacerdotes\n\n"
			),
			color=0xffcc00
		)

		ordens = [
			[],
			["Serafim", "Querubim", "Trono"],
			["Dominação", "Virtude", "Potestade"],
			["Principado", "Arcanjo", "Anjo da Guarda"]
		]

		ultima_triade = 0

		anjos_config = self.bot.config.get('cargos', {}).get('anjos', {})
		for nome, cargo_dict in list(anjos_config.items())[::-1]:
			triade_idx = next((idx for idx, triade in enumerate(ordens) if nome in triade), None)
			
			if triade_idx is not None and triade_idx != ultima_triade:
				ultima_triade = triade_idx
				embed.description += f"# Tríade {ultima_triade}\n"

			cargo = interaction.guild.get_role(cargo_dict['id'])
			if not cargo:
				continue
			
			embed.description += f"\n## **{nome.capitalize()} - {len(cargo.members)}**:\n"
			embed.description += f"{cargo.mention} - {cargo_dict.get('descricao', '')}\n"

			for bot in cargo.members:
				embed.description += f"- {bot.mention}\n"

		await interaction.response.send_message(embed=embed)
	
	def nivel_sacerdote(self, sacerdote: discord.Member) -> discord.Role | None:
		cargos = self.bot.config["cargos"]["sacerdotes"]
		cargos_sacerdote = [
			role for role in sacerdote.roles
			if any(r_dict['id'] == role.id for _, r_dict in cargos.items())
		]
		return max(cargos_sacerdote, key=lambda r: r, default=None)

	async def update_sacerdote(
		self,
		interaction: discord.Interaction,
		ordinante: discord.Member,
		sacerdote: discord.Member,
		tipo: int,
		funcao: discord.Role = None,
		motivo: str | None = None
	):
		if sacerdote.bot:
			return await interaction.response.send_message("Eu não sei o que te fez pensar que poderia mexer nas permissões de um ser angelical.", ephemeral=True)

		if tipo not in range(4):
			return await interaction.response.send_message(
				"Tipo de ação inválido.", ephemeral=True
			)

		guild = interaction.guild
		config = self.bot.config
		leigo_cargo = guild.get_role(config["cargos"]["membros"]["Leigo"]["id"])
		novico_cargo = guild.get_role(config["cargos"]["membros"]["Noviço"]["id"])
		bispo_role = guild.get_role(config["cargos"]["sacerdotes"]["Bispo"]["id"])
		clearo_cargo = guild.get_role(config["cargos"]["sacerdotes"]["Clero"]["id"])

		cargos_sacerdotais = [
			guild.get_role(cargo_dict["id"])
			for _, cargo_dict in config["cargos"]["sacerdotes"].items()
		]

		cargo_maximo_atual = self.nivel_sacerdote(sacerdote)
		motivo_txt = f"\n**Motivo:** {motivo}" if motivo else ""

		if tipo == 0:
			if any(r in sacerdote.roles for r in cargos_sacerdotais):
				return await interaction.response.send_message(
					f"{sacerdote.mention} já faz parte do clero e não pode ser nomeado novamente.",
					ephemeral=True
				)
			if not any(novico_cargo.id == r.id for r in sacerdote.roles):
				return await interaction.response.send_message(
					f"{sacerdote.mention} ainda não é um noviço para ser nomeado.",
					ephemeral=True
				)

		if tipo == 1 and not any(r in sacerdote.roles for r in cargos_sacerdotais):
			return await interaction.response.send_message(
				f"{sacerdote.mention} ainda não é sacerdote. Use `/sacerdocio nomear` primeiro.",
				ephemeral=True
			)

		if tipo == 2:
			if not cargo_maximo_atual:
				return await interaction.response.send_message(
					f"{sacerdote.mention} não possui cargo sacerdotal para ser rebaixado.",
					ephemeral=True
				)
			if funcao and funcao >= cargo_maximo_atual:
				return await interaction.response.send_message(
					"O novo cargo deve ser **inferior** ao atual.",
					ephemeral=True
				)

		if tipo == 3 and not any(r in sacerdote.roles for r in cargos_sacerdotais):
			return await interaction.response.send_message(
				f"{sacerdote.mention} não é sacerdote, portanto não pode ser dispensado.",
				ephemeral=True
			)
		
		citacoes = [
			# Ingressão
			[
				"1Tm 3,13",
				"Ap 21,5",
				"1Sm 16,7",
				"Sb 6,1-3",
				"Cl 3,23",
				"Pr 22,29"
			],
			# Promoção
			[
				"Lc 12:48",
				"1Pd 5,2-3",
				"Mt 25:21",
				"Sb 6,20-21",
				"Rm 12,8",
				"2Tm 2,15"
			],
			# Rebaixamento
			[
				"Hb 12,6",
				"Sl 51,10",
				"Pr 3,11-12",
				"Lm 3,31-33",
				"Mq 6,8",
				"Sl 119,71"
			],
			# Remoção
			[
				"Pr 24,16",
				"2Cor 12,9",
				"Jó 1,21",
				"Ecl 3,1",
				"Sl 34,19",
				"Is 55,8-9"
			]
		]
		versiculo = random.choice(citacoes[tipo])
		await self.bot.send_to_console(f"[Debug] {versiculo}")
		res = expand_bible_verse(versiculo)[0]
		separador = ":" if res["tipo"] == "Evangelhos" else ","
		cargo_color = funcao.color if funcao is not None else discord.Color.default()

		texto = "\n".join(t.strip() for t in res["texto"])

		passagem_txt = res['versículo_inicial'] if res['versículo_final'] == res['versículo_inicial'] else f"{res['versículo_inicial']}-{res['versículo_final']}"

		citacao = f"_\u201C{texto}\u201D_ ({res['livro']} {res['capítulo']}{separador}{passagem_txt})"

		match tipo:
			case 0:
				titulo = "Anunciação Sacra"
				message = (
					f"Com júbilo e gratidão, a comunidade anuncia a elevação de {sacerdote.mention} à digna função de {funcao.mention}.\n\n"
					"Que o Espírito Santo o conduza com sabedoria, prudência e zelo pastoral, para servir fielmente à comunidade e à Santa Igreja.\n\n"
					f"{citacao}\n\n"
					"Bendizemos este novo passo em seu ministério, confiando-o à graça de Deus."
				)
				await sacerdote.remove_roles(leigo_cargo)
				await sacerdote.remove_roles(novico_cargo)
			
			case 1:
				titulo = "Proclamação Celeste"
				message = (
					f"Hoje, a Sacra Communitas reconhece a fidelidade e o zelo de {sacerdote.mention}, que é promovido a {funcao.mention}.\n\n"
					"Que esta nova missão seja vivida com discernimento, firmeza e caridade, para maior glória de Deus e edificação da comunidade.\n\n"
					f"{citacao}\n\n"
					"Rendamos graças por este servo dedicado."
				)
				if cargo_maximo_atual and cargo_maximo_atual < bispo_role:
					await sacerdote.remove_roles(cargo_maximo_atual, reason="Promoção")

			case 2:
				titulo = "Aviso do Conselho"
				message = (
					f"Após discernimento do Conclave e em espírito de correção fraterna, {sacerdote.mention} passa a exercer a função de {funcao.mention}.{motivo_txt}\n\n"
					"Que este tempo seja ocasião de humildade, conversão interior e amadurecimento espiritual.\n\n"
					f"{citacao}\n\n"
					"Rezemos para que retome, com renovado ardor, o caminho do serviço fiel."
				)
				if cargo_maximo_atual:
					await sacerdote.remove_roles(cargo_maximo_atual, reason="Rebaixamento")

			case 3:
				titulo = "Decreto de Retiro"
				message = (
					f"Por decisão do Conclave e em conformidade com as diretrizes da Sacra Communitas, {sacerdote.mention} é removido de suas funções sacerdotais.{motivo_txt}\n\n"
					"Que o Senhor lhe conceda paz, discernimento e retidão neste novo caminho.\n\n"
					f"{citacao}\n\n"
					"Confiamos este momento à misericórdia divina."
				)
				for _, cargo_dict in self.bot.config["cargos"]["sacerdotes"].items():
					for r in sacerdote.roles:
						if r.id == cargo_dict['id']:
							await sacerdote.remove_roles(r)
				await sacerdote.add_roles(leigo_cargo)
				cargo_color = leigo_cargo.color

		if funcao and tipo != 3:
			await sacerdote.add_roles(clearo_cargo)
			await sacerdote.add_roles(funcao)

		await interaction.response.send_message("Cargo alterado com sucesso!", ephemeral=True)

		view = ui.LayoutView()
		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"## {titulo}"),
				accessory=ui.Thumbnail(sacerdote.display_avatar.url)
			),
			accent_color=cargo_color
		)
		container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
		container.add_item(
			ui.TextDisplay(message)
		)
		container.add_item(
			ui.TextDisplay(f"**Mudança realizada por:**\n{ordinante.mention}")
		)
		container.add_item(
			ui.TextDisplay("-# Sacra Communitas • Conclave")
		)
		view.add_item(container)

		canal = self.bot.get_channel(self.bot.config["canais"]["nomeacoes"])
		if canal:
			await canal.send(view=view)

	@sacerdocio_group.command(
		name="nomear",
		description="Nomeia um noviço à função sacerdotal."
	)
	@permissao(designar_cargos=True)
	@app_commands.describe(
		sacerdote="O membro que será nomeado noviço"
	)
	async def nomear(self, interaction: discord.Interaction, sacerdote: discord.Member):
		cargo = interaction.guild.get_role(int(self.bot.config["cargos"]["sacerdotes"]["Seminarista"]["id"]))
		await self.update_sacerdote(
			interaction=interaction,
			ordinante=interaction.user,
			sacerdote=sacerdote,
			tipo=0,
			funcao=cargo
		)


	@sacerdocio_group.command(
		name="ordenar",
		description="Ordena um sacerdote a um cargo maior."
	)
	@app_commands.choices(
		cargo=[
			app_commands.Choice(name=cargo, value=str(cargo_dict['id']))
			for cargo, cargo_dict in get_config()["cargos"]["sacerdotes"].items()
		]
	)
	@permissao(designar_cargos=True)
	@app_commands.describe(
		sacerdote="O sacerdote que será promovido",
		cargo="O cargo para o qual será promovido"
	)
	async def ordenar(self, interaction: discord.Interaction, sacerdote: discord.Member, cargo: str):
		cargo = interaction.guild.get_role(int(cargo))
		await self.update_sacerdote(
			interaction=interaction,
			ordinante=interaction.user,
			sacerdote=sacerdote,
			tipo=1,
			funcao=cargo
		)


	@sacerdocio_group.command(
		name="exonerar",
		description="Rebaixa um sacerdote a um cargo menor."
	)
	@app_commands.choices(
		cargo=[
			app_commands.Choice(name=cargo, value=str(cargo_dict['id']))
			for cargo, cargo_dict in get_config()["cargos"]["sacerdotes"].items()
		]
	)
	@permissao(designar_cargos=True)
	@app_commands.describe(
		sacerdote="O sacerdote que será rebaixado",
		cargo="O cargo para o qual será rebaixado",
		motivo="Motivo da exoneração (opcional)"
	)
	async def exonerar(self, interaction: discord.Interaction, sacerdote: discord.Member, cargo: str, motivo: str = None):
		cargo = interaction.guild.get_role(int(cargo))
		await self.update_sacerdote(
			interaction=interaction,
			ordinante=interaction.user,
			sacerdote=sacerdote,
			tipo=2,
			funcao=cargo,
			motivo=motivo
		)


	@sacerdocio_group.command(
		name="dispensar",
		description="Dispensa um sacerdote de suas funções."
	)
	@permissao(designar_cargos=True)
	@app_commands.describe(
		sacerdote="O sacerdote que será dispensado",
		motivo="Motivo da dispensa (opcional)"
	)
	async def dispensar(self, interaction: discord.Interaction, sacerdote: discord.Member, motivo: str = None):
		await self.update_sacerdote(
			interaction=interaction,
			ordinante=interaction.user,
			sacerdote=sacerdote,
			tipo=3,
			funcao=None,
			motivo=motivo
		)

class LiturgiaCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot
		self.session = aiohttp.ClientSession()
		self.envio_liturgia.start()
	
	liturgia_gp = app_commands.Group(name="liturgia", description="Comandos relacionados a liturgia diária.")

	@liturgia_gp.command(name="calendario", description="Obter informações sobre o calendário litúrgico.")
	@app_commands.describe(
		ano="Ano para o qual calcular o calendário litúrgico (padrão: ano atual)"
	)
	async def calendario(self, interaction: discord.Interaction, ano: int = None):
		embed = discord.Embed(
			title="Cálculo do Calendário Litúrgico",
			description="Aqui estão as datas móveis do calendário litúrgico para o ano atual:\n",
			color=0xffcc00
		)
		
		calendario_dict = {
			"Tempo Comum 1": {
				"Início": (0, 0),
				"Terça-feira antes da Quarta-feira de Cinzas": (0, 0)
			},
			"Quaresma": {
				"Quarta-feira de Cinzas": (0, 0),
				"Domingo de Ramos": (0, 0)
			},
			"Tríduo Pascal": {
				"Quinta-feira Santa": (0, 0),
				"Sexta-feira Santa": (0, 0),
				"Sábado Santo": (0, 0)
			},
			"Páscoa": {
				"Domingo de Páscoa": (0, 0)
			},
			"Tempo Comum 2": {
				"Pentecostes": (0, 0),
				"Solenidade de Cristo Rei": (0, 0)
			},
			"Advento": {
				"Primeiro Domingo do Advento": (0, 0),
				"Segundo Domingo do Advento": (0, 0),
				"Terceiro Domingo do Advento": (0, 0),
				"Quarto Domingo do Advento": (0, 0),
				"Véspera de Natal": (12, 24)
			},
			"Natal": {
				"Natal": (12, 25),
				"Solenidade de Maria, Mãe de Deus": (1, 1),
				"Batismo do Senhor": (0, 0)
			}
		}

		Y = datetime.datetime.now().year if ano is None else ano
		tipos_ano = ["A", "B", "C"]
		tipo_ano = tipos_ano[(Y - 1) % 3]
		embed.title += f" - Ano {tipo_ano} ({Y})"

		def mod(x, y):
			return x % y

		a = mod(Y, 19)
		b = mod(Y, 4)
		c = mod(Y, 7)
		k = Y // 100
		p = (13 + 8*k) // 25
		q = k // 4
		m = mod(15 - p + k - q, 30)
		n = mod(4 + k - q, 7)
		d = mod(19*a + m, 30)
		e = mod(2*b + 4*c + 6*d + n, 7)

		if d == 29 and e == 6:
			pascoa = (4, 19)

		elif d == 28 and e == 6 and a > 10:
			pascoa = (4, 18)

		else:
			pascoa = (
				3 + ((d + e + 22) // 31),
				mod(d + e + 21, 31) + 1
			)
		
		calendario_dict["Páscoa"]["Domingo de Páscoa"] = pascoa
		
		pascoa_dt = datetime.datetime(year=Y, month=pascoa[0], day=pascoa[1])

		quarta_cinzas = pascoa_dt - datetime.timedelta(days=46)
		domingo_ramos = pascoa_dt - datetime.timedelta(days=7)
		quinta_santa = pascoa_dt - datetime.timedelta(days=3)
		sexta_santa = pascoa_dt - datetime.timedelta(days=2)
		sabado_santo = pascoa_dt - datetime.timedelta(days=1)
		pentecostes = pascoa_dt + datetime.timedelta(days=49)

		terca_antes_cinzas = quarta_cinzas - datetime.timedelta(days=1)

		def primeiro_domingo_do_ano(ano):
			d = datetime.date(ano, 1, 1)
			return d + datetime.timedelta(days=(6 - d.weekday()) % 7)

		inicio_tc1 = primeiro_domingo_do_ano(Y)

		def primeiro_domingo_advento(ano: int) -> datetime.date:
			natal = datetime.date(ano, 12, 25)
			ultimo_domingo = natal - datetime.timedelta(days=(natal.weekday() + 1) % 7)
			return ultimo_domingo - datetime.timedelta(days=21)

		d1 = primeiro_domingo_advento(Y)
		d2 = d1 + datetime.timedelta(days=7)
		d3 = d1 + datetime.timedelta(days=14)
		d4 = d1 + datetime.timedelta(days=21)

		epifania = datetime.date(Y, 1, 6)
		batismo_senhor = epifania + datetime.timedelta(days=(6 - epifania.weekday()) % 7)

		cristo_rei = d1 - datetime.timedelta(days=7)

		calendario_dict["Tempo Comum 1"]["Início"] = (inicio_tc1.month, inicio_tc1.day)
		calendario_dict["Tempo Comum 1"]["Terça-feira antes da Quarta-feira de Cinzas"] = (terca_antes_cinzas.month, terca_antes_cinzas.day)

		calendario_dict["Quaresma"]["Quarta-feira de Cinzas"] = (quarta_cinzas.month, quarta_cinzas.day)
		calendario_dict["Quaresma"]["Domingo de Ramos"] = (domingo_ramos.month, domingo_ramos.day)

		calendario_dict["Tríduo Pascal"]["Quinta-feira Santa"] = (quinta_santa.month, quinta_santa.day)
		calendario_dict["Tríduo Pascal"]["Sexta-feira Santa"] = (sexta_santa.month, sexta_santa.day)
		calendario_dict["Tríduo Pascal"]["Sábado Santo"] = (sabado_santo.month, sabado_santo.day)

		calendario_dict["Tempo Comum 2"]["Pentecostes"] = (pentecostes.month, pentecostes.day)
		calendario_dict["Tempo Comum 2"]["Solenidade de Cristo Rei"] = (cristo_rei.month, cristo_rei.day)

		calendario_dict["Advento"]["Primeiro Domingo do Advento"] = (d1.month, d1.day)
		calendario_dict["Advento"]["Segundo Domingo do Advento"] = (d2.month, d2.day)
		calendario_dict["Advento"]["Terceiro Domingo do Advento"] = (d3.month, d3.day)
		calendario_dict["Advento"]["Quarto Domingo do Advento"] = (d4.month, d4.day)

		calendario_dict["Natal"]["Batismo do Senhor"] = (batismo_senhor.month, batismo_senhor.day)

		for tempo, eventos in calendario_dict.items():
			embed.description += f"\n### {tempo}:\n"
			for evento, (m, d) in eventos.items():
				data = datetime.date(year=Y, month=m, day=d) if (m != 0 and d != 0) else None
				if data is not None:
					data_dt = datetime.datetime.combine(data, datetime.time.min)
					dia_semana = data.strftime('%A')

					semana_table = {
						"Sunday": "Domingo",
						"Monday": "Segunda-feira",
						"Tuesday": "Terça-feira",
						"Wednesday": "Quarta-feira",
						"Thursday": "Quinta-feira",
						"Friday": "Sexta-feira",
						"Saturday": "Sábado"
					}

					embed.description += f"- **{evento}**: {semana_table.get(dia_semana, dia_semana)}, {data.strftime('%d/%m/%Y')} ({discord.utils.format_dt(data_dt, 'D')})\n"
		
		await interaction.response.send_message(embed=embed)

	config_bp = app_commands.Group(name="config", description="Configurações das funções relacionadas a liturgia diária.", parent=liturgia_gp)

	@config_bp.command(name="hora", description="A hora do envio da liturgia.")
	@permissao(gerenciar_comunidade=True)
	@app_commands.describe(
		hora="Formato HH:MM"
	)
	async def hora_config(self, interaction: discord.Interaction, hora: str):
		if not re.fullmatch(r"\d{2}:\d{2}", hora):
			return await interaction.response.send_message(
				"O formato exigido não foi satisfeito. Use o formato **HH:MM**, por exemplo: `08:30`.",
				ephemeral=True
			)

		self.atualizar_config(hora=hora)
		await interaction.response.send_message(
			f"Horário do envio das liturgias diárias alterado para: **{hora}**"
		)
	
	@config_bp.command(name="webhook", description="Definir o webhook para enviar as liturgias diárias.")
	@app_commands.describe(
		webhook_url="Link do webhook para enviar quando a liturgia for enviada"
	)
	@permissao(gerenciar_comunidade=True)
	async def canal_config(self, interaction: discord.Interaction, webhook_url: str):
		self.atualizar_config(webhook_url=webhook_url)
		await interaction.response.send_message(f"Webhook do envio das liturgias diárias alterado para: **{webhook_url}**")

	@config_bp.command(name="ping", description="Define o cargo a ser marcado nas liturgias diárias.")
	@app_commands.describe(
		ping="Cargo para marcar quando a liturgia for enviada"
	)
	@permissao(gerenciar_comunidade=True)
	async def ping_config(self, interaction: discord.Interaction, ping: discord.Role):
		self.atualizar_config(cargo_ping=ping)
		await interaction.response.send_message(f"Cargo de marcação alterado para: **{ping.name}**")

	def atualizar_config(self, *, hora: str | None = None, webhook_url: str | None = None, cargo_ping: discord.Role | None = None):
		config = self.bot.config
		config_liturgia = config["liturgia"]
		
		if hora is not None:
			config_liturgia["hora"] = hora
		
		if webhook_url is not None:
			config["urls"]["webhooks"]["Liturgia Diária"] = webhook_url
		
		if cargo_ping is not None:
			config_liturgia["ping"] = cargo_ping.id
		
		config["liturgia"] = config_liturgia
		
		save_config(config)
	
	def cog_unload(self):
		self.envio_liturgia.cancel()
		return super().cog_unload()
	
	@tasks.loop(minutes=1)
	async def envio_liturgia(self):
		config = self.bot.config["liturgia"]
		fuso = ZoneInfo("America/Sao_Paulo")
		agora = datetime.datetime.now(fuso)
		hora_config = datetime.time.fromisoformat(config["hora"])

		canal = self.bot.get_channel(config["canal"])
		if canal is None:
			await self.bot.send_to_console(f"Canal {config['canal']} não encontrado.")
			logging.error(f"Canal {config['canal']} não encontrado.")
			return

		if agora.hour >= hora_config.hour or (agora.minute > hora_config.minute and agora.hour == hora_config.hour):
			last = None
			async for msg in canal.history(limit=1):
				last = msg
			if last and last.created_at.date() == agora.date() and last.webhook_id:
				return
		
		webhook_url = self.bot.config.get("urls", {}).get("webhooks", {}).get("Liturgia Diária")
		if not webhook_url:
			await self.bot.send_to_console("Não há webhook registrado para liturgia.")
			return

		try:
			view = await self.generate_liturgy_view(
				url=self.bot.config["urls"]["requests"]["liturgia"],
				content=f"<@&{config['ping']}>"
			)
			
			webhook = discord.Webhook.from_url(webhook_url, session=self.session)
			allowed_mentions = discord.AllowedMentions()
			allowed_mentions.all()

			await webhook.send(view=view, allowed_mentions=allowed_mentions)
		except Exception as e:
			print(f"Erro ao enviar liturgia: {e}")

	@envio_liturgia.before_loop
	async def before_envio(self):
		await self.bot.wait_until_ready()

	async def generate_liturgy_view(self, url: str, content: str) -> ui.LayoutView:
		liturgia = await self.get_liturgy(url)
		containers = []

		def get_container_color(cor: str):
			cores = {"Verde": 0x00FF00, "Branco": 0xFFFFFF, "Vermelho": 0xFF0000, "Azul": 0x0000FF}
			return cores.get(cor, 0xFFCC00)

		def create_container(title: str, description: str = ""):
			return ui.Container(
				ui.TextDisplay(f"## {title}"),
				ui.Separator(spacing=discord.SeparatorSpacing.large),
				ui.TextDisplay(f"\n{description}"),
				accent_color = get_container_color(liturgia["cor"])
			)

		for key in ["primeiraLeitura", "salmo", "segundaLeitura", "evangelho", "extras"]:
			leitura = liturgia.get(key)
			if isinstance(leitura, list) and leitura:
				leitura = leitura[0]
			elif not leitura:
				continue

			titulo_base = f'{leitura["titulo"]} - {leitura["referencia"]}'
			
			versiculos_info = expand_bible_verse(leitura["referencia"].replace(", ", ",").replace(". ", "."))
			
			if not versiculos_info:
				texto_final = leitura["texto"]
			else:
				todos_versiculos = []
				for v in versiculos_info:
					todos_versiculos.extend(v["texto"])

				texto_final = "\n".join(todos_versiculos)

			containers.append(create_container(titulo_base, texto_final))

		view = ui.LayoutView()

		for i, c in enumerate(containers, start=1):
			if i == len(containers):
				c.add_item(ui.TextDisplay(content))
			view.add_item(c)
		return view

	async def get_liturgy(self, url: str) -> dict:
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as response:
				data: dict[str, dict] = await response.json()

		return {
			"titulo": data.get("liturgia", ""),
			"cor": data.get("cor", "Amarelo"),
			"primeiraLeitura": data["leituras"].get("primeiraLeitura", []),
			"segundaLeitura": data["leituras"].get("segundaLeitura", []),
			"evangelho": data["leituras"].get("evangelho", [])
		}

class ModalRegras(discord.ui.Modal):
	def __init__(self, i: int):
		super().__init__(title="Mudar regra do servidor", timeout=None, custom_id="regras_servidor")
		self.regras = CanonesCog.get_regras()
		self.i = i

		self.add_item(
			discord.ui.TextInput(label=f"Regra {contar(i+1)}", style=discord.TextStyle.long, custom_id=str(i), id=i, default=self.regras[i] if len(self.regras) > i else None, required=True, placeholder=f"Regra de número {i+1}")
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

		await interaction.response.send_message("Regras atualizadas com sucesso!", ephemeral=True)

class CanonesCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot
	
	@staticmethod
	def get_regras() -> list[str]:
		with open(DataFiles.CANONES.value, "r", encoding="utf-8") as f:
			canones = json.load(f)["Regras"]
		return canones
	
	regras_gp = app_commands.Group(name="regras", description="Comandos relacionados as regras do servidor.")

	@regras_gp.command(name="listar", description="Mostra as regras do servidor")
	async def regras(self, interaction: discord.Interaction):
		embed = self.gerar_regras_embed(interaction.guild)

		await interaction.response.send_message(embed=embed, ephemeral=True)
	
	@regras_gp.command(name="atualizar", description="Atualiza as regras do servidor")
	@app_commands.checks.has_permissions(administrator=True)
	async def regras_update(self, interaction: discord.Interaction):
		embed = self.gerar_regras_embed(interaction.guild)

		canal_regras = self.bot.get_channel(self.bot.config["canais"]["regras"])

		await canal_regras.purge(limit=None)
		
		await canal_regras.send(embed=embed)

		await interaction.response.send_message("Regras enviadas com sucesso!", ephemeral=True)
	
	def gerar_regras_embed(self, guild: discord.Guild) -> discord.Embed:
		regras = self.get_regras()
		embed = discord.Embed(
			title=f"Decálogo da {guild.name}",
			description="",
			color=0xffcc00
		)

		embed.set_footer(
			text=f"{guild.name} - Decálogo",
			icon_url=guild.icon.url
		)
		embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Emblem_of_the_Papacy_SE.svg/250px-Emblem_of_the_Papacy_SE.svg.png")
		embed.set_author(
			name = guild.owner.name,
			icon_url=guild.owner.display_avatar.url
		)

		regras_txt = []

		for i, regra in enumerate(regras):
			regras_txt.append(f"**{contar(i+1)}.** {regra}")

		embed.description = "\n".join(regras_txt)

		return embed
	
	@regras_gp.command(name="definir", description="Defina uma das regras")
	@app_commands.choices(
		numero=[
			app_commands.Choice(name=str(contar(i+1)), value=i) for i in range(10)
		]
	)
	@app_commands.describe(
		numero="A posição com a qual a regra situará."
	)
	@app_commands.checks.has_permissions(administrator=True)
	async def definir(self, interaction: discord.Interaction, numero: int):
		await interaction.response.send_modal(ModalRegras(i=numero))
	
	def get_canones(self) -> list[CanonesDict]:
		with open(DataFiles.CANONES.value, "r", encoding="utf-8") as f:
			canones = json.load(f)["Cânones"]
		return canones
	
	canone_gp = app_commands.Group(name="canone", description="Comandos relacionados aos cânones da comunidade.")

	@canone_gp.command(name="setup", description="Envia os cânones dos seus respecitvos canais.")
	@app_commands.checks.has_permissions(administrator=True)
	async def setup_canone(self, interaction: discord.Interaction):
		await interaction.response.defer(thinking=True, ephemeral=True)
		canones = self.get_canones()
		contagem_artigos = 0

		embed_codigo = discord.Embed(
			title="Código Canônico",
			description="Preâmbulo: Inspirado no zelo pela ordem, pela caridade e pela comunhão com a Igreja de Cristo, o presente Código estabelece os funcionamentos sacerdotais disciplinares e as normas punitivas aplicáveis a todos os membros da comunidade, a fim de preservar a verdade, a paz e a integridade da fé católica neste espaço.\n\n## Sumário:\n",
			color=0xffcc00
		)
		embed_codigo.set_author(name=interaction.user.name, url=f"https://discord.com/users/{interaction.user.id}", icon_url=interaction.user.display_avatar.url)
		embed_codigo.set_footer(text=f"{interaction.guild.name} - Código Canônico", icon_url=interaction.guild.icon.url)
		embed_codigo.set_thumbnail(url=interaction.guild.icon.url)

		sumario = []

		for c, canone in enumerate(canones):
			embed = discord.Embed(
				title=f"Cânone {contar(c+1)} — {canone['titulo']}",
				description=f"{canone['conteudo']}\n\n",
				colour=0xffcc00
			)
			embed.set_author(name=interaction.user.name, url=f"https://discord.com/users/{interaction.user.id}", icon_url=interaction.user.display_avatar.url)
			embed.set_footer(text=f"{interaction.guild.name} - Código Canônico", icon_url=interaction.guild.icon.url)
			embed.set_thumbnail(url=interaction.guild.icon.url)

			for artigo in canone["artigos"]:

				contagem_artigos+=1
				embed.description += f"**Art. {contar(contagem_artigos)}º** {artigo['texto']}\n"

				for i, inciso in enumerate(artigo.get("incisos", [])):
					embed.description += f"\n**{contar(i+1)} —** {inciso}"
					embed.description += "." if len(artigo["incisos"])-1 == i else ";"
				
				for i, paragrafo in enumerate(artigo.get("paragrafos", [])):
					if i == 0 and len(artigo.get("incisos", [])) > 0:
						embed.description+="\n"
					
					if len(artigo["paragrafos"]) == 1:
						embed.description += f"\n**Parágrafo único.** {paragrafo}"
					else:
						embed.description += f"\n**§{contar(i+1)}.** {paragrafo}"
				
				embed.description += "\n" if not any(len(artigo.get(j, [])) != 0 for j in ["incisos", "paragrafos"]) else "\n\n"
			
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

async def setup(bot: Bot):
	await bot.add_cog(SacerdocioCog(bot))
	await bot.add_cog(LiturgiaCog(bot))
	await bot.add_cog(CanonesCog(bot))
	bot.add_view(SacerdocioNovicoView(bot=bot))
	bot.add_view(SolicitacaoSacerdocioView(bot=bot))