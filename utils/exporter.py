"""Exportador de mensagens do Discord para o template HTML da Sacra Communitas.

O módulo foi escrito para funcionar com objetos do discord.py sem exigir um
import de discord.py. Isso também permite testar a serialização com objetos
simulados.

Compatibilidade esperada: discord.py 2.6 ou superior para tags de servidor.
As demais partes usam os atributos públicos usuais de Message, Member, User,
Role, Attachment, Embed e componentes.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = Path(__file__).with_name("messages.html")
_UPDATED_TEMPLATE_PATH = Path(__file__).with_name("messages_sacra.html")

_DATA_BLOCKS = {
    "export-info-data": "export_info",
    "users-data": "users",
    "messages-data": "messages",
}

_MENTION_PATTERN = re.compile(r"<@!?(\d+)>|<@&(\d+)>|<#(\d+)>")
_HEX_COLOR_PATTERN = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def _get(value: Any, key: str, default: Any = None) -> Any:
    """Obtém uma chave de dict ou atributo de objeto sem lançar AttributeError."""
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _asset_url(value: Any) -> str:
    """Retorna a URL de um discord.Asset ou uma URL já serializada."""
    if value is None:
        return ""

    url = _get(value, "url")
    if url:
        return str(url)

    if isinstance(value, str) and _URL_PATTERN.match(value):
        return value

    return ""


def _color_hex(value: Any) -> str:
    """Converte discord.Colour, inteiro RGB ou string hexadecimal para #RRGGBB."""
    if value is None:
        return ""

    color_value = _get(value, "value", value)

    if isinstance(color_value, bool):
        return ""

    if isinstance(color_value, int):
        if not 0 <= color_value <= 0xFFFFFF or color_value == 0:
            return ""
        return f"#{color_value:06x}"

    if isinstance(color_value, str) and _HEX_COLOR_PATTERN.fullmatch(color_value):
        hexadecimal = color_value.removeprefix("#")
        if len(hexadecimal) == 3:
            hexadecimal = "".join(character * 2 for character in hexadecimal)
        if int(hexadecimal, 16) == 0:
            return ""
        return f"#{hexadecimal.lower()}"

    return ""


def _as_json_value(value: Any) -> Any:
    """Converte recursivamente valores comuns e objetos com to_dict() para JSON."""
    if value is None or isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return _as_json_value(value.value)

    if isinstance(value, Mapping):
        return {str(key): _as_json_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set, frozenset)):
        return [_as_json_value(item) for item in value]

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _as_json_value(to_dict())

    raise TypeError(
        f"Valor não serializável na exportação: {type(value).__name__}"
    )


def _serialize_component(component: Any) -> dict[str, Any]:
    """Serializa componentes de mensagens, incluindo estruturas aninhadas."""
    if isinstance(component, Mapping):
        return _as_json_value(component)

    to_component_dict = getattr(component, "to_component_dict", None)
    if callable(to_component_dict):
        return _as_json_value(to_component_dict())

    to_dict = getattr(component, "to_dict", None)
    if callable(to_dict):
        return _as_json_value(to_dict())

    fields = (
        "type",
        "label",
        "style",
        "url",
        "disabled",
        "placeholder",
        "options",
        "emoji",
        "content",
        "text",
        "description",
        "accent_color",
        "accent_colour",
        "spoiler",
        "id",
        "media",
        "items",
        "filename",
        "children",
        "components",
        "rows",
        "accessory",
    )

    serialized: dict[str, Any] = {}
    for field in fields:
        value = getattr(component, field, None)
        if value is None:
            continue

        key = "accentColor" if field in ("accent_color", "accent_colour") else field

        if key == "items" and isinstance(value, (list, tuple)):
            serialized[key] = [
                _as_json_value(item.to_dict())
                if callable(getattr(item, "to_dict", None))
                else _as_json_value(item)
                for item in value
            ]
        elif key in ("children", "components", "rows") and isinstance(
            value, (list, tuple)
        ):
            serialized[key] = [_serialize_component(item) for item in value]
        else:
            serialized[key] = _as_json_value(value)

    if not serialized:
        raise TypeError(
            f"Componente não serializável na exportação: {type(component).__name__}"
        )

    return serialized


