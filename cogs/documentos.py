
from os import name

import discord

from discord import app_commands
from discord.ext import commands

from utils.recursos import Bot
from utils.vatican import pesquisar_documentos, pesquisar_papas

class Documentos(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	@commands.hybrid_group(
		name="magisterium",
		aliases=["mag", "magisterio"],
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
		quantidade: app_commands.Range[int, 1, 5] = 1
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

	@magisterium_api.command(
		name="concilio",
		aliases=["con", "conc", "concilios"],
		description="Pesquisa documentos dos Concílios no site do Vaticano."
	)
	@app_commands.describe(
		concilio="Nome do Concílio"
	)
	async def concilios(self, ctx: commands.Context, *, concilio: str):
		if ctx.interaction:
			await ctx.interaction.response.defer(thinking=True)

		try:
			resultados = await pesquisar_documentos(
				concilio,
				quantidade=5
			)

			if not resultados:
				mensagem = (
					"Não encontrei documentos para esse Concílio. "
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
					f"# Documentos de Concílios\n"
					f"Pesquisa: **{concilio}**"
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
			print(f"Erro na pesquisa de Concílios: {erro}")

			mensagem = (
				"Não foi possível consultar os documentos "
				"dos Concílios no site do Vaticano."
			)

			if ctx.interaction:
				await ctx.interaction.followup.send(
					mensagem,
					ephemeral=True
				)
			else:
				await ctx.reply(mensagem)

	@magisterium_api.command(
		name="papa",
		aliases=["papas"],
		description="Consulta informações sobre os Sumos Pontífices."
	)
	@app_commands.describe(
		papa="Nome do Papa ou número de ordem"
	)
	async def papa_cmd(
		self,
		ctx: commands.Context,
		*,
		papa: str
	):
		if ctx.interaction:
			await ctx.interaction.response.defer(thinking=True)

		try:
			resultados = await pesquisar_papas(
				papa,
				quantidade=5
			)

			if not resultados:
				mensagem = (
					"Não encontrei nenhum pontífice correspondente "
					"à pesquisa."
				)

				if ctx.interaction:
					await ctx.interaction.followup.send(mensagem)
				else:
					await ctx.reply(mensagem)

				return

			view = discord.ui.LayoutView()

			container = discord.ui.Container(
				discord.ui.TextDisplay(
					"# Sumo Pontífice\n"
				),
				accent_color=0xFFCC00
			)

			for item in resultados:
				nome = (
					f"{item['nome_pt']} / "
					f"{item['nome_it']}"
				)

				fim = item["fim"]

				if fim == "—":
					fim = "Em exercício"

				conteudo = (
					f"## {item['numero']}º Papa\n"
					f"**{nome}**\n\n"
					f"**Pontificado:**\n"
					f"{item['inicio']} – {fim}\n\n"
					f"**Nome de nascimento:**\n"
					f"{item['nome_nascimento'] or 'Desconhecido'}\n\n"
					f"**Nascimento:**\n"
					f"{item['nascimento'] or 'Desconhecido'}\n\n"
					f"**Século:** {item['seculo'] or 'Desconhecido'}\n\n"
				)

				texto = discord.ui.TextDisplay(conteudo)

				if item["imagem"]:
					secao = discord.ui.Section(
						texto,
						accessory=discord.ui.Thumbnail(
							media=item["imagem"].replace(" ", "%20"),
							description=f"Fotografia de {item['nome_pt']}"
						)
					)

					container.add_item(secao)
				else:
					container.add_item(texto)

				row = discord.ui.ActionRow(
					discord.ui.Button(
						style=discord.ButtonStyle.link,
						label="Consultar no Vaticano",
						url=item['url']
					)
				)
				container.add_item(row)

			view.add_item(container)

			if ctx.interaction:
				await ctx.interaction.followup.send(view=view)
			else:
				await ctx.reply(view=view)

		except Exception as erro:
			print(f"Erro na pesquisa de Papas: {erro}")

			mensagem = (
				"Não foi possível consultar os registros "
				"dos Sumos Pontífices."
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
