import aiohttp
import discord
import xml.etree.ElementTree as ET
import datetime

from email.utils import parsedate_to_datetime

from discord.ext import commands, tasks
from discord import app_commands, ui

from html import unescape
from html.parser import HTMLParser

from typing import TypedDict, Literal

from utils.recursos import Bot
from utils.data import get_connection
from utils.console import is_unix

RSS_FEED_URL = "https://www.vaticannews.va/pt.rss.xml"
VATICAN_NEWS_ICON = "https://yt3.googleusercontent.com/oUqd0UFUR4S99mrjuaWZNacoCKTlsFGwwFKNeDUwBOBAPd2NZt2GhrLKYDKAwTt9pbHrXbhZxw=s160-c-k-c0x00ffffff-no-rj"


class NewsConfig(TypedDict, total=False):
	ping: int
	ultimo_guid: str
	webhook_url: str
	canal: int


def get_news_config_db(guild_id: int) -> NewsConfig:
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM vatican_news_config WHERE guild_id = %s", (guild_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        return {
            "ping": row["ping"],
            "webhook_url": row["webhook_url"],
            "canal": row["canal"],
            "ultimo_guid": row["ultimo_guid"]
        }
    finally:
        cursor.close()
        conn.close()


def save_news_config_db(guild_id: int, config: NewsConfig):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vatican_news_config (guild_id, ping, webhook_url, canal, ultimo_guid)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                ping = VALUES(ping),
                webhook_url = VALUES(webhook_url),
                canal = VALUES(canal),
                ultimo_guid = VALUES(ultimo_guid)
        """, (
            guild_id,
            config.get("ping"),
            config.get("webhook_url"),
            config.get("canal"),
            config.get("ultimo_guid")
        ))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def carregar_ultimo_guid(guild_id: int) -> str | None:
	return get_news_config_db(guild_id).get("ultimo_guid")


def salvar_ultimo_guid(guild_id: int, guid: str):
	config = get_news_config_db(guild_id)
	config["ultimo_guid"] = guid
	save_news_config_db(guild_id, config)


class HTMLToDiscord(HTMLParser):
	def __init__(self):
		super().__init__()
		self.parts = []
		self.ignore_link = False

	def handle_starttag(self, tag, attrs):
		if tag == "a":
			self.ignore_link = True

	def handle_endtag(self, tag):
		if tag == "a":
			self.ignore_link = False

	def handle_data(self, data):
		if not self.ignore_link:
			self.parts.append(data)

	def get_text(self):
		return unescape("".join(self.parts)).strip()


async def buscar_ultima_noticia(session: aiohttp.ClientSession) -> dict | None:
	try:
		async with session.get(RSS_FEED_URL, timeout=10) as res:
			if res.status != 200:
				print(f"[RSS] Erro ao buscar feed: {res.status}")
				return None
			text = await res.text()

		root = ET.fromstring(text)
		item = root.find("channel/item")

		guid_elem = item.find("guid")
		link_elem = item.find("link")
		title_elem = item.find("title")
		desc_elem = item.find("description")
		pub_elem = item.find("pubDate")

		guid = guid_elem.text if guid_elem is not None else link_elem.text
		title = title_elem.text or "Sem título"
		link = link_elem.text or ""
		summary = HTMLToDiscord()
		summary.feed(desc_elem.text if desc_elem is not None else "")
		summary_text = summary.get_text()
		pub_date = (
			parsedate_to_datetime(pub_elem.text)
			if pub_elem is not None
			else datetime.datetime.now()
		)

		NS = {"media": "http://search.yahoo.com/mrss/"}
		media_elem = item.find("media:content", NS)
		media_url = media_elem.get("url") if media_elem is not None else None

		return {
			"guid": guid,
			"title": title,
			"link": link,
			"summary": summary_text,
			"pub_date": pub_date,
			"media": media_url,
		}
	except Exception as e:
		print(f"[RSS] Erro ao parsear feed: {e}")
		return None


class NewsView(ui.LayoutView):
	def __init__(self, noticia: dict, ping: str | None = None):
		super().__init__(timeout=None)
		container = ui.Container(
			ui.Section(
				ui.TextDisplay(
					content=f'## {noticia["title"]}'
				),
				accessory=ui.Thumbnail(VATICAN_NEWS_ICON)
			),
			accent_color=0xDB0102
		)

		container.add_item(ui.TextDisplay(noticia["summary"]))

		container.add_item(
			ui.ActionRow(
				ui.Button(
					label="Ler notícia completa",
					url=noticia["link"],
					style=discord.ButtonStyle.link,
					emoji="📰",
				)
			)
		)

		container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

		pub_data: datetime.datetime = noticia["pub_date"]
		if pub_data.tzinfo is None:
			pub_data = pub_data.replace(tzinfo=datetime.timezone.utc)

		data_str = f"{discord.utils.format_dt(pub_data, style='f')} ({discord.utils.format_dt(pub_data, style='R')})"

		rodape = f"-# Notícia datada de {data_str}"
		if ping is not None:
			rodape += f" - {ping}"

		container.add_item(ui.TextDisplay(rodape))

		if noticia["media"]:
			container.add_item(ui.MediaGallery(discord.MediaGalleryItem(noticia["media"])))
		
		self.add_item(container)



class VaticanNewsCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		if is_unix():
			self.session = aiohttp.ClientSession()
			self.check_news.start()

	def cog_unload(self):
		if is_unix():
			self.check_news.cancel()
			self.bot.loop.create_task(self.session.close())

	@tasks.loop(minutes=1)
	async def check_news(self):
		SERVER_ID = 1429152785252876328
		config = get_news_config_db(SERVER_ID)
		webhook_url = config.get("webhook_url")
		if not webhook_url:
			return

		webhook = discord.Webhook.from_url(webhook_url, session=self.session)
		ping = f"<@&{config['ping']}>" if "ping" in config else None

		noticia = await buscar_ultima_noticia(self.session)
		if not noticia:
			return

		ultimo_guid = carregar_ultimo_guid(SERVER_ID)
		if noticia["guid"] == ultimo_guid:
			return

		try:
			await webhook.send(view=NewsView(noticia=noticia, ping=ping))
			salvar_ultimo_guid(SERVER_ID, noticia["guid"])
		except Exception as e:
			await self.bot.send_to_console(f"[VN] Erro ao enviar webhook: {e}")

	news_gp = app_commands.Group(
		name="news", description="Comandos relacionados às notícias do Vaticano."
	)

	@news_gp.command(name="last", description="Veja a última notícia.")
	async def last(self, interaction: discord.Interaction):
		noticia = await buscar_ultima_noticia(self.session)
		await interaction.response.send_message(view=NewsView(noticia=noticia), ephemeral=True)

	@news_gp.command(name="vnstatus", description="Verificar o último GUID salvo.")
	async def status(self, interaction: discord.Interaction):
		ultimo = carregar_ultimo_guid(interaction.guild.id) or "Nenhum ainda"
		await interaction.response.send_message(
			f"Último GUID salvo: `{ultimo}`", ephemeral=True
		)

	@news_gp.command(
		name="set", description="Define o valor das configurações de notícias."
	)
	@app_commands.choices(
		tipo=[
			app_commands.Choice(name="Cargo de marcação", value="ping"),
			app_commands.Choice(name="Webhook", value="webhook_url"),
		]
	)
	async def set_news_config(self, interaction: discord.Interaction, tipo: str):
		await interaction.response.send_message(
			view=SetNewsConfig(tipo=tipo, guild=interaction.guild), ephemeral=True
		)


class SetNewsConfig(ui.LayoutView):
	def __init__(self, tipo: Literal["ping", "webhook"], guild: discord.Guild):
		super().__init__(timeout=None)
		self.tipo = tipo
		self.guild = guild

		title = "Configurações das notícias do Vaticano"
		desc = "Escolha adequadamente o valor para evitar problemas."

		if tipo == "ping":
			desc = "Escolha o cargo a ser marcado quando uma nova notícia sair. " + desc
			self.select = ui.RoleSelect(
				custom_id="escolher_ping",
				placeholder="Escolha o cargo",
				min_values=1,
				max_values=1,
			)
			self.select.callback = self._on_ping_selected

		else:
			desc = "Escolha o canal onde o webhook enviará as notícias. " + desc
			self.select = ui.ChannelSelect(
				custom_id="escolher_canal",
				placeholder="Escolha o canal",
				channel_types=[discord.ChannelType.text, discord.ChannelType.news],
				min_values=1,
				max_values=1,
			)
			self.select.callback = self._on_channel_selected

		self.container = ui.Container(
			ui.Section(
				ui.TextDisplay(title), accessory=ui.Thumbnail(media=VATICAN_NEWS_ICON)
			),
			accent_color=0xDB0102,
		)

		self.container.add_item(ui.Separator())
		self.action_row = ui.ActionRow(self.select)

		self.container.add_item(self.action_row)
		self.add_item(self.container)

	async def _on_ping_selected(self, interaction: discord.Interaction):
		role: discord.Role = self.select.values[0]

		config = get_news_config_db(interaction.guild.id)
		config["ping"] = role.id
		save_news_config_db(interaction.guild.id, config)

		await self._finish(
			interaction, f"Cargo configurado com sucesso: {role.mention}."
		)

	async def _on_channel_selected(self, interaction: discord.Interaction):
		selected = self.select.values[0]
		channel = interaction.guild.get_channel(selected.id)

		if not channel.permissions_for(interaction.guild.me).manage_webhooks:
			return await interaction.response.send_message(
				"Não tenho permissão para gerenciar webhooks nesse canal.",
				ephemeral=True,
			)

		webhooks = await self._get_webhooks(channel)

		if not webhooks:
			return await interaction.response.send_message(
				"Não há nenhum webhook no canal selecionado.", ephemeral=True
			)

		if len(webhooks) == 1:
			config = get_news_config_db(interaction.guild.id)
			config["webhook_url"] = webhooks[0].url
			config["canal"] = channel.id
			save_news_config_db(interaction.guild.id, config)

			return await self._finish(
				interaction, f"Webhook configurado com sucesso em {channel.mention}."
			)

		await self._ask_webhook_selection(interaction, channel, webhooks)

	async def _get_webhooks(
		self, channel: discord.TextChannel
	) -> list[discord.Webhook]:
		return await channel.webhooks()

	async def _ask_webhook_selection(
		self,
		interaction: discord.Interaction,
		channel: discord.TextChannel,
		webhooks: list[discord.Webhook],
	):
		options = [
			discord.SelectOption(
				label=wh.name or f"Webhook {i + 1}",
				description=f"ID: {wh.id}",
				value=str(wh.id),
			)
			for i, wh in enumerate(webhooks)
		]

		self.webhook_select = ui.Select(
			placeholder="Escolha o webhook",
			options=options,
			min_values=1,
			max_values=1,
			custom_id="escolher_webhook",
		)

		async def callback(interaction_select: discord.Interaction):
			webhook_id = int(self.webhook_select.values[0])
			webhook = discord.utils.get(webhooks, id=webhook_id)

			config = get_news_config_db(interaction_select.guild.id)
			config["webhook_url"] = webhook.url
			config["canal"] = channel
			save_news_config_db(interaction_select.guild.id, config)

			await self._finish(
				interaction_select,
				f"Webhook **{webhook.name}** configurado com sucesso em {channel.mention}.",
			)

		self.webhook_select.callback = callback

		self.container.remove_item(self.action_row)

		self.action_row.clear_items()
		self.action_row.add_item(self.webhook_select)

		self.container.add_item(self.action_row)

		await interaction.response.edit_message(view=self)

	async def _finish(self, interaction: discord.Interaction, message: str):
		for item in self.action_row.children:
			item.disabled = True

		self.add_item(ui.TextDisplay(message))
		await interaction.response.edit_message(view=self)


async def setup(bot: Bot):
	await bot.add_cog(VaticanNewsCog(bot))
	for guild in bot.guilds:
		bot.add_view(SetNewsConfig("ping", guild))
		bot.add_view(SetNewsConfig("webhook_url", guild))
