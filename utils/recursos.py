import datetime
import discord
import os
import re

from bs4 import BeautifulSoup
from discord.ext import commands
from typing import TypedDict

from .console import is_unix
from .data import Config, get_config, carregar_biblia, setup_database
from .errors import setup_error_manager


class BibleDict(TypedDict):
	testamento: str
	livro: str
	capítulo: int
	versículo_inicial: int
	versículo_final: int
	texto: list[str]
	tipo: str


BIBLIA_INFO = {
	"antigoTestamento": {
		"Gênesis": {"abrev": "Gn", "abreviacoes": [], "tipo": "Pentateuco"},
		"Êxodo": {"abrev": "Êx", "abreviacoes": [], "tipo": "Pentateuco"},
		"Levítico": {"abrev": "Lv", "abreviacoes": [], "tipo": "Pentateuco"},
		"Números": {"abrev": "Nm", "abreviacoes": [], "tipo": "Pentateuco"},
		"Deuteronômio": {"abrev": "Dt", "abreviacoes": [], "tipo": "Pentateuco"},
		"Josué": {"abrev": "Js", "abreviacoes": [], "tipo": "Históricos"},
		"Juízes": {"abrev": "Jz", "abreviacoes": [], "tipo": "Históricos"},
		"Rute": {"abrev": "Rt", "abreviacoes": [], "tipo": "Históricos"},
		"I Samuel": {"abrev": "1Sm", "abreviacoes": ["Samuel"], "tipo": "Históricos"},
		"II Samuel": {"abrev": "2Sm", "abreviacoes": [], "tipo": "Históricos"},
		"I Reis": {"abrev": "1Rs", "abreviacoes": ["Reis"], "tipo": "Históricos"},
		"II Reis": {"abrev": "2Rs", "abreviacoes": [], "tipo": "Históricos"},
		"I Crônicas": {
			"abrev": "1Cr",
			"abreviacoes": ["Crônicas", "Cronicas"],
			"tipo": "Históricos",
		},
		"II Crônicas": {"abrev": "2Cr", "abreviacoes": [], "tipo": "Históricos"},
		"Esdras": {"abrev": "Esd", "abreviacoes": [], "tipo": "Históricos"},
		"Neemias": {"abrev": "Ne", "abreviacoes": [], "tipo": "Históricos"},
		"Tobias": {"abrev": "Tb", "abreviacoes": [], "tipo": "Históricos"},
		"Judite": {"abrev": "Jt", "abreviacoes": [], "tipo": "Históricos"},
		"Ester": {"abrev": "Est", "abreviacoes": [], "tipo": "Históricos"},
		"I Macabeus": {
			"abrev": "1Mc",
			"abreviacoes": ["Macabeus"],
			"tipo": "Históricos",
		},
		"II Macabeus": {"abrev": "2Mc", "abreviacoes": [], "tipo": "Históricos"},
		"Jó": {"abrev": "Jó", "abreviacoes": ["Jo"], "tipo": "Poéticos e Sapienciais"},
		"Salmos": {
			"abrev": "Sl",
			"abreviacoes": ["Salmo"],
			"tipo": "Poéticos e Sapienciais",
		},
		"Provérbios": {
			"abrev": "Pr",
			"abreviacoes": ["Provérbio"],
			"tipo": "Poéticos e Sapienciais",
		},
		"Eclesiastes": {
			"abrev": "Ecl",
			"abreviacoes": [],
			"tipo": "Poéticos e Sapienciais",
		},
		"Cântico dos Cânticos": {
			"abrev": "Ct",
			"abreviacoes": ["Cântico", "Cânticos", "Cantares"],
			"tipo": "Poéticos e Sapienciais",
		},
		"Sabedoria": {
			"abrev": "Sb",
			"abreviacoes": [],
			"tipo": "Poéticos e Sapienciais",
		},
		"Eclesiástico": {
			"abrev": "Eclo",
			"abreviacoes": [],
			"tipo": "Poéticos e Sapienciais",
		},
		"Isaías": {"abrev": "Is", "abreviacoes": [], "tipo": "Profetas Maiores"},
		"Jeremias": {"abrev": "Jr", "abreviacoes": [], "tipo": "Profetas Maiores"},
		"Lamentações": {"abrev": "Lm", "abreviacoes": [], "tipo": "Profetas Maiores"},
		"Baruc": {"abrev": "Br", "abreviacoes": [], "tipo": "Profetas Maiores"},
		"Ezequiel": {"abrev": "Ez", "abreviacoes": [], "tipo": "Profetas Maiores"},
		"Daniel": {"abrev": "Dn", "abreviacoes": [], "tipo": "Profetas Maiores"},
		"Oséias": {
			"abrev": "Os",
			"abreviacoes": ["Oseias"],
			"tipo": "Profetas Menores",
		},
		"Joel": {"abrev": "Jl", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Amós": {"abrev": "Am", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Abdias": {"abrev": "Ab", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Jonas": {"abrev": "Jn", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Miqueias": {"abrev": "Mq", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Naum": {"abrev": "Na", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Habacuc": {"abrev": "Hc", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Sofonias": {"abrev": "Sf", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Ageu": {"abrev": "Ag", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Zacarias": {"abrev": "Zc", "abreviacoes": [], "tipo": "Profetas Menores"},
		"Malaquias": {"abrev": "Ml", "abreviacoes": [], "tipo": "Profetas Menores"},
	},
	"novoTestamento": {
		"São Mateus": {
			"abrev": "Mt",
			"abreviacoes": ["Mateus", "Matheus"],
			"tipo": "Evangelhos",
		},
		"São Marcos": {"abrev": "Mc", "abreviacoes": ["Marcos"], "tipo": "Evangelhos"},
		"São Lucas": {"abrev": "Lc", "abreviacoes": ["Lucas"], "tipo": "Evangelhos"},
		"São João": {
			"abrev": "Jo",
			"abreviacoes": ["João", "Joao"],
			"tipo": "Evangelhos",
		},
		"Atos dos Apóstolos": {
			"abrev": "At",
			"abreviacoes": ["Atos"],
			"tipo": "Histórico",
		},
		"Romanos": {"abrev": "Rm", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"I Coríntios": {
			"abrev": "1Cor",
			"abreviacoes": ["Coríntios"],
			"tipo": "Cartas Paulinas",
		},
		"II Coríntios": {"abrev": "2Cor", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Gálatas": {"abrev": "Gl", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Efésios": {"abrev": "Ef", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Filipenses": {"abrev": "Fl", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Colossenses": {"abrev": "Cl", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"I Tessalonicenses": {
			"abrev": "1Ts",
			"abreviacoes": ["Tessalonicenses"],
			"tipo": "Cartas Paulinas",
		},
		"II Tessalonicenses": {
			"abrev": "2Ts",
			"abreviacoes": [],
			"tipo": "Cartas Paulinas",
		},
		"I Timóteo": {
			"abrev": "1Tm",
			"abreviacoes": ["Timóteo"],
			"tipo": "Cartas Paulinas",
		},
		"II Timóteo": {"abrev": "2Tm", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Tito": {"abrev": "Tt", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Filemon": {"abrev": "Fm", "abreviacoes": [], "tipo": "Cartas Paulinas"},
		"Hebreus": {"abrev": "Hb", "abreviacoes": [], "tipo": "Cartas Gerais"},
		"São Tiago": {
			"abrev": "Tg",
			"abreviacoes": ["Tiago", "Thiago", "Santiago", "Ti", "Th"],
			"tipo": "Cartas Gerais",
		},
		"I São Pedro": {
			"abrev": "1Pd",
			"abreviacoes": ["Pedro"],
			"tipo": "Cartas Gerais",
		},
		"II São Pedro": {"abrev": "2Pd", "abreviacoes": [], "tipo": "Cartas Gerais"},
		"I São João": {"abrev": "1Jo", "abreviacoes": [], "tipo": "Cartas Gerais"},
		"II São João": {"abrev": "2Jo", "abreviacoes": [], "tipo": "Cartas Gerais"},
		"III São João": {"abrev": "3Jo", "abreviacoes": [], "tipo": "Cartas Gerais"},
		"São Judas": {
			"abrev": "Jd",
			"abreviacoes": ["Judas", "Tadeu", "São Tadeu", "São Judas Tadeu"],
			"tipo": "Cartas Gerais",
		},
		"Apocalipse": {"abrev": "Ap", "abreviacoes": [], "tipo": "Apocalíptico"},
	},
}

ROMANOS = {1: "I", 2: "II", 3: "III"}

ORDINAIS = {
	1: ["Primeira", "1º", "1ª"],
	2: ["Segunda", "2º", "2ª"],
	3: ["Terceira", "3º", "3ª"],
}


def gerar_variacoes(nome):
	"""
	Gera automaticamente:
	I João
	1 João
	Primeira João
	1º João
	etc
	"""

	match = re.match(r"^(I|II|III)\s+(.*)", nome)

	if not match:
		return [nome]

	romano, base = match.groups()

	n = {"I": 1, "II": 2, "III": 3}[romano]

	variacoes = [nome, f"{n} {base}"]

	for forma in ORDINAIS[n]:
		variacoes.append(f"{forma} {base}")

	return variacoes


def montar_livros_map():
	mapa = {}

	for testamento, livros in BIBLIA_INFO.items():
		for nome, info in livros.items():
			variacoes = set()

			variacoes.add(nome)
			variacoes.add(info["abrev"])

			for v in gerar_variacoes(nome):
				variacoes.add(v)

			for a in info["abreviacoes"]:
				variacoes.add(a)

			for item in variacoes:
				mapa[item.lower()] = {
					"testamento": testamento,
					"livro": nome,
					"abrev": info["abrev"],
					"tipo": info["tipo"],
				}

	return mapa


LIVROS_MAP = montar_livros_map()


def gerar_info(biblia, livro_meta, cap, v1, v2):

	livro_nome = livro_meta["livro"]

	for livro in biblia[livro_meta["testamento"]]:
		if livro["nome"].lower() == livro_nome.lower():
			versos = livro["capitulos"][cap - 1]["versiculos"][v1 - 1 : v2]

			texto = [f"**{v['versiculo']}.** {v['texto']}" for v in versos]

			return {
				"testamento": livro_meta["testamento"],
				"livro": livro_nome,
				"capítulo": cap,
				"versículo_inicial": v1,
				"versículo_final": v2,
				"texto": texto,
				"tipo": livro_meta["tipo"],
			}


def expand_bible_verse(content: str) -> list[BibleDict]:

	data = []

	biblia = carregar_biblia()

	pattern = (
		r"^((?:[1-3]\s?)?"
		r"[A-Za-zÀ-ÿ]+"
		r"(?:\s+[A-Za-zÀ-ÿ]+)*)"
		r"\s*(\d+[,:\dab\.-]*)$"
	)

	def limpar_versiculo(v):
		return int(re.match(r"\d+", v).group())

	def parse_chapter_verses(text):

		match = re.match(r"^(\d+)[,:](.+)$", text.strip())

		if not match:
			return []

		capitulo = int(match.group(1))

		ranges = []

		for trecho in match.group(2).split("."):
			trecho = trecho.strip()

			if not trecho:
				continue

			if "-" in trecho:
				a, b = trecho.split("-")

				v1 = limpar_versiculo(a)
				v2 = limpar_versiculo(b)

			else:
				v1 = v2 = limpar_versiculo(trecho)

			ranges.append((capitulo, v1, v2))

		return ranges

	for bloco in content.split(";"):
		for linha in bloco.splitlines():
			linha = linha.strip()

			if not linha:
				continue

			match = re.match(pattern, linha)

			if not match:
				continue

			livro_input, cap_vers = match.groups()

			livro_meta = LIVROS_MAP.get(livro_input.lower())

			if not livro_meta:
				continue

			for cap, v1, v2 in parse_chapter_verses(cap_vers):
				data.append(
					gerar_info(biblia, livro_meta, cap, min(v1, v2), max(v1, v2))
				)

	return data


def _personalize_transcript(
	soup: BeautifulSoup, channel: discord.TextChannel, mensagens: int
):
	hoje = datetime.datetime.now()
	meses = [
		"janeiro",
		"fevereiro",
		"março",
		"abril",
		"maio",
		"junho",
		"julho",
		"agosto",
		"setembro",
		"outubro",
		"novembro",
		"dezembro",
	]
	data_formatada = f"{hoje.day} de {meses[hoje.month - 1].title()} de {hoje.year} às {hoje.hour:02d}:{hoje.minute:02d}:{hoje.second:02d}"
	titulo = f"Transcript do Ticket: {channel.name} - {channel.id}"

	for title in soup.find_all("title"):
		title.string = titulo

	for meta in soup.find_all("meta"):
		if meta.get("property") in ["og:title", "twitter:title"] or meta.get(
			"name"
		) in ["title", "og:title", "twitter:title"]:
			meta["content"] = titulo
		if meta.get("name") in [
			"description",
			"og:description",
			"twitter:description",
		] or meta.get("property") in [
			"description",
			"og:description",
			"twitter:description",
		]:
			meta["content"] = (
				f"Transcript do Ticket: {channel.name} - {channel.id}. Com {mensagens} mensagens. O transcript foi gerado em {data_formatada}"
			)

	traduzir = {
		"Summary": "Sumário",
		"Guild ID": "ID do Servidor",
		"Channel ID": "ID do Canal",
		"Channel Creation Date": "Data de Criação do Canal",
		"Total Message Count": "Quantidade Total de Mensagens",
		"Total Message Participants": "Total de Participantes nas Mensagens",
		"Member Since": "Membro Desde",
		"Member ID": "ID do Membro",
		"Message Count": "Quantidade de Mensagens",
	}

	for meta__value in soup.find_all("meta__value"):
		if meta__value.string and meta__value.string in traduzir:
			meta__value.string = traduzir[meta__value.string]

	for span in soup.find_all("span"):
		if span.string and span.string in traduzir:
			span.string = traduzir[span.string]
		if span.string:
			span.string = (
				span.string.replace("Today at", "Hoje às")
				.replace("Yesterday at", "Ontem às")
				.replace("Tomorrow at", "Amanhã às")
			)

	for span in soup.find_all("span", class_="info__title"):
		span.string = f"Bem-vindo ao canal #{channel.name}!"

	for span in soup.find_all("span", class_="info__subject"):
		span.string = f"Essas são as últimas 200 mensagens do canal #{channel.name}."

	for span in soup.find_all("span", class_="footer__text"):
		span.string = f"Esse transcript foi gerado em {data_formatada}"

	for style_tag in soup.find_all("style"):
		if style_tag.string:
			style_tag.string = style_tag.string.replace("#36393f", "#000")

	for tag in soup.find_all(style=True):
		tag["style"] = tag["style"].replace("#36393f", "#000")


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
		("I", 1),
	]

	resultado = ""
	for simbolo, valor in algarismos:
		while num >= valor:
			resultado += simbolo
			num -= valor

	return resultado


class HelpCommand(commands.HelpCommand):
	def __init__(self, bot: "Bot"):
		super().__init__()
		self.bot = bot

	async def send_bot_help(self, mapping):
		destination = self.get_destination()

		embed = discord.Embed(
			title="Lista de Comandos",
			description="Aqui estão todos os comandos disponíveis:",
			color=0xFFCC00,
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
		super().__init__(
			command_prefix=commands.when_mentioned_or("!"),
			intents=discord.Intents.all(),
			help_command=HelpCommand(self),
		)
		self.debug = is_unix()

	async def on_ready(self):
		await self.wait_until_ready()
		await self.load_cogs()
		setup_error_manager(self)
		print(f"Entramos como {self.user}")
		setup_database()

		texto = "Roma Locuta, Causa Finita."
		status = discord.Status.online
		emoji = discord.PartialEmoji.from_str("<:vaticano:1468962682123325552>")

		if self.debug:
			texto = "Em manutenção."
			status = discord.Status.idle

		activity = discord.CustomActivity(name=texto, emoji=emoji)
		await self.change_presence(status=status, activity=activity)

		"""
		view = discord.ui.LayoutView()
		view.add_item(
			discord.ui.Container(
				discord.ui.Section(
					discord.ui.TextDisplay("## Bot iniciado com sucesso!"),
					accessory=discord.ui.Thumbnail(self.user.display_avatar.url),
				)
			)
		)
		await self.send_to_console(view=view)
		"""

	async def load_cogs(self):
		for extension in os.listdir("cogs"):
			if extension.endswith(".py"):
				try:
					await self.load_extension(f"cogs.{extension[:-3]}")
				except commands.errors.ExtensionAlreadyLoaded:
					await self.reload_extension(f"cogs.{extension[:-3]}")
		await self.tree.sync()
		await self.tree.sync(guild=discord.Object(1464281876507398168))

	async def send_to_console(
		self,
		content: str = None,
		*,
		embeds: list[discord.Embed] = None,
		view: discord.ui.View = None,
	):
		console = self.get_channel(1462077223140851903)
		if console:
			return await console.send(content=content, embeds=embeds, view=view)

	@property
	def config(self) -> Config:
		return get_config()