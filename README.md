# Sacra Communitas Bot

Este projeto é um bot para Discord criado para ajudar na organização da comunidade **Sacra Communitas**.

## Visão geral

- Bot em Python usando `discord.py`.
- Configuração central em `data/config.json`.
- Dados estruturados em JSON para Bíblia, embeds, canones e membros.
- Logs de auditoria via canais do Discord e registros locais em `logs/bot.log`.

## Instalação

1. Crie um ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Instale as dependências:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Configure a variável de ambiente do token no arquivo `.env`:

```text
TOKEN=seu_token_aqui
BOT_DEBUG=true
LOG_LEVEL=INFO
```

4. Execute o bot:

```powershell
python bot.py
```

## Estrutura do projeto

- `bot.py`: ponto de entrada do bot.
- `cogs/`: extensões do Discord agrupadas por funcionalidades.
- `data/`: arquivos JSON com configurações, textos bíblicos, embeds e listas de palavrões.
- `utils/`: módulos auxiliares de suporte.
- `.env`: variáveis de ambiente sensíveis.
- `logs/`: histórico de execução gerado automaticamente.
- `database.db`: armazenagem local de membros e warns.

## Arquivos principais em `utils/`

- `logger.py`: configura logging para console e arquivo.
- `console.py`: utilitários para terminal e dependências.
- `data.py`: gerencia leitura e escrita de JSON e inicialização de banco SQLite.
- `errors.py`: captura exceções e envia relatórios de erro.
- `logs.py`: formata e publica logs de auditoria no Discord.
- `recursos.py`: contém o bot principal, comandos auxiliares e a lógica de cogs.

## Configuração

- `data/config.json` deve conter IDs de canais, cargos, URLs e logs.
- O bot carrega automaticamente todas as extensões em `cogs/`.
- Use `BOT_DEBUG=true` para forçar modo de manutenção.
- `LOG_LEVEL` controla o nível de log no console (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

## Melhoria aplicada

- Entry point mais seguro e apropriado para produção.
- Logging unificado em arquivo e console.
- Tratamento de exceções melhorado e relatórios úteis.
- Carregamento de cogs robusto com feedback em logs.
- README atualizado com instruções de setup e execução.
- `.gitignore` atualizado para ignorar ambiente virtual, logs e bancos de dados locais.

## Notas

- Não deixe o token exposto em `README` ou no controle de versão.
- O banco local `database.db` deve ser mantido fora do repositório quando possível.
- Para adicionar recursos, crie um novo cog em `cogs/` e reinicie o bot.
