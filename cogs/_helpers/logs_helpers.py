import random
import unicodedata

import discord
from discord import ui

from utils.catecismo import check_cic_verse
from utils.data import DataFiles, get_member, save_member
from utils.logs import TipoPunicao, log_punicao
from utils.recursos import Bot, expand_bible_verse
from better_profanity import profanity

CYRILLIC_TO_LATIN = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
    }
)


def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.translate(CYRILLIC_TO_LATIN)
    texto = (
        texto.replace("0", "o").replace("1", "i").replace("3", "e").replace("4", "a")
    )
    texto = texto.replace("5", "s").replace("7", "t")
    texto = texto.replace("-", "")
    texto = texto.replace(" ", "")
    return texto


def gerar_variacoes(palavras: list[str]) -> set[str]:
    variacoes: set[str] = set()
    sufixos = ["", "s", "es", "inho", "inha", "ao", "ona"]
    substituicoes = {
        "a": ["a", "@"],
        "e": ["e", "3"],
        "i": ["i", "1"],
        "o": ["o", "0"],
        "s": ["s", "$"],
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
                    variacoes.add(base[:i] + sub + base[i + 1 :])

    return variacoes


class GetBumpRow(ui.ActionRow):
    def __init__(self):
        super().__init__()

    @ui.button(
        custom_id="get_bump",
        emoji="⬆️",
        label="Pegar Cargo",
        style=discord.ButtonStyle.blurple,
    )
    async def get_bump_role(self, interaction: discord.Interaction, button: ui.Button):
        cargo = interaction.guild.get_role(1442131698732105840)
        reason = "Menção de bumps"
        if cargo in interaction.user.roles:
            await interaction.user.remove_roles(cargo, reason=reason)
            return await interaction.response.send_message(
                f"{cargo.mention} removido com sucesso!", ephemeral=True
            )

        await interaction.user.add_roles(cargo, reason=reason)
        await interaction.response.send_message(
            f"{cargo.mention} adicionado com sucesso!", ephemeral=True
        )


class GetBumpRole(ui.LayoutView):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        container = ui.Container(
            ui.Section(
                ui.TextDisplay("## Pegue a menção de Bumps"),
                accessory=ui.Thumbnail(guild.icon.url) if guild.icon else None,
            )
        )
        container.add_item(
            ui.TextDisplay(
                "Clique no botão abaixo para receber o cargo de marcação de Bumps. "
                "Toda vez que um Bump pode ser dado na Disboard, você será notificado."
            )
        )
        container.add_item(GetBumpRow())
        container.add_item(ui.TextDisplay("-# Sacra Communitas - Bumps"))
        self.add_item(container)
