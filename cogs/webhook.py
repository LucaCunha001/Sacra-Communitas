import aiohttp
import discord

from discord import app_commands, Webhook, ui
from discord.ext import commands

from utils.data import get_config
from utils.embed import convert_embed
from utils.recursos import Bot

from typing import TypedDict, Optional


class MediaDict(TypedDict):
	url: str
	description: Optional[str]
	spoiler: Optional[bool]


class ItemsDict(TypedDict):
	media: MediaDict


class ComponentDict(TypedDict):
	type: int
	spoiler: Optional[bool]
	accent_color: Optional[int]
	label: Optional[str]
	style: Optional[int]
	url: Optional[str]
	emoji: Optional[dict[str, str]]
	custom_id: Optional[str]
	content: Optional[str]
	spacing: Optional[int]
	items: Optional[list[ItemsDict]]
	components: Optional[list["ComponentDict"]]


class DataDict(TypedDict):
	flags: int
	components: list[ComponentDict]
	username: Optional[str]
	avatar_url: Optional[str]


def generate_component(component: ComponentDict):
	match component["type"]:
		case 1:
			return ui.ActionRow(
				*[generate_component(item) for item in component["components"]]
			)
		case 2:
			return ui.Button(
				label=component["label"],
				style=component["style"],
				url=component.get("url"),
				emoji=component.get("emoji", {}).get("name"),
				custom_id=component.get("custom_id"),
			)
		case 10:
			return ui.TextDisplay(component["content"])
		case 12:
			return ui.MediaGallery(
				*[
					discord.MediaGalleryItem(
						media=media["media"]["url"],
						description=media["media"].get("description"),
						spoiler=media["media"].get("spoiler", False),
					)
					for media in component["items"]
				]
			)
		case 14:
			return ui.Separator(
				spacing=discord.SeparatorSpacing.small
				if component["spacing"] == 2
				else discord.SeparatorSpacing.large
			)
		case 17:
			accent = component.get("accent_color")
			return ui.Container(
				*[generate_component(c) for c in component["components"]],
				accent_color=accent,
				spoiler=component.get("spoiler", False),
			)
		case _:
			raise ValueError(f"Component type {component['type']} não suportado")


def dict_to_layoutview(data: DataDict):
	view = ui.LayoutView(timeout=None)

	for component in data["components"]:
		view.add_item(generate_component(component))

	return view


class WebhookCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	webhook_group = app_commands.Group(
		name="webhook",
		description="Comandos relacionados a webhooks",
		default_permissions=discord.Permissions(manage_webhooks=True),
		guild_ids=[get_config()["config"]["servidores"]["main"]],
	)

	@webhook_group.command(
		name="convite", description="Envia a mensagem de convite através de um Webhook."
	)
	@app_commands.describe(
		url="O link do webhoook.",
		message_id="O ID da mensagem a ser editada (Caso tenha)",
	)
	async def send_message(
		self, interaction: discord.Interaction, url: str, message_id: int = None
	):
		data: DataDict = self.get_webhook_embeds("Convite")

		view = dict_to_layoutview(data)

		async with aiohttp.ClientSession() as session:
			webhook = Webhook.from_url(url, session=session)
			if message_id:
				await webhook.edit_message(message_id=message_id, view=view)
			else:
				await webhook.send(
					view=view,
					username=data.get("username"),
					avatar_url=data.get("avatar_url"),
				)

		await interaction.response.send_message(
			"Mensagem enviada via webhook!", ephemeral=True
		)

	def get_webhook_embeds(self, embed_key: str):
		return convert_embed(embed_key)


async def setup(bot: Bot):
	await bot.add_cog(WebhookCog(bot))
