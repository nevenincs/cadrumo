"""Gettext for the authoritative locale audit."""

from __future__ import annotations

from pathlib import Path

from babel.messages.pofile import read_po

from dev._paths import UTF_8


def read_gettext_messages(path: Path) -> dict[str, str] | None:
    """Return canonical identities and source prose from one POT template."""
    if not path.is_file():
        return None
    with path.open(encoding=UTF_8) as handle:
        return {po_message_identity(message): po_message_id(message.id) for message in read_po(handle) if message.id}


def po_message_id(value: object) -> str:
    """Normalize singular and plural Babel message identifiers."""
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)):
        parts: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("gettext plural message ids must contain text")
            parts.append(item)
        return "\x04".join(parts)
    raise TypeError("gettext message id must be text or plural forms")


def po_message_identity(message: object) -> str:
    """Return a gettext identity that retains msgctxt and plural identity."""
    message_id_value = getattr(message, "id", None)
    if not isinstance(message_id_value, (str, tuple, list)):
        raise TypeError("gettext message id must be text or plural forms")
    if isinstance(message_id_value, (tuple, list)) and not all(isinstance(item, str) for item in message_id_value):
        raise TypeError("gettext plural message ids must contain text")
    message_id = po_message_id(message_id_value)
    context = getattr(message, "context", None)
    return f"{context}\x1f{message_id}" if isinstance(context, str) and context else message_id


def po_translation_strings(value: object) -> tuple[str, ...]:
    """Return every gettext translation form without treating an empty plural tuple as complete."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        strings: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return ()
            strings.append(item)
        return tuple(strings)
    return ()
