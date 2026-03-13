import datetime
import discord

from discord import app_commands, ui
from discord.ext import commands

from enum import Enum

from typing import TypedDict, Optional

from utils.recursos import Bot
from utils.data import get_member


class LogEnum(Enum):
	ban = 0
	unban = 1
	mute = 2
	unmute = 3
	warn = 4
	warnremove = 5
	kick = 6

class PunicaoDict(TypedDict):
	tipo: LogEnum
	author: str
	data: datetime.datetime
	motivo: str
	ativo: Optional[bool]

async def get_punicoes(user: discord.User, guild: discord.Guild) -> list[PunicaoDict]:
	punicoes = []

	tipos = {
		discord.AuditLogAction.ban: LogEnum.ban,
		discord.AuditLogAction.kick: LogEnum.kick,
		discord.AuditLogAction.unban: LogEnum.unban,
	}

	async for entry in guild.audit_logs(limit=None):
		if not entry.target or entry.target.id != user.id:
			continue

		if entry.action in tipos:
			punicoes.append({
				"tipo": tipos[entry.action],
				"author": entry.user.mention if entry.user else "Desconhecido",
				"data": entry.created_at,
				"motivo": entry.reason or "Não informado"
			})

		elif entry.action == discord.AuditLogAction.member_update:
			before = entry.before.timed_out_until
			after = entry.after.timed_out_until

			if before != after:
				punicoes.append({
					"tipo": LogEnum.mute if after else LogEnum.unmute,
					"author": entry.user.mention if entry.user else "Desconhecido",
					"data": entry.created_at,
					"motivo": entry.reason or "Não informado"
				})

	user_data = get_member(user.id) or {"warns": []}

	for w in user_data["warns"]:
		punicoes.append({
			"tipo": LogEnum.warnremove if w.get("remocao", False) else LogEnum.warn,
			"author": w["dado_por"],
			"data": datetime.datetime.fromtimestamp(w["quando"]),
			"motivo": w["motivo"]
		})

	punicoes.sort(key=lambda x: x["data"])

	return punicoes
class PunView(ui.LayoutView):
	def __init__(self, user: discord.User, punicoes: list[PunicaoDict], tipo: int = 0):
		super().__init__(timeout=None)
		container = ui.Container(
			ui.TextDisplay(f"## Punições de {user.mention}"),
		)
		for p in punicoes:
			p["ativo"] = True
		
		for i, p in enumerate(punicoes):
			if p["tipo"] == LogEnum.unban:
				for j in range(i - 1, -1, -1):
					if punicoes[j]["tipo"] == LogEnum.ban:
						punicoes[j]["ativo"] = False
						break

			elif p["tipo"] == LogEnum.unmute:
				for j in range(i - 1, -1, -1):
					if punicoes[j]["tipo"] == LogEnum.mute:
						punicoes[j]["ativo"] = False
						break

			elif p["tipo"] == LogEnum.warnremove:
				for j in range(i - 1, -1, -1):
					if punicoes[j]["tipo"] == LogEnum.warn:
						punicoes[j]["ativo"] = False
						break

		for i, p in enumerate(punicoes):
			texto = (
				f"**{p['tipo'].name.upper()}** - {discord.utils.format_dt(p['data'], 'F')}\n"
				f"> **Autor:** {p['author']}\n"
				f"> **Motivo:** {p['motivo']}"
			)

			if p["tipo"] in (LogEnum.ban, LogEnum.mute, LogEnum.warn) and p["ativo"]:
				btn = ui.Button(
					label="Apelar desta punição",
					custom_id=f"apel_{i}",
					emoji="⚖️"
				)
				async def callback(interaction: discord.Interaction):
					index = btn.custom_id[5:]
					await interaction.response.send_message(index, ephemeral=True)
				btn.callback = callback

				section = ui.Section(
					ui.TextDisplay(texto),
					accessory=btn
				)

				container.add_item(section)

			else:
				container.add_item(ui.TextDisplay(texto + "\n"))
		
		self.punicoes = punicoes

		self.add_item(container)

class OpenApelView(ui.LayoutView):
	def __init__(self, guild: discord.Guild, sacra: discord.Guild):
		super().__init__(timeout=None)
		self.guild = sacra
		container = ui.Container(
			ui.Section(
				ui.TextDisplay(
					"## Pedido de remoção de punição."
				),
				accessory=ui.Thumbnail(guild.icon.url)
			),
			ui.Separator(spacing=discord.SeparatorSpacing.large),
			ui.TextDisplay(
				"Caso acredite que sua punição foi aplicada de forma indevida na Sacra Communitas, ou quer se redimir, pode pedir uma revisão."
			),
			accent_color=0xFFCC00
		)

		btn = ui.Button(
			label="Fazer pedido",
			custom_id="add_pedido",
			emoji="📝"
		)
		btn.callback = self.callback
		container.add_item(
			ui.ActionRow(btn)
		)

		self.add_item(container)
	
	async def callback(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True, thinking=True)

		punicoes = await get_punicoes(interaction.user, self.guild)
		
		if not punicoes:
			return await interaction.followup.send("Nenhuma punição encontrada.", ephemeral=True)
		
		await interaction.followup.send(view=PunView(interaction.user, punicoes), ephemeral=True)

class ApelCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot
		self.sacra = bot.get_guild(1429152785252876328)
		self.tribunal = bot.get_guild(1464281876507398168)
	
	async def cog_load(self):
		await super().cog_load()
		self.bot.add_view(OpenApelView(self.tribunal, self.sacra))

	
	apel_gp = app_commands.Group(name="apel", description="Comandos para o servidor de apelação.", guild_ids=[1464281876507398168])

	@apel_gp.command(name="get", description="Pega informações das últimas punições de um usuário.")
	@app_commands.describe(
		user="O usuário a ser verificado."
	)
	async def get_user_info(self, interaction: discord.Interaction, user: discord.User):
		await interaction.response.defer(ephemeral=True)

		punicoes = await get_punicoes(user, self.sacra)

		if not punicoes:
			return await interaction.followup.send("Nenhuma punição encontrada.", ephemeral=True)

		membro = self.sacra.get_member(user.id)

		view = ui.LayoutView()
		container = ui.Container(
			ui.Section(
				ui.TextDisplay(f"Punições de {user.mention}"),
				accessory=ui.Thumbnail(user.display_avatar.url)
			),
			ui.Separator(spacing=discord.SeparatorSpacing.large),
			accent_color=membro.color if membro else None 
		)

		for p in punicoes:
			container.add_item(ui.TextDisplay(
				f"**{p['tipo'].name.upper()}** - {discord.utils.format_dt(p['data'], "F")}\n"
				f"> **Autor:** {p['author']}\n"
				f"> **Motivo:** {p['motivo']}\n\n"
			))
		
		view.add_item(container)

		await interaction.followup.send(view=view)

	@apel_gp.command(name="message", description="Envia a mensagem de apelação.")
	async def apel_message(self, interaction: discord.Interaction):
		await interaction.channel.send(view=OpenApelView(interaction.guild))
		await interaction.response.send_message("Mensagem enviada com sucesso!", ephemeral=True)

async def setup(bot: Bot):
	await bot.add_cog(ApelCog(bot=bot))