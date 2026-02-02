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
		if numero <= 0:
			await interaction.response.send_message("Por favor, insira um número inteiro positivo maior que zero.", ephemeral=True)
			return
		
		romano = contar(numero)
		await interaction.response.send_message(f"O número {numero} em algarismos romanos é: **{romano}**")

async def setup(bot: Bot):
	await bot.add_cog(BasicCog(bot))