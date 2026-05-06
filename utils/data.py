import os
import json
import sqlite3

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
	remocao: bool = False

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

def get_connection():
	conn = sqlite3.connect("database.db")
	conn.row_factory = sqlite3.Row
	return conn

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
	try:
		conn = get_connection()
		cursor = conn.cursor(dictionary=True)
		cursor.execute("SELECT * FROM membros")
		rows = cursor.fetchall()
		membros = {}
		for row in rows:
			warns = row["warns"]
			if warns is None:
				warns = "[]"

			membros[str(row["member_id"])] = {
				"warns": json.loads(warns),
				"ja_boostou": bool(row["ja_boostou"] if row["ja_boostou"] else 0),
				"palavroes": int(row["palavroes"] if row["palavroes"] else 0)
			}
		return membros
	finally:
		cursor.close()
		conn.close()

def get_member(member_id: int) -> MembrosJson:
	try:
		conn = get_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT * FROM membros WHERE member_id = ?", (member_id,))
		row = cursor.fetchone()
		if not row:
			return {"warns": [], "ja_boostou": False, "palavroes": 0}
		
		warns = row["warns"]
		if warns is None:
			warns = "[]"
		return {
			"warns": json.loads(warns),
			"ja_boostou": bool(row["ja_boostou"] if row["ja_boostou"] else 0),
			"palavroes": int(row["palavroes"] if row["palavroes"] else 0)
		}
	finally:
		cursor.close()
		conn.close()

def save_member(member_id: int, obj: MembrosJson):
	try:
		conn = get_connection()
		cursor = conn.cursor()
		warns_json = json.dumps(obj.get("warns", []))
		ja_boostou = int(obj.get("ja_boostou", False))
		palavroes = int(obj.get("palavroes", 0))
		
		cursor.execute("""
			INSERT INTO membros (member_id, warns, ja_boostou, palavroes)
			VALUES (?, ?, ?, ?)
			ON CONFLICT(member_id) DO UPDATE SET
				warns=excluded.warns,
				ja_boostou=excluded.ja_boostou,
				palavroes=excluded.palavroes
		""", (member_id, warns_json, ja_boostou, palavroes))
		conn.commit()
	finally:
		cursor.close()
		conn.close()

def get_embeds() -> dict[str, EmbedData | list[EmbedData]]:
	return abrir_json(DataFiles.EMBEDS.value)

def get_config() -> Config:
	return abrir_json(DataFiles.CONFIG.value)

def save_config(config: Config):
	salvar_json(DataFiles.CONFIG.value, config)

def carregar_biblia() -> BibliaDict:
	return abrir_json(DataFiles.BIBLIA.value)

def create_tables():
	conn = get_connection()
	cursor = conn.cursor()
	
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS membros (
			member_id BIGINT PRIMARY KEY,
			warns JSON,
			ja_boostou BOOLEAN DEFAULT FALSE,
			palavroes INT DEFAULT 0
		)
	""")

	cursor.execute("""
		CREATE TABLE IF NOT EXISTS vatican_news_config (
			guild_id BIGINT PRIMARY KEY,
			ping BIGINT NULL,
			webhook_url TEXT NULL,
			canal BIGINT NULL,
			ultimo_guid TEXT NULL
		)
	""")
	
	conn.commit()
	cursor.close()
	conn.close()

def setup_database():
	create_tables()