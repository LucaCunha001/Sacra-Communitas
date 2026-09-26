import chat_exporter
import datetime
import discord
import io
import unicodedata

from bs4 import BeautifulSoup
from discord import ui
from discord import app_commands

from typing import Union

from utils.data import get_config
from utils.recursos import Bot, _personalize_transcript

class AprovarIntencao(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	async def disable_all(self):
		for btn in self.children:
			btn.disabled = True

	@discord.ui.button(
		label="Aprovar", style=discord.ButtonStyle.green, custom_id="aprov"
	)
	async def aprovar(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		config = get_config()
		await interaction.client.get_channel(config["canais"]["intencoes"]).send(
			content="@everyone", embeds=interaction.message.embeds
		)
		await self.disable_all()
		await interaction.response.edit_message(view=self, content="Intenção aprovada!")

	@discord.ui.button(
		label="Desaprovar", style=discord.ButtonStyle.gray, custom_id="desaprov"
	)
	async def desaprovar(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		await self.disable_all()
		await interaction.response.edit_message(
			view=self, content="Intenção desaprovada."
		)


class TipoPedidoView(discord.ui.View):
	opcoes = [
		["🌐", "Pública"],
		["👤", "Anônima"],
	]

	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.button(
		style=discord.ButtonStyle.blurple,
		label=opcoes[0][1],
		custom_id="pub",
		emoji=opcoes[0][0],
	)
	async def publica(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		await self.callback(interaction=interaction, type=0)

	@discord.ui.button(
		style=discord.ButtonStyle.gray,
		label=opcoes[1][1],
		custom_id="ano",
		emoji=opcoes[1][0],
	)
	async def anonima(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		await self.callback(interaction=interaction, type=1)

	async def callback(self, interaction: discord.Interaction, type: int):
		config = get_config()
		embed = interaction.message.embeds[0]
		if type == 0:
			embed.description += f"\n\nPedido solicitado por {interaction.user.mention}"
			embed.set_thumbnail(url=interaction.user.display_avatar)
			embed.set_author(
				name=interaction.user.name, icon_url=interaction.user.display_avatar
			)

		solicitacoes = config["canais"]["intencoes_solicitacoes"]
		await interaction.client.get_channel(solicitacoes).send(
			embed=embed, view=AprovarIntencao()
		)
		await interaction.response.edit_message(
			content=f"Sua intenção foi enviada ao Clero. Se for considerada urgente, ela será exibida em <#{config['canais']['intencoes']}>",
			view=None,
		)


class PedidoModal(discord.ui.Modal):
	def __init__(self):
		super().__init__(title="Pedido de Oração", timeout=None, custom_id="pedido")

	intencao = discord.ui.TextInput(
		label="Sua intenção", style=discord.TextStyle.long, custom_id="intencao"
	)

	async def on_submit(self, interaction: discord.Interaction):
		from utils.embed import criar_embed

		embed = criar_embed(
			titulo="Pedido de Oração",
			descricao=self.intencao.value,
			cor=0xFFCC00,
			footer="Intenções",
			servidor=interaction.guild,
		)
		await interaction.response.send_message(
			embeds=[embed], ephemeral=True, view=None
		)


def _get_ticket_type_by_emoji(channel_name: str) -> str:
	if not channel_name:
		return "Geral"

	emoji = channel_name.split("・", 1)[0].strip()
	type_map = {
		"🚨": "Denúncia",
		"🤝": "Parceria",
		"💌": "Contato com a Administração",
		"📜": "Secretaria",
		"📖": "Teologia",
	}
	return type_map.get(emoji, "Geral")


def _get_ticket_message_specs(ticket_type: str = "geral") -> dict:
	defaults = {
		"geral": {
			"title": "Bem-vindo ao Suporte",
			"description": (
				"Olá! Este é o seu canal de suporte.\n\n"
				"**Como funciona:**\n"
				"1 - Explique seu problema com detalhes.\n"
				"2 - Um membro da equipe irá te atender em breve.\n"
				"3 - Seja paciente e respeitoso.\n\n"
				"⚠️ Uso indevido do ticket pode resultar em punições."
			),
			"color": 0xFFCC00,
		},
		"denuncia": {
			"title": "🚨 Ticket de Denúncia",
			"description": (
				"Olá! Este canal foi aberto para registrar sua denúncia.\n\n"
				"**Importante:**\n"
				"1 - Descreva o ocorrido com o máximo de clareza.\n"
				"2 - Informe dados relevantes, horários e envolvidos.\n"
				"3 - Aguarde a análise da equipe responsável.\n\n"
				"⚠️ Mantenha um tom respeitoso e objetivo durante o atendimento."
			),
			"color": 0xE74C3C,
		},
		"parceria": {
			"title": "🤝 Ticket de Parceria",
			"description": (
				"Olá! Este canal foi aberto para tratar de parcerias e convênios.\n\n"
				"**Como prosseguir:**\n"
				"1 - Apresente sua proposta ou intenção.\n"
				"2 - Compartilhe detalhes sobre a iniciativa ou organização.\n"
				"3 - Aguarde o retorno da equipe para continuar o contato.\n\n"
				"⚠️ Seja claro, profissional e objetivo em sua mensagem."
			),
			"color": 0x2ECC71,
		},
		"contato": {
			"title": "💌 Contato com a Administração",
			"description": (
				"Olá! Este canal foi aberto para o contato direto com a administração.\n\n"
				"**Antes de enviar:**\n"
				"1 - Explique sua dúvida, sugestão ou solicitação.\n"
				"2 - Informe os detalhes que possam ajudar no atendimento.\n"
				"3 - Aguarde o retorno da equipe.\n\n"
				"⚠️ Mantenha uma comunicação respeitosa e objetiva."
			),
			"color": 0x5DADE2,
		},
		"secretaria": {
			"title": "📜 Ticket da Secretaria",
			"description": (
				"Olá! Este é o canal de atendimento da secretaria.\n\n"
				"**Como funciona:**\n"
				"1 - Descreva sua demanda ou solicitação.\n"
				"2 - Aguarde a análise e o retorno da equipe.\n"
				"3 - Seja claro e respeitoso durante a conversa."
			),
			"color": 0xF1C40F,
		},
		"teologia": {
			"title": "📖 Ticket de Teologia",
			"description": (
				"Olá! Este é o canal de atendimento da equipe teológica.\n\n"
				"**Como funciona:**\n"
				"1 - Compartilhe sua dúvida ou intenção.\n"
				"2 - Aguarde a análise e o retorno da equipe.\n"
				"3 - Mantenha um diálogo respeitoso e objetivo."
			),
			"color": 0x8E44AD,
		},
	}
	return defaults.get(ticket_type, defaults["geral"]) 


class TicketSelectMenu(discord.ui.Select):
	def __init__(self, bot: Bot):
		super().__init__(
			custom_id="ticket_select_menu",
			placeholder="Escolha uma opção para abrir um ticket",
			min_values=1,
			max_values=1,
		)

		self.opcoes = [
			["🚨", "Denúncia", "denuncia"],
			["🤝", "Parceria", "parceria"],
			["🙏", "Pedidos de Oração", "oracao", "Caso considere sua intenção com urgente."],
			["💌", "Contato com a Administração", "contato"],
		]

		for opcao in self.opcoes:
			self.add_option(
				label=opcao[1],
				emoji=opcao[0],
				value=opcao[2],
				description="" if len(opcao) < 3 else None,
			)

		self.bot = bot

	async def callback(self, interaction: discord.Interaction):
		canais = interaction.guild.text_channels
		if any(canal.topic == str(interaction.user.id) for canal in canais):
			return await interaction.response.send_message(
				"Você já tem um ticket aberto! Para abrir outro, finalize o primeiro antes.",
				ephemeral=True,
			)

		ticket_type = self.values[0]
		
		if ticket_type == "oracao":
			if self.bot.config["canais"].get("intencoes") is None:
				return await interaction.response.send_message(
					"Ainda não foi configurado o sistema de intenções. Aguarde um pouco.",
					ephemeral=True,
				)
			return await interaction.response.send_modal(PedidoModal())
		
		channel_name = f"{self.get_emoji_for_type(ticket_type)}・{interaction.user.name}"
		await create_ticket_channel(
			self.bot,
			interaction,
			channel_name,
			ticket_type=ticket_type,
		)

	def get_emoji_for_type(self, ticket_type: str) -> str:
		mapping = {
			"denuncia": "🚨",
			"parceria": "🤝",
			"contato": "💌",
		}
		return mapping.get(ticket_type, "🎟️")


async def create_ticket_channel(
	bot: Bot,
	interaction: discord.Interaction,
	channel_name: str,
	ticket_type: str = "geral",
):
	config = bot.config
	ticket_category = interaction.guild.get_channel(
		config["canais"]["categoria_tickets"]
	)
	ticket_channel = await ticket_category.create_text_channel(
		name=channel_name,
		topic=str(interaction.user.id)
	)
	overwrite = discord.PermissionOverwrite(send_messages=True, view_channel=True, attach_files=True, embed_links=True)
	await ticket_channel.set_permissions(interaction.user, overwrite=overwrite)

	confirm_view = ui.LayoutView(timeout=None)
	confirm_container = ui.Container(
		ui.Section(
			ui.TextDisplay("## ✅ Ticket criado com sucesso!"),
			accessory=ui.Thumbnail(interaction.guild.icon.url)
			if interaction.guild.icon
			else None,
		),
		ui.Separator(spacing=discord.SeparatorSpacing.large),
		ui.TextDisplay("Seu ticket foi criado e está pronto para atendimento."),
		accent_color=0xFFCC00,
	)
	confirm_button = ui.Button(
		label="Acessar ticket",
		style=discord.ButtonStyle.link,
		url=ticket_channel.jump_url,
		emoji="🔗",
	)
	confirm_container.add_item(ui.ActionRow(confirm_button))
	confirm_view.add_item(confirm_container)

	await interaction.response.send_message(view=confirm_view, ephemeral=True)

	cargos_staffs = config["cargos"]["sacerdotes"]
	clero = interaction.guild.get_role(cargos_staffs["Clero"]["id"])
	seminarista = interaction.guild.get_role(cargos_staffs["Seminarista"]["id"])

	await ticket_channel.set_permissions(clero, overwrite=overwrite)
	overwrite.send_messages = False
	await ticket_channel.set_permissions(seminarista, overwrite=overwrite)

	ticket_view = TicketView(bot=bot, user=interaction.user, ticket_type=ticket_type)
	await ticket_channel.send(
		view=ticket_view,
	)


class OpenTicketView(ui.LayoutView):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		container = ui.Container(
			ui.Section(
				ui.TextDisplay("## Sistema de tickets"),
				accessory=ui.Thumbnail(bot.guild_icon) if bot.guild_icon else None,
			),
			ui.Separator(spacing=discord.SeparatorSpacing.large),
			ui.TextDisplay(
				"Precisa de ajuda? Nossa equipe está pronta para te atender!\n\n"
				"1 - Clique no menu abaixo para abrir um ticket.\n"
				"2 - Aguarde um membro da equipe responder.\n"
				"3 - Explique sua dúvida ou problema com clareza.\n\n"
				"⚠️ Uso indevido pode resultar em punições."
			),
			ui.ActionRow(TicketSelectMenu(bot=bot)),
			accent_color=0xFFCC00,
		)
		self.add_item(container)


class TicketView(ui.LayoutView):
	def __init__(self, bot: Bot, user: discord.User, ticket_type: str = "geral"):
		super().__init__(timeout=None)
		self.bot = bot
		self.ticket_type = ticket_type
		specs = _get_ticket_message_specs(ticket_type)
		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"## {specs['title']}"),
				accessory=ui.Thumbnail(bot.guild_icon),
			),
			ui.Separator(spacing=discord.SeparatorSpacing.large),
			ui.TextDisplay(f"@everyone {user.mention}"),
			ui.TextDisplay(specs["description"]),
			ui.TextDisplay("-# Sitema de ticket da Sacra Communitas"),
			accent_color=specs["color"],
		)

		fechar_btn = ui.Button(
			label="Fechar Ticket",
			style=discord.ButtonStyle.blurple,
			custom_id="fechar",
			emoji="🔒",
		)
		fechar_btn.callback = self.fechar

		add_btn = ui.Button(
			label="Adicionar Membro",
			style=discord.ButtonStyle.green,
			custom_id="add_member",
			emoji="➕",
		)
		add_btn.callback = self.add_member

		remove_btn = ui.Button(
			label="Remover Membro",
			style=discord.ButtonStyle.red,
			custom_id="remove_member",
			emoji="➖",
		)
		remove_btn.callback = self.remove_member

		ping_btn = ui.Button(
			label="Pingar",
			style=discord.ButtonStyle.gray,
			custom_id="ping",
			emoji="🔔",
		)
		ping_btn.callback = self.ping_member
		
		container.add_item(ui.ActionRow(fechar_btn, add_btn, remove_btn, ping_btn))
		self.add_item(container)

	async def fechar(self, interaction: discord.Interaction):
		if (
			not any(
				role.id == get_config()["cargos"]["sacerdotes"]["Clero"]
				for role in interaction.user.roles
			)
			and not interaction.permissions.administrator
		):
			return await interaction.response.send_message(
				'Ei... O que pensa que está fazendo? Membros não podem fechar tickets! Não queremos que alguém mal intencionado fuja de uma situação... "apertada", digamos assim.',
				ephemeral=True,
			)
		await self.fechar_ticket(channel=interaction.channel, staff=interaction.user)

	async def add_member(self, interaction: discord.Interaction):
		modal = AddMemberModal(interaction.channel)
		await interaction.response.send_modal(modal)

	async def remove_member(self, interaction: discord.Interaction):
		modal = RemoveMemberModal(interaction.channel)
		await interaction.response.send_modal(modal)

	async def ping_member(self, interaction: discord.Interaction):
		now = datetime.datetime.now(datetime.timezone.utc)
		if now.hour < 7:
			return await interaction.response.send_message(
				"O sistema de ping está bloqueado antes das 7h da manhã.",
				ephemeral=True,
			)

		history = [msg async for msg in interaction.channel.history(limit=50)]
		last_bot_ping = None
		for msg in history:
			if msg.author == interaction.client.user and "precisamos continuar o ticket!" in msg.content:
				last_bot_ping = msg
				break

		if last_bot_ping is not None:
			elapsed = now - last_bot_ping.created_at
			if elapsed < datetime.timedelta(hours=1):
				return await interaction.response.send_message(
					"Este ticket já recebeu um ping do bot há menos de 1 hora.",
					ephemeral=True,
				)

		messages = [msg for msg in history if not msg.author.bot]
		ping_target = None

		seen_authors = []
		seen_ids = set()
		for msg in messages:
			author = msg.author
			if author.id in seen_ids:
				continue
			seen_authors.append(author)
			seen_ids.add(author.id)
			if len(seen_authors) >= 2:
				break

		if len(seen_authors) >= 2:
			ping_target = seen_authors[1]
		else:
			clero_role = interaction.guild.get_role(
				get_config()["cargos"]["sacerdotes"]["Clero"]["id"]
			)
			if clero_role and not any(
				role.id == clero_role.id for role in interaction.user.roles
			):
				ping_target = clero_role
			else:
				ticket_owner = self._get_ticket_owner(interaction.channel)
				ping_target = ticket_owner

		if ping_target is None:
			return await interaction.response.send_message(
				"Não foi possível identificar o alvo do ping no momento.",
				ephemeral=True,
			)

		await interaction.response.send_message(
			f"{ping_target.mention}, precisamos continuar o ticket!",
			allowed_mentions=discord.AllowedMentions.all(),
		)

	async def fechar_ticket(self, channel: discord.TextChannel, staff: discord.User):
		ticket_owner = self._get_ticket_owner(channel)
		mensagens = await self._count_messages(channel)
		transcript_html = await self._generate_transcript(channel, mensagens)
		await self._send_transcripts(ticket_owner, transcript_html, channel, staff)
		await channel.delete()

	def _get_ticket_owner(
		self, channel: discord.TextChannel
	) -> Union[discord.User, "TicketView._FakeUser"]:
		try:
			user_id = int(channel.topic.splitlines()[0])
			user = self.bot.get_user(user_id)
			if not user:
				raise AttributeError
			return user
		except AttributeError:
			return self._FakeUser(user_id)

	def _create_ticket_log_view(
		self,
		channel: discord.TextChannel,
		qm_abriu: discord.User,
		qm_fechou: discord.User,
		transcript: discord.File
	) -> ui.LayoutView:
		view = ui.LayoutView(timeout=None)
		ticket_type = _get_ticket_type_by_emoji(channel.name)
		container = ui.Container(
			ui.Section(
				ui.TextDisplay("## Ticket Finalizado"),
				accessory=ui.Thumbnail(channel.guild.icon.url) if channel.guild.icon else None,
			),
			ui.Separator(spacing=discord.SeparatorSpacing.large),
			ui.TextDisplay(
				f"**Tipo:** {ticket_type}\n"
				f"**Aberto por:** {qm_abriu.mention}\n"
				f"**Fechado por:** {qm_fechou.mention}\n"
				f"**ID do ticket:** `{channel.id}`\n"
				f"**Data:** {discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc), style='F')}"
			),
			ui.TextDisplay("-# Sistema de Gerenciamento de Tickets"),
			ui.File(transcript),
			accent_color=0xFFCC00,
		)
		view.add_item(container)
		return view

	async def _count_messages(self, channel: discord.TextChannel) -> int:
		return len([msg async for msg in channel.history(limit=None)])

	async def _generate_transcript(
		self, channel: discord.TextChannel, mensagens: int
	) -> str:
		msg_count = len([msg async for msg in channel.history(limit=None)])
		transcript = await chat_exporter.export(
			channel,
			limit=msg_count,
			tz_info="America/Sao_Paulo",
			military_time=True,
			bot=self.bot,
		)
		soup = BeautifulSoup(transcript, "html.parser")
		_personalize_transcript(soup, channel, mensagens)
		return str(soup)

	async def _send_transcripts(
		self,
		qm_abriu: Union[discord.User, "TicketView._FakeUser"],
		transcript_html: str,
		channel: discord.TextChannel,
		staff: discord.User,
	):
		file = discord.File(
			io.BytesIO(transcript_html.encode()), filename=f"ticket-{channel.id}.html"
		)
		user_log_view = self._create_ticket_log_view(channel, qm_abriu, staff, file)
		try:
			await qm_abriu.send(view=user_log_view, file=file)
		except discord.Forbidden:
			print("Não consegui enviar a DM ao usuário, permissão negada.")
		except discord.NotFound:
			print("Não consegui enviar a DM ao usuário, ele não foi encontrado.")
		except Exception as e:
			print(f"Erro ao enviar a DM: {e}")

		config = get_config()
		log_channel = self.bot.get_channel(config["logs"]["ticket_logs"])
		if log_channel:
			log_view = self._create_ticket_log_view(channel, qm_abriu, staff, file)
			await log_channel.send(view=log_view, file=file)

	class _FakeUser:
		def __init__(self, id_):
			self.mention = f"<@{id_}>"
			self.id = id_

		async def send(self, *args, **kwargs):
			raise discord.NotFound(response=None, message="Usuário não encontrado")


class AddMemberModal(discord.ui.Modal):
	def __init__(self, channel: discord.TextChannel):
		super().__init__(title="Adicionar Membro")
		self.channel = channel
		self.user_select = discord.ui.UserSelect(
			custom_id="add_member_user_select",
			placeholder="Selecione o usuário para adicionar",
			min_values=1,
			max_values=1,
		)
		self.add_item(
			discord.ui.Label(
				text="Usuário",
				description="Selecione quem deve entrar no ticket.",
				component=self.user_select,
			)
		)

	async def on_submit(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True)
		guild = interaction.guild
		try:
			selected_user = self.user_select.values[0]
			member = guild.get_member(selected_user.id)
			if member:
				await self.channel.set_permissions(
					member, read_messages=True, send_messages=True
				)
				layout = ui.LayoutView(timeout=None)
				container = ui.Container(
					ui.Section(
						ui.TextDisplay("## ✅ Membro adicionado"),
						accessory=ui.Thumbnail(member.display_avatar.url),
					),
					ui.Separator(spacing=discord.SeparatorSpacing.large),
					ui.TextDisplay(f"{member.mention} entrou no ticket com sucesso."),
					accent_color=0x2ECC71,
				)
				layout.add_item(container)
				await interaction.followup.send(view=layout, ephemeral=True)
			else:
				error_layout = ui.LayoutView(timeout=None)
				error_container = ui.Container(
					ui.Section(
						ui.TextDisplay("## ⚠️ Usuário não encontrado"),
						accessory=ui.Thumbnail(interaction.guild.icon.url) if interaction.guild.icon else None,
					),
					ui.Separator(spacing=discord.SeparatorSpacing.large),
					ui.TextDisplay("Não foi possível localizar esse usuário no servidor."),
					accent_color=0xE74C3C,
				)
				error_layout.add_item(error_container)
				await interaction.followup.send(view=error_layout, ephemeral=True)
		except Exception as e:
			error_layout = ui.LayoutView(timeout=None)
			error_container = ui.Container(
				ui.Section(
					ui.TextDisplay("## ❌ Erro ao adicionar membro"),
					accessory=ui.Thumbnail(interaction.guild.icon.url) if interaction.guild.icon else None,
				),
				ui.Separator(spacing=discord.SeparatorSpacing.large),
				ui.TextDisplay(f"Erro: {e}"),
				accent_color=0xE74C3C,
			)
			error_layout.add_item(error_container)
			await interaction.followup.send(view=error_layout, ephemeral=True)


class RemoveMemberModal(discord.ui.Modal):
	def __init__(self, channel: discord.TextChannel):
		super().__init__(title="Remover Membro")
		self.channel = channel
		self.user_select = discord.ui.UserSelect(
			custom_id="remove_member_user_select",
			placeholder="Selecione o usuário para remover",
			min_values=1,
			max_values=1,
		)
		self.add_item(
			discord.ui.Label(
				text="Usuário",
				description="Selecione quem deve sair do ticket.",
				component=self.user_select,
			)
		)

	async def on_submit(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True)
		guild = interaction.guild
		try:
			selected_user = self.user_select.values[0]
			member = guild.get_member(selected_user.id)
			if member:
				await self.channel.set_permissions(member, overwrite=None)
				layout = ui.LayoutView(timeout=None)
				container = ui.Container(
					ui.Section(
						ui.TextDisplay("## ✅ Membro removido"),
						accessory=ui.Thumbnail(member.display_avatar.url),
					),
					ui.Separator(spacing=discord.SeparatorSpacing.large),
					ui.TextDisplay(f"{member.mention} saiu do ticket com sucesso."),
					accent_color=0xE74C3C,
				)
				layout.add_item(container)
				await interaction.followup.send(view=layout, ephemeral=True)
			else:
				error_layout = ui.LayoutView(timeout=None)
				error_container = ui.Container(
					ui.Section(
						ui.TextDisplay("## ⚠️ Usuário não encontrado"),
						accessory=ui.Thumbnail(interaction.guild.icon.url) if interaction.guild.icon else None,
					),
					ui.Separator(spacing=discord.SeparatorSpacing.large),
					ui.TextDisplay("Não foi possível localizar esse usuário no servidor."),
					accent_color=0xE74C3C,
				)
				error_layout.add_item(error_container)
				await interaction.followup.send(view=error_layout, ephemeral=True)
		except Exception as e:
			error_layout = ui.LayoutView(timeout=None)
			error_container = ui.Container(
				ui.Section(
					ui.TextDisplay("## ❌ Erro ao remover membro"),
					accessory=ui.Thumbnail(interaction.guild.icon.url) if interaction.guild.icon else None,
				),
				ui.Separator(spacing=discord.SeparatorSpacing.large),
				ui.TextDisplay(f"Erro: {e}"),
				accent_color=0xE74C3C,
			)
			error_layout.add_item(error_container)
			await interaction.followup.send(view=error_layout, ephemeral=True)


class TicketsCommands(app_commands.Group):
	def __init__(self):
		super().__init__(name="ticket", description="Comandos relacionados a tickets.")

	@app_commands.command(name="message", description="Mensagem dos tickets")
	async def message_ticket(self, interaction: discord.Interaction):
		embed = discord.Embed(
			title="Sistema de tickets",
			description="Precisa de ajuda? Nossa equipe está pronta para te atender!",
			color=interaction.user.color,
		)
		embed.set_thumbnail(url=interaction.client.guild_icon)
		embed.add_field(
			name="Como funciona?",
			value="1 - Clique no botão abaixo para abrir um ticket.\n2 - Aguarde um membro da equipe responder.\n3 - Explique sua dúvida ou problema com clareza.\n\n⚠️ Uso indevido pode resultar em punições.",
		)
		view = OpenTicketView(bot=interaction.client)
		await interaction.channel.purge(limit=None)
		await interaction.channel.send(view=view)
		await interaction.response.send_message(
			"Mensagem enviada com sucesso!", ephemeral=True
		)
