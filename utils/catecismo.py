import discord
import os
import re
import requests

from bs4 import BeautifulSoup
from discord import ui
from typing import TypedDict, Optional

class PaginaDict(TypedDict):
	titulo: Optional[str]
	p_init: int
	p_end: int

class SecaoDict(TypedDict):
	p_init: Optional[int]
	p_end: Optional[int]
	capitulos: Optional[list[PaginaDict]]

class ParteDict(TypedDict):
	titulo: str
	introducao: Optional[PaginaDict]
	ps: SecaoDict
	ss: SecaoDict

class PaginasDict(TypedDict):
	prologo: PaginaDict
	p_parte: ParteDict
	s_parte: ParteDict
	t_parte: ParteDict
	q_parte: ParteDict

PAGINAS: PaginasDict = {
	"prologo": {
		"titulo": "Prólogo",
		"p_init": 1,
		"p_end": 25
	},
	"p_parte": {
		"titulo": "A Profissão da Fé",
		"ps": {
			"p_init": 26,
			"capitulos": [
				{
					"p_init": 27,
					"p_end": 49
				},
				{
					"p_init": 50,
					"p_end": 141
				},
				{
					"p_init": 142,
					"p_end": 184
				}
			]
		},
		"ss": {
			"p_init": 185,
			"p_end": 197,
			"capitulos": [
				{
					"p_init": 198,
					"p_end": 421
				},
				{
					"p_init": 422,
					"p_end": 682
				},
				{
					"p_init": 683,
					"p_end": 1065
				}
			]
		}
	},
	"s_parte": {
		"titulo": "A Celebração do Mistério Cristão",
		"introducao": {
			"p_init": 1066,
			"p_end": 1075
		},
		"ps": {
			"capitulos": [
				{
					"p_init": 1076,
					"p_end": 1134
				},
				{
					"p_init": 1135,
					"p_end": 1209
				}
			]
		},
		"ss": {
			"p_init": 1210,
			"p_end": 1211,
			"capitulos": [
				{
					"p_init": 1212,
					"p_end": 1419
				},
				{
					"p_init": 1420,
					"p_end": 1532
				},
				{
					"p_init": 1533,
					"p_end": 1666
				},
				{
					"p_init": 1667,
					"p_end": 1690
				}
			]
		}
	},
	"t_parte": {
		"titulo": "A Vida em Cristo",
		"introducao": {
			"p_init": 1691,
			"p_end": 1698
		},
		"ps": {
			"p_init": 1699,
			"capitulos": [
				{
					"p_init": 1700,
					"p_end": 1876
				},
				{
					"p_init": 1877,
					"p_end": 1948
				},
				{
					"p_init": 1949,
					"p_end": 2051
				}
			]
		},
		"ss": {
			"p_init": 2052,
			"p_end": 2082,
			"capitulos": [
				{
					"p_init": 2083,
					"p_end": 2195
				},
				{
					"p_init": 2196,
					"p_end": 2557
				}
			]
		}
	},
	"q_parte": {
		"titulo": "A Oração Cristã",
		"ps": {
			"p_init": 2558,
			"p_end": 2565,
			"capitulos": [
				{
					"p_init": 2566,
					"p_end": 2649
				},
				{
					"p_init": 2650,
					"p_end": 2696
				},
				
				{
					"p_init": 2697,
					"p_end": 2758
				}
			]
		},
		"ss": {
			"p_init": 2759,
			"p_end": 2865
		}
	}
}

