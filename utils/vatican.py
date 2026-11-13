import aiohttp
import asyncio
import base64
import binascii
import html
import math
import re
import unicodedata
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from urllib.parse import (
	urlparse,
	parse_qs,
	unquote,
	urljoin,
	urlunparse,
)

SEARCH_URL = "https://www.bing.com/search"
COUNCIL_INDEX_URL = (
	"https://www.vatican.va/archive/hist_councils/"
	"ii_vatican_council/index_po.htm"
)

PREFERRED_LANGUAGES = ("PT", "EN", "IT")

DOCUMENT_SELECTORS = (
	"div.documento",
	"div.document",
	"div.text",
	"article",
	"main",
	"#content",
	"body",
)

STOPWORDS = {
	"de", "da", "do", "das", "dos", "a", "o", "e",
	"em", "no", "na", "nos", "nas", "um", "uma",
	"para", "por", "com", "sobre", "ao", "aos",
	"the", "of", "and", "in", "on", "to", "for",
	"il", "lo", "la", "gli", "le", "di", "del", "della",
}

IDIOMAS_POR_NOME = {
	"PT": {
		"pt", "po", "portugues", "portuguese", "pt portugues",
	},
	"EN": {
		"en", "english", "ingles", "inglês",
	},
	"IT": {
		"it", "italiano", "italian",
	},
}

PAPAS_INDEX_URL = (
	"https://www.vatican.va/content/vatican/"
	"{idioma}/holy-father.index.html"
)

PAPAS_IDIOMAS = set(l.lower() for l in IDIOMAS_POR_NOME.keys())

MESES_ROMANOS = {
	"I": "01",
	"II": "02",
	"III": "03",
	"IV": "04",
	"V": "05",
	"VI": "06",
	"VII": "07",
	"VIII": "08",
	"IX": "09",
	"X": "10",
	"XI": "11",
	"XII": "12",
}

PADRAO_MESES = re.compile(
	r"(?<![A-Za-z])"
	r"(XII|XI|IX|VIII|VII|VI|IV|V|III|II|I)"
	r"(?![A-Za-z])",
	re.IGNORECASE,
)

def normalizar(texto: str) -> str:
	texto = html.unescape(texto or "")
	texto = unicodedata.normalize("NFD", texto.lower())
	texto = "".join(
		caractere
		for caractere in texto
		if unicodedata.category(caractere) != "Mn"
	)
	return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def is_vatican_url(url: str) -> bool:
	hostname = (urlparse(url).hostname or "").lower().rstrip(".")
	return hostname in {"vatican.va", "www.vatican.va"}


def decodificar_url_bing(url: str) -> str:
	"""Converte links de redirecionamento do Bing em URLs de destino."""
	partes = urlparse(url)
	hostname = (partes.hostname or "").lower()

	if hostname not in {"bing.com", "www.bing.com"}:
		return url

	parametros = parse_qs(partes.query)

	for chave in ("u", "url"):
		valores = parametros.get(chave, [])

		for valor in valores:
			valor = unquote(valor).strip()

			if valor.startswith(("http://", "https://")):
				return valor

			codificado = valor[2:] if valor.startswith("a1") else valor
			if not codificado:
				continue

			try:
				codificado += "=" * (-len(codificado) % 4)
				destino = base64.urlsafe_b64decode(codificado).decode("utf-8")
				destino = html.unescape(destino).strip()

				if destino.startswith(("http://", "https://")):
					return destino
			except (binascii.Error, UnicodeDecodeError, ValueError):
				continue

	return url


def normalizar_url(url: str) -> str:
	"""Remove fragmentos e redirecionamentos desnecessários da URL."""
	url = decodificar_url_bing(html.unescape(url.strip()))
	partes = urlparse(url)
	return urlunparse(partes._replace(fragment=""))


def identificar_idioma_url(url: str) -> str | None:
	"""Identifica o idioma tanto nas URLs modernas quanto nas antigas."""
	path = urlparse(url).path.lower()
	partes = path.strip("/").split("/")

	if len(partes) >= 3 and partes[0] == "content":
		codigo = partes[2].upper()
		if codigo in PREFERRED_LANGUAGES:
			return codigo

	sufixos = {
		"_po.html": "PT",
		"_pt.html": "PT",
		"_en.html": "EN",
		"_it.html": "IT",
	}

	for sufixo, idioma in sufixos.items():
		if path.endswith(sufixo):
			return idioma

	return None


