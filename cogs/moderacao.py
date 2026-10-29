import discord

from discord import app_commands, ui
from discord.ext import commands

from utils.data import get_config
from utils.recursos import Bot


class ModeracaoCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot

	moderacao_group = app_commands.Group(
		name="moderacao",
		description="Comandos relacionados à Moderação",
	)

	# ============================================================
	# HIERARQUIA
	# ============================================================

	def get_roles(self, guild: discord.Guild) -> dict[str, discord.Role]:
		config = self.bot.config["cargos"].get("moderativos", {})

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

		cargos_hierarquicos = {
			role.id
			for nome, role in roles.items()
			if nome != "Militar"
		}

		return max(
			(
				role
				for role in membro.roles
				if role.id in cargos_hierarquicos
			),
			key=lambda role: role.position,
			default=None,
		)

	async def can_manage_member(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
	) -> bool:
		# O dono sempre pode administrar.
		if interaction.user.id == interaction.guild.owner_id:
			return True

		roles = self.get_roles(interaction.guild)

		# Somente Comandante e Tenente podem alterar a estrutura.
		cargos_autorizados = {
			roles[nome].id
			for nome in ("Comandante", "Tenente")
			if nome in roles
		}

		if not any(
			role.id in cargos_autorizados
			for role in interaction.user.roles
		):
			await interaction.response.send_message(
				"Somente o Papa, o Comandante ou o Tenente "
				"podem alterar cargos da Moderação.",
				ephemeral=True,
			)
			return False

		ator = self.get_rank(interaction.user, interaction.guild)
		alvo = self.get_rank(membro, interaction.guild)

		# Se o alvo possui cargo hierárquico, ele deve estar abaixo do ator.
		if ator and alvo and alvo.position >= ator.position:
			await interaction.response.send_message(
				"Você não pode alterar alguém com cargo moderativo "
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
		membro: discord.Member,
		cargo_novo: discord.Role | None,
		titulo: str,
		motivo: str | None = None,
	):
		roles = self.get_roles(interaction.guild)

		cargos_estrutura = {
			role.id
			for role in roles.values()
		}

		# Mantém absolutamente todos os cargos que não pertencem
		# à estrutura da Moderação.
		cargos_membro = [
			role
			for role in membro.roles
			if role.id not in cargos_estrutura
		]

		# Militar é um cargo auxiliar/base e não conta como posto.
		cargo_militar = roles.get("Militar")

		if cargo_militar is not None:
			if cargo_novo is not None:
				cargos_membro.append(cargo_militar)

		if cargo_novo is not None:
			cargos_membro.append(cargo_novo)

		try:
			await membro.edit(
				roles=cargos_membro,
				reason=(
					f"{titulo} por {interaction.user} "
					f"({interaction.user.id})"
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
			membro=membro,
			cargo_novo=cargo_novo,
			titulo=titulo,
			motivo=motivo,
		)

	# ============================================================
	# REGISTRO DA ALTERAÇÃO
	# ============================================================

	async def send_appointment_log(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
		cargo_novo: discord.Role | None,
		titulo: str,
		motivo: str | None = None,
	):
		canal = self.bot.get_channel(
			self.bot.config["canais"].get("nomeacoes")
		)

		if canal is None:
			return

		if cargo_novo is None:
			titulo = "Dispensa da Moderação"
			mensagem = (
				f"{membro.mention} deixa de integrar a estrutura "
				"da Moderação da Sacra Communitas."
			)

		elif titulo.startswith("Admissão"):
			titulo = "Admissão à Moderação"
			mensagem = (
				f"{membro.mention} passa a integrar a estrutura "
				f"da Moderação como {cargo_novo.mention}.\n\n"
				"Confiamos a ele o dever de auxiliar na preservação "
				"da ordem, da convivência e das regras da comunidade."
			)

		elif titulo.startswith("Promoção"):
			titulo = "Promoção na Moderação"
			mensagem = (
				f"{membro.mention} foi promovido a {cargo_novo.mention}.\n\n"
				"A nova função traz consigo maiores responsabilidades "
				"na condução, organização e proteção da comunidade."
			)

		else:
			titulo = "Rebaixamento na Moderação"
			mensagem = (
				f"{membro.mention} foi rebaixado para {cargo_novo.mention}."
				f"{motivo}\n\n"
				"A alteração corresponde à nova posição do membro "
				"dentro da estrutura da Moderação."
			)

		view = ui.LayoutView()

		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"## {titulo}"),
				accessory=ui.Thumbnail(
					membro.display_avatar.url
				),
			),
			ui.Separator(
				spacing=discord.SeparatorSpacing.large
			),
			ui.TextDisplay(mensagem),
			ui.TextDisplay(
				f"**Responsável:** {interaction.user.mention}\n"
				f"**Cargo:** "
				f"{cargo_novo.mention if cargo_novo else 'Dispensado'}"
			),
			ui.TextDisplay(
				"-# Sacra Communitas • Moderação"
			),
			accent_color=(
				cargo_novo.color
				if cargo_novo
				else discord.Color.dark_grey()
			),
		)

		view.add_item(container)

		try:
			await canal.send(view=view)
		except discord.Forbidden:
			pass

	# ============================================================
	# INFORMAÇÕES
	# ============================================================

	@moderacao_group.command(
		name="info",
		description="Mostra os cargos e as atribuições da Moderação.",
	)
	async def info(self, interaction: discord.Interaction):
		config_roles = self.bot.config["cargos"].get(
			"moderativos",
			{},
		)

		roles = self.get_roles(interaction.guild)

		view = ui.LayoutView()

		container = ui.Container(
			ui.Section(
				ui.TextDisplay("## Estrutura da Moderação"),
				accessory=ui.Thumbnail(
					interaction.guild.icon.url
					if interaction.guild.icon
					else self.bot.user.display_avatar.url
				),
			),
			ui.Separator(
				spacing=discord.SeparatorSpacing.large
			),
			ui.TextDisplay(
				"A Moderação cuida dos membros, da aplicação "
				"das regras e da organização dos canais."
			),
			ui.Separator(),
			accent_color=0x2E86C1,
		)

		for nome, dados in config_roles.items():
			role = roles.get(nome)

			if role is None:
				continue

			container.add_item(
				ui.TextDisplay(
					f"### {nome} · {len(role.members)}\n"
					f"{role.mention}\n"
					f"{dados.get('descricao', '')}"
				)
			)

		view.add_item(container)

		await interaction.response.send_message(
			view=view
		)

	# ============================================================
	# EFETIVO
	# ============================================================

	@moderacao_group.command(
		name="efetivo",
		description="Lista os membros da estrutura da Moderação.",
	)
	async def efetivo(self, interaction: discord.Interaction):
		roles = self.get_roles(interaction.guild)

		if not roles:
			return await interaction.response.send_message(
				"Os cargos da Moderação não foram encontrados.",
				ephemeral=True,
			)

		view = ui.LayoutView()

		container = ui.Container(
			ui.Section(
				ui.TextDisplay("## Efetivo da Moderação"),
				accessory=ui.Thumbnail(
					interaction.guild.icon.url
					if interaction.guild.icon
					else self.bot.user.display_avatar.url
				),
			),
			ui.Separator(
				spacing=discord.SeparatorSpacing.large
			),
			ui.TextDisplay(
				"Membros organizados por posto na Guarda Suíça."
			),
			ui.Separator(),
			accent_color=0x2E86C1,
		)

		for nome, role in roles.items():
			membros = role.members

			if nome == "Militar":
				postos = {
					posto.id
					for nome_posto, posto in roles.items()
					if nome_posto != "Militar"
				}

				membros = [
					membro
					for membro in membros
					if not any(
						cargo.id in postos
						for cargo in membro.roles
					)
				]

			lista = [
				membro.mention
				for membro in membros[:20]
			]

			if len(membros) > 20:
				lista.append(
					f"... e mais {len(membros) - 20} membro(s)"
				)

			container.add_item(
				ui.TextDisplay(
					f"### {nome} · {len(membros)}\n"
					+ (
						"\n".join(lista)
						if lista
						else "Nenhum membro."
					)
				)
			)

		view.add_item(container)

		await interaction.response.send_message(
			view=view,
			ephemeral=True,
		)

	# ============================================================
	# ADMISSÃO
	# ============================================================

	@moderacao_group.command(
		name="nomear",
		description="Admite um membro como Soldado da Moderação.",
	)
	@app_commands.describe(
		membro="Membro que será admitido"
	)
	async def nomear(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
	):
		if not await self.can_manage_member(
			interaction,
			membro,
		):
			return

		roles = self.get_roles(interaction.guild)

		if self.get_rank(membro, interaction.guild):
			return await interaction.response.send_message(
				f"{membro.mention} já faz parte da Moderação.",
				ephemeral=True,
			)

		cargo = roles.get("Soldado")

		if cargo is None:
			return await interaction.response.send_message(
				"O cargo Soldado não foi encontrado na configuração.",
				ephemeral=True,
			)

		await self.change_roles(
			interaction=interaction,
			membro=membro,
			cargo_novo=cargo,
			titulo="Admissão à Moderação",
		)

	# ============================================================
	# PROMOÇÃO / REBAIXAMENTO
	# ============================================================

	async def set_rank(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
		cargo_id: str,
		promocao: bool,
		motivo: str | None = None,
	):
		if not await self.can_manage_member(
			interaction,
			membro,
		):
			return

		roles = self.get_roles(interaction.guild)

		cargo_atual = self.get_rank(
			membro,
			interaction.guild,
		)

		cargo_novo = interaction.guild.get_role(
			int(cargo_id)
		)

		if cargo_atual is None:
			return await interaction.response.send_message(
				f"{membro.mention} ainda não faz parte da "
				"Moderação. Use `/moderacao nomear` primeiro.",
				ephemeral=True,
			)

		if (
			cargo_novo is None
			or cargo_novo.id not in {
				role.id
				for role in roles.values()
			}
		):
			return await interaction.response.send_message(
				"O cargo selecionado não pertence à hierarquia "
				"da Moderação.",
				ephemeral=True,
			)

		if cargo_novo.id == roles.get("Militar", discord.Object(0)).id:
			return await interaction.response.send_message(
				"O cargo Militar não é um posto da hierarquia.",
				ephemeral=True,
			)

		if promocao:
			if cargo_novo.position <= cargo_atual.position:
				return await interaction.response.send_message(
					"O cargo escolhido deve ser superior "
					"ao cargo atual.",
					ephemeral=True,
				)

			titulo = "Promoção na Moderação"

		else:
			if cargo_novo.position >= cargo_atual.position:
				return await interaction.response.send_message(
					"O cargo escolhido deve ser inferior "
					"ao cargo atual.",
					ephemeral=True,
				)

			titulo = "Rebaixamento na Moderação"

		await self.change_roles(
			interaction=interaction,
			membro=membro,
			cargo_novo=cargo_novo,
			titulo=titulo,
			motivo=motivo,
		)

	@moderacao_group.command(
		name="promover",
		description="Promove um membro a um cargo superior da Moderação.",
	)
	@app_commands.describe(
		membro="Membro que será promovido",
		cargo="Novo cargo",
		motivo="Motivo da promoção",
	)
	@app_commands.choices(
		cargo = [
			app_commands.Choice(
				name=nome,
				value=str(dados["id"]),
			)
			for nome, dados in get_config()["cargos"]
			.get("moderativos", {})
			.items()
			if nome not in ["Militar", "Soldado"]
		]
	)
	async def promover(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
		cargo: str,
		motivo: str | None = None,
	):

		cargo_id = cargo

		await self.set_rank(
			interaction,
			membro,
			cargo_id,
			promocao=True,
			motivo=motivo,
		)

	@moderacao_group.command(
		name="rebaixar",
		description="Rebaixa um membro a um cargo inferior da Moderação.",
	)
	@app_commands.describe(
		membro="Membro que será rebaixado",
		cargo="Novo cargo",
		motivo="Motivo do rebaixamento",
	)
	@app_commands.choices(
		cargo = [
			app_commands.Choice(
				name=nome,
				value=str(dados["id"]),
			)
			for nome, dados in get_config()["cargos"]
			.get("moderativos", {})
			.items()
			if nome not in ["Militar", "Comandante"]
		]
	)
	async def rebaixar(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
		cargo: str,
		motivo: str | None = None,
	):
		await self.set_rank(
			interaction,
			membro,
			cargo,
			promocao=False,
			motivo=motivo,
		)

	# ============================================================
	# DISPENSA
	# ============================================================

	@moderacao_group.command(
		name="dispensar",
		description="Remove os cargos de um membro da Moderação.",
	)
	@app_commands.describe(
		membro="Membro que será dispensado",
		motivo="Motivo da dispensa",
	)
	async def dispensar(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
		motivo: str | None = None,
	):
		if not await self.can_manage_member(
			interaction,
			membro,
		):
			return

		if not self.get_rank(
			membro,
			interaction.guild,
		):
			return await interaction.response.send_message(
				f"{membro.mention} não faz parte da Moderação.",
				ephemeral=True,
			)

		await self.change_roles(
			interaction=interaction,
			membro=membro,
			cargo_novo=None,
			titulo="Dispensa da Moderação",
			motivo=motivo,
		)


async def setup(bot: Bot):
	await bot.add_cog(ModeracaoCog(bot))