URLS = {
	"0": {
		"0": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/prologo%201-25_po.html"
		}
	},
	"1": {
		"1": {
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p1s1c1_26-49_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p1s1c2_50-141_po.html",
			"3": "https://www.vatican.va/archive/cathechism_po/index_new/p1s1c3_142-184_po.html"
		},
		"2": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p1s2_185-197_po.html",
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p1s2c1_198-421_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p1s2cap2_422-682_po.html",
			"3": "https://www.vatican.va/archive/cathechism_po/index_new/p1s2cap3_683-1065_po.html"
		}
	},
	"2": {
		"0": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p2s1cap1_1066-1075_po.html"
		},
		"1": {
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p2s1cap1_1076-1134_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p2s1cap2_1135-1209_po.html"
		},
		"2": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p2s2cap1_1210-1419_po.html",
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p2s2cap1_1210-1419_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p2s2cap1_1420-1532_po.html",
			"3": "https://www.vatican.va/archive/cathechism_po/index_new/p2s2cap3_1533-1666_po.html",
			"4": "https://www.vatican.va/archive/cathechism_po/index_new/p2s2cap4_1667-1690_po.html"
		}
	},
	"3": {
		"0": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p3-intr_1691-1698_po.html"
		},
		"1": {
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p3s1cap1_1699-1876_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p3s1cap2_1877-1948_po.html",
			"3": "https://www.vatican.va/archive/cathechism_po/index_new/p3s1cap3_1949-2051_po.html"
		},
		"2": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p3s2-intr_2052-2082_po.html",
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p3s2cap1_2083-2195_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p3s2cap2_2196-2557_po.html"
		}
	},
	"4": {
		"1": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p4-intr_2558-2565_po.html",
			"1": "https://www.vatican.va/archive/cathechism_po/index_new/p4s1cap1_2566-2649_po.html",
			"2": "https://www.vatican.va/archive/cathechism_po/index_new/p4s1cap2_2650-2696_po.html",
			"3": "https://www.vatican.va/archive/cathechism_po/index_new/p4s1cap3_2697-2758_po.html"
		},
		"2": {
			"null": "https://www.vatican.va/archive/cathechism_po/index_new/p4s2_2759-2865_po.html"
		}
	}
}

def get_url(parte: int, secao: int, capitulo: int | None = None):
	parte_k = str(parte)
	secao_k = str(secao)
	capitulo_k = "null" if capitulo is None else str(capitulo)

	url = URLS[parte_k][secao_k][capitulo_k]
	
	parte_ks = ["prologo", "p_parte", "s_parte", "t_parte", "q_parte"]
	titulo = PAGINAS[parte_ks[parte]]["titulo"]

	return url, titulo


def descobrir_bloco(n: int):
	prologo = PAGINAS["prologo"]
	if prologo["p_init"] <= n <= prologo["p_end"]:
		return 0, 0, None

	for i, chave in enumerate(["p_parte", "s_parte", "t_parte", "q_parte"], start=1):
		parte = PAGINAS[chave]

		intro = parte.get("introducao")
		if intro and intro["p_init"] <= n <= intro["p_end"]:
			return i, 0, None

		for secao_idx, secao_key in enumerate(["ps", "ss"], start=1):
			secao = parte.get(secao_key)
			if not secao:
				continue

			if secao.get("p_init") and secao.get("p_end"):
				if secao["p_init"] <= n <= secao["p_end"]:
					return i, secao_idx, None

			for cap_idx, cap in enumerate(secao.get("capitulos") or [], start=1):
				if cap["p_init"] <= n <= cap["p_end"]:
					return i, secao_idx, cap_idx

	return None, None, None

def extrair_intervalo(p_init: int, p_end: int):
	textos = []
	cache = {}
	last_url = None
	pars = {}
	titulo = None
	parte_base = None
	secao_base = None
	capitulo_base = None

	for n in range(p_init, p_end + 1):
		parte, secao, capitulo = descobrir_bloco(n)
		if parte is None:
			continue

		url, titulo_atual = get_url(parte, secao, capitulo)

		if parte_base is None:
			parte_base = parte
			secao_base = secao
			capitulo_base = capitulo
			titulo = titulo_atual

		if url != last_url:
			if url not in cache:
				cache[url] = baixar_e_extrair(url)
			pars = cache[url]
			last_url = url

		if n in pars:
			textos.append(f"**§{n}.** {pars[n]}")

	return {
		"p_init": p_init,
		"p_end": p_end,
		"texto": textos,
		"titulo": titulo,
		"parte": parte_base,
		"secao": secao_base,
		"capitulo": capitulo_base
	}