def identidade_documento_url(url: str) -> str:
	"""Gera uma identidade comparável entre versões traduzidas do documento."""
	partes = urlparse(url).path.lower().strip("/").split("/")

	if (
		len(partes) >= 4
		and partes[0] == "content"
		and partes[2] in {idioma.lower() for idioma in PREFERRED_LANGUAGES}
	):
		del partes[2]

	if partes:
		partes[-1] = re.sub(r"_(?:po|pt|en|it)(?=\.html?$)", "", partes[-1])

	return "/".join(partes)


def corresponde_pesquisa(
	consulta: str,
	titulo: str,
	url: str,
	descricao: str = "",
) -> bool:
	"""Confere a relevância usando título, URL e descrição do resultado."""
	termos = [
		termo
		for termo in normalizar(consulta).split()
		if termo not in STOPWORDS
	]

	if not termos:
		return True

	caminho = urlparse(url).path.rsplit("/", 1)[-1]
	palavras_titulo_url = set(normalizar(f"{titulo} {caminho}").split())
	palavras = set(normalizar(f"{titulo} {caminho} {descricao}").split())

	encontrados_titulo_url = sum(
		termo in palavras_titulo_url for termo in termos
	)
	encontrados = sum(termo in palavras for termo in termos)
	minimo = max(1, math.ceil(len(termos) * 0.6))

	return encontrados_titulo_url > 0 and encontrados >= minimo


def extrair_texto(soup: BeautifulSoup) -> str:
	"""Extrai o conteúdo provável sem modificar o BeautifulSoup original."""
	copia = BeautifulSoup(str(soup), "html.parser")

	for elemento in copia.select(
		"script, style, noscript, nav, header, footer, "
		"form, button, svg, iframe, "
		".translation-field, .breadcrumb, .breadcrumbs, "
		".navigation, .footer, .header"
	):
		elemento.decompose()

	candidatos = []

	for seletor in DOCUMENT_SELECTORS:
		for elemento in copia.select(seletor):
			texto = elemento.get_text(" ", strip=True)
			if texto:
				candidatos.append(texto)

	if candidatos:
		return max(candidatos, key=len)

	return copia.get_text(" ", strip=True)


def tem_conteudo(soup: BeautifulSoup) -> bool:
	"""Verifica o volume textual sem exigir uma estrutura específica de <p>."""
	texto = extrair_texto(soup)
	palavras = normalizar(texto).split()

	return len(texto) >= 250 and len(palavras) >= 40


def identificar_idioma_link(link) -> str | None:
	nome = normalizar(link.get_text(" ", strip=True))

	for codigo, nomes in IDIOMAS_POR_NOME.items():
		if nome in nomes:
			return codigo

	destino = link.get("href", "")
	return identificar_idioma_url(destino)


def extrair_valor_item(item: ET.Element, nome: str) -> str:
	"""Lê uma tag do RSS mesmo quando o XML usa namespaces."""
	for elemento in item.iter():
		tag = elemento.tag.rsplit("}", 1)[-1].lower()
		if tag == nome.lower():
			return "".join(elemento.itertext()).strip()
	return ""


def limpar_descricao(descricao: str) -> str:
	descricao = html.unescape(descricao or "")
	return BeautifulSoup(descricao, "html.parser").get_text(" ", strip=True)


