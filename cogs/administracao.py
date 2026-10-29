import random

import discord
from discord import app_commands, ui
from discord.ext import commands

from utils.data import get_config
from utils.recursos import Bot, expand_bible_verse

class InscricoesView(ui.LayoutView):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		buttons = [
			ui.Button(
				label="Administração",
				style=discord.ButtonStyle.link,
				url=bot.config["forms"]["administracao"],
				emoji="🕊️",
			),
			ui.Button(
				label="Moderação",
				style=discord.ButtonStyle.link,
				url=bot.config["forms"]["moderacao"],
				emoji="🪖",
			),
			ui.Button(
				label="Teologia",
				style=discord.ButtonStyle.link,
				url=bot.config["forms"]["teologia"],
				emoji="📖",
			),
		]

		container = ui.Container(
			ui.Section(
				ui.TextDisplay("## Envie sua solicitação"),
				accessory=ui.Thumbnail(
					"https://cdn-icons-png.flaticon.com/512/2682/2682065.png"
				),
			),
			ui.Separator(spacing=discord.SeparatorSpacing.large),
			ui.TextDisplay(
				"Acesse o formulário correspondente à sua solicitação nos botões abaixo."
			),
			ui.ActionRow(*buttons),
			accent_color=0x5DADE2,
		)
		self.add_item(container)


class SacerdocioCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot

	sacerdocio_group = app_commands.Group(
		name="sacerdocio",
		description="Comandos relacionados ao sacerdócio",
	)

	# ============================================================
	# HIERARQUIA
	# ============================================================

	def get_roles(
		self,
		guild: discord.Guild,
	) -> dict[str, discord.Role]:
		config = self.bot.config["cargos"].get(
			"sacerdotes",
			{},
		)

		return {
			nome: role
			for nome, dados in config.items()
			if (role := guild.get_role(dados["id"])) is not None
		}

	def get_rank(
		self,
		membro: discord.Member,
		guild: discord.Guild,
	) -> discord.Role | None:
		roles = self.get_roles(guild)

		return max(
			(
				role
				for role in membro.roles
				if role.id in {
					cargo.id
					for cargo in roles.values()
				}
			),
			key=lambda role: role.position,
			default=None,
		)

	async def can_manage_member(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
	) -> bool:
		# O dono sempre pode administrar.
		if interaction.user.id == interaction.guild.owner_id:
			return True

		# Mantém sua regra global de designação de cargos.
		# Se ela já controla Papa/Conclave etc., continua sendo
		# a primeira barreira.
		#
		# Aqui estamos apenas adicionando a proteção hierárquica.

		ator = self.get_rank(
			interaction.user,
			interaction.guild,
		)

		alvo = self.get_rank(
			sacerdote,
			interaction.guild,
		)

		if ator and alvo and alvo.position >= ator.position:
			await interaction.response.send_message(
				"Você não pode alterar um sacerdote com cargo "
				"igual ou superior ao seu.",
				ephemeral=True,
			)
			return False

		return True

	# ============================================================
	# ALTERAÇÃO DE CARGOS
	# ============================================================

	async def change_roles(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
		cargo_novo: discord.Role | None,
		tipo: int,
		motivo: str | None = None,
	):
		guild = interaction.guild
		roles = self.get_roles(guild)

		cargos_sacerdotais = {
			role.id
			for role in roles.values()
		}

		leigo = guild.get_role(
			self.bot.config["cargos"]["membros"]["Leigo"]["id"]
		)

		novico = guild.get_role(
			self.bot.config["cargos"]["membros"]["Noviço"]["id"]
		)

		clero = guild.get_role(
			self.bot.config["cargos"]["sacerdotes"]["Clero"]["id"]
		)

		cargo_atual = self.get_rank(
			sacerdote,
			guild,
		)

		# Mantém todos os cargos que não pertencem ao sacerdócio.
		cargos_membro = [
			role
			for role in sacerdote.roles
			if role.id not in cargos_sacerdotais
		]

		# --------------------------------------------------------
		# ADMISSÃO
		# --------------------------------------------------------

		if tipo == 0:
			if cargo_atual:
				return await interaction.response.send_message(
					f"{sacerdote.mention} já faz parte do clero.",
					ephemeral=True,
				)

			if novico is not None:
				cargos_membro = [
					role
					for role in cargos_membro
					if role.id != novico.id
				]

			if leigo is not None:
				cargos_membro = [
					role
					for role in cargos_membro
					if role.id != leigo.id
				]

		# --------------------------------------------------------
		# PROMOÇÃO
		# --------------------------------------------------------

		elif tipo == 1:
			if cargo_atual is None:
				return await interaction.response.send_message(
					f"{sacerdote.mention} ainda não é sacerdote.",
					ephemeral=True,
				)

			if cargo_novo is None:
				return await interaction.response.send_message(
					"O novo cargo não foi encontrado.",
					ephemeral=True,
				)

			if cargo_novo.position <= cargo_atual.position:
				return await interaction.response.send_message(
					"O novo cargo deve ser superior ao atual.",
					ephemeral=True,
				)

			cargos_membro = [
				role
				for role in cargos_membro
				if role.id != cargo_atual.id
			]

		# --------------------------------------------------------
		# REBAIXAMENTO
		# --------------------------------------------------------

		elif tipo == 2:
			if cargo_atual is None:
				return await interaction.response.send_message(
					f"{sacerdote.mention} não possui cargo sacerdotal.",
					ephemeral=True,
				)

			if cargo_novo is None:
				return await interaction.response.send_message(
					"O novo cargo não foi encontrado.",
					ephemeral=True,
				)

			if cargo_novo.position >= cargo_atual.position:
				return await interaction.response.send_message(
					"O novo cargo deve ser inferior ao atual.",
					ephemeral=True,
				)

			cargos_membro = [
				role
				for role in cargos_membro
				if role.id != cargo_atual.id
			]

		# --------------------------------------------------------
		# DISPENSA
		# --------------------------------------------------------

		elif tipo == 3:
			if cargo_atual is None:
				return await interaction.response.send_message(
					f"{sacerdote.mention} não é sacerdote.",
					ephemeral=True,
				)

			if leigo is not None:
				cargos_membro.append(leigo)

		else:
			return await interaction.response.send_message(
				"Tipo de ação inválido.",
				ephemeral=True,
			)

		# --------------------------------------------------------
		# NOVO CARGO
		# --------------------------------------------------------

		if cargo_novo is not None and tipo != 3:
			if clero is not None:
				cargos_membro.append(clero)

			cargos_membro.append(cargo_novo)

		try:
			await sacerdote.edit(
				roles=cargos_membro,
				reason=(
					f"Alteração sacerdotal por "
					f"{interaction.user} ({interaction.user.id})"
				),
			)

		except discord.Forbidden:
			return await interaction.response.send_message(
				"Não consegui alterar os cargos. "
				"Verifique as permissões e a hierarquia do bot.",
				ephemeral=True,
			)

		except discord.HTTPException:
			return await interaction.response.send_message(
				"O Discord recusou a alteração dos cargos.",
				ephemeral=True,
			)

		await interaction.response.send_message(
			"Cargo alterado com sucesso!",
			ephemeral=True,
		)

		await self.send_appointment_log(
			interaction=interaction,
			sacerdote=sacerdote,
			cargo_novo=cargo_novo,
			tipo=tipo,
			motivo=motivo,
		)

	# ============================================================
	# REGISTRO
	# ============================================================

	async def send_appointment_log(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
		cargo_novo: discord.Role | None,
		tipo: int,
		motivo: str | None = None,
	):
		citacoes = [
			[
				"1Tm 3,13",
				"Ap 21,5",
				"1Sm 16,7",
				"Sb 6,1-3",
				"Cl 3,23",
				"Pr 22,29",
			],
			[
				"Lc 12,48",
				"1Pd 5,2-3",
				"Mt 25,21",
				"Sb 6,20-21",
				"Rm 12,8",
				"2Tm 2,15",
			],
			[
				"Hb 12,6",
				"Sl 51,10",
				"Pr 3,11-12",
				"Lm 3,31-33",
				"Mq 6,8",
				"Sl 119,71",
			],
			[
				"Pr 24,16",
				"2Cor 12,9",
				"Jó 1,21",
				"Ecl 3,1",
				"Sl 34,19",
				"Is 55,8-9",
			],
		]

		versiculo = random.choice(citacoes[tipo])

		res = expand_bible_verse(
			versiculo
		)[0]

		separador = (
			":"
			if res["tipo"] == "Evangelhos"
			else ","
		)

		texto = "\n".join(
			t.strip()
			for t in res["texto"]
		)

		passagem = (
			res["versículo_inicial"]
			if res["versículo_final"]
			== res["versículo_inicial"]
			else (
				f"{res['versículo_inicial']}-"
				f"{res['versículo_final']}"
			)
		)

		citacao = (
			f"_“{texto}”_ "
			f"({res['livro']} "
			f"{res['capítulo']}"
			f"{separador}"
			f"{passagem})"
		)

		motivo_txt = (
			f"\n\n**Motivo:** {motivo}"
			if motivo
			else ""
		)

		match tipo:
			case 0:
				titulo = "Novo sacerdote"
				message = (
					f"{sacerdote.mention} foi admitido ao sacerdócio "
					f"da Sacra Communitas, assumindo o cargo de "
					f"{cargo_novo.mention}.\n\n"
					"Que exerça seu serviço com sabedoria, prudência "
					"e zelo pela comunidade."
				)

			case 1:
				titulo = "Promoção sacerdotal"
				message = (
					f"{sacerdote.mention} foi promovido ao cargo de "
					f"{cargo_novo.mention}, em reconhecimento ao seu "
					"serviço e às responsabilidades assumidas.\n\n"
					"Que esta nova missão seja exercida com "
					"discernimento, firmeza e caridade."
				)

			case 2:
				titulo = "Rebaixamento sacerdotal"
				message = (
					f"{sacerdote.mention} foi rebaixado ao cargo de "
					f"{cargo_novo.mention}."
					f"{motivo_txt}\n\n"
					"Que este momento seja ocasião de reflexão, "
					"humildade e renovação no serviço à comunidade."
				)

			case 3:
				titulo = "Dispensa do sacerdócio"
				message = (
					f"{sacerdote.mention} foi dispensado de suas "
					"funções sacerdotais."
					f"{motivo_txt}\n\n"
					"Que Deus lhe conceda paz e discernimento "
					"neste novo caminho."
				)
		
		message += f"\n\n> {citacao}"

		canal = self.bot.get_channel(
			self.bot.config["canais"]["nomeacoes"]
		)

		if canal is None:
			return

		cor = (
			cargo_novo.color
			if cargo_novo is not None
			else discord.Color.dark_grey()
		)

		view = ui.LayoutView()

		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"## {titulo}"),
				accessory=ui.Thumbnail(
					sacerdote.display_avatar.url
				),
			),
			ui.Separator(
				spacing=discord.SeparatorSpacing.large
			),
			ui.TextDisplay(message),
			ui.TextDisplay(
				f"**Mudança realizada por:**\n"
				f"{interaction.user.mention}"
			),
			ui.TextDisplay(
				"-# Sacra Communitas • Conclave"
			),
			accent_color=cor,
		)

		view.add_item(container)

		try:
			await canal.send(view=view)
		except discord.Forbidden:
			pass

	# ============================================================
	# COMANDOS
	# ============================================================

	@sacerdocio_group.command(
		name="nomear",
		description="Nomeia um noviço à função sacerdotal.",
	)
	@app_commands.describe(
		sacerdote="O membro que será nomeado"
	)
	async def nomear(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
	):
		if not await self.can_manage_member(
			interaction,
			sacerdote,
		):
			return

		roles = self.get_roles(
			interaction.guild
		)

		if self.get_rank(
			sacerdote,
			interaction.guild,
		):
			return await interaction.response.send_message(
				f"{sacerdote.mention} já faz parte do clero.",
				ephemeral=True,
			)

		novico = interaction.guild.get_role(
			self.bot.config["cargos"]["membros"]["Noviço"]["id"]
		)

		if novico not in sacerdote.roles:
			return await interaction.response.send_message(
				f"{sacerdote.mention} ainda não é um noviço.",
				ephemeral=True,
			)

		cargo = roles.get("Seminarista")

		if cargo is None:
			return await interaction.response.send_message(
				"O cargo Seminarista não foi encontrado.",
				ephemeral=True,
			)

		await self.change_roles(
			interaction,
			sacerdote,
			cargo,
			tipo=0,
		)

	@sacerdocio_group.command(
		name="ordenar",
		description="Ordena um sacerdote a um cargo maior.",
	)
	@app_commands.describe(
		sacerdote="Sacerdote que será promovido",
		cargo="Cargo para o qual será promovido",
		motivo="Motivo da promoção",
	)
	@app_commands.choices(
		cargo = [
			app_commands.Choice(
				name=nome,
				value=str(dados["id"]),
			)
			for nome, dados in get_config()["cargos"]
			.get("sacerdotes", {})
			.items()
			if nome not in ["Clero", "Seminarista", "Papa"]
		]
	)
	async def ordenar(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
		cargo: str,
		motivo: str | None = None,
	):
		if not await self.can_manage_member(
			interaction,
			sacerdote,
		):
			return

		cargo_role = interaction.guild.get_role(
			int(cargo)
		)

		if cargo_role is None:
			return await interaction.response.send_message(
				"Cargo não encontrado.",
				ephemeral=True,
			)

		await self.change_roles(
			interaction,
			sacerdote,
			cargo_role,
			tipo=1,
			motivo=motivo,
		)

	@sacerdocio_group.command(
		name="exonerar",
		description="Rebaixa um sacerdote a um cargo menor.",
	)
	@app_commands.describe(
		sacerdote="Sacerdote que será rebaixado",
		cargo="Cargo para o qual será rebaixado",
		motivo="Motivo do rebaixamento",
	)
	@app_commands.choices(
		cargo = [
			app_commands.Choice(
				name=nome,
				value=str(dados["id"]),
			)
			for nome, dados in get_config()["cargos"]
			.get("sacerdotes", {})
			.items()
			if nome not in ["Clero", "Cardeal", "Papa"]
		]
	)
	async def exonerar(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
		cargo: str,
		motivo: str | None = None,
	):
		if not await self.can_manage_member(
			interaction,
			sacerdote,
		):
			return

		cargo_role = interaction.guild.get_role(
			int(cargo)
		)

		if cargo_role is None:
			return await interaction.response.send_message(
				"Cargo não encontrado.",
				ephemeral=True,
			)

		await self.change_roles(
			interaction,
			sacerdote,
			cargo_role,
			tipo=2,
			motivo=motivo,
		)

	@sacerdocio_group.command(
		name="dispensar",
		description="Dispensa um sacerdote de suas funções.",
	)
	@app_commands.describe(
		sacerdote="Sacerdote que será dispensado",
		motivo="Motivo da dispensa",
	)
	async def dispensar(
		self,
		interaction: discord.Interaction,
		sacerdote: discord.Member,
		motivo: str | None = None,
	):
		if not await self.can_manage_member(
			interaction,
			sacerdote,
		):
			return

		await self.change_roles(
			interaction,
			sacerdote,
			None,
			tipo=3,
			motivo=motivo,
		)

	@app_commands.command(name="inscricoes", description="Envia a mensagemd de inscrições no canal adequado.")
	async def inscricoes_msg(self, interaction: discord.Interaction):
		canal_id = self.bot.config["canais"]["inscricoes"]
		canal = self.bot.get_channel(canal_id)
		await canal.purge()
		await canal.send(view=InscricoesView(self.bot))
		await interaction.response.send_message("Mensagem enviada com sucesso!", ephemeral=True)


async def setup(bot: Bot):
	await bot.add_cog(SacerdocioCog(bot))
	bot.add_view(InscricoesView(bot=bot))