"""Conflict-checked documentation gettext message replacements."""

from __future__ import annotations

from pathlib import Path

from babel.messages.catalog import Catalog

from .locale_catalogue_io import _catalogue_messages
from .locale_message_format import _validate_format_contract
from .locale_mutation_contracts import DocumentationLocaleMutationError, ManifestMessage


def _apply_messages(
    catalogue: Catalog,
    updates: tuple[ManifestMessage, ...],
    path: Path,
) -> tuple[int, int]:
    """Validate identities, conflicts, and formatting before mutating messages."""
    active = _catalogue_messages(catalogue)
    changed = 0
    cleared_fuzzy = 0
    for update in updates:
        identity = (update.context or "", update.msgid)
        message = active.get(identity)
        if message is None:
            raise DocumentationLocaleMutationError(f"missing gettext msgid in {path}: {identity!r}")
        if message.fuzzy != update.expected_fuzzy:
            raise DocumentationLocaleMutationError(
                f"fuzzy state mismatch in {path} for {identity!r}: "
                f"expected {update.expected_fuzzy!r}, got {message.fuzzy!r}"
            )
        current = message.string
        if not isinstance(current, str):
            raise DocumentationLocaleMutationError(
                f"plural gettext msgid is not supported by this manifest: {identity!r}"
            )
        if current != update.expected:
            raise DocumentationLocaleMutationError(
                f"translation conflict in {path} for {identity!r}: expected {update.expected!r}, got {current!r}"
            )
        _validate_format_contract(update.msgid, current, update.replacement, path, identity)
        if current != update.replacement:
            changed += 1
            message.string = update.replacement
        if update.clear_fuzzy and message.fuzzy:
            message.flags.discard("fuzzy")
            cleared_fuzzy += 1
    return changed, cleared_fuzzy
