import datetime
import discord

from discord.ext import commands
from discord import app_commands

from utils.data import get_member, save_member
from utils.logs import log_punicao, make_embed, TipoPunicao
from utils.permissoes import permissao
from utils.recursos import Bot
from utils.data import WarnsJson

def is_staff():
	return app_commands.checks.has_permissions(mute_members=True)

class RemoveWarnOptions(discord.ui.Select):
	def __init__(self, membro: discord.Member, motivo: str):
		membro_json = get_member(membro.id)
		warns = membro_json["warns"]

		options = [
			discord.SelectOption(label=warn["motivo"][:100], value=str(i))
			for i, warn in enumerate(warns)
		]

		super().__init__(
			placeholder="Selecione uma penitência",
			min_values=1,
			max_values=1,
			options=options,
		)

		self.membro = membro
		self.motivo = motivo

	async def callback(self, interaction: discord.Interaction):
		if not interaction.user.guild_permissions.moderate_members:
			return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

		membro_json = get_member(self.membro.id)

		index = int(self.values[0])
		if index >= len(membro_json["warns"]):
			return await interaction.response.send_message("⚠️ Essa penitência já foi removida.", ephemeral=True)

		warn_original = membro_json["warns"].pop(index)
		save_member(self.membro.id, membro_json)

		embed = make_embed(
			"Penitência removida",
			f"{self.membro.mention} teve uma penitência removida.\n\n"
			f"> Removido por: {interaction.user.mention}\n"
			f"> Motivo da remoção: {self.motivo}\n"
			f"> Motivo original: {warn_original['motivo']}",
			discord.Color.green(),
			user=self.membro,
		)

		await interaction.response.edit_message(embed=embed, view=None)
		await log_punicao(interaction.guild, TipoPunicao.Unwarn, self.membro, interaction.user, self.motivo)


class WarnGP(app_commands.Group):
	def __init__(self):
		super().__init__(name="pen", description="Comandos relacionados a penitências.")

	@app_commands.command(name="add", description="Adiciona uma penitência a um membro")
	@app_commands.describe(membro="Membro que receberá a penitência", motivo="Motivo")
	@is_staff()
	async def warn_add(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Não informado"):
		await interaction.response.defer(ephemeral=True)

		novo_warn = WarnsJson()
		novo_warn["dado_por"] = interaction.user.id
		novo_warn["motivo"] = motivo
		novo_warn["quando"] = datetime.datetime.now(datetime.timezone.utc).timestamp()

		membro_json = get_member(membro.id)
		membro_json["warns"].append(novo_warn)
		save_member(membro.id, membro_json)

		tabela_mute = [
			{"hours": 1},
			{"hours": 12},
			{"days": 1},
			{"days": 4},
			{"weeks": 1},
		]

		idx = min(len(membro_json["warns"]) - 1, len(tabela_mute) - 1)
		dados = tabela_mute[idx]
		duracao = datetime.timedelta(
			hours=dados.get("hours", 0),
			days=dados.get("days", 0),
			weeks=dados.get("weeks", 0),
		)

		try:
			if interaction.guild.me.top_role > membro.top_role:
				await membro.timeout(duracao, reason=motivo)
			else:
				await interaction.followup.send("⚠️ Warn aplicado, mas não consegui aplicar timeout por hierarquia de cargos.", ephemeral=True)
		except discord.Forbidden:
			await interaction.followup.send("⚠️ Warn aplicado, mas não tenho permissão para aplicar timeout.", ephemeral=True)

		embed = make_embed(
			"Membro penitenciado",
			f"{membro.mention} recebeu uma penitência.\n\n> Staff: {interaction.user.mention}\n> Motivo: {motivo}",
			discord.Color.green(),
			user=membro,
		)

		await interaction.followup.send(embed=embed, ephemeral=True)
		await log_punicao(interaction.guild, TipoPunicao.Warn, membro, interaction.user, motivo)
	
	@app_commands.command(name="log", description="Veja as penitências de um membro")
	@is_staff()
	async def warn_logs(self, interaction: discord.Interaction, membro: discord.Member):
		membro_json = get_member(membro.id)

		if not membro_json["warns"]:
			return await interaction.response.send_message("Esse membro não possui penitências.", ephemeral=True)

		linhas = []
		for w in membro_json["warns"]:
			linhas.append(
				f"> Motivo: {w['motivo']}\n"
				f"> Staff: <@{w['dado_por']}>\n"
				f"> Data: <t:{int(w['quando'])}:f>"
			)

		embed = make_embed(
			"Penitências do membro",
			f"{membro.mention}\n\n" + "\n\n".join(linhas),
			discord.Color.red(),
			user=membro,
		)

		await interaction.response.send_message(embed=embed, ephemeral=True)
	
	@app_commands.command(name="remove", description="Remove uma penitência de um membro")
	@app_commands.describe(membro="Membro que terá a penitência removida", motivo="Motivo da remoção")
	@is_staff()
	async def warn_remove(
		self,
		interaction: discord.Interaction,
		membro: discord.Member,
		motivo: str = "Não informado",
	):
		membro_json = get_member(membro.id)

		if not membro_json["warns"]:
			embed = make_embed(
				"Sem penitências",
				f"{membro.mention} não possui penitências ativas.",
				discord.Color.green(),
				user=membro,
			)
			return await interaction.response.send_message(embed=embed, ephemeral=True)

		embed = make_embed(
			"Remover penitência",
			"Selecione abaixo qual penitência deve ser removida.",
			discord.Color.blurple(),
			user=membro,
		)

		view = discord.ui.View(timeout=60)
		view.add_item(self.RemoveWarnOptions(membro=membro, motivo=motivo))

		await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



class ModCog(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.warn_gp = WarnGP()

	async def cog_load(self):
		self.bot.tree.add_command(self.warn_gp)
	
	@app_commands.command(name="excomungar", description="Excomunga um membro do servidor")
	@permissao(excomungar=True)
	async def excomungar(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str | None = None):

		if usuario == interaction.user:
			return await interaction.response.send_message("❌ Você não pode se banir.", ephemeral=True)

		if usuario.top_role >= interaction.user.top_role:
			return await interaction.response.send_message("❌ Você não pode banir alguém com cargo igual ou superior.", ephemeral=True)

		if usuario.top_role >= interaction.guild.me.top_role:
			return await interaction.response.send_message("❌ Não posso banir esse membro por causa da hierarquia de cargos.", ephemeral=True)

		await interaction.guild.ban(usuario, reason=motivo or f"Banido por {interaction.user}")

		embed = make_embed(
			"Membro Excomungado",
			f"{usuario.mention} foi banido.\n\n> Staff: {interaction.user.mention}\n> Motivo: {motivo or 'Não informado'}",
			0xff0000,
			user=usuario,
		)

		await interaction.response.send_message(embed=embed)
		await log_punicao(interaction.guild, TipoPunicao.Excomunhao, usuario, interaction.user, motivo)

async def setup(bot: Bot):
	await bot.add_cog(ModCog(bot=bot))