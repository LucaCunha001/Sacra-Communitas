# Repositório do bot Sancte Michael Archangele

Fiz esse bot para ajudar na organização do servidor [Sacra Communitas](https://discord.gg/NJMTbNukrk).

## Linguagens usadas:
| Programação | Banco de dados | Palavrões e bibliotecas |
| ----------- | -------------- | --------- |
| Python (.py) | JSON (.json) | Texto (.txt)

## Códigos de auxílio (`utils/`)

Cada código dentro da pasta `utils/` serve para auxiliar os funcionamentos dos cogs ou do código principal.

### utils/recursos.py:
- Contém as principais classes e funções para o funcionamento geral do bot, sendo requisitadas quase sempre pelo projeto.
- Classes:
	```py
	class BibleDict(TypedDict):
		"""
		Serve para tipagem da funcão expand_bible_verse().
		"""
		testamento: str
		livro: str
		capítulo: int
		versículo_inicial: int
		versículo_final: int
		texto: list[str]
		tipo: str
	
	class HelpCommand(commands.HelpCommand):
		"""
		Configura os comandos de ajuda (!help) do bot.
		"""
	
	class Bot(commands.Bot):
		"""
		Classe do bot. Aqui há a sincronização dos comandos e envio de mensagens ao console (Canal específico).
		"""
	```
- Funções:
	```py
	def expand_bible_verse(content: str) -> list[BibleDict]:
		"""
		Extrai as passagens bíblicas de acordo com um texto de referência.
		Ex:
			expand_bible_verse("Jo 1:1")
			>>> [
			>>>     {
			>>>         "testamento": "Antigo Testamento",
			>>>         "livro": "São João",
			>>>         "capítulo": 1,
			>>>         "versículo_inicial": 1,
			>>>         "versículo_final": 1,
			>>>         "texto": "1. No princípio era o Verbo, e o Verbo estava junto de Deus e o Verbo era Deus.*",
			>>>         "tipo": "Evangelhos"
			>>>     }
			>>> ]
		"""
	
	def contar(num: int) -> str:
		"""
		Converte um determinado número inteiro em romano.
		Ex:
			contar(1962)
			>>> MCMLXII
		"""
	```
