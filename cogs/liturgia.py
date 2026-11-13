from __future__ import annotations

import aiohttp
import calendar
import certifi
import datetime as dt
import discord
import os
import re
import ssl
import traceback

from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from discord import app_commands, ui
from discord.ext import commands, tasks

from utils.recursos import Bot, expand_bible_verse
from utils.permissoes import permissao
from utils.data import save_config

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
MESES = (
	"janeiro", "fevereiro", "março", "abril", "maio", "junho",
	"julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
DIAS_SEMANA = ("Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab")

CORES_LITURGICAS: dict[str, int] = {
	"Verde": 0x27865B,
	"Branco": 0xD8D0BC,
	"Vermelho": 0xB83A43,
	"Roxo": 0x7651A8,
	"Rosa": 0xD47DA7,
	"Azul": 0x2878C8,
	"Dourado": 0xD4AF37,
	"Preto": 0x303030,
}

ORDEM_GRAUS = {
	"Solenidade": 0,
	"Festa": 1,
	"Domingo": 2,
	"Comemoração": 3,
	"Memória": 4,
	"Memória facultativa": 5,
}

@dataclass(frozen=True, slots=True)
class CelebracaoLiturgica:
	nome: str
	grau: str
	cor: str
	observacao: str = ""

def calcular_pascoa(ano: int) -> dt.date:
	"""Calcula a Páscoa pelo algoritmo gregoriano de Meeus/Jones/Butcher."""
	if not 1 <= ano <= 9999:
		raise ValueError("O ano deve estar entre 1 e 9999.")

	a = ano % 19
	b = ano // 100
	c = ano % 100
	d = b // 4
	e = b % 4
	f = (b + 8) // 25
	g = (b - f + 1) // 3
	h = (19 * a + b - d - g + 15) % 30
	i = c // 4
	k = c % 4
	l = (32 + 2 * e + 2 * i - h - k) % 7
	m = (a + 11 * h + 22 * l) // 451
	valor = h + l - 7 * m + 114

	mes = valor // 31
	dia = valor % 31 + 1
	return dt.date(ano, mes, dia)


def _domingo_mais_proximo(data: dt.date) -> dt.date:
	"""Retorna o domingo mais próximo; em empate, prefere o posterior."""
	dias_ate_anterior = (data.weekday() + 1) % 7
	dias_ate_posterior = (6 - data.weekday()) % 7
	anterior = data - dt.timedelta(days=dias_ate_anterior)
	posterior = data + dt.timedelta(days=dias_ate_posterior)
	return anterior if dias_ate_anterior < dias_ate_posterior else posterior

def _primeiro_domingo_depois(data: dt.date) -> dt.date:
	dias = (6 - data.weekday()) % 7
	if dias == 0:
		dias = 7
	return data + dt.timedelta(days=dias)

def calcular_datas_liturgicas(ano: int) -> dict[str, dt.date]:
	"""Datas móveis e principais datas transferidas segundo o uso brasileiro."""
	if not 1 <= ano <= 9999:
		raise ValueError("O ano deve estar entre 1 e 9999.")

	pascoa = calcular_pascoa(ano)
	quarta_cinzas = pascoa - dt.timedelta(days=46)
	domingo_ramos = pascoa - dt.timedelta(days=7)
	quinta_santa = pascoa - dt.timedelta(days=3)
	sexta_santa = pascoa - dt.timedelta(days=2)
	sabado_santo = pascoa - dt.timedelta(days=1)

	epifania = dt.date(ano, 1, 2) + dt.timedelta(
		days=(6 - dt.date(ano, 1, 2).weekday()) % 7
	)

	batismo = (
		epifania + dt.timedelta(days=1)
		if epifania.day in (7, 8)
		else epifania + dt.timedelta(days=7)
	)

	véspera_natal = dt.date(ano, 12, 24)
	quarto_advento = véspera_natal - dt.timedelta(
		days=(véspera_natal.weekday() + 1) % 7
	)
	primeiro_advento = quarto_advento - dt.timedelta(days=21)

	ascensao = pascoa + dt.timedelta(days=42)
	sao_pedro_paulo = _domingo_mais_proximo(dt.date(ano, 6, 29))
	assuncao = _domingo_mais_proximo(dt.date(ano, 8, 15))

	todos_santos = dt.date(ano, 11, 1)
	if todos_santos.weekday() != 6 and dt.date(ano, 11, 2).weekday() != 6:
		todos_santos = _primeiro_domingo_depois(todos_santos)

	imaculada = dt.date(ano, 12, 8)
	if imaculada.weekday() == 6:
		imaculada += dt.timedelta(days=1)

	sao_jose = dt.date(ano, 3, 19)
	if domingo_ramos <= sao_jose < pascoa:
		sao_jose = domingo_ramos - dt.timedelta(days=1)
	elif sao_jose.weekday() == 6:
		sao_jose += dt.timedelta(days=1)

	anunciacao = dt.date(ano, 3, 25)
	if domingo_ramos <= anunciacao <= pascoa + dt.timedelta(days=7):
		anunciacao = pascoa + dt.timedelta(days=8)
	elif anunciacao.weekday() == 6:
		anunciacao += dt.timedelta(days=1)

	sagrada_familia = _primeiro_domingo_depois(dt.date(ano, 12, 25))
	if sagrada_familia.year != ano:
		sagrada_familia = dt.date(ano, 12, 30)

	return {
		"Epifania do Senhor": epifania,
		"Batismo do Senhor": batismo,
		"Quarta-feira de Cinzas": quarta_cinzas,
		"Domingo de Ramos": domingo_ramos,
		"Quinta-feira Santa": quinta_santa,
		"Sexta-feira Santa": sexta_santa,
		"Sábado Santo": sabado_santo,
		"Domingo de Páscoa": pascoa,
		"Domingo da Divina Misericórdia": pascoa + dt.timedelta(days=7),
		"Ascensão do Senhor": ascensao,
		"Pentecostes": pascoa + dt.timedelta(days=49),
		"Santíssima Trindade": pascoa + dt.timedelta(days=56),
		"Corpus Christi": pascoa + dt.timedelta(days=60),
		"Sagrado Coração de Jesus": pascoa + dt.timedelta(days=68),
		"Imaculado Coração de Maria": pascoa + dt.timedelta(days=69),
		"Domingo de Laetare": pascoa - dt.timedelta(days=21),
		"Primeiro Domingo do Advento": primeiro_advento,
		"Segundo Domingo do Advento": primeiro_advento + dt.timedelta(days=7),
		"Terceiro Domingo do Advento": primeiro_advento + dt.timedelta(days=14),
		"Quarto Domingo do Advento": quarto_advento,
		"Solenidade de Cristo Rei": primeiro_advento - dt.timedelta(days=7),
		"São José": sao_jose,
		"Anunciação do Senhor": anunciacao,
		"São Pedro e São Paulo": sao_pedro_paulo,
		"Assunção de Nossa Senhora": assuncao,
		"Todos os Santos": todos_santos,
		"Imaculada Conceição": imaculada,
		"Sagrada Família": sagrada_familia,
		"Véspera de Natal": dt.date(ano, 12, 24),
		"Natal": dt.date(ano, 12, 25),
		"Santa Maria, Mãe de Deus": dt.date(ano, 1, 1),
	}


def obter_tempo_liturgico(data: dt.date) -> str:
	datas = calcular_datas_liturgicas(data.year)

	if data.month == 12 and data.day >= 25:
		return "Tempo do Natal"
	if data >= datas["Primeiro Domingo do Advento"]:
		return "Advento"
	if data <= datas["Batismo do Senhor"]:
		return "Tempo do Natal"
	if data < datas["Quarta-feira de Cinzas"]:
		return "Tempo Comum"
	if data < datas["Quinta-feira Santa"]:
		return "Quaresma"
	if data < datas["Domingo de Páscoa"]:
		return "Tríduo Pascal"
	if data <= datas["Pentecostes"]:
		return "Tempo Pascal"
	return "Tempo Comum"


def obter_ano_liturgico(data: dt.date) -> int:
	"""O ano litúrgico muda no primeiro domingo do Advento."""
	inicio_ano = data.year
	if data >= calcular_datas_liturgicas(data.year)["Primeiro Domingo do Advento"]:
		inicio_ano += 1
	return inicio_ano


def obter_ciclo_dominical(data: dt.date) -> str:
	"""Ciclo A/B/C das leituras dominicais."""
	return {0: "C", 1: "A", 2: "B"}[obter_ano_liturgico(data) % 3]


def obter_ciclo_ferial(data: dt.date) -> str:
	"""Ciclo I/II das primeiras leituras dos dias de semana."""
	return "II" if obter_ano_liturgico(data) % 2 == 0 else "I"


def _cor_base_tempo(data: dt.date) -> str:
	datas = calcular_datas_liturgicas(data.year)
	tempo = obter_tempo_liturgico(data)

	if data in (datas["Domingo de Ramos"], datas["Sexta-feira Santa"], datas["Pentecostes"]):
		return "Vermelho"
	if data in (datas["Domingo de Laetare"], datas["Terceiro Domingo do Advento"]):
		return "Rosa"
	if data == datas["Quinta-feira Santa"]:
		return "Branco"
	if data == datas["Sábado Santo"]:
		return "Branco"
	if tempo in ("Advento", "Quaresma"):
		return "Roxo"
	if tempo in ("Tempo do Natal", "Tempo Pascal"):
		return "Branco"
	if tempo == "Tríduo Pascal":
		return "Vermelho"
	return "Verde"


def obter_celebracoes_do_ano(ano: int) -> dict[dt.date, list[CelebracaoLiturgica]]:
	"""Monta os destaques do calendário universal e as principais adaptações do Brasil."""
	datas = calcular_datas_liturgicas(ano)
	eventos: dict[dt.date, list[CelebracaoLiturgica]] = {}

	def adicionar(
		data: dt.date,
		nome: str,
		grau: str = "Solenidade",
		cor: str = "Branco",
		observacao: str = "",
	) -> None:
		if data.year != ano:
			return
		eventos.setdefault(data, []).append(
			CelebracaoLiturgica(nome, grau, cor, observacao)
		)

	adicionar(datas["Santa Maria, Mãe de Deus"], "Santa Maria, Mãe de Deus", "Solenidade")
	adicionar(datas["Epifania do Senhor"], "Epifania do Senhor", "Solenidade")
	adicionar(datas["Batismo do Senhor"], "Batismo do Senhor", "Festa")
	adicionar(datas["Sagrada Família"], "Sagrada Família", "Festa")
	adicionar(dt.date(ano, 2, 2), "Apresentação do Senhor", "Festa")

	adicionar(dt.date(ano, 1, 2), "São Basílio Magno e São Gregório Nazianzeno", "Memória", "Branco")
	adicionar(dt.date(ano, 1, 17), "Santo Antão, abade", "Memória", "Branco")
	adicionar(dt.date(ano, 1, 20), "São Fabião e São Sebastião, mártires", "Memória", "Vermelho")
	adicionar(dt.date(ano, 1, 21), "Santa Inês, virgem e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 1, 22), "São Vicente, diácono e mártir", "Memória facultativa", "Vermelho")
	adicionar(dt.date(ano, 1, 24), "São Francisco de Sales", "Memória", "Branco")
	adicionar(dt.date(ano, 1, 25), "Conversão de São Paulo", "Festa", "Branco")
	adicionar(dt.date(ano, 1, 26), "São Timóteo e São Tito", "Memória", "Branco")
	adicionar(dt.date(ano, 1, 27), "Santa Ângela Merici, virgem", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 1, 28), "São Tomás de Aquino", "Memória", "Branco")
	adicionar(dt.date(ano, 1, 31), "São João Bosco", "Memória", "Branco")
	adicionar(dt.date(ano, 2, 3), "São Brás, bispo e mártir", "Memória facultativa", "Vermelho")
	adicionar(dt.date(ano, 2, 5), "Santa Águeda, virgem e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 2, 6), "São Paulo Miki e companheiros, mártires", "Memória", "Vermelho")
	adicionar(dt.date(ano, 2, 10), "Santa Escolástica, virgem", "Memória", "Branco")
	adicionar(dt.date(ano, 2, 11), "Nossa Senhora de Lourdes", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 2, 14), "São Cirilo e São Metódio", "Memória", "Branco")
	adicionar(dt.date(ano, 2, 22), "Cátedra de São Pedro", "Festa", "Branco")
	adicionar(datas["São José"], "São José, esposo da Virgem Maria", "Solenidade", "Branco")
	adicionar(dt.date(ano, 3, 7), "Santas Perpétua e Felicidade, mártires", "Memória", "Vermelho")
	adicionar(dt.date(ano, 3, 17), "São Patrício, bispo", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 3, 23), "São Turíbio de Mongrovejo, bispo", "Memória facultativa", "Branco")
	adicionar(datas["Anunciação do Senhor"], "Anunciação do Senhor", "Solenidade", "Branco")
	adicionar(dt.date(ano, 4, 11), "Santo Estanislau, bispo e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 4, 25), "São Marcos, evangelista", "Festa", "Vermelho")
	adicionar(dt.date(ano, 5, 1), "São José Operário", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 5, 13), "Nossa Senhora de Fátima", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 5, 3), "São Filipe e São Tiago, apóstolos", "Festa", "Vermelho")
	adicionar(dt.date(ano, 5, 14), "São Matias, apóstolo", "Festa", "Vermelho")
	adicionar(dt.date(ano, 5, 26), "São Filipe Néri, presbítero", "Memória", "Branco")
	adicionar(dt.date(ano, 5, 31), "Visitação da Bem-aventurada Virgem Maria", "Festa", "Branco")
	adicionar(dt.date(ano, 6, 3), "São Carlos Lwanga e companheiros, mártires", "Memória", "Vermelho")
	adicionar(dt.date(ano, 6, 5), "São Bonifácio, bispo e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 6, 9), "São José de Anchieta", "Memória", "Branco", "Celebração do calendário brasileiro.")
	adicionar(dt.date(ano, 6, 11), "São Barnabé, apóstolo", "Memória", "Vermelho")
	adicionar(dt.date(ano, 6, 13), "Santo Antônio de Pádua", "Memória", "Branco")
	adicionar(dt.date(ano, 6, 21), "São Luís Gonzaga, religioso", "Memória", "Branco")
	adicionar(dt.date(ano, 6, 22), "São Tomás More e São João Fisher, mártires", "Memória facultativa", "Vermelho")
	adicionar(dt.date(ano, 6, 24), "Natividade de São João Batista", "Solenidade", "Branco")
	adicionar(datas["São Pedro e São Paulo"], "São Pedro e São Paulo, apóstolos", "Solenidade", "Vermelho", "No Brasil, celebrada no domingo mais próximo de 29 de junho.")
	adicionar(dt.date(ano, 7, 3), "São Tomé, apóstolo", "Festa", "Vermelho")
	adicionar(dt.date(ano, 7, 11), "São Bento, abade", "Memória", "Branco")
	adicionar(dt.date(ano, 7, 15), "São Boaventura, bispo e doutor da Igreja", "Memória", "Branco")
	adicionar(dt.date(ano, 7, 16), "Nossa Senhora do Carmo", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 7, 22), "Santa Maria Madalena", "Festa", "Branco")
	adicionar(dt.date(ano, 7, 25), "São Tiago, apóstolo", "Festa", "Vermelho")
	adicionar(dt.date(ano, 7, 26), "São Joaquim e Santa Ana", "Memória", "Branco")
	adicionar(dt.date(ano, 7, 29), "Santa Marta, Santa Maria e São Lázaro", "Memória", "Branco")
	adicionar(dt.date(ano, 7, 31), "Santo Inácio de Loyola, presbítero", "Memória", "Branco")
	adicionar(dt.date(ano, 8, 1), "Santo Afonso Maria de Ligório", "Memória", "Branco")
	adicionar(dt.date(ano, 8, 4), "São João Maria Vianney", "Memória", "Branco")
	adicionar(dt.date(ano, 8, 6), "Transfiguração do Senhor", "Festa", "Branco")
	adicionar(dt.date(ano, 8, 8), "São Domingos, presbítero", "Memória", "Branco")
	adicionar(dt.date(ano, 8, 11), "Santa Clara, virgem", "Memória", "Branco")
	adicionar(dt.date(ano, 8, 14), "São Maximiliano Maria Kolbe, presbítero e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 8, 10), "São Lourenço, diácono e mártir", "Festa", "Vermelho")
	adicionar(datas["Assunção de Nossa Senhora"], "Assunção de Nossa Senhora", "Solenidade", "Branco", "No Brasil, celebrada no domingo mais próximo de 15 de agosto.")
	adicionar(dt.date(ano, 8, 22), "Nossa Senhora, Rainha", "Memória", "Branco")
	adicionar(dt.date(ano, 8, 29), "Martírio de São João Batista", "Memória", "Vermelho")
	adicionar(dt.date(ano, 9, 3), "São Gregório Magno, papa e doutor da Igreja", "Memória", "Branco")
	adicionar(dt.date(ano, 9, 5), "Santa Teresa de Calcutá", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 9, 8), "Natividade da Bem-aventurada Virgem Maria", "Festa", "Branco")
	adicionar(dt.date(ano, 9, 14), "Exaltação da Santa Cruz", "Festa", "Vermelho")
	adicionar(dt.date(ano, 9, 15), "Nossa Senhora das Dores", "Memória", "Branco")
	adicionar(dt.date(ano, 9, 21), "São Mateus, apóstolo e evangelista", "Festa", "Vermelho")
	adicionar(dt.date(ano, 9, 23), "São Pio de Pietrelcina, presbítero", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 9, 27), "São Vicente de Paulo, presbítero", "Memória", "Branco")
	adicionar(dt.date(ano, 9, 29), "São Miguel, São Gabriel e São Rafael, arcanjos", "Festa", "Branco")
	adicionar(dt.date(ano, 10, 1), "Santa Teresinha do Menino Jesus", "Memória", "Branco")
	adicionar(dt.date(ano, 10, 4), "São Francisco de Assis", "Memória", "Branco")
	adicionar(dt.date(ano, 10, 7), "Nossa Senhora do Rosário", "Memória", "Branco")
	adicionar(dt.date(ano, 10, 15), "Santa Teresa de Jesus, virgem e doutora da Igreja", "Memória", "Branco")
	adicionar(dt.date(ano, 10, 18), "São Lucas, evangelista", "Festa", "Vermelho")
	adicionar(dt.date(ano, 10, 28), "São Simão e São Judas Tadeu, apóstolos", "Festa", "Vermelho")
	adicionar(dt.date(ano, 10, 12), "Nossa Senhora da Conceição Aparecida, Padroeira do Brasil", "Solenidade", "Branco")
	adicionar(datas["Todos os Santos"], "Todos os Santos", "Solenidade", "Branco", "No Brasil, normalmente transferida para o domingo seguinte.")
	adicionar(dt.date(ano, 11, 2), "Comemoração de Todos os Fiéis Defuntos", "Comemoração", "Roxo")
	adicionar(dt.date(ano, 11, 3), "São Martinho de Lima", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 11, 4), "São Carlos Borromeu", "Memória", "Branco")
	adicionar(dt.date(ano, 11, 10), "São Leão Magno, papa e doutor da Igreja", "Memória", "Branco")
	adicionar(dt.date(ano, 11, 11), "São Martinho de Tours, bispo", "Memória", "Branco")
	adicionar(dt.date(ano, 11, 13), "Santa Francisca Xavier Cabrini", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 11, 17), "Santa Isabel da Hungria, religiosa", "Memória", "Branco")
	adicionar(dt.date(ano, 11, 22), "Santa Cecília, virgem e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 11, 23), "São Clemente I, papa e mártir", "Memória facultativa", "Vermelho")
	adicionar(dt.date(ano, 11, 24), "Santo André Dung-Lac e companheiros, mártires", "Memória", "Vermelho")
	adicionar(dt.date(ano, 11, 9), "Dedicação da Basílica de Latrão", "Festa", "Branco")
	adicionar(dt.date(ano, 11, 21), "Apresentação de Nossa Senhora", "Memória", "Branco")
	adicionar(dt.date(ano, 11, 30), "Santo André, apóstolo", "Festa", "Vermelho")
	adicionar(datas["Imaculada Conceição"], "Imaculada Conceição da Bem-aventurada Virgem Maria", "Solenidade", "Branco")
	adicionar(dt.date(ano, 12, 3), "São Francisco Xavier, presbítero", "Memória", "Branco")
	adicionar(dt.date(ano, 12, 6), "São Nicolau, bispo", "Memória facultativa", "Branco")
	adicionar(dt.date(ano, 12, 7), "Santo Ambrósio, bispo e doutor da Igreja", "Memória", "Branco")
	adicionar(dt.date(ano, 12, 12), "Nossa Senhora de Guadalupe", "Memória", "Branco")
	adicionar(dt.date(ano, 12, 13), "Santa Luzia, virgem e mártir", "Memória", "Vermelho")
	adicionar(dt.date(ano, 12, 14), "São João da Cruz, presbítero e doutor da Igreja", "Memória", "Branco")
	adicionar(dt.date(ano, 12, 25), "Natal de Nosso Senhor Jesus Cristo", "Solenidade", "Branco")
	adicionar(dt.date(ano, 12, 26), "Santo Estêvão, primeiro mártir", "Festa", "Vermelho")
	adicionar(dt.date(ano, 12, 27), "São João, apóstolo e evangelista", "Festa", "Branco")
	adicionar(dt.date(ano, 12, 28), "Santos Inocentes, mártires", "Festa", "Vermelho")

	adicionar(datas["Quarta-feira de Cinzas"], "Quarta-feira de Cinzas", "Dia litúrgico especial", "Roxo")
	adicionar(datas["Domingo de Ramos"], "Domingo de Ramos e da Paixão do Senhor", "Domingo", "Vermelho")
	adicionar(datas["Quinta-feira Santa"], "Quinta-feira da Ceia do Senhor", "Tríduo Pascal", "Branco")
	adicionar(datas["Sexta-feira Santa"], "Sexta-feira da Paixão do Senhor", "Tríduo Pascal", "Vermelho")
	adicionar(datas["Sábado Santo"], "Sábado Santo — Vigília Pascal à noite", "Tríduo Pascal", "Branco")
	adicionar(datas["Domingo de Páscoa"], "Domingo da Ressurreição do Senhor", "Solenidade", "Branco")
	adicionar(datas["Domingo da Divina Misericórdia"], "Domingo da Divina Misericórdia", "Domingo", "Branco")
	adicionar(datas["Ascensão do Senhor"], "Ascensão do Senhor", "Solenidade", "Branco", "No Brasil, celebrada no sétimo domingo da Páscoa.")
	adicionar(datas["Pentecostes"], "Pentecostes", "Solenidade", "Vermelho")
	adicionar(datas["Santíssima Trindade"], "Santíssima Trindade", "Solenidade", "Branco")
	adicionar(datas["Corpus Christi"], "Santíssimo Corpo e Sangue de Cristo — Corpus Christi", "Solenidade", "Branco")
	adicionar(datas["Sagrado Coração de Jesus"], "Sagrado Coração de Jesus", "Solenidade", "Branco")
	adicionar(datas["Imaculado Coração de Maria"], "Imaculado Coração de Maria", "Memória", "Branco")
	adicionar(datas["Domingo de Laetare"], "Quarto Domingo da Quaresma — Laetare", "Domingo", "Rosa")

	adicionar(datas["Solenidade de Cristo Rei"], "Nosso Senhor Jesus Cristo, Rei do Universo", "Solenidade", "Branco")
	adicionar(datas["Primeiro Domingo do Advento"], "Primeiro Domingo do Advento", "Domingo", "Roxo")
	adicionar(datas["Segundo Domingo do Advento"], "Segundo Domingo do Advento", "Domingo", "Roxo")
	adicionar(datas["Terceiro Domingo do Advento"], "Terceiro Domingo do Advento — Gaudete", "Domingo", "Rosa")
	adicionar(datas["Quarto Domingo do Advento"], "Quarto Domingo do Advento", "Domingo", "Roxo")
	adicionar(dt.date(ano, 12, 24), "Véspera de Natal", "Comemoração", "Roxo")

	for celebracoes in eventos.values():
		celebracoes.sort(key=lambda c: (ORDEM_GRAUS.get(c.grau, 9), c.nome))

	return eventos


def obter_cor_do_dia(data: dt.date) -> str:
	"""Cor do dia para a interface, considerando os destaques cadastrados."""
	eventos = obter_celebracoes_do_ano(data.year).get(data, [])
	if eventos:
		return eventos[0].cor
	return _cor_base_tempo(data)


def obter_cor_do_mes(ano: int, mes: int, hoje: dt.date) -> int:
	"""Usa a cor do dia atual no mês corrente e a cor predominante nos demais."""
	if (ano, mes) == (hoje.year, hoje.month):
		cor = _cor_base_tempo(hoje)
		return CORES_LITURGICAS.get(cor, CORES_LITURGICAS["Verde"])

	quantidade_dias = calendar.monthrange(ano, mes)[1]
	cores = Counter(
		_cor_base_tempo(dt.date(ano, mes, dia))
		for dia in range(1, quantidade_dias + 1)
	)
	cor_predominante = cores.most_common(1)[0][0]
	return CORES_LITURGICAS.get(cor_predominante, CORES_LITURGICAS["Verde"])

class CalendarioLiturgicoView(ui.LayoutView):
	def __init__(self, ano: int, mes: int, owner_id: int | None = None):
		super().__init__(timeout=15 * 60)
		self.ano = ano
		self.mes = mes
		self.owner_id = owner_id

		hoje = dt.datetime.now(FUSO_HORARIO).date()
		eventos = obter_celebracoes_do_ano(ano)
		eventos_do_mes = sorted(
			[
				(data, celebracao)
				for data, celebracoes in eventos.items()
				if data.year == ano and data.month == mes
				for celebracao in celebracoes
			],
			key=lambda item: (item[0], ORDEM_GRAUS.get(item[1].grau, 9), item[1].nome),
		)
		dias_com_evento = {data.day for data, _ in eventos_do_mes}

		linhas = [" ".join(DIAS_SEMANA)]
		calendario_mes = calendar.Calendar(firstweekday=6)
		for semana in calendario_mes.monthdayscalendar(ano, mes):
			celulas: list[str] = []
			for dia in semana:
				if not dia:
					celulas.append("   ")
					continue
				marcador = "*" if dia in dias_com_evento else " "
				if (ano, mes, dia) == (hoje.year, hoje.month, hoje.day):
					marcador = ">"
				celulas.append(f"{dia:02d}{marcador}")
			linhas.append(" ".join(celulas))

		datas_mes = [
			dt.date(ano, mes, dia)
			for dia in range(1, calendar.monthrange(ano, mes)[1] + 1)
		]
		tempos = list(dict.fromkeys(obter_tempo_liturgico(data) for data in datas_mes))
		ciclos = list(dict.fromkeys(obter_ciclo_dominical(data) for data in datas_mes))
		ciclos_feriais = list(dict.fromkeys(obter_ciclo_ferial(data) for data in datas_mes))

		eventos_por_data: dict[dt.date, list[CelebracaoLiturgica]] = {}
		for data, celebracao in eventos_do_mes:
			eventos_por_data.setdefault(data, []).append(celebracao)

		if eventos_do_mes:
			linhas_eventos = []
			for data, celebracoes in eventos_por_data.items():
				for celebracao in celebracoes:
					observacao = f" — {celebracao.observacao}" if celebracao.observacao else ""
					linhas_eventos.append(
						f"- **{data:%d/%m}** · **{celebracao.grau}** · "
						f"{celebracao.nome} _(cor: {celebracao.cor})_{observacao}"
					)
			lista_eventos = "\n".join(linhas_eventos)
		else:
			lista_eventos = "Nenhuma celebração de destaque cadastrada neste mês."

		nome_mes = MESES[mes - 1].capitalize()
		titulo = f"Calendário Litúrgico — {nome_mes} de {ano}"
		texto_hoje = f"**Hoje:** {hoje:%d/%m/%Y}"
		if hoje.year == ano and hoje.month == mes:
			celebracoes_hoje = eventos.get(hoje, [])
			tempo_hoje = obter_tempo_liturgico(hoje)
			detalhe_hoje = f" · {tempo_hoje}"
			if celebracoes_hoje:
				detalhe_hoje += f" · {celebracoes_hoje[0].nome}"
			texto_hoje += detalhe_hoje

		conteudo = (
			f"## {titulo}\n"
			f"{texto_hoje}\n\n"
			f"**Tempos litúrgicos:** {' → '.join(tempos)}\n"
			f"**Ciclo dominical:** {' → '.join(ciclos)} · "
			f"**Ciclo ferial:** {' → '.join(ciclos_feriais)}\n\n"
			f"```text\n{chr(10).join(linhas)}\n```\n"
			"`*` Celebração cadastrada · `>` Dia de hoje.\n\n"
			f"### Celebrações em destaque\n{lista_eventos}"
		)

		anterior = CalendarioMesButton(self, -1, "◀")
		hoje_button = CalendarioMesButton(self, 0, "Hoje")
		proximo = CalendarioMesButton(self, 1, "▶")
		anterior.disabled = ano == 1 and mes == 1
		hoje_button.disabled = (ano, mes) == (hoje.year, hoje.month)
		proximo.disabled = ano == 9999 and mes == 12

		cor = obter_cor_do_mes(ano, mes, hoje)
		self.add_item(
			ui.Container(
				ui.TextDisplay(conteudo),
				ui.Separator(spacing=discord.SeparatorSpacing.small),
				ui.ActionRow(anterior, hoje_button, proximo),
				accent_color=cor,
			)
		)

	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		if self.owner_id is None or interaction.user.id == self.owner_id:
			return True
		await interaction.response.send_message(
			"Este calendário pertence a quem executou o comando.",
			ephemeral=True,
		)
		return False

	async def navegar(self, interaction: discord.Interaction, direcao: int) -> None:
		hoje = dt.datetime.now(FUSO_HORARIO).date()

		if direcao == 0:
			ano, mes = hoje.year, hoje.month
		else:
			mes = self.mes + direcao
			ano = self.ano
			if mes == 0:
				mes = 12
				ano -= 1
			elif mes == 13:
				mes = 1
				ano += 1

		nova_view = CalendarioLiturgicoView(ano, mes, self.owner_id)
		await interaction.response.edit_message(view=nova_view)


class CalendarioMesButton(ui.Button):
	def __init__(
		self,
		calendario_view: CalendarioLiturgicoView,
		direcao: int,
		label: str,
	):
		super().__init__(
			label=label,
			style=discord.ButtonStyle.primary if direcao == 0 else discord.ButtonStyle.secondary,
			disabled=False,
		)
		self.calendario_view = calendario_view
		self.direcao = direcao

	async def callback(self, interaction: discord.Interaction) -> None:
		await self.calendario_view.navegar(interaction, self.direcao)


class LiturgiaCog(commands.Cog):
	liturgia_gp = app_commands.Group(
		name="liturgia",
		description="Comandos relacionados à liturgia diária.",
	)
	config_bp = app_commands.Group(
		name="config",
		description="Configurações da publicação da liturgia diária.",
		parent=liturgia_gp,
	)

	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.session: aiohttp.ClientSession | None = None
		self._ultimo_log: tuple[str, dt.date] | None = None

		if not getattr(bot, "debug", False):
			self.envio_liturgia.start()

	def _obter_session(self) -> aiohttp.ClientSession:
		if self.session is None or self.session.closed:
			contexto_ssl = ssl.create_default_context(cafile=certifi.where())
			timeout = aiohttp.ClientTimeout(total=30, connect=10)
			self.session = aiohttp.ClientSession(
				connector=aiohttp.TCPConnector(ssl=contexto_ssl),
				timeout=timeout,
			)
		return self.session

	async def _logar_uma_vez(self, chave: str, mensagem: str) -> None:
		hoje = dt.datetime.now(FUSO_HORARIO).date()
		identificador = (chave, hoje)
		if self._ultimo_log == identificador:
			return
		self._ultimo_log = identificador
		await self.bot.send_to_console(mensagem)

	def atualizar_config(
		self,
		*,
		hora: str | None = None,
		webhook_url: str | None = None,
		cargo_ping: discord.Role | None = None,
		canal: discord.TextChannel | None = None,
	) -> None:
		config = self.bot.config
		config_liturgia = config.setdefault("liturgia", {})

		if hora is not None:
			config_liturgia["hora"] = hora
		if cargo_ping is not None:
			config_liturgia["ping"] = cargo_ping.id
		if canal is not None:
			config_liturgia["canal"] = canal.id
		if webhook_url is not None:
			urls = config.setdefault("urls", {})
			webhooks = urls.setdefault("webhooks", {})
			webhooks["Liturgia Diária"] = webhook_url

		config["liturgia"] = config_liturgia
		save_config(config)

	@staticmethod
	def _validar_webhook(url: str) -> bool:
		try:
			partes = urlsplit(url.strip())
			caminho = partes.path.strip("/").split("/")
			return (
				partes.scheme == "https"
				and partes.hostname in {"discord.com", "discordapp.com"}
				and len(caminho) == 4
				and caminho[0] == "api"
				and caminho[1] == "webhooks"
				and caminho[2].isdigit()
				and bool(caminho[3])
			)
		except (TypeError, ValueError):
			return False

	@staticmethod
	def _id_webhook(url: str) -> int | None:
		try:
			caminho = urlsplit(url).path.strip("/").split("/")
			if len(caminho) == 4 and caminho[:2] == ["api", "webhooks"]:
				return int(caminho[2])
		except (TypeError, ValueError):
			pass
		return None

	async def _buscar_canal(self, canal_id: int) -> discord.TextChannel | None:
		canal = self.bot.get_channel(canal_id)
		if canal is None:
			try:
				canal = await self.bot.fetch_channel(canal_id)
			except (discord.NotFound, discord.Forbidden, discord.HTTPException):
				return None
		return canal if isinstance(canal, discord.TextChannel) else None

	async def _ja_enviou_hoje(
		self,
		canal: discord.TextChannel,
		webhook_id: int,
		hoje: dt.date,
	) -> bool:
		inicio_local = dt.datetime.combine(hoje, dt.time.min, tzinfo=FUSO_HORARIO)
		inicio_utc = inicio_local.astimezone(dt.timezone.utc)
		async for mensagem in canal.history(limit=100, after=inicio_utc):
			if (
				mensagem.webhook_id == webhook_id
				and mensagem.created_at.astimezone(FUSO_HORARIO).date() == hoje
			):
				return True
		return False

	@liturgia_gp.command(
		name="calendario",
		description="Consultar o calendário litúrgico de um mês e ano.",
	)
	@app_commands.describe(
		ano="Ano desejado (padrão: ano atual)",
		mes="Mês desejado (padrão: mês atual ou janeiro, se informar outro ano)",
	)
	async def calendario(
		self,
		interaction: discord.Interaction,
		ano: app_commands.Range[int, 1, 9999] | None = None,
		mes: app_commands.Range[int, 1, 12] | None = None,
	) -> None:
		hoje = dt.datetime.now(FUSO_HORARIO).date()
		ano_calendario = ano if ano is not None else hoje.year
		mes_calendario = mes if mes is not None else (hoje.month if ano is None else 1)

		await interaction.response.send_message(
			view=CalendarioLiturgicoView(
				ano_calendario,
				mes_calendario,
				owner_id=interaction.user.id,
			)
		)

	@config_bp.command(name="hora", description="Definir o horário de envio da liturgia diária.")
	@permissao(gerenciar_comunidade=True)
	@app_commands.describe(hora="Horário no formato HH:MM, usando o fuso de Brasília")
	async def hora_config(self, interaction: discord.Interaction, hora: str) -> None:
		if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", hora):
			await interaction.response.send_message(
				"Horário inválido. Use **HH:MM**, por exemplo `08:30`.",
				ephemeral=True,
			)
			return

		self.atualizar_config(hora=hora)
		await interaction.response.send_message(
			f"Horário de envio alterado para **{hora}** (horário de Brasília).",
			ephemeral=True,
		)

	@config_bp.command(name="canal", description="Definir o canal de publicação da liturgia diária.")
	@permissao(gerenciar_comunidade=True)
	@app_commands.describe(canal="Canal de texto que receberá a liturgia diária")
	async def canal_config(
		self,
		interaction: discord.Interaction,
		canal: discord.TextChannel,
	) -> None:
		self.atualizar_config(canal=canal)
		await interaction.response.send_message(
			f"Canal da liturgia diária definido para {canal.mention}.",
			ephemeral=True,
		)

	@config_bp.command(name="webhook", description="Definir o webhook de publicação da liturgia diária.")
	@permissao(gerenciar_comunidade=True)
	@app_commands.describe(webhook_url="URL completa do webhook do Discord")
	async def webhook_config(self, interaction: discord.Interaction, webhook_url: str) -> None:
		webhook_url = webhook_url.strip()
		if not self._validar_webhook(webhook_url):
			await interaction.response.send_message(
				"URL inválida. Informe um webhook HTTPS do Discord no formato "
				"`https://discord.com/api/webhooks/ID/TOKEN`.",
				ephemeral=True,
			)
			return

		self.atualizar_config(webhook_url=webhook_url)
		await interaction.response.send_message(
			"Webhook da liturgia diária atualizado. A URL foi armazenada sem ser exibida na resposta.",
			ephemeral=True,
		)

	@config_bp.command(name="ping", description="Definir o cargo marcado na liturgia diária.")
	@permissao(gerenciar_comunidade=True)
	@app_commands.describe(ping="Cargo que será mencionado na publicação")
	async def ping_config(self, interaction: discord.Interaction, ping: discord.Role) -> None:
		self.atualizar_config(cargo_ping=ping)
		await interaction.response.send_message(
			f"Cargo de marcação definido para {ping.mention}.",
			ephemeral=True,
			allowed_mentions=discord.AllowedMentions.none(),
		)

	@config_bp.command(name="status", description="Consultar a configuração da liturgia diária.")
	@permissao(gerenciar_comunidade=True)
	async def status_config(self, interaction: discord.Interaction) -> None:
		config = self.bot.config
		liturgia = config.get("liturgia", {})
		urls = config.get("urls", {}).get("webhooks", {})
		webhook = os.getenv("LITURGIADIARIA") or urls.get("Liturgia Diária")

		canal_id = liturgia.get("canal")
		canal = None
		if canal_id:
			try:
				canal = await self._buscar_canal(int(canal_id))
			except (TypeError, ValueError):
				canal = None
		cargo_id = liturgia.get("ping")
		try:
			cargo = interaction.guild.get_role(int(cargo_id)) if interaction.guild and cargo_id else None
		except (TypeError, ValueError):
			cargo = None

		linhas = [
			f"**Horário:** `{liturgia.get('hora', 'não configurado')}`",
			f"**Canal:** {canal.mention if isinstance(canal, discord.TextChannel) else 'não configurado ou inacessível'}",
			f"**Cargo:** {cargo.mention if cargo else 'não configurado ou inacessível'}",
			f"**Webhook:** {'configurado' if webhook and self._validar_webhook(webhook) else 'não configurado ou inválido'}",
			f"**Tarefa automática:** {'ativa' if self.envio_liturgia.is_running() else 'inativa'}",
		]
		await interaction.response.send_message("\n".join(linhas), ephemeral=True)

	@tasks.loop(minutes=1)
	async def envio_liturgia(self) -> None:
		config = self.bot.config
		config_liturgia = config.get("liturgia", {})
		agora = dt.datetime.now(FUSO_HORARIO)
		hoje = agora.date()

		hora_texto = config_liturgia.get("hora", "07:00")
		try:
			hora_config = dt.time.fromisoformat(hora_texto)
		except (TypeError, ValueError):
			await self._logar_uma_vez(
				"hora_invalida",
				f"Horário inválido na configuração da liturgia: {hora_texto!r}.",
			)
			return

		if agora.time().replace(tzinfo=None) < hora_config:
			return

		canal_id = config_liturgia.get("canal")
		if not canal_id:
			await self._logar_uma_vez(
				"canal_ausente",
				"A publicação da liturgia está ativa, mas nenhum canal foi configurado.",
			)
			return

		canal = await self._buscar_canal(int(canal_id))
		if canal is None:
			await self._logar_uma_vez(
				"canal_invalido",
				f"O canal configurado para a liturgia ({canal_id}) não existe, não está acessível ou não é um canal de texto.",
			)
			return

		urls = config.get("urls", {}).get("webhooks", {})
		webhook_url = (os.getenv("LITURGIADIARIA") or urls.get("Liturgia Diária") or "").strip()
		if not self._validar_webhook(webhook_url):
			await self._logar_uma_vez(
				"webhook_ausente",
				"Não há um webhook válido configurado para a liturgia diária.",
			)
			return

		webhook_id = self._id_webhook(webhook_url)
		if webhook_id is None:
			return

		try:
			if await self._ja_enviou_hoje(canal, webhook_id, hoje):
				return

			url_liturgia = config.get("urls", {}).get("requests", {}).get("liturgia")
			if not url_liturgia:
				await self._logar_uma_vez(
					"endpoint_ausente",
					"O endereço da API da liturgia não está configurado em urls.requests.liturgia.",
				)
				return

			cargo_id = config_liturgia.get("ping")
			mencao = f"<@&{cargo_id}>" if cargo_id else ""
			views = await self.generate_liturgy_view(url=url_liturgia, content=mencao)

			webhook = discord.Webhook.from_url(webhook_url, session=self._obter_session())
			allowed_mentions = discord.AllowedMentions(
				everyone=False,
				users=False,
				roles=bool(cargo_id),
				replied_user=False,
			)

			for view in views:
				await webhook.send(
					view=view,
					allowed_mentions=allowed_mentions,
					wait=True,
				)

			self._ultimo_log = None
		except Exception as erro:
			traceback.print_exc()
			await self._logar_uma_vez(
				"erro_envio",
				f"Falha ao publicar a liturgia diária: {type(erro).__name__}: {erro}",
			)

	@envio_liturgia.before_loop
	async def before_envio(self) -> None:
		await self.bot.wait_until_ready()

	async def cog_unload(self) -> None:
		if self.envio_liturgia.is_running():
			self.envio_liturgia.cancel()
		if self.session is not None and not self.session.closed:
			await self.session.close()

	async def _get_json(self, url: str) -> dict[str, Any]:
		session = self._obter_session()
		async with session.get(url) as resposta:
			resposta.raise_for_status()
			dados = await resposta.json(content_type=None)
		if not isinstance(dados, dict):
			raise ValueError("A API da liturgia retornou um formato inesperado.")
		return dados

	@staticmethod
	def _url_legada(url: str) -> str | None:
		partes = urlsplit(url)
		caminho = partes.path.rstrip("/")
		if not caminho.endswith("/v3"):
			return None
		caminho = caminho[:-3] or "/"
		return partes._replace(path=caminho).geturl()

	async def get_liturgy(self, url: str) -> dict[str, Any]:
		"""Busca a API atual e usa o endpoint legado somente quando necessário."""
		dados: dict[str, Any]
		try:
			dados = await self._get_json(url)
		except (aiohttp.ClientError, TimeoutError, ValueError) as erro_atual:
			url_legada = self._url_legada(url)
			if not url_legada or url_legada == url:
				raise RuntimeError(f"Não foi possível consultar a API da liturgia: {erro_atual}") from erro_atual
			try:
				dados = await self._get_json(url_legada)
			except (aiohttp.ClientError, TimeoutError, ValueError) as erro_legado:
				raise RuntimeError(
					f"Falha na API atual ({erro_atual}) e também no endpoint legado ({erro_legado})."
				) from erro_legado

		celebracoes = dados.get("celebracoes", [])
		if celebracoes:
			celebracao = next(
				(item for item in celebracoes if item.get("principal")),
				celebracoes[0],
			)
			return {
				"titulo": celebracao.get("liturgia", ""),
				"cor": celebracao.get("cor", "Verde"),
				"leituras": celebracao.get("leituras", []),
				"oracoes": celebracao.get("oracoes", {}),
				"antifonas": celebracao.get("antifonas", {}),
			}

		if not any(dados.get(chave) for chave in ("primeiraLeitura", "evangelho", "salmo")):
			url_legada = self._url_legada(url)
			if url_legada and url_legada != url:
				dados = await self._get_json(url_legada)

		leituras: list[dict[str, Any]] = []

		def adicionar_leitura(rotulo: str, leitura: Any) -> None:
			if not isinstance(leitura, dict):
				return
			leituras.append({
				"rotulo": rotulo,
				"opcoes": [{
					"referencia": leitura.get("referencia", "") or "",
					"titulo": leitura.get("titulo", rotulo) or rotulo,
					"texto": leitura.get("texto", "") or "",
				}],
			})

		adicionar_leitura("Primeira Leitura", dados.get("primeiraLeitura"))

		salmo = dados.get("salmo")
		if isinstance(salmo, dict):
			texto_salmo = "\n\n".join(
				parte for parte in (salmo.get("refrao", ""), salmo.get("texto", "")) if parte
			)
			leituras.append({
				"rotulo": "Salmo",
				"opcoes": [{
					"referencia": salmo.get("referencia", "") or "",
					"titulo": "Salmo Responsorial",
					"texto": texto_salmo,
				}],
			})

		adicionar_leitura("Segunda Leitura", dados.get("segundaLeitura"))
		adicionar_leitura("Evangelho", dados.get("evangelho"))

		return {
			"titulo": dados.get("liturgia", "") or "",
			"cor": dados.get("cor", "Verde") or "Verde",
			"leituras": leituras,
			"oracoes": {
				"coleta": dados.get("coleta", "") or dados.get("dia", "") or "",
				"oferendas": dados.get("oferendas", "") or "",
				"comunhao": dados.get("comunhao", "") or "",
			},
			"antifonas": dados.get("antifonas", {}) or {},
		}

	@staticmethod
	def _formatar_dados_auxiliares(dados: Any) -> str:
		"""Converte orações/antífonas em texto legível sem presumir a estrutura da API."""
		linhas: list[str] = []

		def percorrer(valor: Any, rotulo: str = "") -> None:
			if valor is None or valor == "":
				return
			if isinstance(valor, str):
				texto = valor.strip()
				if texto:
					linhas.append(f"**{rotulo}:** {texto}" if rotulo else texto)
			elif isinstance(valor, dict):
				for chave, conteudo in valor.items():
					nome = str(chave).replace("_", " ").strip().capitalize()
					percorrer(conteudo, nome)
			elif isinstance(valor, (list, tuple)):
				for item in valor:
					percorrer(item, rotulo)
			else:
				texto = str(valor).strip()
				if texto:
					linhas.append(f"**{rotulo}:** {texto}" if rotulo else texto)

		percorrer(dados)
		return "\n\n".join(linhas)

	@staticmethod
	def _dividir_texto(texto: str, limite: int) -> list[str]:
		partes: list[str] = []
		restante = texto.strip()
		while restante:
			if len(restante) <= limite:
				partes.append(restante)
				break

			corte = restante.rfind("\n", 0, limite)
			if corte < limite // 2:
				corte = restante.rfind(" ", 0, limite)
			if corte < limite // 2:
				corte = limite

			partes.append(restante[:corte].rstrip())
			restante = restante[corte:].lstrip()
		return partes

	async def generate_liturgy_view(self, url: str, content: str) -> list[ui.LayoutView]:
		liturgia = await self.get_liturgy(url)
		secoes: list[tuple[str, str]] = []

		titulo_liturgia = str(liturgia.get("titulo", "")).strip()
		if titulo_liturgia:
			secoes.append(("Liturgia do dia", titulo_liturgia))

		for leitura in liturgia.get("leituras") or []:
			if not isinstance(leitura, dict):
				continue
			rotulo = leitura.get("rotulo", "Leitura")
			opcoes = leitura.get("opcoes", [])
			if not opcoes:
				continue

			opcao = opcoes[0]
			if not isinstance(opcao, dict):
				continue

			referencia = str(opcao.get("referencia", "") or "").strip()
			titulo = str(opcao.get("titulo", rotulo) or rotulo).strip()
			texto = str(opcao.get("texto", "") or "").strip()
			titulo_secao = f"{titulo} — {referencia}" if referencia else titulo

			texto_final = texto
			if referencia:
				try:
					versiculos_info = expand_bible_verse(
						referencia.replace(", ", ",").replace(". ", ".")
					)
					if versiculos_info:
						versiculos: list[str] = []
						for versiculo in versiculos_info:
							trecho = versiculo.get("texto", [])
							if isinstance(trecho, str):
								versiculos.append(trecho)
							elif isinstance(trecho, (list, tuple)):
								versiculos.extend(str(item) for item in trecho)
						if versiculos:
							texto_final = "\n".join(versiculos)
				except Exception:
					traceback.print_exc()

			if texto_final:
				secoes.append((titulo_secao, texto_final))

		oracoes = self._formatar_dados_auxiliares(liturgia.get("oracoes", {}))
		if oracoes:
			secoes.append(("Orações", oracoes))

		antifonas = self._formatar_dados_auxiliares(liturgia.get("antifonas", {}))
		if antifonas:
			secoes.append(("Antífonas", antifonas))

		if not secoes:
			secoes.append((
				"Liturgia diária",
				"A API não retornou leituras, orações ou antífonas para esta data.",
			))

		limite_pagina = 3600
		paginas: list[str] = []
		pagina_atual = ""

		for titulo, corpo in secoes:
			bloco = f"## {titulo}\n\n{corpo}".strip()
			partes = self._dividir_texto(bloco, limite_pagina)
			for parte in partes:
				candidato = f"{pagina_atual}\n\n{parte}".strip() if pagina_atual else parte
				if len(candidato) > limite_pagina:
					if pagina_atual:
						paginas.append(pagina_atual)
					pagina_atual = parte
				else:
					pagina_atual = candidato

		if content:
			mencao = content.strip()
			candidato = f"{pagina_atual}\n\n{mencao}".strip() if pagina_atual else mencao
			if len(candidato) <= limite_pagina:
				pagina_atual = candidato
			else:
				if pagina_atual:
					paginas.append(pagina_atual)
				paginas.extend(self._dividir_texto(mencao, limite_pagina))

		if pagina_atual:
			paginas.append(pagina_atual)

		cor = self._cor_api_para_hex(liturgia.get("cor", "Verde"))
		views: list[ui.LayoutView] = []
		for pagina in paginas:
			view = ui.LayoutView(timeout=None)
			view.add_item(
				ui.Container(
					ui.TextDisplay(pagina),
					accent_color=cor,
				)
			)
			views.append(view)

		return views

	@staticmethod
	def _cor_api_para_hex(cor: str) -> int:
		nome = str(cor or "Verde").strip().casefold()
		equivalencias = {
			"verde": "Verde",
			"branco": "Branco",
			"vermelho": "Vermelho",
			"roxo": "Roxo",
			"violeta": "Roxo",
			"rosa": "Rosa",
			"róseo": "Rosa",
			"rose": "Rosa",
			"azul": "Azul",
			"amarelo": "Dourado",
			"dourado": "Dourado",
			"preto": "Preto",
		}
		return CORES_LITURGICAS.get(equivalencias.get(nome, "Verde"), CORES_LITURGICAS["Verde"])


async def setup(bot: Bot) -> None:
	await bot.add_cog(LiturgiaCog(bot))
