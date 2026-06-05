import discord

from discord import app_commands
from functools import wraps
from typing import Literal
from .data import get_config

class FaltaPermissaoSacerdotal(app_commands.AppCommandError):
	def __init__(self, cargo: discord.Role, permissao: str, *args):
		self.role = cargo
		self.permissao = permissao
		super().__init__(*args)

def verificar_permissao(permissao: Literal["designar_cargos", "gerenciar_comunidade", "excomungar", "suspensao", "admoestar", "penitencia", "atender_tickets"], cargo: discord.Role) -> bool:
	cargos_sacerdotes = get_config()["cargos"]["sacerdotes"]

	id_papa = cargos_sacerdotes["Papa"]["id"]
	id_cardeal = cargos_sacerdotes["Cardeal"]["id"]
	id_bispo = cargos_sacerdotes["Bispo"]["id"]
	id_arcebispo = cargos_sacerdotes["Arcebispo"]["id"]
	id_padre = cargos_sacerdotes["Padre"]["id"]
	id_diacono = cargos_sacerdotes["Diácono"]["id"]

	if cargo.id in [id_papa, id_cardeal]:
		return True

	if cargo.id in [id_bispo, id_arcebispo]:
		if permissao in ["designar_cargos", "excomungar", "suspensao", "admoestar", "penitencia", "atender_tickets"]:
			return True

	if cargo.id == id_padre and permissao in ["suspensao", "admoestar", "penitencia", "atender_tickets"]:
		return True

	if cargo.id == id_diacono and permissao in ["admoestar", "penitencia", "atender_tickets"]:
		return True

	return False


def permissao(
	*,
	designar_cargos: bool = False,
	gerenciar_comunidade: bool = False,
	excomungar: bool = False,
	suspensao: bool = False,
	admoestar: bool = False,
	penitencia: bool = False,
	atender_tickets: bool = False
):
	def decorator(func):
		@wraps(func)
		async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
			config = get_config()
			cargos = config["cargos"]["sacerdotes"]
			cargos_sacerdote = [
				role for role in interaction.user.roles
				if any(r_dict['id'] == role.id for _, r_dict in cargos.items())
			]
			cargo = max(cargos_sacerdote, key=lambda r: r.position, default=None)

			if not cargo:
				await interaction.response.send_message("❌ Você não é um sacerdote ordenado.", ephemeral=True)
				return

			permissoes = {
				"designar_cargos": designar_cargos,
				"gerenciar_comunidade": gerenciar_comunidade,
				"excomungar": excomungar,
				"suspensao": suspensao,
				"admoestar": admoestar,
				"penitencia": penitencia,
				"atender_tickets": atender_tickets
			}

			for nome_perm, ativa in permissoes.items():
				if ativa and not verificar_permissao(nome_perm, cargo):
					raise FaltaPermissaoSacerdotal(cargo, nome_perm, f"{cargo.name}: não possui autoridade para executar {nome_perm.replace('_', ' ')}.")

			return await func(self, interaction, *args, **kwargs)
		return wrapper
	return decorator