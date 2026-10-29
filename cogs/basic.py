import asyncio
import discord

from discord import app_commands
from discord.ext import commands

from utils.data import get_embeds
from utils.embed import convert_embed
from utils.recursos import Bot, contar
from utils.permissoes import permissao

class BasicCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

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