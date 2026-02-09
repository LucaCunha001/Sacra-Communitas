import discord

from discord import app_commands, ui
from discord.ext import commands

from enum import Enum

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

class ApelCog(commands.Cog):
	def __init__(self, bot: Bot):
		super().__init__()
		self.bot = bot
		self.sacra = bot.get_guild(1429152785252876328)
	
	apel_gp = app_commands.Group(name="apel", description="Comandos para o servidor de apelação.", guild_ids=[1464281876507398168])

	@apel_gp.command(name="get", description="Pega informações das últimas punições de um usuário")
	@app_commands.describe(
		user="O usuário a ser verificado."
	)
	async def get_user_info(self, interaction: discord.Interaction, user: discord.User):
		await interaction.response.defer(ephemeral=True)

		punicoes = []
		guild = self.sacra

		tipos = {
			discord.AuditLogAction.ban: LogEnum.ban,
			discord.AuditLogAction.kick: LogEnum.kick,
			discord.AuditLogAction.unban: LogEnum.unban,
		}

		for action in [discord.AuditLogAction.ban, discord.AuditLogAction.kick, discord.AuditLogAction.unban]:
			async for entry in guild.audit_logs(limit=50, action=action):
				if not entry.target or entry.target.id != user.id:
					continue

				punicoes.append({
					"tipo": tipos[action],
					"author": entry.user.id if entry.user else None,
					"data": int(entry.created_at.timestamp()),
					"motivo": entry.reason or "Não informado"
				})

		async for entry in guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
			if not entry.target or entry.target.id != user.id:
				continue

			if entry.after.communication_disabled_until:
				punicoes.append({
					"tipo": LogEnum.mute,
					"author": entry.user.id if entry.user else None,
					"data": int(entry.created_at.timestamp()),
					"motivo": entry.reason or "Não informado"
				})

		user_data = get_member(user.id)
		for w in user_data["warns"]:
			punicoes.append({
				"tipo": LogEnum.warnremove if w.get("remocao", False) else LogEnum.warn,
				"author": w["dado_por"],
				"data": int(w["quando"]),
				"motivo": w["motivo"]
			})

		if not punicoes:
			return await interaction.followup.send("Nenhuma punição encontrada.", ephemeral=True)

		punicoes.sort(key=lambda x: x["data"], reverse=False)

		membro = guild.get_member(user.id)

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
				f"**{p['tipo'].name.upper()}** - <t:{p['data']}:f>\n"
				f"> **Autor:** <@{p['author']}>\n"
				f"> **Motivo:** {p['motivo']}\n\n"
			))
		
		view.add_item(container)

		await interaction.followup.send(view=view)

async def setup(bot: Bot):
	await bot.add_cog(ApelCog(bot=bot))