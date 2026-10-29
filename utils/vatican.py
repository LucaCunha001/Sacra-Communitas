import aiohttp
import re
import unicodedata
import xml.etree.cElementTree as ET

from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote, urljoin

SEARCH_URL = "https://www.bing.com/search"

PREFERRED_LANGUAGES = ("PT", "EN", "IT")

DOCUMENT_SELECTORS = (
	"div.documento",
	"div.document",
	"div.text",
	"article",
	"main",
	"#content",
)

def normalizar(texto: str) -> str:
	texto = unicodedata.normalize("NFD", texto.lower())
	texto = "".join(
		caractere
		for caractere in texto
		if unicodedata.category(caractere) != "Mn"
	)
	return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def corresponde_pesquisa(
	consulta: str,
	titulo: str,
	url: str,
) -> bool:
	termos = normalizar(consulta).split()
	termos = [
		termo for termo in termos
		if termo not in {"de", "da", "do", "das", "dos", "a", "o", "e"}
	]

	if not termos:
		return True

	# Verifica o título e o nome do arquivo, não apenas o domínio.
	texto = normalizar(
		titulo + " " + urlparse(url).path.rsplit("/", 1)[-1]
	)
	palavras = set(texto.split())

	return all(termo in palavras for termo in termos)

def is_vatican_url(url: str) -> bool:
	return urlparse(url).hostname in {
		"vatican.va",
		"www.vatican.va",
	}


def extrair_texto(soup: BeautifulSoup) -> str:
	"""Extrai o conteúdo provável do documento, sem a navegação."""

	for elemento in soup.select(
		"script, style, nav, header, footer, "
		".translation-field, .breadcrumb, "
		".breadcrumbs, .navigation, .footer, .header"
	):
		elemento.decompose()

	candidatos = []

	for seletor in DOCUMENT_SELECTORS:
		for elemento in soup.select(seletor):
			texto = elemento.get_text(" ", strip=True)

			if texto:
				candidatos.append((len(texto), texto))

	if candidatos:
		return max(candidatos, key=lambda item: item[0])[1]

	return soup.get_text(" ", strip=True)


def tem_conteudo(soup: BeautifulSoup) -> bool:
	"""Evita aceitar páginas que só possuem título ou navegação."""

	texto = extrair_texto(soup)

	paragrafos = soup.find_all("p")
	paragrafos_validos = [
		p for p in paragrafos
		if len(p.get_text(" ", strip=True)) >= 40
	]

	return len(texto) >= 250 and (
		len(paragrafos_validos) >= 2 or len(texto) >= 600
	)


async def obter_pagina(
	session: aiohttp.ClientSession,
	url: str,
) -> tuple[str, BeautifulSoup] | None:
	try:
		async with session.get(
			url,
			allow_redirects=True,
		) as response:
			if response.status != 200:
				return None

			html = await response.text()

		soup = BeautifulSoup(html, "html.parser")
		return str(response.url), soup

	except (aiohttp.ClientError, TimeoutError):
		return None


async def selecionar_idioma(
	session: aiohttp.ClientSession,
	url: str,
) -> str | None:
	"""Seleciona a primeira versão com conteúdo: PT > EN > IT."""

	pagina = await obter_pagina(session, url)
	if not pagina:
		return None

	url_original, soup_original = pagina

	nomes_idiomas = {
		"PT": {"PT", "PORTUGUÊS", "PORTUGUES", "PORTUGUESE"},
		"EN": {"EN", "ENGLISH", "INGLÊS", "INGLES"},
		"IT": {"IT", "ITALIANO", "ITALIAN"},
	}

	idiomas = {}
	campo = soup_original.select_one("div.translation-field")

	if campo:
		for link in campo.select("a[href]"):
			nome = link.get_text(" ", strip=True).upper()
			destino = urljoin(url_original, link["href"])

			if not is_vatican_url(destino):
				continue

			for codigo, nomes in nomes_idiomas.items():
				if nome in nomes:
					idiomas[codigo] = destino
					break

	# Identifica o idioma na estrutura /content/{pontífice}/{idioma}/...
	partes = urlparse(url_original).path.strip("/").split("/")

	if len(partes) >= 4 and partes[0] == "content":
		codigo = partes[2].upper()

		if codigo in PREFERRED_LANGUAGES:
			idiomas.setdefault(codigo, url_original)

	# Garante que a URL original também possa ser validada.
	if not idiomas:
		idiomas["PT"] = url_original

	for idioma in PREFERRED_LANGUAGES:
		destino = idiomas.get(idioma)

		if not destino:
			continue

		if destino == url_original:
			soup = soup_original
		else:
			resultado = await obter_pagina(session, destino)

			if not resultado:
				continue

			destino, soup = resultado

		if tem_conteudo(soup):
			return destino

	return None

async def pesquisar_documentos(
	consulta: str,
	quantidade: int = 5,
) -> list[dict[str, str]]:
	headers = {
		"User-Agent": "Mozilla/5.0",
		"Accept": "application/rss+xml, application/xml, text/xml",
		"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,it;q=0.7",
	}

	timeout = aiohttp.ClientTimeout(total=30)

	async with aiohttp.ClientSession(
		headers=headers,
		timeout=timeout,
	) as session:
		async with session.get(
			SEARCH_URL,
			params={
				"q": f"site:vatican.va/content/ {consulta}",
				"format": "rss",
			},
		) as response:
			response.raise_for_status()
			xml = await response.text()

		try:
			raiz = ET.fromstring(xml)
		except ET.ParseError as erro:
			raise RuntimeError(
				"O Bing não retornou um RSS válido."
			) from erro

		resultados = []
		vistos = set()

		for item in raiz.findall(".//item"):
			titulo = item.findtext("title", default="").strip()
			url = item.findtext("link", default="").strip()
			descricao = item.findtext("description", default="").strip()

			if not titulo or not url:
				continue

			if not is_vatican_url(url):
				continue

			if not corresponde_pesquisa(consulta, titulo, url):
				continue

			if not urlparse(url).path.lower().endswith(".html"):
				continue

			url_final = await selecionar_idioma(session, url)

			if not url_final or url_final in vistos:
				continue

			vistos.add(url_final)

			resultados.append({
				"titulo": titulo,
				"url": url_final,
				"descricao": descricao,
			})

			if len(resultados) >= quantidade:
				break

		return resultados