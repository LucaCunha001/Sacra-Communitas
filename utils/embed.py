from discord import Embed, Color, User, Guild

from .data import get_embeds

def open_embed(embed_key: str) -> list[dict] | dict:
	return get_embeds()[embed_key]

def convert_embed(embed_key: str) -> list[Embed]:
	embeds = []
	embed_data = open_embed(embed_key)

	if isinstance(embed_data, list):
		for data in embed_data:
			embed = Embed.from_dict(data)
			embeds.append(embed)
	else:
		embed = Embed.from_dict(embed_data)
		embeds.append(embed)
	
	return embeds

def criar_embed(*,
	titulo: str = "", descricao: str = "", cor: int | str,
	footer: str = "", membro: User = None, servidor: Guild = None,
	author: User = None) -> Embed:
	embed = Embed(
		title=titulo,
		description=descricao
	)

	if (isinstance(cor, str)):
		cor = Color.from_str(cor)
	embed.color = cor

	if servidor:
		embed.set_thumbnail(url=servidor.icon.url)
	if membro:
		embed.set_thumbnail(url=membro.display_avatar.url)
	
	if footer:
		embed.set_footer(
			icon_url=servidor.icon.url,
			text=f"{servidor.name} • {footer}"
		)
	
	if author:
		embed.set_author(
			url=f"https://discord.com/users/{author.id}",
			name=author.display_name,
			icon_url=author.display_avatar.url
		)

	return embed