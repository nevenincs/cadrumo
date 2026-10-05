"""Parallel gettext for the authoritative locale audit."""

from __future__ import annotations

import io
from collections import Counter
from pathlib import Path

from babel.messages.catalog import Message
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from dev._paths import UTF_8

from .signal_gettext import po_message_identity, po_translation_strings
from .signal_parallel_findings import data_finding


def inventory_parallel_po_sources(
    docs_root: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    docs_catalogue_files: set[tuple[str, str]],
    docs_messages: dict[tuple[str, str], dict[str, bool]],
    docs_translations: dict[tuple[str, str], dict[str, tuple[str, ...]]],
    docs_obsolete: dict[tuple[str, str], set[str]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory parallel po sources."""
    from dev.docs.i18n import TARGET_LANGUAGES

    for path in sorted(docs_root.rglob("*.po")) if docs_root.is_dir() else ():
        inventory_parallel_po_file(
            path,
            docs_root,
            repository,
            counts,
            findings,
            docs_catalogue_files,
            docs_messages,
            docs_translations,
            docs_obsolete,
            spelling_values,
            TARGET_LANGUAGES,
        )


def inventory_parallel_po_file(
    path: Path,
    docs_root: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    docs_catalogue_files: set[tuple[str, str]],
    docs_messages: dict[tuple[str, str], dict[str, bool]],
    docs_translations: dict[tuple[str, str], dict[str, tuple[str, ...]]],
    docs_obsolete: dict[tuple[str, str], set[str]],
    spelling_values: dict[str, dict[str, str]] | None,
    target_languages: tuple[str, ...],
) -> None:
    """Inventory parallel po file."""
    try:
        with path.open(encoding=UTF_8) as handle:
            catalogue_payload = read_po(handle)
        write_mo(io.BytesIO(), catalogue_payload)
        messages = [message for message in catalogue_payload if message.id]
    except (OSError, UnicodeError, ValueError) as exc:
        counts["invalid_data_files"] += 1
        findings.append(data_finding("invalid_localization_data", path, "", type(exc).__name__))
        return
    relative = path.relative_to(docs_root)
    if len(relative.parts) < 3 or relative.parts[0] not in target_languages or relative.parts[1] != "LC_MESSAGES":
        counts["invalid_data_files"] += 1
        findings.append(data_finding("invalid_docs_catalogue_layout", path, "", "unknown_locale_or_layout"))
        return
    locale = relative.parts[0]
    catalogue = Path(*relative.parts[2:]).as_posix()
    docs_catalogue_files.add((locale, catalogue))
    counts["docs_catalogues_compiled"] += 1
    counts[f"docs_catalogues_compiled_{locale}"] += 1
    for message in messages:
        inventory_po_translation_message(
            message, locale, catalogue, path, repository, counts, docs_messages, docs_translations, spelling_values
        )
    for message in catalogue_payload.obsolete.values():
        if message.id:
            docs_obsolete[(locale, catalogue)].add(po_message_identity(message))


def inventory_po_translation_message(
    message: Message,
    locale: str,
    catalogue: str,
    path: Path,
    repository: Path,
    counts: Counter[str],
    docs_messages: dict[tuple[str, str], dict[str, bool]],
    docs_translations: dict[tuple[str, str], dict[str, tuple[str, ...]]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory po translation message."""
    message_id = po_message_identity(message)
    translations = po_translation_strings(message.string)
    translated = bool(translations) and all(value.strip() for value in translations) and "fuzzy" not in message.flags
    docs_messages[(catalogue, message_id)][locale] = translated
    if translated:
        docs_translations[(catalogue, message_id)][locale] = translations
    counts["parallel_localization_cells"] += 1
    if spelling_values is not None and translated:
        for index, value in enumerate(translations):
            cell = f"parallel:{path.relative_to(repository).as_posix()}:{message_id}"
            if len(translations) > 1:
                cell = f"{cell}:plural[{index}]"
            spelling_values.setdefault(locale, {})[cell] = value