async def obter_pagina(
	session: aiohttp.ClientSession,
	url: str,
) -> tuple[str, BeautifulSoup] | None:
	try:
		async with session.get(
			url,
			allow_redirects=True,
			headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
		) as response:
			if response.status != 200:
				return None

			html_pagina = await response.text(errors="replace")
			url_final = str(response.url)

		soup = BeautifulSoup(html_pagina, "html.parser")
		return url_final, soup

	except (aiohttp.ClientError, TimeoutError, UnicodeError):
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
	identidade_original = identidade_documento_url(url_original)
	idiomas: dict[str, str] = {}

	for link in soup_original.select("a[href]"):
		destino = normalizar_url(urljoin(url_original, link["href"]))

		if not is_vatican_url(destino):
			continue

		if identidade_documento_url(destino) != identidade_original:
			continue

		idioma = identificar_idioma_link(link)
		if idioma in PREFERRED_LANGUAGES:
			idiomas.setdefault(idioma, destino)

	idioma_original = identificar_idioma_url(url_original)
	if idioma_original:
		idiomas[idioma_original] = url_original

	candidatos = [idiomas[idioma] for idioma in PREFERRED_LANGUAGES if idioma in idiomas]
	candidatos.append(url_original)

	vistos = set()

	for destino in candidatos:
		destino = normalizar_url(destino)

		if destino in vistos:
			continue
		vistos.add(destino)

		if destino == url_original:
			soup = soup_original
			url_final = url_original
		else:
			resultado = await obter_pagina(session, destino)
			if not resultado:
				continue
			url_final, soup = resultado

		if (
			is_vatican_url(url_final)
			and identidade_documento_url(url_final) == identidade_original
			and tem_conteudo(soup)
		):
			return url_final

	return None


async def pesquisar_indice_concilio(
	session: aiohttp.ClientSession,
	consulta: str,
	quantidade: int,
	vistos: set[str],
) -> list[dict[str, str]]:
	"""Busca no índice oficial quando o Bing não encontra documentos do Concílio."""
	pagina = await obter_pagina(session, COUNCIL_INDEX_URL)
	if not pagina:
		return []

	url_indice, soup = pagina
	resultados: list[dict[str, str]] = []
	documentos_vistos: set[str] = set()

	for link in soup.select("a[href]"):
		titulo = link.get_text(" ", strip=True)
		url = normalizar_url(urljoin(url_indice, link["href"]))
		partes = urlparse(url)

		if (
			not is_vatican_url(url)
			or not partes.path.startswith(
				"/archive/hist_councils/ii_vatican_council/documents/"
			)
			or not partes.path.lower().endswith((".html", ".htm"))
			or not corresponde_pesquisa(consulta, titulo, url)
		):
			continue

		identidade = identidade_documento_url(url)
		if identidade in documentos_vistos:
			continue
		documentos_vistos.add(identidade)

		url_final = await selecionar_idioma(session, url)
		if not url_final:
			continue

		chave = normalizar_url(url_final)
		if chave in vistos:
			continue
		vistos.add(chave)

		resultados.append({
			"titulo": titulo,
			"url": url_final,
			"descricao": "",
		})

		if len(resultados) >= quantidade:
			break

	return resultados


async def pesquisar_documentos(
	consulta: str,
	quantidade: int = 1,
) -> list[dict[str, str]]:
	if quantidade <= 0 or not consulta.strip():
		return []

	headers = {
		"User-Agent": (
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
			"AppleWebKit/537.36 (KHTML, like Gecko) "
			"Chrome/120.0.0.0 Safari/537.36"
		),
		"Accept": (
			"text/html,application/xhtml+xml,"
			"application/xml;q=0.9,*/*;q=0.8"
		),
		"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,it;q=0.7",
	}

	timeout = aiohttp.ClientTimeout(
		total=30,
		connect=10,
		sock_read=20,
	)

	async with aiohttp.ClientSession(
		headers=headers,
		timeout=timeout,
	) as session:

		async with session.get(
			SEARCH_URL,
			params={
				"q": f"{consulta.strip()} site:vatican.va",
				"count": 50,
			},
		) as response:
			print("URL:", response.url)
			response.raise_for_status()
			html = await response.text(errors="replace")

		soup = BeautifulSoup(html, "html.parser")

		itens = soup.select("li.b_algo")

		resultados: list[dict[str, str]] = []
		vistos = set()

		for item in itens:
			link = item.select_one("h2 a[href]")

			if not link:
				continue

			titulo = link.get_text(" ", strip=True)
			url = link.get("href", "").strip()

			descricao_elemento = item.select_one(
				".b_caption p, p"
			)

			descricao = (
				limpar_descricao(
					descricao_elemento.get_text(" ", strip=True)
				)
				if descricao_elemento
				else ""
			)

			if not titulo or not url:
				continue

			url = normalizar_url(url)

			if not is_vatican_url(url):
				continue

			caminho = urlparse(url).path.lower()

			if not caminho.endswith((".html", ".htm")):
				continue

			if not corresponde_pesquisa(
				consulta,
				titulo,
				url,
				descricao,
			):
				continue

			url_final = await selecionar_idioma(session, url)

			if not url_final:
				continue

			chave = normalizar_url(url_final)

			if chave in vistos:
				continue

			vistos.add(chave)

			resultados.append({
				"titulo": titulo,
				"url": url_final,
				"descricao": descricao,
			})

			if len(resultados) >= quantidade:
				break

		if len(resultados) < quantidade:
			resultados.extend(
				await pesquisar_indice_concilio(
					session,
					consulta,
					quantidade - len(resultados),
					vistos,
				)
			)

		return resultados