def extract_cic(texto: str):
	data = []
	textos = (t_ for t in texto.split(";") for t_ in t.split("\n"))

	pattern = r"(?:CIC\s*)?[§$]+\s*(\d+)(?:\s*-\s*(\d+))?"

	for texto in textos:
		for match_ in re.finditer(pattern, texto.upper()):
			p_init = int(match_.group(1))
			p_end = int(match_.group(2)) if match_.group(2) else p_init

			intervalo = extrair_intervalo(p_init, p_end)

			if intervalo["texto"]:
				data.append(intervalo)

	return data

def baixar_e_extrair(url: str):
	resp = requests.get(url)
	resp.raise_for_status()

	soup = BeautifulSoup(resp.text, "html.parser")
	paragrafos = {}

	for p in soup.find_all("p"):
		b = p.find("b")
		if not b:
			continue

		numero = b.get_text(strip=True).replace(".", "")
		if not numero.isdigit():
			continue

		b.extract()
		texto = p.get_text(" ", strip=True)
		texto = texto.lstrip(".-–—:; ")
		texto = texto.replace("«", '"').replace("»", '"')

		palavras = {
			"secção": "seção",
			"actor": "ator",
			"actos": "atos"
		}
		
		palavras_variacoes = {}

		for antiga, nova in palavras.items():
			palavras_variacoes[antiga.capitalize()] = nova.capitalize()
			palavras_variacoes[antiga.upper()] = nova.upper()

		for antiga, nova in palavras_variacoes.items():
			texto = texto.replace(antiga, nova)

		paragrafos[int(numero)] = texto

	return paragrafos


async def check_cic_verse(msg: discord.Message):
	datas = extract_cic(msg.content)
	for data in datas:
		if not data:
			return

		if not data["texto"]:
			await msg.reply("Não encontrei esse trecho no Catecismo.")
			return
		
		passagem_txt = f"**CIC §{data['p_init']}**" if data['p_init'] == data['p_end'] else f"**CIC §§{data['p_init']}-{data['p_end']}**"
		if data["parte"] != 0:
			passagem_txt += f" - Parte {data['parte']}, Seção {data['secao']}"
			if data["capitulo"] is not None:
				passagem_txt += f", Capítulo {data['capitulo']}"
		
		view = ui.LayoutView()
		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"## {data['titulo']}\n{passagem_txt}"),
				accessory=ui.Thumbnail("https://pocketterco.com.br/catecismo/img_catecismo.png")
			),
			accent_color=0xFFCC00
		)
		container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
		items_count = 4
		
		novos_containers = 0

		for p in data['texto']:
			container.add_item(ui.TextDisplay(p))
			items_count+=1
			if items_count == 40:
				view.add_item(container)
				if novos_containers == 0:
					await msg.reply(view=view)
				else:
					await msg.channel.send(view=view)
				
				view = ui.LayoutView()
				container = ui.Container(
					ui.TextDisplay(f"## {data['titulo']}\n{passagem_txt}"),
					accent_color=0xFFCC00
				)
				container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
				items_count = 3
		
		if items_count > 3:
			view.add_item(container)
			if novos_containers == 0:
				await msg.reply(view=view)
			else:
				await msg.channel.send(view=view)

def check_all_urls(urls_dict: dict):
	os.system("cls" if os.name == "nt" else "clear")

	def walk(d, path=""):
		for key, value in d.items():
			current_path = f"{path}/{key}" if path else key

			if isinstance(value, dict):
				walk(value, current_path)
			else:
				check_url(value, current_path)

	def check_url(url: str, path: str):
		try:
			resp = requests.head(url, allow_redirects=True, timeout=5)
			status = resp.status_code

			if status == 200:
				print(f"\033[92m✔ {path} -> {status}\033[0m")
			else:
				end = url.split("/")[-1]
				print(f"\033[91m✘ {path} -> {status} ({end})\033[0m")

		except requests.RequestException as e:
			print(f"\033[91m✘ {path} -> ERRO ({e})\033[0m ")

	walk(urls_dict)

if __name__ == "__main__":
	check_all_urls(URLS)