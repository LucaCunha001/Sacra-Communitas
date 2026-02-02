import datetime
import discord

from enum import Enum
from .data import get_config

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
			descricao = (
				f"{membro.mention} foi removido permanentemente da comunidade, "
				"em consequência de ação grave contra a ordem e doutrina."
				f"\n> Decisão aplicada por: {author.mention}"
			)

		case 1:  # Penitência / Mute
			titulo = "Penitência imposta"
			cor = 0xffff00
			descricao = (
				f"{membro.mention} foi colocado em silêncio temporário para reflexão espiritual."
				f"\n> Determinada por: {author.mention}"
			)

		case 2:  # Admoestação / Warn
			titulo = "Admoestação concedida"
			cor = 0xff6600
			descricao = (
				f"{membro.mention} recebeu uma advertência formal."
				f"\n> Concedida por: {author.mention}"
			)

		case 3:  # Revogação de excomunhão / Ban remove
			titulo = "Comunhão restaurada"
			cor = 0x00ff00
			descricao = (
				f"{membro.mention} foi reintegrado à comunidade."
				f"\n> Restaurado por: {author.mention}"
			)

		case 4:  # Revogação de penitência / Mute remove
			titulo = "Penitência concluída"
			cor = 0x00ff00
			descricao = (
				f"{membro.mention} teve seu silêncio removido."
				f"\n> Liberado por: {author.mention}"
			)

		case 5:  # Revogação de admoestação / Warn remove
			titulo = "Admoestação removida"
			cor = 0x00ff00
			descricao = (
				f"A advertência de {membro.mention} foi removida."
				f"\n> Revogada por: {author.mention}"
			)

		case 6:  # Suspensão / Kick
			titulo = "Suspensão aplicada"
			cor = 0xc27c0e
			descricao = (
				f"{membro.mention} foi temporariamente removido da comunidade para preservar a ordem."
				f"\n> Decisão tomada por: {author.mention}"
			)
		
		case _:
			return

	if motivo:
		descricao += f"\n> Motivo: {motivo}"

	embed = make_embed(titulo, descricao, cor, user=membro)
	if canal_punicoes:
		await canal_punicoes.send(embed=embed)

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