def formatar_data_vaticano(valor: str) -> str:
	"""
	Converte datas do índice do Vaticano para DD/MM/YYYY.

	Preserva datas alternativas e não inventa informações
	quando o dia ou mês não são conhecidos.
	"""

	valor = re.sub(r"\s+", " ", valor or "").strip()

	if not valor:
		return "—"

	meses = list(PADRAO_MESES.finditer(valor))
	anos = list(re.finditer(r"(?<!\d)\d{1,4}(?!\d)", valor))

	resultados = []

	if not meses:
		for ano in anos:
			numero = int(ano.group())
			resultados.append(
				f"??/??/{numero:04d}"
			)

		return " / ".join(dict.fromkeys(resultados)) or "—"

	for indice, mes in enumerate(meses):
		anterior = meses[indice - 1].end() if indice else 0
		trecho = valor[anterior:mes.start()]

		dias = re.findall(r"(?<!\d)\d{1,2}(?!\d)", trecho)

		if "..." in trecho or not dias:
			dias = ["??"]

		ano = next(
			(
				int(item.group())
				for item in anos
				if item.start() >= mes.end()
			),
			None
		)

		ano_formatado = f"{ano:04d}" if ano is not None else "????"

		numero_mes = MESES_ROMANOS[mes.group().upper()]

		for dia in dias:
			dia_formatado = (
				f"{int(dia):02d}"
				if dia != "??"
				else "??"
			)

			resultados.append(
				f"{dia_formatado}/{numero_mes}/{ano_formatado}"
			)

	return " / ".join(dict.fromkeys(resultados))


def extrair_papas(soup: BeautifulSoup) -> dict[int, dict]:
	"""Extrai os registros da tabela oficial dos Papas."""

	tabela = soup.select_one("#holy-father")

	if tabela is None:
		raise ValueError("Tabela #holy-father não encontrada.")

	papas = {}

	for linha in tabela.select("tr"):
		celulas = linha.find_all(
			["td", "th"],
			recursive=False
		)

		if len(celulas) < 7:
			continue

		numero_texto = celulas[0].get_text(" ", strip=True)
		numero_match = re.search(r"\d+", numero_texto)

		if not numero_match:
			continue

		link = celulas[1].select_one("a[href]")

		if not link:
			continue

		numero = int(numero_match.group())

		papas[numero] = {
			"numero": numero,
			"nome": link.get_text(" ", strip=True),
			"inicio_original": celulas[2].get_text(" ", strip=True),
			"fim_original": celulas[3].get_text(" ", strip=True),
			"nome_nascimento": celulas[4].get_text(" ", strip=True),
			"nascimento": celulas[5].get_text(" ", strip=True),
			"seculo": celulas[6].get_text(" ", strip=True),
			"url": urljoin(
				"https://www.vatican.va",
				link["href"]
			),
		}

	return papas


async def obter_indice_papas(
	session: aiohttp.ClientSession,
	idioma: str,
) -> dict[int, dict]:

	url = PAPAS_INDEX_URL.format(idioma=idioma)

	pagina = await obter_pagina(session, url)

	if not pagina:
		raise RuntimeError(
			f"Não foi possível consultar o índice {idioma}."
		)

	_, soup = pagina

	return extrair_papas(soup)


def corresponde_nome_papa(
	consulta: str,
	nome: str,
) -> bool:
	"""
	Compara sequências completas de palavras.

	Evita, por exemplo, que Leão X corresponda a Leão XIV.
	"""

	termos = normalizar(consulta).split()
	palavras = normalizar(nome).split()

	if termos and termos[0] in {"papa", "pope"}:
		termos.pop(0)

	if not termos:
		return False

	tamanho = len(termos)

	return any(
		palavras[indice:indice + tamanho] == termos
		for indice in range(len(palavras) - tamanho + 1)
	)


