
import discord

from discord import app_commands
from discord.ext import commands

from utils.recursos import Bot
from utils.vatican import pesquisar_documentos


class Documentos(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	@commands.hybrid_group(
		name="magisterium",
		aliases=["mag"],
		invoke_without_command=True
	)
	async def magisterium_api(
		self,
		ctx: commands.Context
	):
		await ctx.send_help(ctx.command)

	@magisterium_api.command(
		name="documentos",
		aliases = ["doc"],
		description="Pesquisa documentos no site oficial do Vaticano."
	)
	@app_commands.describe(
		pesquisa="Título ou assunto do documento",
		quantidade="Quantidade de resultados (1 a 5)"
	)
	async def documentos(
		self,
		ctx: commands.Context,
		*,
		pesquisa: str,
		quantidade: app_commands.Range[int, 1, 5] = 3
	):
		if ctx.interaction:
			await ctx.interaction.response.defer(thinking=True)

		try:
			resultados = await pesquisar_documentos(
				pesquisa,
				quantidade
			)

			if not resultados:
				mensagem = (
					"Não encontrei resultados. "
					"Tente outros termos de pesquisa."
				)
				if ctx.interaction:
					await ctx.interaction.followup.send(mensagem)
				else:
					await ctx.reply(mensagem)
				return

			view = discord.ui.LayoutView()

			container = discord.ui.Container(
				discord.ui.TextDisplay(
					f"# Documentos da Santa Sé\n"
					f"Pesquisa: **{pesquisa}**"
				),
				accent_color=0xFFCC00
			)

			for item in resultados:
				container.add_item(
					discord.ui.TextDisplay(
						f"**{item['titulo']}**\n"
						f"{item['url']}"
					)
				)

			view.add_item(container)

			if ctx.interaction:
				await ctx.interaction.followup.send(view=view)
			else:
				await ctx.reply(view=view)

		except Exception as erro:
			print(f"Erro na busca do Vaticano: {erro}")

			mensagem = (
				"Não foi possível consultar o site do Vaticano."
			)

			if ctx.interaction:
				await ctx.interaction.followup.send(
					mensagem,
					ephemeral=True
				)
			else:
				await ctx.reply(mensagem)


async def setup(bot: Bot):
	await bot.add_cog(Documentos(bot))
