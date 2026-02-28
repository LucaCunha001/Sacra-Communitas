import datetime
import discord

from discord import ui

from enum import Enum
from .data import get_config


class PunicaoLayout(discord.ui.LayoutView):
	def __init__(self, titulo: str, descricao: str, cor: int, membro: discord.User, autor: discord.Member | None, motivo: str | None):
		super().__init__(timeout=None)

		container = ui.Container(
			ui.Section(
				ui.TextDisplay(
					f"# {titulo}\n"
					f"{descricao}\n"
				),
				accessory=ui.Thumbnail(membro.display_avatar.url)
			),
			accent_color=cor
		)

		info_lines = [f"**Membro:** {membro.mention}"]

		if autor:
			info_lines.append(f"**Responsável:** {autor.mention}")

		if motivo:
			info_lines.append(f"**Motivo:** {motivo}")

		time = int(datetime.datetime.now().timestamp())

		info_lines.append(f"-# <t:{time}:F> (<t:{time}:R>)")

		info = "\n".join(info_lines)

		container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

		container.add_item(
			discord.ui.TextDisplay(info)
		)
		self.add_item(container)

class TipoPunicao(Enum):
	Excomunhao = 0
	Penitencia = 1
	Admoestacao = 2
	ComunhaoRestaurada = 3
	RevogacaoPenitencia = 4
	RevogacaoAdmoestacao = 5
	Suspensao = 6	

async def log_punicao(
	guild: discord.Guild,
	tipo: TipoPunicao | int,
	membro: discord.User,
	author: discord.Member = None,
	motivo: str = None,
):
	if isinstance(tipo, TipoPunicao):
		tipo=tipo.value

	canal_punicoes = guild.get_channel(get_config()["canais"]["punicoes"])

	match tipo:
		case 0:  # Excomunhão / Ban
			titulo = "Excomunhão aplicada!"
			cor = 0xff0000
			descricao = f"{membro.mention} foi removido permanentemente da comunidade, em consequência de ação grave contra a ordem e doutrina."

		case 1:  # Penitência / Mute
			titulo = "Penitência imposta"
			cor = 0xffff00
			descricao = f"{membro.mention} foi colocado em silêncio temporário para reflexão espiritual."

		case 2:  # Admoestação / Warn
			titulo = "Admoestação concedida"
			cor = 0xff6600
			descricao = f"{membro.mention} recebeu uma advertência formal."

		case 3:  # Revogação de excomunhão / Ban remove
			titulo = "Comunhão restaurada"
			cor = 0x00ff00
			descricao = f"{membro.mention} foi reintegrado à comunidade."

		case 4:  # Revogação de penitência / Mute remove
			titulo = "Penitência concluída"
			cor = 0x00ff00
			descricao = f"{membro.mention} teve seu silêncio removido."

		case 5:  # Revogação de admoestação / Warn remove
			titulo = "Admoestação removida"
			cor = 0x00ff00
			descricao = f"A advertência de {membro.mention} foi removida."

		case 6:  # Suspensão / Kick
			titulo = "Suspensão aplicada"
			cor = 0xc27c0e
			descricao = f"{membro.mention} foi temporariamente removido da comunidade para preservar a ordem."
		
		case _:
			return

	view = PunicaoLayout(
		titulo,
		descricao,
		cor,
		membro,
		author,
		motivo
	)

	if canal_punicoes:
		await canal_punicoes.send(view=view)

async def log_normal(
	guild: discord.Guild,
	tipo: int,
	membro: discord.User | None = None,
	author: discord.Member | None = None,
	msg_before: discord.Message | None = None,
	msg_after: discord.Message | None = None,
	user_before: discord.Member | None = None,
	user_after: discord.Member | None = None,
	motivo: str | None = None,
):
	titulo = ""
	descricao = ""
	canal_id = None

	config = get_config()

	match tipo:
		case 0:  # Mensagem apagada
			titulo = "Mensagem apagada"
			canal_id = config["logs"]["msgs_apagadas"]
			descricao = (
				f"A mensagem de {membro.mention} foi apagada"
				f"{f' por {author.mention}' if author else ''}.\n\n"
				f"**Mensagem apagada:**\n"
				f"```{desformatar(msg_before.content if msg_before else '')}```\n"
				"**ID da mensagem:\n**"
				f"`{msg_before.id}`"
			)

		case 1:  # Mensagem editada
			titulo = "Mensagem editada"
			canal_id = config["logs"]["msgs_editadas"]
			descricao = (
				f"A mensagem de {membro.mention} foi editada.\n\n"
				f"**Mensagem original:**\n"
				f"```{desformatar(msg_before.content if msg_before else '')}```\n"
				f"**Mensagem nova:**\n"
				f"```{desformatar(msg_after.content if msg_after else '')}```\n"
				"**Link da mensagem:**\n"
				f"{msg_after.jump_url}\n"
				"**ID da mensagem:**\n"
				f"`{msg_after.id}`"
			)

		case 2:  # Cargos de usuário alterados
			titulo = "Cargos de usuário alterados"
			canal_id = config["logs"]["cargos_alterados"]

			roles_before = set(user_before.roles) - {user_before.guild.default_role}
			roles_after = set(user_after.roles) - {user_after.guild.default_role}

			cargos_adicionados = roles_after - roles_before
			cargos_removidos = roles_before - roles_after

			cargos_adicionados_fmt = (
				", ".join(r.mention for r in cargos_adicionados)
				if cargos_adicionados
				else None
			)
			cargos_removidos_fmt = (
				", ".join(r.mention for r in cargos_removidos)
				if cargos_removidos
				else None
			)

			descricao = (
				f"Os cargos de {user_after.mention} foram alterados"
				f"{f' por {author.mention}' if author else ''}.\n\n"
			)

			if cargos_adicionados_fmt is not None:
				descricao += f"**Cargos adicionados:**\n{cargos_adicionados_fmt}\n\n"
			
			if cargos_removidos_fmt is not None:
				descricao += f"**Cargos removidos:**\n{cargos_removidos_fmt}"
		
		case _:
			return

	embed = make_embed(titulo, descricao, discord.Color.blurple(), user=membro)

	if motivo:
		embed.add_field(name="Motivo", value=motivo, inline=False)

	canal = guild.get_channel(canal_id)
	if canal:
		await canal.send(embed=embed)

def desformatar(texto: str) -> str:
	for caractere in ["`"]:
		texto = texto.replace(caractere, f"\\{caractere}")

	return texto

def make_embed(
	title: str,
	description: str,
	colour: discord.Color,
	user: discord.abc.User | None = None,
	error: bool = False,
) -> discord.Embed:
	embed = discord.Embed(
		title=title,
		description=description,
		colour=colour if not error else 0xff0000,
		timestamp=datetime.datetime.now(),
	)
	if user:
		embed.set_thumbnail(url=user.display_avatar.url)
	return embed
