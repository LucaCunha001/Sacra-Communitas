import os
import json

from enum import Enum
from typing import TypedDict

class DataFiles(Enum):
	CONFIG = 'data/config.json'
	EMBEDS = 'data/embeds.json'
	BIBLIA = 'data/biblia.json'
	CANONES = 'data/canones.json'
	MEMBROS = 'data/membros.json'
	NEWS_VA = 'data/news_va.json'
	PALAVROES = 'data/badwords.txt'

class WarnsJson(TypedDict):
	dado_por: int
	quando: int
	motivo: str = ""

class ArtigoDict(TypedDict):
	texto: str
	incisos: list[str]
	paragrafos: list[str]

class CanonesDict(TypedDict):
	titulo: str
	conteudo: str
	artigos: list[ArtigoDict]
	canal: int

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

class EmbedData(TypedDict):
	title: str
	description: str
	color: int
	fields: list[dict[str, str | bool]]
	footer: dict[str, str]

class CargoDict(TypedDict):
	id: int
	descricao: str

class CargosDict(TypedDict):
	sacerdotes: dict[str, dict[str, CargoDict]]
	membros: dict[str, dict[str, CargoDict]]
	anjos: dict[str, dict[str, CargoDict]]
	config: dict[str, int]

class CallDict(TypedDict):
	id: int
	nome: str
	emoji: str

class ServidoresDict(TypedDict):
	main: int
	apel: int

class ConfigDict(TypedDict):
	servidores: ServidoresDict

class Config(TypedDict):
	canais: dict[str, int]
	config: ConfigDict
	cargos: CargosDict[str, CargosDict]
	urls: dict[str, dict[str, str]]
	liturgia: dict[str, str | int]
	logs: dict[str, int]
	calls: dict[str, CallDict]

class MembrosJson(TypedDict):
	warns: list[WarnsJson] = []
	ja_boostou: bool = False
	palavroes: int

def abrir_json(arquivo: str) -> dict | list:
	if os.path.isfile(arquivo):
		with open(arquivo, "r", encoding="utf-8") as f:
			return json.load(f)

	return {}

def salvar_json(arquivo: str, conteudo: dict | list):
	os.makedirs(os.path.dirname(arquivo), exist_ok=True)
	with open(arquivo, "w", encoding="utf-8") as f:
		json.dump(conteudo, f, ensure_ascii=False, indent=4)

def get_members() -> dict[str, MembrosJson]:
	return abrir_json(DataFiles.MEMBROS.value)

def get_member(member_id: int) -> MembrosJson:
	arquivo = get_members()
	membro = arquivo.get(str(member_id), {})
	membro.setdefault("warns", [])
	membro.setdefault("ja_boostou", False)
	membro.setdefault("palavroes", 0)
	return membro

def save_member(member_id: int, obj: MembrosJson):
	members = get_members()
	members[str(member_id)] = obj
	salvar_json(DataFiles.MEMBROS.value, members)

def get_embeds() -> dict[str, EmbedData | list[EmbedData]]:
	return abrir_json(DataFiles.EMBEDS.value)

def get_config() -> Config:
	return abrir_json(DataFiles.CONFIG.value)

def save_config(config: Config):
	salvar_json(DataFiles.CONFIG.value, config)

def carregar_biblia() -> BibliaDict:
	return abrir_json(DataFiles.BIBLIA.value)