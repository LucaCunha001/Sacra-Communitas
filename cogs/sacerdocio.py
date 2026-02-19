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

from .tickets import create_ticket_channel

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

class InscricoesView(ui.LayoutView):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.bot = bot

		c_novico = ui.Container(
			ui.Section(
				ui.TextDisplay("## Torne-se um sacerdote da Sacra Communitas!"),
				accessory=ui.Thumbnail("https://cdn-icons-png.flaticon.com/512/443/443603.png")
			),
			accent_color=0x98FFC3
		)
		c_novico.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
		c_novico.add_item(ui.TextDisplay(
			"Gostaria de servir nossa comunidade em um papel mais profundo e significativo? "
			"Estamos aceitando solicitações para novos sacerdotes que desejam se juntar ao nosso clero dedicado.\n\n"
			"Como sacerdote, você terá a oportunidade de ajudar a cuidar do servidor e de seus membros, "
			"promovendo um ambiente mais acolhedor e seguro para todos da comunidade.\n\n"
			"Ao fazer a sua solicitação, você se compromete a manter uma conduta exemplar, "
			"respeitando as diretrizes e valores da comunidade.\n\n"
			"Ao enviar sua solicitação, ganhará automaticamente o cargo de Noviço, iniciando sua jornada rumo ao sacerdócio.Depois, basta aguardar a análise dos bispos do servidor.\n\n"
			"Clique no botão abaixo para enviar sua solicitação e dar o primeiro passo em direção a essa nobre vocação!"
		))

		novico_btn = ui.Button(label="Enviar Solicitação", style=discord.ButtonStyle.primary, custom_id="enviar_solicitacao_sacerdocio", emoji="🕊️")
		novico_btn.callback = self.solicitacao_novico

		c_novico.add_item(ui.ActionRow(novico_btn))

		c_doutrina = ui.Container(
			ui.Section(
				ui.TextDisplay("## Participe da equipe doutrinária!"),
				accessory=ui.Thumbnail("https://cdn-icons-png.flaticon.com/512/2682/2682065.png")
			),
			accent_color=0xB7950B
		)
		c_doutrina.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
		
		c_doutrina.add_item(ui.TextDisplay(
			"Você gosta de estudar a fé católica com profundidade e fidelidade à doutrina da Igreja? "
			"Estamos recebendo solicitações para o cargo de Doutrina, voltado a membros que desejam ajudar na orientação teológica do servidor.\n\n"
			"Quem ocupa essa função auxilia na explicação de temas doutrinários, esclarecimento de dúvidas e manutenção da fidelidade dos conteúdos compartilhados, "
			"sempre em comunhão com o Magistério da Igreja.\n\n"
			"Ao se candidatar, você assume o compromisso de buscar formação contínua, agir com caridade nas correções e evitar debates desnecessariamente acalorados, "
			"preservando a unidade e o bom clima da comunidade.\n\n"
			"O cargo não é apenas um título, mas um serviço: exige responsabilidade, prudência e humildade intelectual.\n\n"
			"Clique no botão abaixo para enviar sua solicitação e passar pela avaliação da equipe responsável pela área doutrinária."
		))


		doutrina_btn = ui.Button(label="Enviar Solicitação", style=discord.ButtonStyle.primary, custom_id="enviar_solicitacao_doutrina", emoji="📖")
		doutrina_btn.callback = self.solicitacao_doutrina

		c_doutrina.add_item(ui.ActionRow(doutrina_btn))

		self.add_item(c_novico)
		self.add_item(c_doutrina)
	
	async def solicitacao_novico(self, interaction: discord.Interaction):
		await enviar_solicitacao(self.bot, interaction)
	
	async def solicitacao_doutrina(self, interaction: discord.Interaction):
		if not any(r == role.id for role in interaction.user.roles for r in [1429972827209207878, 1429973276041412658]):
			return await interaction.response.send_message("Precisa ser católico para se inscrever!", ephemeral=True)
		await create_ticket_channel(self.bot, interaction, f"📜・{interaction.user.name}")

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

	@sacerdocio_group.command(name="solicitacoes_msg", description="Envia as mensagens de solicitações no canal designado.")
	@permissao(gerenciar_comunidade=True)
	async def solicitacao_msg(self, interaction: discord.Interaction):
		canal_id = self.bot.config['canais'].get('solicitacoes_sacerdocio_pub')
		canal: discord.TextChannel = interaction.guild.get_channel(canal_id)
		
		if not canal:
			return await interaction.response.send_message("Canal de solicitações de sacerdócio não encontrado.", ephemeral=True)
		
		await canal.purge(limit=None)

		await canal.send(view=InscricoesView(bot=self.bot))
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
	
	async def na_saida(self, membro: discord.Member):
		await self.update_sacerdote(
			interaction=None,
			ordinante=self.bot.user,
			sacerdote=membro,
			tipo=3,
			funcao=None,
			motivo="Saiu do servidor"
		)

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
		motivo: str | None = None,
		guild: discord.Guild | None = None
	):
		responder_interacao = interaction is not None 
		if sacerdote.bot and responder_interacao:
			return await interaction.response.send_message("Eu não sei o que te fez pensar que poderia mexer nas permissões de um ser angelical.", ephemeral=True)

		if tipo not in range(4) and responder_interacao:
			return await interaction.response.send_message(
				"Tipo de ação inválido.", ephemeral=True
			)

		guild = interaction.guild if responder_interacao else sacerdote.guild 
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
				if responder_interacao:
					await interaction.response.send_message(
						f"{sacerdote.mention} já faz parte do clero e não pode ser nomeado novamente.",
						ephemeral=True
					)
				return
			if not any(novico_cargo.id == r.id for r in sacerdote.roles):
				if responder_interacao:
					await interaction.response.send_message(
						f"{sacerdote.mention} ainda não é um noviço para ser nomeado.",
						ephemeral=True
					)
				return

		if tipo == 1 and not any(r in sacerdote.roles for r in cargos_sacerdotais):
			if responder_interacao:
				await interaction.response.send_message(
					f"{sacerdote.mention} ainda não é sacerdote. Use `/sacerdocio nomear` primeiro.",
					ephemeral=True
				)
			return

		if tipo == 2:
			if not cargo_maximo_atual:
				if responder_interacao:
					await interaction.response.send_message(
						f"{sacerdote.mention} não possui cargo sacerdotal para ser rebaixado.",
						ephemeral=True
					)
				return
			if funcao and funcao >= cargo_maximo_atual:
				if responder_interacao:
					await interaction.response.send_message(
						"O novo cargo deve ser **inferior** ao atual.",
						ephemeral=True
					)
				return

		if tipo == 3 and not any(r in sacerdote.roles for r in cargos_sacerdotais):
			if responder_interacao:
				await interaction.response.send_message(
					f"{sacerdote.mention} não é sacerdote, portanto não pode ser dispensado.",
					ephemeral=True
				)
			return
		
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

		no_servidor = guild.get_member(sacerdote.id) is not None

		match tipo:
			case 0:
				titulo = "Anunciação Sacra"
				message = (
					f"Com júbilo e gratidão, a comunidade anuncia a elevação de {sacerdote.mention} à digna função de {funcao.mention}.\n\n"
					"Que o Espírito Santo o conduza com sabedoria, prudência e zelo pastoral, para servir fielmente à comunidade e à Santa Igreja.\n\n"
					f"{citacao}\n\n"
					"Bendizemos este novo passo em seu ministério, confiando-o à graça de Deus."
				)
				if no_servidor:
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
				if no_servidor and cargo_maximo_atual and cargo_maximo_atual < bispo_role:
					await sacerdote.remove_roles(cargo_maximo_atual, reason="Promoção")

			case 2:
				titulo = "Aviso do Conselho"
				message = (
					f"Após discernimento do Conclave e em espírito de correção fraterna, {sacerdote.mention} passa a exercer a função de {funcao.mention}.{motivo_txt}\n\n"
					"Que este tempo seja ocasião de humildade, conversão interior e amadurecimento espiritual.\n\n"
					f"{citacao}\n\n"
					"Rezemos para que retome, com renovado ardor, o caminho do serviço fiel."
				)
				if no_servidor and cargo_maximo_atual:
					await sacerdote.remove_roles(cargo_maximo_atual, reason="Rebaixamento")

			case 3:
				titulo = "Decreto de Retiro"
				message = (
					f"Por decisão do Conclave e em conformidade com as diretrizes da Sacra Communitas, {sacerdote.mention} é removido de suas funções sacerdotais.{motivo_txt}\n\n"
					"Que o Senhor lhe conceda paz, discernimento e retidão neste novo caminho.\n\n"
					f"{citacao}\n\n"
					"Confiamos este momento à misericórdia divina."
				)
				if no_servidor:
					for _, cargo_dict in self.bot.config["cargos"]["sacerdotes"].items():
						for r in sacerdote.roles:
							if r.id == cargo_dict['id']:
								await sacerdote.remove_roles(r)
					await sacerdote.add_roles(leigo_cargo)
					cargo_color = leigo_cargo.color

		if funcao and tipo != 3 and no_servidor:
			await sacerdote.add_roles(clearo_cargo)
			await sacerdote.add_roles(funcao)

		if responder_interacao:
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
	await bot.add_cog(CanonesCog(bot))
	bot.add_view(InscricoesView(bot=bot))
	bot.add_view(SolicitacaoSacerdocioView(bot=bot))