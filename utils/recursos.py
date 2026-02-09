import discord
import os
import re

from discord.ext import commands
from typing import TypedDict

from .console import is_unix
from .data import Config, get_config, carregar_biblia

class BibleDict(TypedDict):
	testamento: str
	livro: str
	capítulo: int
	versículo_inicial: int
	versículo_final: int
	texto: list[str]
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

	def gerar_info(testamento: str, livro: str, capitulo: int, versiculo1: int, versiculo2: int) -> BibleDict:
		texto: list[str] = []
		for livro_ in biblia[testamento]:
			if livro_["nome"].lower() == livro.lower():
				cap_idx = capitulo - 1
				vers_ini = versiculo1 - 1
				vers_fim = versiculo2
				versiculos = livro_["capitulos"][cap_idx]["versiculos"][vers_ini:vers_fim]
				texto = []
				for v in versiculos:
					versiculo = (
						v['versiculo'],
						v['texto'].replace("“", "\"").replace("”", "\"")
					)
					texto.append(f"**{versiculo[0]}.** {versiculo[1]} ")
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

	def limpar_versiculo(v: str) -> int:
		return int(re.match(r"\d+", v).group())

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
				v_start_raw, v_end_raw = trecho.split('-')
				v_start = limpar_versiculo(v_start_raw)
				v_end = limpar_versiculo(v_end_raw)
			else:
				v_start = v_end = limpar_versiculo(trecho)

			ranges.append((capitulo, v_start, v_end))

		return ranges

	pattern = r"^((?:[1-3]\s?)?[A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)*)\s*(\d+[,:\dab\.-]*)$"

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

def contar(num: int) -> str:
	algarismos = [
		("M", 1000),
		("CM", 900),
		("D", 500),
		("CD", 400),
		("C", 100),
		("XC", 90),
		("L", 50),
		("XL", 40),
		("X", 10),
		("IX", 9),
		("V", 5),
		("IV", 4),
		("I", 1)
	]

	resultado = ""
	for simbolo, valor in algarismos:
		while num >= valor:
			resultado += simbolo
			num -= valor

	return resultado

class HelpCommand(commands.HelpCommand):
	def __init__(self, bot: 'Bot'):
		super().__init__()
		self.bot = bot

	async def send_bot_help(self, mapping):
		destination = self.get_destination()

		embed = discord.Embed(
			title="Lista de Comandos",
			description="Aqui estão todos os comandos disponíveis:",
			color=0xFFCC00
		)

		for cog, commands_list in mapping.items():
			comandos_visiveis = await self.filter_commands(commands_list, sort=True)
			if comandos_visiveis:
				nome_cog = getattr(cog, "qualified_name", "Sem categoria")
				comandos_formatados = " ".join(f"`{c.name}`" for c in comandos_visiveis)
				embed.add_field(name=nome_cog, value=comandos_formatados, inline=False)

		await destination.send(embed=embed)

class Bot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=discord.Intents.all(), help_command=HelpCommand(self))
	
	async def on_ready(self):
		await self.wait_until_ready()
		await self.load_cogs()
		print(f'Entramos como {self.user}')

		texto = "Roma Locuta, Causa Finita."
		status = discord.Status.online
		emoji = discord.PartialEmoji.from_str("<:vaticano:1468962682123325552>")

		if not is_unix():
			texto = "Em manutenção."
			status = discord.Status.idle
		
		activity = discord.CustomActivity(name=texto, emoji=emoji)
		await self.change_presence(status=status, activity=activity)
	
	async def load_cogs(self):
		for extension in os.listdir("cogs"):
			if extension.endswith(".py"):
				try:
					await self.load_extension(f"cogs.{extension[:-3]}")
				except commands.errors.ExtensionAlreadyLoaded:
					await self.reload_extension(f"cogs.{extension[:-3]}")
		await self.tree.sync()
		await self.tree.sync(guild=discord.Object(1464281876507398168))
	
	async def send_to_console(self, content: str = None, *, embeds: list[discord.Embed] = None, view: discord.ui.View = None):
		console = self.get_channel(1462077223140851903)
		if console:
			return await console.send(content=content, embeds=embeds, view=view)

	@property
	def config(self) -> Config:
		return get_config()