import chat_exporter
import datetime
import discord
import io

from bs4 import BeautifulSoup
from discord import app_commands
from utils.data import get_config
from utils.recursos import Bot
from utils.permissoes import verificar_permissao
from utils.embed import criar_embed
from typing import Union

guild_ids = [get_config()["config"]["servidores"]["main"]]

class AprovarIntencao(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)
	
	async def disable_all(self):
		for btn in self.children:
			btn: discord.ui.Button
			btn.disabled = True

	@discord.ui.button(label="Aprovar", style=discord.ButtonStyle.green, custom_id="aprov")
	async def aprovar(self, interaction: discord.Interaction, button: discord.Button):
		config = get_config()
		await interaction.client.get_channel(config['canais']['intencoes']).send(content=interaction.guild.default_role.mention, embeds=interaction.message.embeds)
		await self.disable_all()
		await interaction.response.edit_message(view=self, embeds=interaction.message.embeds, content="Intenção aprovada!")

	@discord.ui.button(label="Desaprovar", style=discord.ButtonStyle.gray, custom_id="desaprov")
	async def desaprovar(self, interaction: discord.Interaction, button: discord.Button):
		await self.disable_all()
		await interaction.response.edit_message(view=self, embeds=interaction.message.embeds, content="Intenção desaprovada.")

class TipoPedidoView(discord.ui.View):
	opcoes = [
		["🌐", "Pública"],
		["👤", "Anônima"]
	]
	
	def __init__(self):
		super().__init__(timeout=None)
	
	@discord.ui.button(style=discord.ButtonStyle.blurple,
					label=opcoes[0][1], custom_id="pub", emoji=opcoes[0][0])
	async def publica(self, interacion: discord.Interaction, button: discord.Button):
		await self.callback(interaction=interacion, type=0)
	
	@discord.ui.button(style=discord.ButtonStyle.gray,
					label=opcoes[1][1], custom_id="ano", emoji=opcoes[1][0])
	async def anonima(self, interacion: discord.Interaction, button: discord.Button):
		await self.callback(interaction=interacion, type=1)


	async def callback(self, interaction: discord.Interaction, type: int):
		config = get_config()
		
		embed = interaction.message.embeds[0]
		if type == 0:
			embed.description += f"\n\nPedido solicitado por {interaction.user.mention}"
			embed.set_thumbnail(url=interaction.user.display_avatar)
			embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)

		solicitacoes = config['canais']['intencoes_solicitacoes']
		await interaction.client.get_channel(solicitacoes).send(embed=embed, view=AprovarIntencao())

		await interaction.response.edit_message(content=f"Sua intenção foi enviada ao Clero. Se for considerada urgente, ela será exibida em <#{config['canais']['intencoes']}>", view=None)

class PedidoModal(discord.ui.Modal):
	def __init__(self):
		super().__init__(title="Pedido de Oração", timeout=None, custom_id="pedido")

	intencao = discord.ui.TextInput(label="Sua intenção", style=discord.TextStyle.long, custom_id="intencao")

	async def on_submit(self, interaction: discord.Interaction):
		embed = criar_embed(titulo="Pedido de Oração", descricao=self.intencao.value, cor=0xffcc00, footer="Intenções", servidor=interaction.guild)

		embed_type = discord.Embed(
			title="Tipo de intenção",
			description="Que tipo de intenção você quer solicitar?"
		)

		await interaction.response.send_message(embeds=[embed, embed_type], ephemeral=True, view=TipoPedidoView())

class TicketSelectMenu(discord.ui.Select):
	def __init__(self, bot: Bot):
		super().__init__(
			custom_id="ticket_select_menu",
			placeholder="Escolha uma opção para abrir um ticket",
			min_values=1,
			max_values=1,
		)

		self.opcoes = [
			["🚨", "Denúncia"],
			["🤝", "Parceria"],
			["🙏", "Pedidos de Oração", "Caso considere sua intenção com urgente."],
			["💌", "Contato com a Administração"]
		]

		for i, opcao in enumerate(self.opcoes):
			self.add_option(label=opcao[1], emoji=opcao[0], value=str(i), description=opcao[2] if len(opcao) == 3 else None)

		self.bot = bot

	async def callback(self, interaction: discord.Interaction):
		canais = interaction.guild.text_channels
		if any(canal.topic == str(interaction.user.id) for canal in canais):
			return await interaction.response.send_message(
				"Você já tem um ticket aberto! Para abrir outro, finalize o primeiro antes.",
				ephemeral=True,
			)

		config = get_config()

		if self.values[0] == str(2):
			if config["canais"].get("intencoes") is None:
				return interaction.response.send_message("Ainda não foi configurado o sistema de intenções. Aguarde um pouco.", ephemeral=True)

			return await interaction.response.send_modal(PedidoModal())

		channel_name = f"{self.opcoes[int(self.values[0])][0]}・{interaction.user.name}"

		await create_ticket_channel(self.bot, interaction, channel_name)

