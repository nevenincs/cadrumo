"""Babel parsing, context-aware message identity, and serialization."""

from __future__ import annotations

import io
from pathlib import Path

from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po, write_po

from dev._paths import UTF_8

from .locale_mutation_contracts import DocumentationLocaleMutationError


def _parse_catalogue(text: str, locale: str, path: Path) -> Catalog:
    """Parse one PO/POT file with Babel and normalize parser failures."""
    try:
        return read_po(io.StringIO(text), locale=locale, abort_invalid=True)
    except (OSError, UnicodeError, ValueError) as exc:
        raise DocumentationLocaleMutationError(f"cannot parse gettext catalogue {path}: {exc}") from exc


def _message_key(message: Message) -> tuple[str, str]:
    """Return a context-aware stable identity for a Babel message."""
    message_id = message.id
    if isinstance(message_id, str):
        identity = message_id
    elif isinstance(message_id, (tuple, list)):
        if not all(isinstance(part, str) for part in message_id):
            raise DocumentationLocaleMutationError("Babel message identity contains non-text components")
        identity = "\x04".join(message_id)
    else:
        raise DocumentationLocaleMutationError("Babel message identity is not text")
    context = message.context if isinstance(message.context, str) else ""
    return context, identity


def _manifest_stale_key(context: str | None, msgid: str, msgid_plural: str | None) -> tuple[str, str]:
    """Return the catalogue identity represented by a stale manifest item."""
    identity = msgid if msgid_plural is None else "\x04".join((msgid, msgid_plural))
    return context or "", identity


def _catalogue_messages(catalogue: Catalog) -> dict[tuple[str, str], Message]:
    """Index active non-header Babel messages by gettext identity."""
    return {_message_key(message): message for message in catalogue if message.id}


def _all_message_keys(catalogue: Catalog) -> set[tuple[str, str]]:
    """Return active and obsolete non-header message identities."""
    keys = set(_catalogue_messages(catalogue))
    obsolete = getattr(catalogue, "obsolete", {})
    if isinstance(obsolete, dict):
        keys.update(_message_key(message) for message in obsolete.values() if message.id)
    return keys


def _render_catalogue(catalogue: Catalog) -> str:
    """Render a Babel catalogue while retaining its existing order and header."""
    output = io.BytesIO()
    write_po(output, catalogue, sort_output=False, sort_by_file=False, ignore_obsolete=False)
    return output.getvalue().decode(UTF_8).rstrip("\n") + "\n"
