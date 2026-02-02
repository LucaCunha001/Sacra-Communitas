import discord
import random

from discord import app_commands, ui
from discord.ext import commands

from utils.recursos import Bot, expand_bible_verse
from utils.data import BibliaDict, carregar_biblia, TestamentoDict, get_config

from typing import Literal

guild_ids = [get_config()["config"]["servidores"]["main"]]

class BibliaCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	biblia_bp = app_commands.Group(
		name="biblia",
		description="Comandos relacionados à Bíblia"
	)

	@biblia_bp.command(name="aleatório", description="Escolha um versículo aleatório")
	async def aleatorio(self, interaction: discord.Interaction):
		biblia = carregar_biblia()
		livros: list[TestamentoDict] = biblia[random.choice(list(biblia))]
		livro = random.choice(livros)
		nome = livro["nome"]
		capitulos = livro["capitulos"]
		capitulo = random.choice(capitulos)
		versiculos = capitulo["versiculos"]
		versiculo = random.choice(versiculos)["versiculo"]

		resultados = expand_bible_verse(f"{nome} {capitulo['capitulo']},{versiculo}")
		embeds = []

		for res in resultados:
			versiculo_inicial = res['versículo_inicial']
			versiculo_final = res['versículo_final']
			versiculo = versiculo_inicial if versiculo_inicial == versiculo_final else f"{versiculo_inicial}-{versiculo_final}"

			tipo = res['tipo']
			separador = ":" if tipo == "Evangelhos" else ","

			passagem = f"{res['capítulo']}{separador}{versiculo}"

			embed = discord.Embed(
				title=f"{res['livro']} {passagem} ({tipo})",
				description=f"{res['texto']}",
				colour=0xffcc00
			)
			embeds.append(embed)

		await interaction.response.send_message(embeds=embeds)

	@biblia_bp.command(name="ler", description="Leia um versículo bíblico")
	@app_commands.choices(
		testamento=[
			app_commands.Choice(name="Antigo Testamento", value="antigoTestamento"),
			app_commands.Choice(name="Novo Testamento", value="novoTestamento")
		]
	)
	@app_commands.describe(
		testamento="O testamento a ser lido"
	)
	async def testamento(
		self,
		interaction: discord.Interaction,
		testamento: app_commands.Choice[str]
	):
		biblia = carregar_biblia()

		await interaction.response.send_message(
			f"📖 Você escolheu o **{testamento.name}**.\nAgora escolha um livro:",
			view=self.LivroSelectView(biblia, testamento.value),
			ephemeral=True
		)

	class LivroSelect(discord.ui.Select):
		def __init__(self, biblia: BibliaDict, testamento: str, pagina: int = 0):
			self.biblia = biblia
			self.testamento = testamento
			self.pagina = pagina

			livros = biblia[testamento]
			inicio = pagina * 25
			fim = inicio + 25

			options = [
				discord.SelectOption(label=livro["nome"], value=str(i))
				for i, livro in enumerate(livros[inicio:fim], start=inicio)
			]

			super().__init__(
				placeholder=f"Selecione um livro... (página {pagina + 1})",
				min_values=1,
				max_values=1,
				options=options
			)

		async def callback(self, interaction: discord.Interaction):
			livro_index = int(self.values[0])
			livro = self.biblia[self.testamento][livro_index]

			await interaction.response.edit_message(
				content=f"📘 Livro selecionado: **{livro['nome']}**\nAgora escolha o capítulo:",
				view=BibliaCog.CapituloSelectView(self.biblia, self.testamento, livro_index)
			)

	class LivroSelectView(discord.ui.View):
		def __init__(self, biblia: BibliaDict, testamento: str, pagina: int = 0):
			super().__init__(timeout=None)
			self.biblia = biblia
			self.testamento = testamento
			self.pagina = pagina
			self.total_paginas = (len(biblia[testamento]) - 1) // 25 + 1

			self.select_menu = BibliaCog.LivroSelect(biblia, testamento, pagina)
			self.add_item(self.select_menu)

			if self.total_paginas > 1:
				self.add_item(BibliaCog.AnteriorButton(self))
				self.add_item(BibliaCog.ProximoButton(self))

	class CapituloSelect(discord.ui.Select):
		def __init__(self, biblia: BibliaDict, testamento: str, livro_index: int, pagina: int = 0):
			self.biblia = biblia
			self.testamento = testamento
			self.livro_index = livro_index
			self.pagina = pagina

			livro = biblia[testamento][livro_index]
			num_capitulos = len(livro["capitulos"])
			inicio = pagina * 25
			fim = inicio + 25

			options = [
				discord.SelectOption(label=f"Capítulo {i+1}", value=str(i+1))
				for i in range(inicio, min(fim, num_capitulos))
			]

			super().__init__(
				placeholder=f"Selecione um capítulo... (página {pagina + 1})",
				min_values=1,
				max_values=1,
				options=options
			)

		async def callback(self, interaction: discord.Interaction):
			capitulo = int(self.values[0])


			views = await BibliaCog.viewBiblia(
				self.biblia, self.testamento, self.livro_index + 1, capitulo
			)

			for i, view in enumerate(views):
				if i == 0:
					await interaction.response.send_message(view=view)
				else:
					await interaction.followup.send(view=view)

	class CapituloSelectView(discord.ui.View):
		def __init__(self, biblia: BibliaDict, testamento: str, livro_index: int, pagina: int = 0):
			super().__init__(timeout=120)
			self.biblia = biblia
			self.testamento = testamento
			self.livro_index = livro_index
			self.pagina = pagina

			livro = biblia[testamento][livro_index]
			self.total_paginas = (len(livro["capitulos"]) - 1) // 25 + 1

			self.select_menu = BibliaCog.CapituloSelect(biblia, testamento, livro_index, pagina)
			self.add_item(self.select_menu)

			if self.total_paginas > 1:
				self.add_item(BibliaCog.AnteriorButton(self))
				self.add_item(BibliaCog.ProximoButton(self))

	class ProximoButton(discord.ui.Button):
		def __init__(self, parent_view):
			super().__init__(label="⏭️ Próxima", style=discord.ButtonStyle.primary)
			self.parent_view = parent_view

		async def callback(self, interaction: discord.Interaction):
			self.parent_view.pagina = (self.parent_view.pagina + 1) % self.parent_view.total_paginas

			if isinstance(self.parent_view, BibliaCog.LivroSelectView):
				nova_view = BibliaCog.LivroSelectView(
					self.parent_view.biblia,
					self.parent_view.testamento,
					self.parent_view.pagina
				)
			else:
				nova_view = BibliaCog.CapituloSelectView(
					self.parent_view.biblia,
					self.parent_view.testamento,
					self.parent_view.livro_index,
					self.parent_view.pagina
				)

			await interaction.response.edit_message(view=nova_view)

	class AnteriorButton(discord.ui.Button):
		def __init__(self, parent_view):
			super().__init__(label="⏮️ Anterior", style=discord.ButtonStyle.secondary)
			self.parent_view = parent_view

		async def callback(self, interaction: discord.Interaction):
			self.parent_view.pagina = (self.parent_view.pagina - 1) % self.parent_view.total_paginas

			if isinstance(self.parent_view, BibliaCog.LivroSelectView):
				nova_view = BibliaCog.LivroSelectView(
					self.parent_view.biblia,
					self.parent_view.testamento,
					self.parent_view.pagina
				)
			else:
				nova_view = BibliaCog.CapituloSelectView(
					self.parent_view.biblia,
					self.parent_view.testamento,
					self.parent_view.livro_index,
					self.parent_view.pagina
				)

			await interaction.response.edit_message(view=nova_view)

	@staticmethod
	async def viewBiblia(
		biblia: BibliaDict,
		testamento: Literal["antigoTestamento", "novoTestamento"],
		livro: int = 1,
		capitulo: int = 1
	) -> list[ui.LayoutView]:

		views: list[ui.LayoutView] = []

		livro -= 1
		capitulo -= 1

		livro_data = biblia[testamento][livro]
		cap = livro_data["capitulos"][capitulo]

		titulo = f"{livro_data['nome']} {capitulo+1}"

		def novo_container(continuacao: bool = False):
			texto_titulo = f"## {titulo}" + (" (continuação)" if continuacao else "")
			container = ui.Container(
				ui.TextDisplay(texto_titulo),
				accent_color=0xFFCC00
			)
			container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
			return container

		view = ui.LayoutView()
		container = novo_container(continuacao=False)

		items_count = 3

		for v in cap["versiculos"]:
			linha = f"**{v['versiculo']}.** {v['texto']}"
			container.add_item(ui.TextDisplay(linha))
			items_count += 1

			if items_count >= 40:
				view.add_item(container)
				views.append(view)

				view = ui.LayoutView()
				container = novo_container(continuacao=True)
				items_count = 3

		if items_count > 3:
			view.add_item(container)
			views.append(view)

		return views

async def setup(bot: Bot):
	await bot.add_cog(BibliaCog(bot))