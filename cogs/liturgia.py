import aiohttp
import datetime
import discord
import re

from discord import app_commands, ui
from discord.ext import commands, tasks

from utils.recursos import Bot, expand_bible_verse
from utils.permissoes import permissao
from utils.data import save_config

from zoneinfo import ZoneInfo

class LiturgiaCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot
		self.session = aiohttp.ClientSession()
		self.envio_liturgia.start()
	
	liturgia_gp = app_commands.Group(name="liturgia", description="Comandos relacionados a liturgia diária.")

	@liturgia_gp.command(name="calendario", description="Obter informações sobre o calendário litúrgico.")
	@app_commands.describe(
		ano="Ano para o qual calcular o calendário litúrgico (padrão: ano atual)"
	)
	async def calendario(self, interaction: discord.Interaction, ano: int = None):
		cores = {
			"Quaresma": 0x6A0DAD,
			"Tríduo Pascal": 0xFFFFFF,
			"Advento": 0x6A0DAD,
			"Natal": 0xFF0000
		}
		
		calendario_dict = {
			"Tempo Comum 1": {
				"Início": (0, 0),
				"Terça-feira antes da Quarta-feira de Cinzas": (0, 0)
			},
			"Quaresma": {
				"Quarta-feira de Cinzas": (0, 0),
				"Domingo de Ramos": (0, 0)
			},
			"Tríduo Pascal": {
				"Quinta-feira Santa": (0, 0),
				"Sexta-feira Santa": (0, 0),
				"Sábado Santo": (0, 0),
				"Domingo de Páscoa": (0, 0)
			},
			"Tempo Comum 2": {
				"Pentecostes": (0, 0),
				"Solenidade de Cristo Rei": (0, 0)
			},
			"Advento": {
				"Primeiro Domingo do Advento": (0, 0),
				"Segundo Domingo do Advento": (0, 0),
				"Terceiro Domingo do Advento": (0, 0),
				"Quarto Domingo do Advento": (0, 0),
				"Véspera de Natal": (12, 24)
			},
			"Natal": {
				"Natal": (12, 25),
				"Solenidade de Maria, Mãe de Deus": (1, 1),
				"Batismo do Senhor": (0, 0)
			}
		}

		Y = datetime.datetime.now().year if ano is None else ano
		tipos_ano = ["A", "B", "C"]
		tipo_ano = tipos_ano[(Y - 1) % 3]

		view = ui.LayoutView()
		container = ui.Container(
			ui.TextDisplay(f"## Cálculo do Calendário Litúrgico - Ano {tipo_ano} ({Y})"),
			ui.TextDisplay("Aqui estão as datas móveis do calendário litúrgico para o ano atual:"),
			accent_color=0xFFCC00
		)
		view.add_item(container)

		def mod(x, y):
			return x % y

		a = mod(Y, 19)
		b = mod(Y, 4)
		c = mod(Y, 7)
		k = Y // 100
		p = (13 + 8*k) // 25
		q = k // 4
		m = mod(15 - p + k - q, 30)
		n = mod(4 + k - q, 7)
		d = mod(19*a + m, 30)
		e = mod(2*b + 4*c + 6*d + n, 7)

		if d == 29 and e == 6:
			pascoa = (4, 19)

		elif d == 28 and e == 6 and a > 10:
			pascoa = (4, 18)

		else:
			pascoa = (
				3 + ((d + e + 22) // 31),
				mod(d + e + 21, 31) + 1
			)
		
		calendario_dict["Tríduo Pascal"]["Domingo de Páscoa"] = pascoa
		
		pascoa_dt = datetime.datetime(year=Y, month=pascoa[0], day=pascoa[1])

		quarta_cinzas = pascoa_dt - datetime.timedelta(days=46)
		domingo_ramos = pascoa_dt - datetime.timedelta(days=7)
		quinta_santa = pascoa_dt - datetime.timedelta(days=3)
		sexta_santa = pascoa_dt - datetime.timedelta(days=2)
		sabado_santo = pascoa_dt - datetime.timedelta(days=1)
		pentecostes = pascoa_dt + datetime.timedelta(days=49)

		terca_antes_cinzas = quarta_cinzas - datetime.timedelta(days=1)

		def primeiro_domingo_do_ano(ano):
			d = datetime.date(ano, 1, 1)
			return d + datetime.timedelta(days=(6 - d.weekday()) % 7)

		inicio_tc1 = primeiro_domingo_do_ano(Y)

		def primeiro_domingo_advento(ano: int) -> datetime.date:
			natal = datetime.date(ano, 12, 25)
			ultimo_domingo = natal - datetime.timedelta(days=(natal.weekday() + 1) % 7)
			return ultimo_domingo - datetime.timedelta(days=21)

		d1 = primeiro_domingo_advento(Y)
		d2 = d1 + datetime.timedelta(days=7)
		d3 = d1 + datetime.timedelta(days=14)
		d4 = d1 + datetime.timedelta(days=21)

		epifania = datetime.date(Y, 1, 6)
		batismo_senhor = epifania + datetime.timedelta(days=(6 - epifania.weekday()) % 7)

		cristo_rei = d1 - datetime.timedelta(days=7)

		calendario_dict["Tempo Comum 1"]["Início"] = (inicio_tc1.month, inicio_tc1.day)
		calendario_dict["Tempo Comum 1"]["Terça-feira antes da Quarta-feira de Cinzas"] = (terca_antes_cinzas.month, terca_antes_cinzas.day)

		calendario_dict["Quaresma"]["Quarta-feira de Cinzas"] = (quarta_cinzas.month, quarta_cinzas.day)
		calendario_dict["Quaresma"]["Domingo de Ramos"] = (domingo_ramos.month, domingo_ramos.day)

		calendario_dict["Tríduo Pascal"]["Quinta-feira Santa"] = (quinta_santa.month, quinta_santa.day)
		calendario_dict["Tríduo Pascal"]["Sexta-feira Santa"] = (sexta_santa.month, sexta_santa.day)
		calendario_dict["Tríduo Pascal"]["Sábado Santo"] = (sabado_santo.month, sabado_santo.day)

		calendario_dict["Tempo Comum 2"]["Pentecostes"] = (pentecostes.month, pentecostes.day)
		calendario_dict["Tempo Comum 2"]["Solenidade de Cristo Rei"] = (cristo_rei.month, cristo_rei.day)

		calendario_dict["Advento"]["Primeiro Domingo do Advento"] = (d1.month, d1.day)
		calendario_dict["Advento"]["Segundo Domingo do Advento"] = (d2.month, d2.day)
		calendario_dict["Advento"]["Terceiro Domingo do Advento"] = (d3.month, d3.day)
		calendario_dict["Advento"]["Quarto Domingo do Advento"] = (d4.month, d4.day)

		calendario_dict["Natal"]["Batismo do Senhor"] = (batismo_senhor.month, batismo_senhor.day)

		for tempo, eventos in calendario_dict.items():
			new_container = ui.Container(
				accent_color=cores.get(tempo, 0x008000)
			)
			description = f"\n### {tempo}:\n"
			for evento, (m, d) in eventos.items():
				data = datetime.date(year=Y, month=m, day=d) if (m != 0 and d != 0) else None
				if data is not None:
					data_dt = datetime.datetime.combine(data, datetime.time.min)
					dia_semana = data.strftime('%A')

					semana_table = {
						"Sunday": "Domingo",
						"Monday": "Segunda-feira",
						"Tuesday": "Terça-feira",
						"Wednesday": "Quarta-feira",
						"Thursday": "Quinta-feira",
						"Friday": "Sexta-feira",
						"Saturday": "Sábado"
					}

					description += f"- **{evento}**: {semana_table.get(dia_semana, dia_semana)}, {data.strftime('%d/%m/%Y')} ({discord.utils.format_dt(data_dt, 'D')})\n"

			new_container.add_item(ui.TextDisplay(description))
			view.add_item(new_container)

		await interaction.response.send_message(view=view)

	config_bp = app_commands.Group(name="config", description="Configurações das funções relacionadas a liturgia diária.", parent=liturgia_gp)

	@config_bp.command(name="hora", description="A hora do envio da liturgia.")
	@permissao(gerenciar_comunidade=True)
	@app_commands.describe(
		hora="Formato HH:MM"
	)
	async def hora_config(self, interaction: discord.Interaction, hora: str):
		if not re.fullmatch(r"\d{2}:\d{2}", hora):
			return await interaction.response.send_message(
				"O formato exigido não foi satisfeito. Use o formato **HH:MM**, por exemplo: `08:30`.",
				ephemeral=True
			)

		self.atualizar_config(hora=hora)
		await interaction.response.send_message(
			f"Horário do envio das liturgias diárias alterado para: **{hora}**"
		)
	
	@config_bp.command(name="webhook", description="Definir o webhook para enviar as liturgias diárias.")
	@app_commands.describe(
		webhook_url="Link do webhook para enviar quando a liturgia for enviada"
	)
	@permissao(gerenciar_comunidade=True)
	async def canal_config(self, interaction: discord.Interaction, webhook_url: str):
		self.atualizar_config(webhook_url=webhook_url)
		await interaction.response.send_message(f"Webhook do envio das liturgias diárias alterado para: **{webhook_url}**")

	@config_bp.command(name="ping", description="Define o cargo a ser marcado nas liturgias diárias.")
	@app_commands.describe(
		ping="Cargo para marcar quando a liturgia for enviada"
	)
	@permissao(gerenciar_comunidade=True)
	async def ping_config(self, interaction: discord.Interaction, ping: discord.Role):
		self.atualizar_config(cargo_ping=ping)
		await interaction.response.send_message(f"Cargo de marcação alterado para: **{ping.name}**")

	def atualizar_config(self, *, hora: str | None = None, webhook_url: str | None = None, cargo_ping: discord.Role | None = None):
		config = self.bot.config
		config_liturgia = config["liturgia"]
		
		if hora is not None:
			config_liturgia["hora"] = hora
		
		if webhook_url is not None:
			config["urls"]["webhooks"]["Liturgia Diária"] = webhook_url
		
		if cargo_ping is not None:
			config_liturgia["ping"] = cargo_ping.id
		
		config["liturgia"] = config_liturgia
		
		save_config(config)
	
	def cog_unload(self):
		self.envio_liturgia.cancel()
		return super().cog_unload()
	
	@tasks.loop(minutes=1)
	async def envio_liturgia(self):
		config = self.bot.config["liturgia"]
		fuso = ZoneInfo("America/Sao_Paulo")
		agora = datetime.datetime.now(fuso)
		hora_config = datetime.time.fromisoformat(config["hora"])

		canal = self.bot.get_channel(config["canal"])
		if canal is None:
			await self.bot.send_to_console(f"Canal {config['canal']} não encontrado.")
			return
		
		if agora.time() < hora_config:
			return
		else:
			last = [msg async for msg in canal.history(limit=1)]
			last = last[0] if last else None
			if last and last.created_at.date() == agora.date() and last.webhook_id:
				return
		
		webhook_url = self.bot.config.get("urls", {}).get("webhooks", {}).get("Liturgia Diária")
		if not webhook_url:
			await self.bot.send_to_console("Não há webhook registrado para liturgia.")
			return

		try:
			view = await self.generate_liturgy_view(
				url=self.bot.config["urls"]["requests"]["liturgia"],
				content=f"<@&{config['ping']}>"
			)
			
			webhook = discord.Webhook.from_url(webhook_url, session=self.session)
			allowed_mentions = discord.AllowedMentions()
			allowed_mentions.all()

			await webhook.send(view=view, allowed_mentions=allowed_mentions)
		except Exception as e:
			print(f"Erro ao enviar liturgia: {e}")

	@envio_liturgia.before_loop
	async def before_envio(self):
		await self.bot.wait_until_ready()

	async def generate_liturgy_view(self, url: str, content: str) -> ui.LayoutView:
		liturgia = await self.get_liturgy(url)
		containers: list[ui.Container] = []

		MAX_CHARS = 3500

		def split_text(text: str, limit: int = MAX_CHARS) -> list[str]:
			partes = []
			while text:
				if len(text) <= limit:
					partes.append(text)
					break

				corte = text.rfind("\n", 0, limit)
				if corte == -1:
					corte = limit

				partes.append(text[:corte])
				text = text[corte:].lstrip("\n")

			return partes


		def get_container_color(cor: str):
			cores = {"Verde": 0x00FF00, "Branco": 0xFFFFFF, "Vermelho": 0xFF0000, "Azul": 0x0000FF, "Roxo": 0x6A0DAD}
			return cores.get(cor, 0xFFCC00)

		def create_containers(title: str, description: str = "") -> list[ui.Container]:
			containers = []
			partes = split_text(description)

			current_items = []
			current_length = 0

			header = f"## {title}"
			current_items.append(ui.TextDisplay(header))
			current_length += len(header)

			current_items.append(ui.Separator(spacing=discord.SeparatorSpacing.large))

			for parte in partes:
				if current_length + len(parte) > MAX_CHARS:
					containers.append(
						ui.Container(
							*current_items,
							accent_color=get_container_color(liturgia["cor"])
						)
					)
					current_items = []
					current_length = 0

				current_items.append(ui.TextDisplay(parte))
				current_length += len(parte)

			if current_items:
				containers.append(
					ui.Container(
						*current_items,
						accent_color=get_container_color(liturgia["cor"])
					)
				)

			return containers

		for key in ["primeiraLeitura", "salmo", "segundaLeitura", "evangelho", "extras"]:
			leitura = liturgia.get(key)
			if isinstance(leitura, list) and leitura:
				leitura = leitura[0]
			elif not leitura:
				continue

			titulo_base = f'{leitura["titulo"]} - {leitura["referencia"]}'
			
			versiculos_info = expand_bible_verse(leitura["referencia"].replace(", ", ",").replace(". ", "."))
			
			if not versiculos_info:
				texto_final = leitura["texto"]
			else:
				todos_versiculos = []
				for v in versiculos_info:
					todos_versiculos.extend(v["texto"])

				texto_final = "\n".join(todos_versiculos)

			containers.extend(create_containers(titulo_base, texto_final))

		view = ui.LayoutView()

		for i, c in enumerate(containers, start=1):
			if i == len(containers) and content:
				for parte in split_text(content):
					c.add_item(ui.TextDisplay(parte))

			view.add_item(c)
		return view

	async def get_liturgy(self, url: str) -> dict:
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as response:
				data: dict[str, dict] = await response.json()

		return {
			"titulo": data.get("liturgia", ""),
			"cor": data.get("cor", "Amarelo"),
			"primeiraLeitura": data["leituras"].get("primeiraLeitura", []),
			"segundaLeitura": data["leituras"].get("segundaLeitura", []),
			"evangelho": data["leituras"].get("evangelho", [])
		}

async def setup(bot: Bot):
	await bot.add_cog(LiturgiaCog(bot))