async def obter_imagem_papa(
	session: aiohttp.ClientSession,
	url: str,
	nome: str,
) -> str | None:
	"""Localiza a fotografia na página individual do pontífice."""

	pagina = await obter_pagina(session, url)

	if not pagina:
		return None

	url_final, soup = pagina

	for seletor, atributo in (
		('meta[property="og:image"]', "content"),
		('meta[name="twitter:image"]', "content"),
	):
		elemento = soup.select_one(seletor)

		if elemento and elemento.get(atributo):
			imagem = urljoin(
				url_final,
				elemento[atributo]
			)

			if is_vatican_url(imagem):
				return imagem

	nome_normalizado = normalizar(nome)

	imagens = soup.select("div.pope-img img[src], div.pope-img img[data-src]")

	if not imagens:
		imagens = soup.select("img[src], img[data-src]")

	for elemento in imagens:
		descricao = normalizar(
			elemento.get("alt", "")
		)

		origem = elemento.get("data-src") or elemento.get("src")

		if not origem:
			continue

		if nome_normalizado and nome_normalizado in descricao:
			return urljoin(url_final, origem)

	for elemento in imagens:
		origem = elemento.get("data-src") or elemento.get("src")

		if not origem:
			continue

		descricao = normalizar(
			elemento.get("alt", "") + " " + origem
		)

		if any(
			termo in descricao
			for termo in ("logo", "icon", "favicon")
		):
			continue

		imagem = urljoin(url_final, origem)

		if is_vatican_url(imagem):
			return imagem

	return None


async def pesquisar_papas(
	consulta: str,
	quantidade: int = 5,
) -> list[dict]:

	consulta = consulta.strip()

	if not consulta or quantidade <= 0:
		return []

	headers = {
		"User-Agent": (
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
			"AppleWebKit/537.36 (KHTML, like Gecko) "
			"Chrome/120.0.0.0 Safari/537.36"
		),
		"Accept-Language": "pt,en,it;q=0.9",
	}

	timeout = aiohttp.ClientTimeout(
		total=30,
		connect=10,
		sock_read=20,
	)

	async with aiohttp.ClientSession(
		headers=headers,
		timeout=timeout,
	) as session:

		indices = await asyncio.gather(
			*[
				obter_indice_papas(session, idioma)
				for idioma in PAPAS_IDIOMAS
			]
		)

		registros = {}

		for idioma, indice in zip(PAPAS_IDIOMAS, indices):
			for numero, papa in indice.items():
				registro = registros.setdefault(
					numero,
					{"numero": numero, "nomes": {}}
				)

				registro["nomes"][idioma] = papa["nome"]

				if idioma == "pt":
					registro["dados"] = papa

		consulta_normalizada = normalizar(consulta)

		if consulta_normalizada.isdigit():
			numero = int(consulta_normalizada)

			candidatos = [
				registro
				for registro in registros.values()
				if registro["numero"] == numero
			]

		else:
			candidatos = []

			for registro in registros.values():
				nomes = registro["nomes"].values()

				if any(
					corresponde_nome_papa(consulta, nome)
					for nome in nomes
				):
					candidatos.append(registro)

		candidatos.sort(key=lambda item: item["numero"])

		resultados = []

		for registro in candidatos[:quantidade]:
			dados = registro.get("dados")

			if not dados:
				continue

			imagem = await obter_imagem_papa(
				session,
				dados["url"],
				dados["nome"],
			)

			resultados.append({
				"numero": registro["numero"],
				"nome_pt": registro["nomes"].get("pt", "Desconhecido"),
				"nome_it": registro["nomes"].get("it", "Desconhecido"),
				"nome_en": registro["nomes"].get("en", "Unknown"),
				"inicio": formatar_data_vaticano(
					dados["inicio_original"]
				),
				"fim": formatar_data_vaticano(
					dados["fim_original"]
				),
				"nome_nascimento": dados["nome_nascimento"],
				"nascimento": dados["nascimento"],
				"seculo": dados["seculo"],
				"imagem": imagem,
				"url": dados["url"],
			})

		return resultados