import asyncio
import logging
import re
import discord

from discord import app_commands, ui
from discord.ext import commands

from utils.data import get_embeds, get_member, save_member
from utils.embed import convert_embed
from utils.recursos import Bot, contar
from utils.permissoes import permissao

logger = logging.getLogger(__name__)
VIP_ROLE_ID = 1442454082861400064


def parse_hex_color(value: str) -> tuple[int, str] | None:
	match = re.fullmatch(r"#?([0-9A-Fa-f]{6})", value.strip())
	if not match:
		return None

	hex_color = match.group(1).upper()
	return int(hex_color, 16), f"#{hex_color}"


class BasicCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	def has_vip_access(self, member: discord.Member) -> bool:
		booster_role = member.guild.premium_subscriber_role
		return (
			(booster_role is not None and booster_role in member.roles)
			or any(role.id == VIP_ROLE_ID for role in member.roles)
		)

	async def sync_vip_role(self, member: discord.Member) -> None:
		member_data = get_member(member.id)
		role_id = member_data["cargo_vip"]
		role = member.guild.get_role(role_id) if role_id else None

		if not self.has_vip_access(member):
			if role is not None:
				await role.delete(reason="Membro não possui mais acesso ao cargo VIP")
			if role_id is not None:
				member_data["cargo_vip"] = None
				save_member(member.id, member_data)
			return

		if role_id is not None and role is None:
			member_data["cargo_vip"] = None
			save_member(member.id, member_data)
			return
		if role is None:
			return

		if role not in member.roles:
			await member.add_roles(role, reason="Sincronização do cargo VIP")

		roles = [member_role for member_role in member.roles if member_role != role]
		highest_role = max(roles, key=lambda member_role: member_role.position)
		needs_position_update = role.position < highest_role.position or role.position-1 > highest_role.position
		if role.permissions != discord.Permissions.none() and needs_position_update:
			await role.edit(
				permissions=discord.Permissions.none(),
				position=highest_role.position,
				reason="Sincronização do cargo VIP",
			)
		elif role.permissions != discord.Permissions.none():
			await role.edit(
				permissions=discord.Permissions.none(),
				reason="Sincronização das permissões do cargo VIP",
			)
		elif needs_position_update:
			await role.edit(
				position=highest_role.position,
				reason="Sincronização da posição do cargo VIP",
			)

	@app_commands.command(name="cor", description="Cria ou atualiza seu cargo VIP colorido.")
	@app_commands.guild_only()
	@app_commands.describe(
		cor1="Cor principal em hexadecimal, por exemplo #AABBCC.",
		cor2="Segunda cor em servidores com suporte a cargos de duas cores."
	)
	async def cor(
		self,
		interaction: discord.Interaction,
		cor1: str,
		cor2: str | None = None,
	):
		guild = interaction.guild
		if guild is None or not isinstance(interaction.user, discord.Member):
			return await interaction.response.send_message(
				"Este comando só pode ser usado em um servidor.", ephemeral=True
			)

		member = interaction.user
		if not self.has_vip_access(member):
			return await interaction.response.send_message(
				"Este comando é exclusivo para boosters e membros com o cargo VIP autorizado.",
				ephemeral=True,
			)

		parsed_color1 = parse_hex_color(cor1)
		if parsed_color1 is None:
			return await interaction.response.send_message(
				"A primeira cor deve estar em hexadecimal, por exemplo `#AABBCC`.",
				ephemeral=True,
			)

		parsed_color2 = parse_hex_color(cor2) if cor2 is not None else None
		if cor2 is not None and parsed_color2 is None:
			return await interaction.response.send_message(
				"A segunda cor deve estar em hexadecimal, por exemplo `#AABBCC`.",
				ephemeral=True,
			)
		if parsed_color2 is not None and "ROLE_COLORS" not in guild.features:
			return await interaction.response.send_message(
				"Este servidor não oferece suporte a cargos com duas cores.",
				ephemeral=True,
			)

		await interaction.response.defer(ephemeral=True, thinking=True)

		hex_color1, name_color1 = parsed_color1
		hex_color2, name_color2 = parsed_color2 if parsed_color2 is not None else (None, None)
		nome = f"VIP・{name_color1}"
		if name_color2 is not None:
			nome += f" → {name_color2}"

		member_data = get_member(member.id)
		role_id = member_data["cargo_vip"]
		role = guild.get_role(role_id) if role_id else None
		try:
			if role is None:
				role = await guild.create_role(
					name=nome,
					permissions=discord.Permissions.none(),
					color=hex_color1,
					secondary_color=hex_color2,
					tertiary_color=None,
					hoist=False,
					mentionable=False,
					reason=f"Cargo VIP de {member}",
				)
				member_data["cargo_vip"] = role.id
				save_member(member.id, member_data)
			else:
				await role.edit(
					name=nome,
					permissions=discord.Permissions.none(),
					color=hex_color1,
					secondary_color=hex_color2,
					tertiary_color=None,
					hoist=False,
					mentionable=False,
					reason=f"Atualização do cargo VIP de {member}",
				)

			other_roles = [member_role for member_role in member.roles if member_role != role]
			if role not in member.roles:
				await member.add_roles(role, reason="Atribuição do cargo VIP")
			
			await self.sync_vip_role(member)

		except discord.Forbidden:
			logger.exception("Sem permissão para criar ou sincronizar cargo VIP de %s", member.id)
			return await interaction.followup.send(
				"Não foi possível gerenciar seu cargo VIP. Verifique a hierarquia de cargos e as permissões do bot.",
				ephemeral=True,
			)
		except discord.HTTPException:
			logger.exception("Falha na API do Discord ao sincronizar cargo VIP de %s", member.id)
			return await interaction.followup.send(
				"O Discord não conseguiu sincronizar seu cargo VIP. Tente novamente mais tarde.",
				ephemeral=True,
			)

		await interaction.followup.send(
			f"Seu cargo VIP foi sincronizado: {role.mention}", ephemeral=True
		)

	@app_commands.command(name="remover_cor", description="Exclui seu cargo VIP colorido.")
	@app_commands.guild_only()
	async def remover_cor(self, interaction: discord.Interaction):
		guild = interaction.guild
		if guild is None or not isinstance(interaction.user, discord.Member):
			return await interaction.response.send_message(
				"Este comando só pode ser usado em um servidor.", ephemeral=True
			)

		member = interaction.user
		await interaction.response.defer(ephemeral=True, thinking=True)

		member_data = get_member(member.id)
		role_id = member_data["cargo_vip"]
		role = guild.get_role(role_id) if role_id else None
		try:
			if role is not None:
				await role.delete(reason=f"Cargo VIP removido por {member}")
		except discord.Forbidden:
			logger.exception("Sem permissão para excluir cargo VIP de %s", member.id)
			return await interaction.followup.send(
				"Não foi possível excluir seu cargo VIP. Verifique as permissões e a hierarquia de cargos do bot.",
				ephemeral=True,
			)
		except discord.HTTPException:
			logger.exception("Falha na API do Discord ao excluir cargo VIP de %s", member.id)
			return await interaction.followup.send(
				"O Discord não conseguiu excluir seu cargo VIP. Tente novamente mais tarde.",
				ephemeral=True,
			)

		member_data["cargo_vip"] = None
		save_member(member.id, member_data)
		if role is None:
			return await interaction.followup.send(
				"Você não tinha um cargo VIP colorido ativo; o registro foi limpo.",
				ephemeral=True,
			)

		await interaction.followup.send(
			"Seu cargo VIP colorido foi excluído.", ephemeral=True
		)

	@app_commands.command(
		name="vantagens_booster",
		description="Publica no canal as vantagens de ser Booster.",
	)
	@app_commands.guild_only()
	@app_commands.checks.has_permissions(manage_guild=True)
	async def vantagens_booster(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True, thinking=True)

		channel = self.bot.get_channel(1568422175164342292)
		if channel is None:
			try:
				channel = await self.bot.fetch_channel(1568422175164342292)
			except discord.NotFound:
				return await interaction.followup.send(
					"Não encontrei o canal configurado para a mensagem de Boosters.",
					ephemeral=True,
				)
			except discord.Forbidden:
				logger.exception("Sem permissão para acessar o canal de vantagens Booster")
				return await interaction.followup.send(
					"Não tenho permissão para acessar o canal de vantagens Booster.",
					ephemeral=True,
				)
			except discord.HTTPException:
				logger.exception("Falha ao buscar o canal de vantagens Booster")
				return await interaction.followup.send(
					"Não foi possível acessar o canal de vantagens Booster.",
					ephemeral=True,
				)

		if not isinstance(channel, discord.TextChannel):
			return await interaction.followup.send(
				"O canal configurado para as vantagens de Booster não é um canal de texto.",
				ephemeral=True,
			)

		view = ui.LayoutView()
		container = ui.Container(accent_color=0xE6B3E6)
		container.add_item(ui.TextDisplay("## ✨ Vantagens de ser Booster"))
		container.add_item(
			ui.TextDisplay(
				"Seu boost ajuda nossa comunidade a crescer e garante vantagens especiais:\n\n"
				"- No <#1429152790608871546>, boosters podem enviar imagens, GIFs e links, "
				"além de usar comandos.\n"
				"- Você ganha um cargo com uma cor linda, e mesmo se não gostar, poderá criar seu próprio cargo colorido com </cor:1568065683273548048>.\n"
				"- Ganha a permissão de mudar o próprio nick.\n"
				"- Mesmo quando o boost terminar, você continuará com o cargo <@&1430640923783594191>. "
				"Ele não concede permissões adicionais. É nossa forma de demonstrar eterna gratidão "
				"pelo seu apoio ao servidor.\n\n"
				"Obrigado por impulsionar a comunidade. Cada boost faz a diferença! ✨"
			)
		)
		container.add_item(
			ui.MediaGallery(
				discord.MediaGalleryItem(
					"https://media.discordapp.net/attachments/1430680590218432663/1568424114002329640/booster.gif?ex=6aefc448&is=6aee72c8&hm=7b7e516c253bf579dcf282606b7d337b14a4a386e4dfc1429e9685a629277bf2&="
				)
			)
		)
		view.add_item(container)

		try:
			msg = await channel.fetch_message(1568427976004079839)
			if msg:
				await msg.edit(view=view, allowed_mentions=discord.AllowedMentions.none())
			else:
				await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())
		except discord.Forbidden:
			logger.exception("Sem permissão para publicar vantagens Booster no canal")
			return await interaction.followup.send(
				"Não tenho permissão para enviar mensagens nesse canal.",
				ephemeral=True,
			)
		except discord.HTTPException:
			logger.exception("Falha ao publicar vantagens Booster no canal")
			return await interaction.followup.send(
				"O Discord não conseguiu publicar a mensagem. Tente novamente.",
				ephemeral=True,
			)

		await interaction.followup.send(
			f"Mensagem de vantagens Booster publicada em {channel.mention}.",
			ephemeral=True,
		)

	@app_commands.command(name="embed", description="Envia um embed padrão.")
	@app_commands.choices(
		embed=[
			app_commands.Choice(name=k, value=k) for k in get_embeds()
		]
	)
	@app_commands.checks.has_permissions(manage_webhooks=True)
	async def embed_cmd(self, interaction: discord.Interaction, embed: str):
		embeds = convert_embed(embed)
		await interaction.response.send_message(embeds=embeds, ephemeral=True)
		await interaction.channel.send(embeds=embeds)

	@app_commands.command(name="say", description="Faz o bot repetir uma mensagem.")
	@app_commands.describe(
		mensagem="A mensagem para o bot enviar.",
		digitar="O bot deve ficar um tempo digitando?"
	)
	@permissao(gerenciar_comunidade=True)
	async def say(self, interaction: discord.Interaction, mensagem: str, digitar: bool = True):
		for role in interaction.guild.roles:
			if role.mention in mensagem:
				if role.is_default() and not interaction.permissions.mention_everyone:
					return await interaction.response.send_message(
						"Você não pode mencionar @everyone ou @here.", ephemeral=True
					)

				if (not role.mentionable) and not interaction.permissions.manage_roles:
					return await interaction.response.send_message(
						f"O cargo {role.name} não pode ser mencionado.", ephemeral=True
					)

				if role >= interaction.user.top_role and not interaction.permissions.administrator:
					return await interaction.response.send_message(
						f"Você não pode mencionar o cargo {role.name} (ele é mais alto que o seu).", ephemeral=True
					)
		
		await interaction.response.send_message("Mensagem enviada!", ephemeral=True)

		if digitar:
			letras_por_segundo = 10
			delay = 1 / letras_por_segundo

			async with interaction.channel.typing():
				await asyncio.sleep(delay * len(mensagem))
		
		await interaction.channel.send(mensagem)
	
	@app_commands.command(name="converter_romano", description="Converte um número inteiro para algarismos romanos.")
	@app_commands.describe(
		numero="Número inteiro a ser convertido para algarismos romanos."
	)
	async def converter_romano(self, interaction: discord.Interaction, numero: int):
		if numero <= 0 or numero >= 4000:
			await interaction.response.send_message("Por favor, insira um número inteiro positivo maior que zero e menor que 4000.", ephemeral=True)
			return
		
		romano = contar(numero)
		await interaction.response.send_message(f"O número {numero} em algarismos romanos é: **{romano}**")
	
	@app_commands.command(name="shutdown", description="Desliga o bot.")
	@commands.is_owner()
	async def shutdown(self, interaction: discord.Interaction):
		await interaction.response.send_message("Bot desligado.")
		await self.bot.close()
	
	@app_commands.command(name="sync_topics", description="Sincroniza os tópicos da aba da Doutrina")
	async def sync_topics(self, interaction: discord.Interaction):
		if interaction.user.id != 1272282414252691517:
			return await interaction.response.send_message("Você não tem permissão de executar esse comando.")

		await interaction.response.defer(thinking=True, ephemeral=True)

		forum = await self.bot.fetch_channel(1558531758666817667)
		if not isinstance(forum, discord.ForumChannel):
			raise TypeError("O canal configurado para sincronização não é um fórum.")

		topico_indice = await self.bot.fetch_channel(1558931945109323807)
		if not isinstance(topico_indice, discord.Thread):
			raise TypeError("O canal configurado para o índice não é um tópico.")
		if topico_indice.parent_id != forum.id:
			raise ValueError("O tópico do índice não pertence ao fórum configurado.")

		if self.bot.user is None:
			raise RuntimeError("O bot ainda não está conectado.")

		topicos = {
			topico.id: topico
			for topico in await forum.guild.active_threads()
			if topico.parent_id == forum.id
		}
		async for topico in forum.archived_threads(limit=None):
			topicos[topico.id] = topico

		linhas = [
			f"- {topico.jump_url}"
			for topico in sorted(
				topicos.values(), key=lambda item: (item.name.casefold(), item.id)
			)
			if topico != topico_indice
		]

		mensagens_antigas = [
			mensagem
			async for mensagem in topico_indice.history(limit=None)
			if mensagem.author.id == self.bot.user.id
		]
		for mensagem in mensagens_antigas:
			await mensagem.delete()

		if not linhas:
			linhas = ["Nenhum tópico encontrado no fórum."]

		partes: list[str] = []
		mensagem_atual = ""
		for linha in linhas:
			if mensagem_atual and len(mensagem_atual) + len(linha) + 1 > 2000:
				partes.append(mensagem_atual)
				mensagem_atual = ""

			if len(linha) > 2000:
				raise ValueError(
					f"O tópico {linha!r} excede o limite de caracteres do Discord."
				)

			mensagem_atual = f"{mensagem_atual}\n{linha}" if mensagem_atual else linha

		if mensagem_atual:
			partes.append(mensagem_atual)

		for parte in partes:
			await topico_indice.send(parte)

		await interaction.followup.send(
			f"Índice sincronizado com {len(topicos)} tópico(s).", ephemeral=True
		)
	

async def setup(bot: Bot):
	await bot.add_cog(BasicCog(bot))