def _display_icon_data(member: Any, role: Any) -> tuple[str, str]:
    """Obtém o ícone realmente exibido para o membro: imagem ou emoji Unicode."""
    display_icon = _get(member, "display_icon")
    if display_icon is None:
        display_icon = _get(role, "display_icon")
    if display_icon is None:
        display_icon = _get(role, "icon")

    icon_url = _asset_url(display_icon)
    if icon_url:
        return icon_url, ""

    if isinstance(display_icon, str) and display_icon and not _URL_PATTERN.match(
        display_icon
    ):
        return "", display_icon

    unicode_emoji = _get(role, "unicode_emoji")
    if isinstance(unicode_emoji, str) and unicode_emoji:
        return "", unicode_emoji

    return "", ""


def _serialize_role(member: Any) -> dict[str, Any] | None:
    """Serializa o cargo usado para representar a cor/nome do membro."""
    role = _get(member, "top_role")
    role_name = _get(role, "name") if role is not None else None

    if role is None or role_name in (None, "", "@everyone"):
        return None

    role_color = _color_hex(_get(role, "color"))
    member_color = _color_hex(_get(member, "color"))

    serialized: dict[str, Any] = {
        "name": str(role_name),
        "color": member_color or role_color,
    }

    role_id = _get(role, "id")
    if role_id is not None:
        serialized["id"] = str(role_id)

    icon_url, icon_emoji = _display_icon_data(member, role)
    if icon_url:
        serialized["iconUrl"] = icon_url
    if icon_emoji:
        serialized["iconEmoji"] = icon_emoji

    primary = role_color or member_color
    secondary = _color_hex(_get(role, "secondary_color")) or _color_hex(
        _get(role, "secondary_colour")
    )
    tertiary = _color_hex(_get(role, "tertiary_color")) or _color_hex(
        _get(role, "tertiary_colour")
    )

    if primary and secondary:
        serialized["gradient"] = [primary, secondary]
    elif primary and tertiary:
        serialized["gradient"] = [primary, tertiary]

    return serialized


def _serialize_server_tag(user: Any) -> dict[str, str] | None:
    """Serializa a tag principal do perfil usando o Asset oficial do discord.py.

    PrimaryGuild.badge já fornece um Asset com a URL correta. Isso evita montar
    manualmente uma rota CDN incorreta ou depender de um atributo inexistente,
    como identity_guild_id.
    """
    primary_guild = _get(user, "primary_guild")
    if primary_guild is None:
        return None

    if _get(primary_guild, "identity_enabled") is False:
        return None

    label = _get(primary_guild, "tag")
    if not isinstance(label, str) or not 1 <= len(label) <= 4:
        return None

    tag: dict[str, str] = {"label": label}

    badge = _get(primary_guild, "badge")
    icon_url = _asset_url(badge)
    if icon_url:
        tag["iconUrl"] = icon_url

    guild_id = _get(primary_guild, "id")
    if guild_id is not None:
        tag["guildId"] = str(guild_id)

    badge_hash = _get(badge, "key") or _get(primary_guild, "badge_hash")
    if badge_hash:
        tag["badgeHash"] = str(badge_hash)

    return tag


def _serialize_user(user: Any) -> dict[str, Any]:
    """Serializa identidade, avatar, condição de bot, tag e cargo de um usuário."""
    display_name = (
        _get(user, "display_name")
        or _get(user, "global_name")
        or _get(user, "name")
        or _get(user, "username")
        or f"Usuário {_get(user, 'id', '')}"
    )

    serialized: dict[str, Any] = {
        "name": str(display_name),
        "avatar": _asset_url(
            _get(user, "display_avatar") or _get(user, "avatar")
        ),
        "bot": bool(_get(user, "bot", False)),
    }

    server_tag = _serialize_server_tag(user)
    if server_tag:
        serialized["serverTag"] = server_tag

    role = _serialize_role(user)
    if role:
        serialized["role"] = role

    return serialized