async def create_ticket_channel(bot: Bot, interaction: discord.Interaction, channel_name: str):
	config = bot.config

	ticket_category = interaction.guild.get_channel(
		config["canais"]["categoria_tickets"]
	)
	ticket_channel = await ticket_category.create_text_channel(name=channel_name)
	await ticket_channel.edit(topic=str(interaction.user.id))

	overwrite = discord.PermissionOverwrite(send_messages=True, view_channel=True)

	cargos_staffs = config["cargos"]["sacerdotes"]

	await ticket_channel.set_permissions(interaction.user, overwrite=overwrite)

	embed_response = discord.Embed(
		title="✅ Ticket criado com sucesso!",
		description="Seu ticket foi criado:",
		colour=0xffcc00,
	)
	view = discord.ui.View()
	view.add_item(
		discord.ui.Button(
			label="Acessar ticket",
			style=discord.ButtonStyle.link,
			url=ticket_channel.jump_url,
		)
	)

	await interaction.response.send_message(
		embed=embed_response, ephemeral=True, view=view
	)

	for _, cargos_staff in cargos_staffs.items():
		role = interaction.guild.get_role(cargos_staff["id"])
		if verificar_permissao("atender_tickets", role):
			await ticket_channel.set_permissions(role, overwrite=overwrite)

	if channel_name.startswith("📜"):
		description = (
			"Olá! Este é o seu canal de suporte.\n\n"
			"**Como funciona:**\n"
			"1 - Apresente-se e explique o porquê de achar ser um bom candidato.\n"
			"2 - Um membro da equipe irá te atender em breve.\n"
			"3 - Seja paciente e respeitoso.\n\n"
			"⚠️ Uso indevido do ticket pode resultar em punições."
		)
	else:
		description=(
			"Olá! Este é o seu canal de suporte.\n\n"
			"**Como funciona:**\n"
			"1 - Explique seu problema com detalhes.\n"
			"2 - Um membro da equipe irá te atender em breve.\n"
			"3 - Seja paciente e respeitoso.\n\n"
			"⚠️ Uso indevido do ticket pode resultar em punições."
		)

	embed_ticket = discord.Embed(
		title="Bem-vindo ao Suporte",
		description=description,
		colour=0xffcc00,
	)
	embed_ticket.set_footer(text=f"Ticket de {interaction.user.display_name}")
	embed_ticket.set_thumbnail(url=interaction.guild.icon.url)

	await ticket_channel.send(
		content=f"{interaction.guild.default_role.mention} {interaction.user.mention}",
		embed=embed_ticket,
		view=TicketView(bot),
	)


class OpenTicketView(discord.ui.View):
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.add_item(TicketSelectMenu(bot=bot))


