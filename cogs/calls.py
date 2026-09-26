import discord

from discord.ext import commands
from discord import app_commands

from utils.recursos import Bot
from utils.data import get_config, save_config

guild_ids = [get_config()["config"]["servidores"]["main"]]


class Calls(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.separador = "・"

	call_gp = app_commands.Group(
		name="calls", description="Comandos relacionados as calls do servidor"
	)

	@call_gp.command(name="registrated", description="Veja as chamadas registradas")
	@app_commands.default_permissions(manage_channels=True)
	async def registrated(self, interaction: discord.Interaction):
		msg = ""
		for call, call_info in self.bot.config["calls"].items():
			msg += f"{call} - <#{call_info['id']}>\n"

		await interaction.response.send_message(msg, ephemeral=True)

	@call_gp.command(
		name="set_category", description="Definir a categoria para chamadas"
	)
	@app_commands.describe(category="Categoria onde os canais de chamada serão criados")
	@app_commands.default_permissions(manage_channels=True)
	async def set_category(
		self, interaction: discord.Interaction, category: discord.CategoryChannel
	):
		config = get_config()
		config["canais"]["calls_category"] = category.id
		save_config(config)
		await interaction.response.send_message(
			f"Categoria de chamadas definida para: {category.name}", ephemeral=True
		)

	@call_gp.command(name="register_call", description="Registrar uma chamada")
	@app_commands.describe(call="Canal de voz da chamada a ser registrada")
	@app_commands.default_permissions(manage_channels=True)
	async def register_call(
		self, interaction: discord.Interaction, call: discord.VoiceChannel
	):
		config = self.bot.config
		calls = config.get("calls", {})
		if call.id in [c["id"] for c in calls.values()]:
			return await interaction.response.send_message(
				"Essa chamada já está registrada.", ephemeral=True
			)

		call_name = call.name.removesuffix(" 1")
		calls[call_name.split(self.separador)[1]] = {"id": call.id, "nome": call_name}

		config["calls"] = calls
		save_config(config)

		await interaction.response.send_message(
			f"Chamada '{call_name}' registrada com sucesso.", ephemeral=True
		)

	async def _hide_channel(self, channel: discord.VoiceChannel):
		overwrites = channel.overwrites

		overwrites[channel.guild.default_role] = discord.PermissionOverwrite(
			view_channel=False
		)

		await channel.edit(
			overwrites=overwrites,
			reason="Ocultando call"
		)


	async def _show_channel(self, channel: discord.VoiceChannel):
		overwrites = channel.overwrites

		if channel.guild.default_role in overwrites:
			overwrite = overwrites[channel.guild.default_role]

			overwrite.view_channel = None

			if overwrite.is_empty():
				del overwrites[channel.guild.default_role]
			else:
				overwrites[channel.guild.default_role] = overwrite

		await channel.edit(
			overwrites=overwrites,
			reason="Exibindo call"
		)
		return channel
	
	def _get_hidden_channel(
		self,
		canais: list[discord.VoiceChannel],
		guild: discord.Guild,
	) -> discord.VoiceChannel | None:
		for canal in canais:
			overwrite = canal.overwrites_for(guild.default_role)

			if overwrite.view_channel is False:
				return canal

		return None

	def _get_call_index(self, channel_name: str) -> int | None:
		try:
			return int(channel_name.rsplit(" ", 1)[-1])
		except (ValueError, IndexError):
			return None

	def _is_hidden(self, channel: discord.VoiceChannel) -> bool:
		return (
			channel.overwrites_for(channel.guild.default_role).view_channel
			is False
		)

	def _get_visible_channels(self, canais: list[discord.VoiceChannel]):
		return [c for c in canais if not self._is_hidden(c)]

	def _get_hidden_channels(self, canais: list[discord.VoiceChannel]):
		return [c for c in canais if self._is_hidden(c)]

	async def _reorganizar_calls(
    self,
    categoria: discord.CategoryChannel,
    call_info: dict,
) -> None:
		todos = self._get_call_channels(categoria, call_info)

		visiveis = self._get_visible_channels(todos)
		ocultos = self._get_hidden_channels(todos)

		visiveis.sort(key=lambda c: self._get_call_index(c.name) or 0)
		ocultos.sort(key=lambda c: self._get_call_index(c.name) or 0)

		base_channel = discord.utils.get(todos, id=call_info["id"])

		if not base_channel:
			return

		base_position = base_channel.position

		canais = visiveis + ocultos

		for i, canal in enumerate(canais, start=1):
			edits = {}

			novo_nome = self._build_call_name(call_info["nome"], i)
			if canal.name != novo_nome:
				edits["name"] = novo_nome

			nova_posicao = base_position + (i - 1)
			if canal.position != nova_posicao:
				edits["position"] = nova_posicao

			if edits:
				await canal.edit(
					**edits,
					reason="Reorganizando chamadas dinâmicas",
				)
	def _get_calls_do_prefixo(
		self, categoria: discord.CategoryChannel, call_info: dict
	):
		canais = [
			c for c in categoria.voice_channels if c.name.startswith(call_info["nome"])
		]
		canais.sort(key=lambda c: self._get_call_index(c.name) or 0)
		return canais

	def _get_call_key(self, channel_name: str) -> str | None:
		try:
			parte = channel_name.split(self.separador, 1)[1]
			return " ".join(parte.strip().split(" ")[:-1])
		except (IndexError, AttributeError):
			return None
		
	def _get_call_channels(self, categoria: discord.CategoryChannel, call_info: dict):
		canais = [
			c for c in categoria.voice_channels
			if c.name.startswith(call_info["nome"])
		]
		return sorted(canais, key=lambda c: self._get_call_index(c.name) or 0)


	def _has_empty_channel(self, canais: list[discord.VoiceChannel]) -> bool:
		return any(len(c.members) == 0 for c in canais)


	def _get_next_index(self, canais: list[discord.VoiceChannel]) -> int:
		return len(canais) + 1


	def _build_call_name(self, base: str, index: int) -> str:
		return f"{base} {index}"

	async def reload_call(self, voice: discord.VoiceState):
		channel = voice.channel
		if not channel:
			return

		config = get_config()
		calls = config.get("calls", {})

		categoria_id = config.get("canais", {}).get("calls_category")
		if not categoria_id or channel.category_id != categoria_id:
			return

		categoria = channel.guild.get_channel(categoria_id)
		if not categoria:
			return

		call_key = self._get_call_key(channel.name)
		if not call_key or call_key not in calls:
			return

		call_info = calls[call_key]

		canais = self._get_call_channels(categoria, call_info)
		visiveis = self._get_visible_channels(canais)
		ocultos = self._get_hidden_channels(canais)

		membros = len(channel.members)
		limite = 3

		# Entrou alguém na call
		if membros == 1 and not self._is_hidden(channel):

			existe_vazia = any(len(c.members) == 0 for c in visiveis)

			if not existe_vazia or len(visiveis) <= limite:
				novo_nome = self._build_call_name(
					call_info["nome"],
					len(visiveis) + 1
				)

				if ocultos:
					canal = await self._show_channel(ocultos[0])
					await canal.edit(name=novo_nome)

				else:
					await categoria.create_voice_channel(
						name=novo_nome,
						position=max(c.position for c in canais),
						overwrites=channel.overwrites,
						reason="Criando canal dinâmico"
					)

		elif membros == 0 and not self._is_hidden(channel):

			if len(visiveis) > limite and channel.id != call_info["id"]:
				await self._hide_channel(channel)

		await self._reorganizar_calls(categoria, call_info)
	
	@commands.Cog.listener()
	async def on_voice_state_update(
		self,
		member: discord.Member,
		before: discord.VoiceState,
		after: discord.VoiceState,
	):
		if before.channel:
			await self.reload_call(before)

		if after.channel:
			await self.reload_call(after)


async def setup(bot: Bot):
	await bot.add_cog(Calls(bot))