def _serialize_emoji(emoji: Any) -> Any:
    """Serializa emojis Unicode e emojis personalizados do Discord."""
    if isinstance(emoji, str) or emoji is None:
        return emoji

    emoji_id = _get(emoji, "id")
    if emoji_id is None:
        return {"name": _get(emoji, "name", str(emoji))}

    return {
        "id": str(emoji_id),
        "name": _get(emoji, "name", ""),
        "animated": bool(_get(emoji, "animated", False)),
    }


def _message_datetime(message: Any) -> datetime | None:
    """Obtém a data da mensagem, aceitando datetime ou ISO 8601."""
    value = _get(message, "created_at") or _get(message, "timestamp")

    if isinstance(value, datetime):
        return value

    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    return None


def _id_key(value: Any) -> str:
    return str(value) if value is not None else ""


def _mention_targets(content: Any) -> dict[str, set[str]]:
    targets = {"users": set(), "channels": set(), "roles": set()}
    if not isinstance(content, str):
        return targets

    for match in _MENTION_PATTERN.finditer(content):
        category = (
            "users"
            if match.group(1)
            else "roles"
            if match.group(2)
            else "channels"
        )
        targets[category].add(next(value for value in match.groups() if value))

    return targets


def _entity_index(entities: Any) -> dict[str, Any]:
    if isinstance(entities, Mapping):
        return {_id_key(key): value for key, value in entities.items()}

    index: dict[str, Any] = {}
    for entity in entities or ():
        if isinstance(entity, (str, int)):
            index[_id_key(entity)] = None
            continue

        entity_id = _get(entity, "id")
        if entity_id is not None:
            index[_id_key(entity_id)] = entity

    return index


def _lookup_guild_entity(guild: Any, method_names: tuple[str, ...], entity_id: str) -> Any:
    """Procura um membro/canal/cargo no cache do servidor sem fazer requisições."""
    if guild is None:
        return None

    try:
        numeric_id = int(entity_id)
    except (TypeError, ValueError):
        return None

    for method_name in method_names:
        method = getattr(guild, method_name, None)
        if callable(method):
            try:
                result = method(numeric_id)
            except (TypeError, ValueError):
                continue
            if result is not None:
                return result

    return None


def _is_member_like(value: Any) -> bool:
    """Distingue Member de User quando o autor já veio com dados do servidor."""
    return (
        value is not None
        and _get(value, "guild") is not None
        and _get(value, "top_role") is not None
    )


def _resolve_member(guild: Any, user_id: str, fallback: Any = None) -> Any:
    member = _lookup_guild_entity(guild, ("get_member",), user_id)
    if member is not None:
        return member
    if _is_member_like(fallback):
        return fallback
    return fallback