class TicketView(discord.ui.View):
	def __init__(self, bot: discord.Client):
		super().__init__(timeout=None)
		self.bot = bot

	@discord.ui.button(
		label="Fechar Ticket", style=discord.ButtonStyle.blurple, custom_id="fechar"
	)
	async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not any(
			role.id == get_config()["cargos"]["sacerdotes"]["Clero"] for role in interaction.user.roles
		) and not interaction.permissions.administrator:
			return await interaction.response.send_message(
				'Ei... O que pensa que está fazendo? Membros não podem fechar tickets! Não queremos que alguém mal intencionado fuja de uma situação... "apertada", digamos assim.\n\nSe já encerraram, marque o staff responsável pelo ticket.',
				ephemeral=True,
			)

		await self.fechar_ticket(channel=interaction.channel, staff=interaction.user)

	@discord.ui.button(
		label="Adicionar Membro",
		style=discord.ButtonStyle.green,
		custom_id="add_member",
	)
	async def add_member(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		modal = AddMemberModal(interaction.channel)
		await interaction.response.send_modal(modal)

	@discord.ui.button(
		label="Remover Membro", style=discord.ButtonStyle.red, custom_id="remove_member"
	)
	async def remove_member(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		modal = RemoveMemberModal(interaction.channel)
		await interaction.response.send_modal(modal)

	@discord.ui.button(label="Pingar", custom_id="ping", style=discord.ButtonStyle.gray)
	async def ping_member(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		config = get_config()

		historico: list[discord.Message] = [
			msg async for msg in interaction.channel.history()
		]
		author = None
		embed = discord.Embed(
			title="Ei, você está aí?",
			description="Precisamos continuar o ticket!",
			colour=0xffcc00,
		)
		embed.set_thumbnail(
			url="https://images.emojiterra.com/twitter/v13.1/512px/1f514.png"
		)

		for msg in historico:
			if msg.author.bot:
				continue
			if author != msg.author and author:
				return await interaction.response.send_message(
					msg.author.mention, embed=embed
				)
			author = msg.author

		if str(interaction.user.id) == interaction.channel.topic.splitlines()[0]:
			return await interaction.response.send_message(
				f"<@&{config['cargos']['sacerdotes']['Clero']['id']}>", embed=embed
			)

		return await interaction.response.send_message(
			f"<@{interaction.channel.topic}>", embed=embed
		)

	async def fechar_ticket(self, channel: discord.TextChannel, staff: discord.Member):
		qm_abriu = self._get_ticket_owner(channel)
		embed = self._create_ticket_embed(channel, qm_abriu, staff)

		await [msg async for msg in channel.history(limit=None)][-1].reply(embed=embed)

		mensagens = await self._count_messages(channel)
		transcript_html = await self._generate_transcript(channel, mensagens)

		await self._send_transcripts(qm_abriu, embed, transcript_html, channel)
		await channel.delete()

		tickets = self.bot.get_channel(get_config()["logs"]["ticket_logs"])
		await tickets.send(
			embed=embed,
			file=discord.File(
				io.BytesIO(transcript_html.encode()),
				filename=f"ticket-{channel.id}.html",
			),
		)

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

	def _create_ticket_embed(
		self,
		channel: discord.TextChannel,
		qm_abriu: discord.User,
		qm_fechou: discord.User,
	) -> discord.Embed:
		embed = discord.Embed(
			title="Ticket Finalizado",
			colour=0xffcc00,
			description="Um ticket foi finalizado e registrado no sistema.",
			timestamp=datetime.datetime.now(),
		)
		embed.add_field(name="Aberto por", value=qm_abriu.mention)
		embed.add_field(name="Fechado por", value=qm_fechou.mention)
		embed.add_field(name="ID do ticket", value=channel.id)
		embed.set_thumbnail(url=channel.guild.icon.url)
		embed.set_footer(text="Sistema de Gerenciamento de Tickets")
		return embed

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
		self._personalize_transcript(soup, channel, mensagens)
		return str(soup)

	def _personalize_transcript(
		self, soup: BeautifulSoup, channel: discord.TextChannel, mensagens: int
	):
		hoje = datetime.datetime.now()
		meses = [
			"janeiro",
			"fevereiro",
			"março",
			"abril",
			"maio",
			"junho",
			"julho",
			"agosto",
			"setembro",
			"outubro",
			"novembro",
			"dezembro",
		]
		data_formatada = f"{hoje.day} de {meses[hoje.month - 1].title()} de {hoje.year} às {hoje.hour:02d}:{hoje.minute:02d}:{hoje.second:02d}"
		titulo = f"Transcript do Ticket: {channel.name} - {channel.id}"

		for title in soup.find_all("title"):
			title.string = titulo

		for meta in soup.find_all("meta"):
			if meta.get("property") in ["og:title", "twitter:title"] or meta.get(
				"name"
			) in ["title", "og:title", "twitter:title"]:
				meta["content"] = titulo
			if meta.get("name") in [
				"description",
				"og:description",
				"twitter:description",
			] or meta.get("property") in [
				"description",
				"og:description",
				"twitter:description",
			]:
				meta["content"] = (
					f"Transcript do Ticket: {channel.name} - {channel.id}. Com {mensagens} mensagens. O transcript foi gerado em {data_formatada}"
				)

		traduzir = {
			"Summary": "Sumário",
			"Guild ID": "ID do Servidor",
			"Channel ID": "ID do Canal",
			"Channel Creation Date": "Data de Criação do Canal",
			"Total Message Count": "Quantidade Total de Mensagens",
			"Total Message Participants": "Total de Participantes nas Mensagens",
			"Member Since": "Membro Desde",
			"Member ID": "ID do Membro",
			"Message Count": "Quantidade de Mensagens",
		}

		for meta__value in soup.find_all("meta__value"):
			if meta__value.string and meta__value.string in traduzir:
				meta__value.string = traduzir[meta__value.string]

		for span in soup.find_all("span"):
			if span.string and span.string in traduzir:
				span.string = traduzir[span.string]
			if span.string:
				span.string = (
					span.string.replace("Today at", "Hoje às")
					.replace("Yesterday at", "Ontem às")
					.replace("Tomorrow at", "Amanhã às")
				)

		for span in soup.find_all("span", class_="info__title"):
			span.string = f"Bem-vindo ao canal #{channel.name}!"

		for span in soup.find_all("span", class_="info__subject"):
			span.string = (
				f"Essas são as últimas 200 mensagens do canal #{channel.name}."
			)

		for span in soup.find_all("span", class_="footer__text"):
			span.string = f"Esse transcript foi gerado em {data_formatada}"
		
		for style_tag in soup.find_all("style"):
			if style_tag.string:
				style_tag.string = style_tag.string.replace("#36393f", "#000")

		for tag in soup.find_all(style=True):
			tag["style"] = tag["style"].replace("#36393f", "#000")

	async def _send_transcripts(
		self,
		qm_abriu: Union[discord.User, "TicketView._FakeUser"],
		embed: discord.Embed,
		transcript_html: str,
		channel: discord.TextChannel,
	):
		file = discord.File(
			io.BytesIO(transcript_html.encode()), filename=f"ticket-{channel.id}.html"
		)
		try:
			await qm_abriu.send(embed=embed, file=file)
		except discord.Forbidden:
			print("Não consegui enviar a DM ao usuário, permissão negada.")
		except discord.NotFound:
			print("Não consegui enviar a DM ao usuário, ele não foi encontrado.")
		except Exception as e:
			print(f"Erro ao enviar a DM: {e}")

	class _FakeUser:
		def __init__(self, id_):
			self.mention = f"<@{id_}>"
			self.id = id_

		async def send(self, *args, **kwargs):
			raise discord.NotFound(response=None, message="Usuário não encontrado")

		def __str__(self):
			return self.mention


class AddMemberModal(discord.ui.Modal):
	def __init__(self, channel: discord.TextChannel):
		super().__init__(title="Adicionar Membro")
		self.channel = channel

		self.add_item(
			discord.ui.TextInput(
				label="ID do Usuário",
				placeholder="Digite o ID do usuário que deseja adicionar",
				style=discord.TextStyle.short,
			)
		)

	async def on_submit(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True)
		user_id = self.children[0].value.strip()
		guild = interaction.guild
		try:
			member = guild.get_member(int(user_id))
			if member:
				await self.channel.set_permissions(
					member, read_messages=True, send_messages=True
				)
				await interaction.followup.send(
					f"O membro {member.mention} foi adicionado ao ticket."
				)
			else:
				await interaction.followup.send(
					"Usuário não encontrado no servidor.", ephemeral=True
				)
		except Exception as e:
			await interaction.followup.send(
				f"Erro ao adicionar membro: {e}", ephemeral=True
			)


class RemoveMemberModal(discord.ui.Modal):
	def __init__(self, channel: discord.TextChannel):
		super().__init__(title="Remover Membro")
		self.channel = channel

		self.add_item(
			discord.ui.TextInput(
				label="ID do Usuário",
				placeholder="Digite o ID do usuário que deseja remover",
				style=discord.TextStyle.short,
			)
		)

	async def on_submit(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True)
		user_id = self.children[0].value.strip()
		guild = interaction.guild
		try:
			member = guild.get_member(int(user_id))
			if member:
				await self.channel.set_permissions(member, overwrite=None)
				await interaction.followup.send(
					f"O membro {member.mention} foi removido do ticket."
				)
			else:
				await interaction.followup.send(
					"Usuário não encontrado no servidor.", ephemeral=True
				)
		except Exception as e:
			await interaction.followup.send(
				f"Erro ao remover membro: {e}", ephemeral=True
			)


class TicketsCommands(app_commands.Group):
	def __init__(self):
		super().__init__(name="ticket", description="Comandos relacionados a tickets.")
	
	@app_commands.command(name="message", description="Mensagem dos tickets")
	async def message_ticket(self, interaction: discord.Interaction):
		embed = discord.Embed(
			title="Sistema de tickets",
			description="Precisa de ajuda? Nossa equipe está pronta para te atender!",
			color=interaction.user.color
		)
		embed.set_thumbnail(url=interaction.guild.icon.url)

		embed.add_field(name="Como funciona?", value="1 - Clique no botão abaixo para abrir um ticket.\n2 - Aguarde um membro da equipe responder.\n3 - Explique sua dúvida ou problema com clareza.\n\n⚠️ Uso indevido pode resultar em punições.")
		
		view = OpenTicketView(bot=interaction.client)

		await interaction.channel.purge(limit=None)
		await interaction.channel.send(embed=embed, view=view)
		await interaction.response.send_message("Mensagem enviada com sucesso!", ephemeral=True)

async def setup(bot: Bot):
	bot.tree.add_command(TicketsCommands())
	bot.add_view(TicketView(bot=bot))
	bot.add_view(OpenTicketView(bot=bot))
	bot.add_view(TipoPedidoView())
	bot.add_view(AprovarIntencao())