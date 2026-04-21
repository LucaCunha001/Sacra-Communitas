# Repositório do bot Sancte Michael Archangele

Fiz esse bot para ajudar na organização do servidor [Sacra Communitas](https://discord.gg/NJMTbNukrk).

## Linguagens usadas:
| Programação | Banco de dados | Palavrões e bibliotecas |
| ----------- | -------------- | --------- |
| Python (.py) | JSON (.json) | Texto (.txt)

## Códigos de auxílio (`utils/`)

Cada código dentro da pasta `utils/` serve para auxiliar os funcionamentos dos cogs ou do código principal.

### catecismo.py:
- Estrai as informações do Catecismo da Igreja Católica direto do site do Vaticano.
### console.py:
- Pequenas funções para ajudar nas atualizações do Python e adaptar comandos de Windows e Linux.
### data.py:
- Gerencia o banco de dados do bot e criar as TypedDicts para o Pylance.
### embed.py (obsoleto):
- Automatiza alguns recursos de embed.
### errors.py:
- Gerencia o log de erros.
### logs.py:
- Envia os registros de auditória em canais específicos.
### permissoes.py:
- Ajuda a definir permissões além daquelas dadas pelo Discord.
### recursos.py:
- Funções e classes auxiliares para:
  - Extrair versículos bíblicos de citações (Ex: "1Ts 2,15");
  - Traduzir tickets;
  - Gerenciar a classe do bot.