def _mention_metadata(message: Any, guild_id: str | None) -> dict[str, Any]:
    guild = _get(message, "guild")

    user_entities = _entity_index(
        _get(message, "mentions", _get(message, "user_mentions", ()))
    )
    channel_entities = _entity_index(_get(message, "channel_mentions", ()))
    role_entities = _entity_index(
        _get(message, "role_mentions", _get(message, "mention_roles", ()))
    )

    existing = _get(message, "mentionData", _get(message, "mention_data", {}))
    metadata: dict[str, dict[str, Any]] = {
        "users": {},
        "channels": {},
        "roles": {},
    }

    for category in ("users", "channels", "roles"):
        existing_values = _get(existing, category, {})
        if isinstance(existing_values, Mapping):
            metadata[category].update(
                {
                    _id_key(key): _as_json_value(value)
                    for key, value in existing_values.items()
                }
            )

    targets = _mention_targets(_get(message, "content", ""))
    targets["users"].update(user_entities)
    targets["channels"].update(channel_entities)
    targets["roles"].update(role_entities)

    for user_id in targets["users"]:
        entity = user_entities.get(user_id)
        if entity is None:
            entity = _lookup_guild_entity(guild, ("get_member",), user_id)
        if entity is not None:
            metadata["users"].setdefault(
                user_id,
                {"name": _serialize_user(entity)["name"]},
            )

    for channel_id in targets["channels"]:
        entity = channel_entities.get(channel_id)
        if entity is None:
            entity = _lookup_guild_entity(
                guild,
                ("get_channel_or_thread", "get_channel"),
                channel_id,
            )
        if entity is not None:
            entity_guild = _get(entity, "guild")
            resolved_guild_id = _get(entity_guild, "id", guild_id or "")
            metadata["channels"].setdefault(
                channel_id,
                {
                    "name": str(_get(entity, "name", "canal")),
                    "guildId": _id_key(resolved_guild_id),
                },
            )

    for role_id in targets["roles"]:
        entity = role_entities.get(role_id)
        if entity is None:
            entity = _lookup_guild_entity(guild, ("get_role",), role_id)
        if entity is not None:
            metadata["roles"].setdefault(
                role_id,
                {
                    "name": str(_get(entity, "name", "cargo")),
                    "color": _color_hex(_get(entity, "color")),
                },
            )

    return {category: values for category, values in metadata.items() if values}


def _serialize_reference(message: Any) -> dict[str, Any] | None:
    """Serializa a referência de resposta, inclusive o estado de bot do autor."""
    reference = _get(message, "reference")
    if reference is None:
        return None

    message_id = _get(reference, "message_id")
    if message_id is None:
        message_id = _get(reference, "id")
    if message_id is None:
        return None

    reply: dict[str, Any] = {"id": str(message_id)}
    resolved = _get(reference, "resolved")

    if resolved:
        author = _get(resolved, "author")
        if author:
            author_data = _serialize_user(author)
            reply["userName"] = author_data["name"]
            reply["user"] = str(_get(author, "id", ""))
            reply["avatar"] = author_data["avatar"]
            reply["bot"] = author_data["bot"]
            if author_data.get("serverTag"):
                reply["serverTag"] = author_data["serverTag"]
            if author_data.get("role"):
                reply["role"] = author_data["role"]

        content = _get(resolved, "content")
        if isinstance(content, str):
            reply["content"] = content

    return reply


def _serialize_embed(embed: Any) -> Any:
    if isinstance(embed, Mapping):
        return _as_json_value(embed)

    to_dict = getattr(embed, "to_dict", None)
    if callable(to_dict):
        return _as_json_value(to_dict())

    return _as_json_value(embed)


