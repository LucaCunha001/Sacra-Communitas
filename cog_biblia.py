import json
import os
import re

import discord
import random

from discord import app_commands
from discord.ext import commands

from typing import TypedDict, Literal

class VersiculoDict(TypedDict):
	versiculo: int
	texto: str

class CapituloDict(TypedDict):
	capitulo: int
	versiculos: list[VersiculoDict]

class TestamentoDict(TypedDict):
	nome: str
	capitulos: list[CapituloDict]

class BibliaDict(TypedDict):
	antigoTestamento: list[TestamentoDict]
	novoTestamento: list[TestamentoDict]

def abrir_json(arquivo: str) -> dict | list:
	if os.path.isfile(arquivo):
		with open(arquivo, "r", encoding="utf-8") as f:
			return json.load(f)

	return {}

def carregar_biblia() -> BibliaDict:
	return abrir_json("data/biblia.json")

class BibleVerseInfo(TypedDict):
	testamento: str
	livro: str
	capítulo: int
	versículo_inicial: int
	versículo_final: int
	texto: str
	tipo: str

class BibleDict(TypedDict):
	testamento: str
	livro: str
	capítulo: int
	versículo_inicial: int
	versículo_final: int
	texto: str
	tipo: str

def expand_bible_verse(content: str) -> list[BibleDict]:
	data = []
	biblia = carregar_biblia()

	abreviacoes = {
		"1Sm": ["1 Samuel", "Primeira Samuel", "1º Samuel", "1ª Samuel"],
		"2Sm": ["2 Samuel", "Segunda Samuel", "2º Samuel", "2ª Samuel"],

		"1Rs": ["1 Reis", "Primeira Reis", "1º Reis", "1ª Reis"],
		"2Rs": ["2 Reis", "Segunda Reis", "2º Reis", "2ª Reis"],

		"1Cr": ["1 Crônicas", "Primeira Crônicas", "1º Crônicas", "1ª Crônicas"],
		"2Cr": ["2 Crônicas", "Segunda Crônicas", "2º Crônicas", "2ª Crônicas"],

		"1Mc": ["1 Macabeus", "Primeira Macabeus", "1º Macabeus", "1ª Macabeus"],
		"2Mc": ["2 Macabeus", "Segunda Macabeus", "2º Macabeus", "2ª Macabeus"],

		"Sl": ["Salmos", "Salmo"],
		"Pr": ["Provérbios", "Provérbio"],
		"Ct": ["Cânticos", "Cântico", "Cantares"],

		"Mt": ["Mateus", "Matheus"],
		"Mc": ["Marcos"],
		"Lc": ["Lucas"],
		"Jo": ["João", "Joao"],
		"At": ["Atos"],

		"1Cor": ["1 Coríntios", "Primeira Coríntios", "1º Coríntios", "1ª Coríntios"],
		"2Cor": ["2 Coríntios", "Segunda Coríntios", "2º Coríntios", "2ª Coríntios"],

		"1Ts": ["1 Tessalonicenses", "Primeira Tessalonicenses", "1º Tessalonicenses", "1ª Tessalonicenses"],
		"2Ts": ["2 Tessalonicenses", "Segunda Tessalonicenses", "2º Tessalonicenses", "2ª Tessalonicenses"],

		"1Tm": ["1 Timóteo", "Primeira Timóteo", "1º Timóteo", "1ª Timóteo"],
		"2Tm": ["2 Timóteo", "Segunda Timóteo", "2º Timóteo", "2ª Timóteo"],

		"1Pd": ["1 Pedro", "Primeira Pedro", "1º Pedro", "1º Pedro"],
		"2Pd": ["2 Pedro", "Segunda Pedro", "2º Pedro", "2ª Pedro"],

		"1Jo": ["1 João", "Primeira João", "1º João", "1ª João"],
		"2Jo": ["2 João", "Segunda João", "2º João", "2ª João"],
		"3Jo": ["3 João", "Terceira João", "3º João", "3ª João"],
		
		"Jd": ["Judas", "Tadeu", "São Tadeu", "São Judas Tadeu", "Judas Tadeu"]
	}

	livros = {
		"antigoTestamento": {
			"Gênesis": "Gn",
			"Êxodo": "Êx",
			"Levítico": "Lv",
			"Números": "Nm",
			"Deuteronômio": "Dt",
			"Josué": "Js",
			"Juízes": "Jz",
			"Rute": "Rt",
			"I Samuel": "1Sm",
			"II Samuel": "2Sm",
			"I Reis": "1Rs",
			"II Reis": "2Rs",
			"I Crônicas": "1Cr",
			"II Crônicas": "2Cr",
			"Esdras": "Esd",
			"Neemias": "Ne",
			"Tobias": "Tb",
			"Judite": "Jt",
			"Ester": "Est",
			"I Macabeus": "1Mc",
			"II Macabeus": "2Mc",
			"Jó": "Jó",
			"Salmos": "Sl",
			"Provérbios": "Pr",
			"Eclesiastes": "Ecl",
			"Cântico dos Cânticos": "Ct",
			"Sabedoria": "Sb",
			"Eclesiástico": "Eclo",
			"Isaías": "Is",
			"Jeremias": "Jr",
			"Lamentações": "Lm",
			"Baruc": "Br",
			"Ezequiel": "Ez",
			"Daniel": "Dn",
			"Oseias": "Os",
			"Joel": "Jl",
			"Amós": "Am",
			"Abdias": "Ab",
			"Jonas": "Jn",
			"Miqueias": "Mq",
			"Naum": "Na",
			"Habacuc": "Hc",
			"Sofonias": "Sf",
			"Ageu": "Ag",
			"Zacarias": "Zc",
			"Malaquias": "Ml"
		},
		"novoTestamento": {
			"São Mateus": "Mt",
			"São Marcos": "Mc",
			"São Lucas": "Lc",
			"São João": "Jo",
			"Atos dos Apóstolos": "At",
			"Romanos": "Rm",
			"I Coríntios": "1Cor",
			"II Coríntios": "2Cor",
			"Gálatas": "Gl",
			"Efésios": "Ef",
			"Filipenses": "Fl",
			"Colossenses": "Cl",
			"I Tessalonicenses": "1Ts",
			"II Tessalonicenses": "2Ts",
			"I Timóteo": "1Tm",
			"II Timóteo": "2Tm",
			"Tito": "Tt",
			"Filemon": "Fm",
			"Hebreus": "Hb",
			"São Tiago": "Tg",
			"I São Pedro": "1Pd",
			"II São Pedro": "2Pd",
			"I São João": "1Jo",
			"II São João": "2Jo",
			"III São João": "3Jo",
			"São Judas": "Jd",
			"Apocalipse": "Ap"
		}
	}

	tipos = {
		"Pentateuco": [
			"Gn", "Êx", "Lv", "Nm", "Dt"
		],
		"Históricos": [
			"Js", "Jz", "Rt", "1Sm", "2Sm", "1Rs", "2Rs", "1Cr", "2Cr", "Esd", "Ne", "Tb", "Jt", "Est", "1Mc", "2Mc"
		],
		"Poéticos e Sapienciais": [
			"Jó", "Sl", "Pr", "Ecl", "Ct", "Sb", "Eclo"
		],
		"Profetas Maiores": [
			"Is", "Jr", "Lm", "Br", "Ez", "Dn"
		],
		"Profetas Menores": [
			"Os", "Jl", "Am", "Ab", "Jn", "Mq", "Na", "Hc", "Sf", "Ag", "Zc", "Ml"
		],
		"Evangelhos": [
			"Mt", "Mc", "Lc", "Jo"
		],
		"Histórico": [
			"At"
		],
		"Cartas Paulinas": [
			"Rm", "1Cor", "2Cor", "Gl", "Ef", "Fl", "Cl", "1Ts", "2Ts", "1Tm", "2Tm", "Tt", "Fm"
		],
		"Cartas Gerais": [
			"Hb", "Tg", "1Pd", "2Pd", "1Jo", "2Jo", "3Jo", "Jd"
		],
		"Apocalíptico": [
			"Ap"
		]
	}

	livros_map: dict[str, tuple[str, str]] = {}
	for _, alternativas in abreviacoes.items():
		for alt in alternativas:
			for testamento, livros_dict in livros.items():
				for livro_nome in livros_dict.keys():
					if alt.lower() in livro_nome.lower() or alt.lower() == livro_nome.lower():
						livros_map[alt.lower()] = (testamento, livro_nome)
	for testamento, livros_dict in livros.items():
		for livro_nome, abrev in livros_dict.items():
			livros_map[livro_nome.lower()] = (testamento, livro_nome)
			livros_map[abrev.lower()] = (testamento, livro_nome)

	def gerar_info(testamento: str, livro: str, capitulo: int, versiculo1: int, versiculo2: int) -> BibleVerseInfo:
		texto = ""
		for livro_ in biblia[testamento]:
			if livro_["nome"].lower() == livro.lower():
				cap_idx = capitulo - 1
				vers_ini = versiculo1 - 1
				vers_fim = versiculo2
				versiculos = livro_["capitulos"][cap_idx]["versiculos"][vers_ini:vers_fim]
				texto = ""
				for v in versiculos:
					texto += f"**{v['versiculo']}.** {v['texto']} "
				texto = texto.replace("“", "\"")
				texto = texto.replace("”", "\"")
				break
		
		abrev = livros[testamento][livro]
		return {
			"testamento": testamento,
			"livro": livro,
			"capítulo": capitulo,
			"versículo_inicial": versiculo1,
			"versículo_final": versiculo2,
			"texto": texto,
			"tipo": next(
				(tipo for tipo, livros_ in tipos.items() if abrev in livros_),
				None
			)
		}

	def parse_chapter_verses(text: str):
		match = re.match(r'^(\d+)[,:](.+)$', text.strip())
		if not match:
			return []

		capitulo = int(match.group(1))
		versiculos_str = match.group(2)
		ranges = []

		for trecho in versiculos_str.split('.'):
			trecho = trecho.strip()
			if not trecho:
				continue
			if '-' in trecho:
				v_start, v_end = map(int, trecho.split('-'))
			else:
				v_start = v_end = int(trecho)
			ranges.append((capitulo, v_start, v_end))
		return ranges

	pattern = r"^([1-3]?\s?(?:[A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)*))\s*(\d+[,:\d\.-]*)$"

	for c in content.split(";"):
		for conteudo in c.split('\n'):
			conteudo = conteudo.strip()
			match = re.match(pattern, conteudo)
			if not match:
				continue

			livro_input, cap_vers_text = match.groups()
			livro_input_lower = livro_input.lower()

			if livro_input_lower in livros_map:
				testamento, nome_oficial = livros_map[livro_input_lower]
				ranges = parse_chapter_verses(cap_vers_text)
				for cap, v_s, v_e in ranges:
					v_start, v_end = sorted((v_s, v_e))
					data.append(gerar_info(testamento, nome_oficial, cap, v_start, v_end))

	return data

class BibliaCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
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

			await interaction.response.defer(thinking=True, ephemeral=False)
			embeds = await BibliaCog.embedBiblia(
				self.biblia, self.testamento, self.livro_index + 1, capitulo
			)

			for embed in embeds:
				await interaction.followup.send(embed=embed)

	class CapituloSelectView(discord.ui.View):
		def __init__(self, biblia: BibliaDict, testamento: str, livro_index: int, pagina: int = 0):
			super().__init__(timeout=None)
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
	async def embedBiblia(
		biblia: BibliaDict,
		testamento: Literal["antigoTestamento", "novoTestamento"],
		livro: int = 1,
		capitulo: int = 1
	) -> list[discord.Embed]:
		embeds = []
		livro -= 1
		capitulo -= 1

		livro_data = biblia[testamento][livro]
		cap = livro_data["capitulos"][capitulo]

		embed = discord.Embed(
			title=f"{livro_data['nome']} {capitulo+1}",
			description="",
			color=0xffcc00
		)

		for v in cap["versiculos"]:
			versiculo_texto = f"**{v['versiculo']}.** {v['texto']}\n"
			if len(embed.description + versiculo_texto) > 4096:
				embeds.append(embed)
				embed = discord.Embed(
					title=f"{livro_data['nome']} {capitulo+1} (continuação)",
					description="",
					color=0xffcc00
				)
			embed.description += versiculo_texto

		embeds.append(embed)
		return embeds
	
	@commands.Cog.listener()
	async def on_message(self, msg: discord.Message):		
		if msg.author.bot:
			return
		
		await self.check_bible_verse(msg=msg)

	async def check_bible_verse(self, msg: discord.Message):
		resultados = expand_bible_verse(msg.content)
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

		if embeds:
			await msg.channel.send(embeds=embeds)

async def setup(bot: commands.Bot):
	await bot.add_cog(BibliaCog(bot))