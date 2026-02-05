import datetime
import discord
import unicodedata
import random
import re

from better_profanity import profanity

from discord import ui
from discord.ext import commands

from utils.catecismo import check_cic_verse
from utils.data import DataFiles, get_member, save_member
from utils.recursos import Bot, expand_bible_verse
from utils.logs import log_normal, log_punicao, TipoPunicao
from utils.embed import criar_embed

CYRILLIC_TO_LATIN = str.maketrans({
	"А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
	"Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
	"Х": "X", "а": "a", "е": "e", "о": "o", "р": "p",
	"с": "c", "у": "y", "х": "x", "і": "i", "ј": "j",
})

def normalizar(texto: str) -> str:
	texto = texto.lower()
	texto = unicodedata.normalize("NFD", texto)
	texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
	texto = texto.translate(CYRILLIC_TO_LATIN)
	texto = texto.replace("0", "o").replace("1", "i").replace("3", "e").replace("4", "a")
	texto = texto.replace("5", "s").replace("7", "t")
	texto = re.sub(r"(.)\1{2,}", r"\1", texto)
	return texto

def gerar_variacoes(palavras: list[str]) -> set[str]:
	variacoes = set()

	sufixos = ["", "s", "es", "inho", "inha", "ao", "ona"]
	substituicoes = {
		"a": ["a", "@"],
		"e": ["e", "3"],
		"i": ["i", "1"],
		"o": ["o", "0"],
		"s": ["s", "$"]
	}

	for palavra in palavras:
		base = normalizar(palavra)
		variacoes.add(base)
		variacoes.add(base.replace("-", ""))
		variacoes.add(base.replace("-", " "))

		for sufixo in sufixos:
			variacoes.add(base + sufixo)

		for i, ch in enumerate(base):
			if ch in substituicoes:
				for sub in substituicoes[ch]:
					variacoes.add(base[:i] + sub + base[i+1:])

	return variacoes

class LogsCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
	
	@commands.command(name="badwords", description="Veja a quantidade de palavrões que alguém falou.")
	async def badwords_count(self, ctx: commands.Context, member: discord.User = None):
		user = member if member else ctx.author
		member_data = get_member(user.id)
		await ctx.reply(f"{user.mention} tem **{member_data['palavroes']}** palavrões registrados.")
	
	@commands.Cog.listener()
	async def on_thread_create(self, thread: discord.Thread):
		if isinstance(thread.parent, discord.ForumChannel):
			if thread.parent.id == self.bot.config["canais"]["sugestoes"]:
				await thread.add_tags(thread.parent.get_tag(1460689239900426573), reason="Setup de sugestões")

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		if member.guild.id != 1429152785252876328:
			return
		if member.bot:
			anjo_role_id = self.bot.config['cargos']['anjos']['Anjo']['id']
			role = member.guild.get_role(anjo_role_id)
			return await member.add_roles(role, reason="Novo membro entrou: Bot")

		leigo_role_id = self.bot.config['cargos']['membros']['Leigo']['id']
		role = member.guild.get_role(leigo_role_id)
		if role:
			try:
				await member.add_roles(role, reason="Novo membro entrou: Leigo")
			except discord.Forbidden:
				print(f"Sem permissão para adicionar cargo ao membro {member}")
			except discord.HTTPException as e:
				print(f"Erro ao adicionar cargo: {e}")
		
		regras_mention = f"<#{self.bot.config['canais']['regras']}>"

		channel_id = self.bot.config['canais'].get('geral')
		channel = self.bot.get_channel(channel_id) if channel_id else None

		if channel:
			embed = criar_embed(
				titulo="✨ Bem-vindo(a)!",
				descricao=f"Seja bem-vindo(a) ao servidor, {member.mention}!\n\nLeia as regras em {regras_mention} e aproveite sua estadia!",
				cor=0xffcc00,
				membro=member,
				footer="Leigo",
				servidor=member.guild
			)
			await channel.send(content=member.mention, embed=embed)
	
	@commands.Cog.listener()
	async def on_message(self, msg: discord.Message):		
		await self.publish_if_news(msg=msg)
		await self.check_boost_message(msg=msg)
		
		if msg.author.bot:
			return
		
		await check_cic_verse(msg=msg)
		await self.check_bible_verse(msg=msg)
		await self.check_badword(msg=msg)
	
	async def publish_if_news(self, msg: discord.Message):
		if msg.channel.type != discord.ChannelType.news:
			return
		
		if msg.flags.crossposted:
			return
		
		try:
			await msg.publish()
		except discord.Forbidden:
			await self.bot.send_to_console("Não tenho permissão para publicar mensagens.")
		except Exception as e:
			await self.bot.send_to_console(f"Ocorreu um erro ao publicar a mensagems: {e.text}")

	async def check_badword(self, msg: discord.Message):
		if not msg.guild:
			return

		if not msg.channel.permissions_for(msg.guild.default_role).send_messages:
			return
		
		with open(DataFiles.PALAVROES.value, encoding="utf-8") as f:
			PALAVROES = {linha.strip() for linha in f if linha.strip()}

		variacoes = gerar_variacoes(PALAVROES)

		profanity.load_censor_words(variacoes)
		
		conteudo = normalizar(msg.content)
		tem_palavrao = profanity.contains_profanity(conteudo)
		
		if tem_palavrao:
			respostas = [
				"Olha a língua.",
				"Sem palavrões aqui.",
				"Um pouco mais de respeito, por favor.",
				["Efésios 4,29"],
				["Colossenses 3,8"],
				["Tiago 3,10"],
				["Mateus 15:11"],
				["Provérbios 4,24"],
				["Efésios 5,4"]
			]
			resposta = random.choice(respostas)
			if isinstance(resposta, list):
				res = expand_bible_verse(resposta[0])[0]
				versiculo_inicial = res['versículo_inicial']
				versiculo_final = res['versículo_final']
				versiculo = versiculo_inicial if versiculo_inicial == versiculo_final else f"{versiculo_inicial}-{versiculo_final}"

				tipo = res['tipo']
				separador = ":" if tipo == "Evangelhos" else ","

				passagem = f"{res['capítulo']}{separador}{versiculo}"

				embed = discord.Embed(
					title=f"{res['livro']} {passagem} ({tipo})",
					description=f"{' '.join(res['texto'])}",
					colour=0xffcc00
				)
				await msg.reply(embed=embed)
			else:
				await msg.reply(resposta)
			await msg.delete()

			member_data = get_member(msg.author.id)
			member_data["palavroes"] += 1
			save_member(msg.author.id, member_data)

			if member_data["palavroes"] > 3:
				duracao = datetime.timedelta(minutes=member_data["palavroes"])

				await msg.author.timeout(duracao, reason="Falando muitos palavrões.")
			

	async def check_boost_message(self, msg: discord.Message):
		match msg.type:
			case discord.MessageType.premium_guild_subscription:
				await self.enviar_mensagem_boost(msg.author)
				await msg.author.add_roles(
					msg.guild.get_role(self.bot.config["cargos"]["config"]["ja_fui_booster"])
				)
			case discord.MessageType.premium_guild_tier_1:
				await self.enviar_novo_nivel(msg.guild, msg.author)
			case discord.MessageType.premium_guild_tier_2:
				await self.enviar_novo_nivel(msg.guild, msg.author)
			case discord.MessageType.premium_guild_tier_3:
				await self.enviar_novo_nivel(msg.guild, msg.author)

	async def check_bible_verse(self, msg: discord.Message):
		resultados = expand_bible_verse(msg.content)

		for res in resultados:
			versiculo_inicial = res['versículo_inicial']
			versiculo_final = res['versículo_final']
			versiculo = versiculo_inicial if versiculo_inicial == versiculo_final else f"{versiculo_inicial}-{versiculo_final}"

			tipo = res['tipo']
			separador = ":" if tipo == "Evangelhos" else ","

			passagem = f"{res['capítulo']}{separador}{versiculo}"

			view = ui.LayoutView()
			container = ui.Container(
				ui.Section(
					ui.TextDisplay(f"## {res['livro']} {passagem} ({tipo})"),
					accessory=ui.Thumbnail("https://upload.wikimedia.org/wikipedia/commons/7/78/Red_Chi_Rho_sign.png")
				),
				accent_color=0xFFCC00
			)
			novos_containers = 0

			container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
			items_count = 4

			for v in res["texto"]:
				container.add_item(ui.TextDisplay(v))
				items_count+=1
				if items_count == 40:
					view.add_item(container)
					if novos_containers == 0:
						await msg.reply(view=view)
					else:
						await msg.channel.send(view=view)
					
					view = ui.LayoutView()
					container = ui.Container(
						ui.TextDisplay(f"## {res['livro']} {passagem} ({tipo})"),
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

	@commands.Cog.listener()
	async def on_message_edit(self, before: discord.Message, after: discord.Message):
		if after.author.bot:
			return

		if before.content == after.content:
			return

		await log_normal(
			guild=after.guild,
			tipo=1,
			membro=after.author,
			msg_before=before,
			msg_after=after,
		)
		await self.check_badword(msg=after)

	@commands.Cog.listener()
	async def on_message_delete(self, msg: discord.Message):
		if msg.author.bot:
			return

		autor = None
		motivo = None

		try:
			async for entry in msg.guild.audit_logs(
				limit=1, action=discord.AuditLogAction.message_delete
			):
				if entry.target and entry.target.id == msg.author.id:
					autor = entry.user
					motivo = entry.reason
					break

		except Exception as e:
			print(f"Erro ao verificar audit_logs: {e}")

		await log_normal(
			guild=msg.guild,
			tipo=0,
			membro=msg.author,
			msg_before=msg,
			author=autor,
			motivo=motivo,
		)

	@commands.Cog.listener()
	async def on_member_remove(self, membro: discord.Member):
		autor = None
		motivo = ""

		try:
			ban_info = await membro.guild.fetch_ban(membro)
			del ban_info
			return
		except discord.NotFound:
			try:
				async for entry in membro.guild.audit_logs(
					limit=1, action=discord.AuditLogAction.kick
				):
					if entry.target.id == membro.id:
						motivo = entry.reason
						autor = entry.user
						break

			except Exception as e:
				print(f"Erro ao verificar audit_logs: {e}")

			if entry.user.id == self.bot.user.id:
				return
			
			if autor is None:
				return
			
			await log_punicao(membro.guild, TipoPunicao.Suspensao, membro, autor, motivo)
	
	@commands.Cog.listener()
	async def on_member_ban(self, servidor: discord.Guild, user: discord.User):
		ban_info = await servidor.fetch_ban(user)

		motivo = ban_info.reason or ""

		autor = None

		async for entry in servidor.audit_logs(
			limit=1,
			action=discord.AuditLogAction.ban
		):
			if entry.target.id == user.id:
				autor = entry.user
				if entry.reason:
					motivo = entry.reason
				break
		
		if autor == self.bot.user:
			return

		await log_punicao(servidor, TipoPunicao.Excomunhao, user, autor, motivo)

	@commands.Cog.listener()
	async def on_member_unban(self, servidor: discord.Guild, user: discord.User):
		autor = None
		motivo = ""

		async for entry in servidor.audit_logs(
			limit=1,
			action=discord.AuditLogAction.unban
		):
			if entry.target.id == user.id:
				autor = entry.user
				motivo = entry.reason or ""
				break
		
		if autor == self.bot:
			return

		await log_punicao(servidor, TipoPunicao.ComunhaoRestaurada, user, autor, motivo)


	async def verificar_timeout(self, before: discord.Member, after: discord.Member):
		autor = None
		motivo = None

		async for entry in after.guild.audit_logs(
			limit=1, action=discord.AuditLogAction.member_update, after=after
		):
			autor = entry.user
			motivo = entry.reason
			break

		if autor is None or autor == self.bot.user:
			return

		if after.timed_out_until and before.timed_out_until != after.timed_out_until:
			await log_punicao(after.guild, 1, after, autor, motivo)
			return

		if before.timed_out_until and before.timed_out_until != after.timed_out_until:
			await log_punicao(after.guild, 4, after, autor, motivo)

	async def verificar_cargos(self, before: discord.Member, after: discord.Member):
		if before.roles == after.roles:
			return

		autor = None
		motivo = None

		async for entry in after.guild.audit_logs(
			limit=1, action=discord.AuditLogAction.member_role_update, after=after
		):
			autor = entry.user
			motivo = entry.reason
			break

		if autor.id == after.id:
			autor = None

		await log_normal(
			guild=after.guild,
			tipo=2,
			membro=after,
			author=autor,
			user_before=before,
			user_after=after,
			motivo=motivo,
		)

	async def enviar_mensagem_boost(self, usuario: discord.Member):
		canal = usuario.guild.get_channel(self.bot.config["canais"]["geral"])

		view = ui.LayoutView()
		container = ui.Container(
			ui.Section(
				ui.TextDisplay("🎉 **Novo Booster!**"),
				accessory=ui.Thumbnail(usuario.display_avatar.url)
			),
			accent_color=usuario.guild.premium_subscriber_role.color
		)

		container.add_item(
			ui.TextDisplay(
				f"✨ {usuario.mention} acabou de impulsionar o servidor!\n"
				"Obrigado por ajudar a tornar nossa comunidade ainda mais incrível!\n\n"
				"Cada boost é um passo a mais para o crescimento da comunidade. Sua ajuda faz diferença!"
			)
		)

		container.add_item(
			ui.MediaGallery(
				discord.MediaGalleryItem("https://media.discordapp.net/attachments/955972869505024020/1325490299874836510/booster.gif")
			)
		)

		agora = int(datetime.datetime.now().timestamp())
		container.add_item(
			ui.TextDisplay(f"<t:{agora}:F>")
		)
		view.add_item(container)

		await canal.send(view=view)

	async def enviar_novo_nivel(self, guild: discord.Guild, ultimo_usuario: discord.Member):
		await self.enviar_mensagem_boost(ultimo_usuario)
		canal = guild.get_channel(self.bot.config["canais"]["geral"])

		nivel = guild.premium_tier
		boosts = guild.premium_subscription_count

		view = ui.LayoutView()

		icone_nivel = {1: "⭐", 2: "🌟", 3: "👑"}.get(nivel, "🚀")

		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"{icone_nivel} **Subimos para o Nível {nivel}!**"),
				accessory=ui.Thumbnail(guild.icon.url) if guild.icon else None
			),
			accent_color=0xFFCC00
		)

		container.add_item(
			ui.TextDisplay(
				f"Graças aos impulsos da comunidade, alcançamos **Nível {nivel}** de boost!\n\n"
				f"💜 Último boost: {ultimo_usuario.mention}\n"
				f"🔥 Total de boosts ativos: **{boosts}**\n\n"
				"Isso libera ainda mais benefícios para o servidor. Obrigado a todos que estão apoiando!"
			)
		)

		agora = int(datetime.datetime.now().timestamp())
		container.add_item(ui.TextDisplay(f"<t:{agora}:F>"))

		view.add_item(container)

		await canal.send(view=view)

	@commands.Cog.listener()
	async def on_member_update(self, before: discord.Member, after: discord.Member):
		await self.verificar_timeout(before, after)
		await self.verificar_cargos(before, after)

async def setup(bot: Bot):
	await bot.add_cog(LogsCog(bot))

	@bot.tree.context_menu(name="Recarregar Boost")
	async def recarregar_boost(interaction: discord.Interaction, msg: discord.Message):
		cog: LogsCog = interaction.client.get_cog("LogsCog")
		if cog:
			await cog.check_boost_message(msg)
			await interaction.response.send_message("Boost recarregado.", ephemeral=True)
		else:
			await interaction.response.send_message("Cog não encontrado.", ephemeral=True)