def _serialize_message(
    message: Any,
    *,
    deleted: bool = False,
    guild_id: str | None,
    users: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    author = _get(message, "author")
    message_id = _get(message, "id")
    created_at = _message_datetime(message)

    if author is None or message_id is None or created_at is None:
        raise ValueError(
            "A exportação exige mensagens com autor, ID e data válidos. "
            "Confira se os objetos recebidos são mensagens do Discord."
        )

    author_id = _get(author, "id")
    if author_id is None:
        raise ValueError("Todas as mensagens exportadas precisam de um autor com ID.")

    serialized: dict[str, Any] = {
        "id": str(message_id),
        "user": str(author_id),
        "timestamp": created_at.isoformat(),
        "content": _get(message, "content", "") or "",
        "edited": _get(message, "edited_at") is not None,
        "deleted": bool(deleted or _get(message, "deleted", False)),
    }

    mention_data = _mention_metadata(message, guild_id)
    for user_id in _mention_targets(serialized["content"])["users"]:
        if user_id in users:
            mention_data.setdefault("users", {}).setdefault(
                user_id,
                {"name": users[user_id]["name"]},
            )

    if any(mention_data.values()):
        serialized["mentionData"] = mention_data

    reply = _serialize_reference(message)
    if reply:
        serialized["replyTo"] = reply

    embeds = [
        _serialize_embed(embed)
        for embed in (_get(message, "embeds", ()) or ())
    ]
    if embeds:
        serialized["embeds"] = embeds

    attachments = []
    for attachment in _get(message, "attachments", ()) or ():
        attachments.append(
            {
                "filename": _get(attachment, "filename", "Arquivo"),
                "url": _asset_url(_get(attachment, "url")),
                "proxy_url": _asset_url(_get(attachment, "proxy_url")),
                "content_type": _get(attachment, "content_type"),
                "size": _get(attachment, "size"),
                "description": _get(attachment, "description"),
            }
        )
    if attachments:
        serialized["attachments"] = _as_json_value(attachments)

    reactions = []
    for reaction in _get(message, "reactions", ()) or ():
        reactions.append(
            {
                "emoji": _serialize_emoji(_get(reaction, "emoji")),
                "count": _get(reaction, "count", 0),
                "me": bool(_get(reaction, "me", False)),
            }
        )
    if reactions:
        serialized["reactions"] = _as_json_value(reactions)

    components = [
        _serialize_component(component)
        for component in (_get(message, "components", ()) or ())
    ]
    if components:
        serialized["components"] = {
            "type": "view",
            "components": components,
        }

    return serialized


def _json_script_data(value: Any) -> str:
    """Gera JSON seguro para inserção em script[type=application/json]."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _replace_data_block(template: str, block_id: str, value: Any) -> str:
    opening_tag = f'<script id="{block_id}" type="application/json">'
    closing_tag = "</script>"

    if template.count(opening_tag) != 1:
        raise ValueError(
            f'O template deve conter exatamente um bloco <script> com id="{block_id}".'
        )

    start = template.index(opening_tag) + len(opening_tag)
    end = template.find(closing_tag, start)
    if end < 0:
        raise ValueError(f'O bloco #{block_id} não possui fechamento </script>.')

    return template[:start] + _json_script_data(value) + template[end:]


def _ticket_value(value: Any) -> Any:
    """Converte valores comuns de um sistema de tickets para dados exibíveis."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return _as_json_value(value)

    if isinstance(value, (datetime, date, Enum, Mapping, list, tuple, set, frozenset)):
        return _as_json_value(value)

    for attribute in ("display_name", "global_name", "username", "name"):
        display_value = _get(value, attribute)
        if isinstance(display_value, str) and display_value:
            return display_value

    object_id = _get(value, "id")
    if object_id is not None:
        return str(object_id)

    return str(value)


def _default_ticket_info(channel: Any, guild: Any) -> dict[str, Any]:
    """Monta os dados que podem ser inferidos do canal sem inventar solicitante."""
    channel_name = str(_get(channel, "name", "Atendimento") or "Atendimento")
    ticket: dict[str, Any] = {
        "title": channel_name,
        "channelName": channel_name,
        "guildName": str(_get(guild, "name", "Sacra Communitas") or "Sacra Communitas"),
    }

    channel_id = _get(channel, "id")
    if channel_id is not None:
        ticket["ticketId"] = str(channel_id)

    created_at = _get(channel, "created_at")
    if isinstance(created_at, datetime):
        ticket["createdAt"] = created_at.isoformat()

    parent = _get(channel, "parent")
    category = _get(channel, "category") or _get(parent, "category")
    category_name = _get(category, "name")
    if category_name:
        ticket["categoryName"] = str(category_name)

    return ticket


def _resolve_template_path(template_path: str | Path | None) -> Path:
    if template_path is not None:
        path = Path(template_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Template HTML não encontrado: {path}")
        return path

    for path in (_UPDATED_TEMPLATE_PATH, _TEMPLATE_PATH):
        if path.is_file():
            return path

    raise FileNotFoundError(
        "Não encontrei o template HTML. Coloque messages_sacra.html ou "
        "messages.html na mesma pasta de exporter.py, ou informe template_path."
    )


def _cache_user(
    users: dict[str, dict[str, Any]],
    user_id: str,
    user: Any,
) -> None:
    """Guarda a melhor identidade conhecida sem apagar metadados já coletados."""
    if user is None:
        return

    fresh = _serialize_user(user)
    current = users.setdefault(user_id, {})

    for key, value in fresh.items():
        if value not in (None, "") or key not in current:
            current[key] = value


def export_messages(
    channel: Any,
    messages: Iterable[Any],
    *,
    export_type: str = "channel",
    title: str = "",
    user_name: str = "",
    ticket_info: Mapping[str, Any] | None = None,
    template_path: str | Path | None = None,
) -> str:
    """Renderiza as mensagens com o template HTML local.

    Args:
        channel: Canal, thread ou canal de texto do discord.py.
        messages: Iterável de discord.Message.
        export_type: "channel", "user", "bulk" ou "ticket".
        title: Título personalizado para exportações em lote.
        user_name: Nome usado quando export_type="user".
        ticket_info: Metadados opcionais do ticket. Pode receber objetos Discord
            diretamente nos campos de nome, por exemplo requester=member.
        template_path: Caminho opcional para o HTML. Por padrão, procura primeiro
            messages_sacra.html e depois messages.html na pasta deste módulo.

    Returns:
        O HTML completo como string.
    """
    message_list = list(messages)
    users: dict[str, dict[str, Any]] = {}

    guild = _get(channel, "guild")
    guild_id_value = _get(guild, "id")
    guild_id = str(guild_id_value) if guild_id_value is not None else ""

    for message in message_list:
        author = _get(message, "author")
        author_id = _get(author, "id") if author is not None else None
        if author is None or author_id is None:
            raise ValueError(
                "Todas as mensagens exportadas precisam ter um autor com ID."
            )

        user_id = str(author_id)
        member = _resolve_member(guild, user_id, author)
        _cache_user(users, user_id, member or author)

        for mentioned_user in _get(message, "mentions", ()) or ():
            mentioned_user_id = _get(mentioned_user, "id")
            if mentioned_user_id is None:
                continue

            mentioned_id = str(mentioned_user_id)
            mentioned_member = _resolve_member(
                guild,
                mentioned_id,
                mentioned_user,
            )
            _cache_user(users, mentioned_id, mentioned_member or mentioned_user)

        for mentioned_id in _mention_targets(
            _get(message, "content", "")
        )["users"]:
            if mentioned_id in users:
                continue

            mentioned_member = _lookup_guild_entity(
                guild,
                ("get_member",),
                mentioned_id,
            )
            if mentioned_member is not None:
                _cache_user(users, mentioned_id, mentioned_member)

    export_info: dict[str, Any] = {
        "type": export_type,
        "channelName": str(_get(channel, "name", "canal") or "canal"),
        "channelId": str(_get(channel, "id", "") or ""),
        "guildId": guild_id,
        "guildName": str(_get(guild, "name", "") or ""),
        "userName": user_name,
    }

    if title:
        export_info["title"] = title

    if export_type == "ticket" or ticket_info is not None:
        ticket = _default_ticket_info(channel, guild)
        if ticket_info is not None:
            if not isinstance(ticket_info, Mapping):
                raise TypeError("ticket_info deve ser um Mapping/dict.")
            ticket.update(
                {
                    str(key): _ticket_value(value)
                    for key, value in ticket_info.items()
                    if value is not None
                }
            )
        export_info["ticket"] = ticket

    serialized_messages = [
        _serialize_message(
            message,
            deleted=False,
            guild_id=guild_id or None,
            users=users,
        )
        for message in message_list
    ]

    template_file = _resolve_template_path(template_path)
    template = template_file.read_text(encoding="utf-8")

    data = {
        "export_info": export_info,
        "users": users,
        "messages": serialized_messages,
    }
    for block_id, key in _DATA_BLOCKS.items():
        template = _replace_data_block(template, block_id, data[key])

    return template
