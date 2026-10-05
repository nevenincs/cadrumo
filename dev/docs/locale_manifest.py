"""Strict manifest decoding, message identities, and duplicate refusal."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final, cast

from dev._paths import UTF_8

from .locale_mutation_contracts import (
    _SCHEMA_VERSION,
    DocumentationLocaleMutationError,
    ManifestMessage,
    ManifestStale,
    ManifestUpdate,
)

_TARGET_LOCALES: Final[frozenset[str]] = frozenset({"ca", "es", "hu"})


_SHA256: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}\Z")


def _read_manifest(path: Path) -> dict[str, object]:
    """Read and validate the manifest envelope."""
    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DocumentationLocaleMutationError(f"cannot read docs translation manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DocumentationLocaleMutationError("docs translation manifest must contain an object")
    if payload.get("schema_version") != _SCHEMA_VERSION:
        raise DocumentationLocaleMutationError(
            f"unsupported docs translation manifest schema: {payload.get('schema_version')!r}"
        )
    if not isinstance(payload.get("updates"), list) or not payload["updates"]:
        raise DocumentationLocaleMutationError("docs translation manifest updates must be a non-empty list")
    if not all(isinstance(key, str) for key in payload):
        raise DocumentationLocaleMutationError("docs translation manifest keys must be strings")
    return {key: value for key, value in payload.items() if isinstance(key, str)}


def _parse_updates(payload: dict[str, object]) -> tuple[ManifestUpdate, ...]:
    """Validate manifest records and reject duplicate catalogue/message targets."""
    raw_updates = payload["updates"]
    if not isinstance(raw_updates, list):
        raise DocumentationLocaleMutationError("docs translation manifest updates must be a non-empty list")
    updates: list[ManifestUpdate] = []
    seen_catalogues: set[tuple[str, str]] = set()
    for update_index, raw_update in enumerate(raw_updates):
        _append_manifest_update(update_index, raw_update, updates, seen_catalogues)
    return tuple(updates)


def _parse_stale_targets(
    raw_targets: list[object],
    *,
    field: str,
    update_index: int,
    locale: str,
    catalogue: str,
) -> tuple[ManifestStale, ...]:
    """Parse one exact active-stale or obsolete-target list."""
    targets: list[ManifestStale] = []
    seen: set[tuple[str, str, str | None]] = set()
    for target_index, raw_target in enumerate(raw_targets):
        if not isinstance(raw_target, dict):
            raise DocumentationLocaleMutationError(
                f"updates[{update_index}].{field}[{target_index}] must contain an object"
            )
        prefix = f"updates[{update_index}].{field}[{target_index}]"
        context = raw_target.get("msgctxt")
        if context is not None and not isinstance(context, str):
            raise DocumentationLocaleMutationError(f"{prefix}.msgctxt must be a string or null")
        msgid = _required_string(raw_target, "msgid", prefix)
        msgid_plural = raw_target.get("msgid_plural")
        if msgid_plural is not None and not isinstance(msgid_plural, str):
            raise DocumentationLocaleMutationError(f"{prefix}.msgid_plural must be a string or null")
        if msgid_plural == "":
            raise DocumentationLocaleMutationError(f"{prefix}.msgid_plural must not be blank")
        target_key = (context or "", msgid, msgid_plural)
        if target_key in seen:
            raise DocumentationLocaleMutationError(f"duplicate {field} target in {locale}/{catalogue}: {target_key!r}")
        seen.add(target_key)
        targets.append(ManifestStale(context=context, msgid=msgid, msgid_plural=msgid_plural))
    return tuple(targets)


def _required_string(record: dict[str, object], key: str, prefix: str) -> str:
    """Read one required non-null string field."""
    value = record.get(key)
    if not isinstance(value, str):
        raise DocumentationLocaleMutationError(f"{prefix}.{key} must be a string")
    return value


def _optional_bool(record: dict[str, object], key: str, default: bool, prefix: str) -> bool:
    """Read an optional strict JSON boolean field."""
    value = record.get(key, default)
    if not isinstance(value, bool):
        raise DocumentationLocaleMutationError(f"{prefix}.{key} must be a boolean")
    return value


def _required_digest(record: dict[str, object], key: str, prefix: str) -> str:
    """Read one required lowercase SHA-256 field."""
    value = _required_string(record, key, prefix)
    if _SHA256.fullmatch(value) is None:
        raise DocumentationLocaleMutationError(f"{prefix}.{key} must be a lowercase SHA-256 digest")
    return value


def _append_manifest_update(
    update_index: int, raw_update: object, updates: list[ManifestUpdate], seen_catalogues: set[tuple[str, str]]
) -> None:
    """Append manifest update."""
    if not isinstance(raw_update, dict):
        raise DocumentationLocaleMutationError(f"updates[{update_index}] must contain an object")
    locale = _required_string(raw_update, "locale", f"updates[{update_index}]")
    if locale not in _TARGET_LOCALES:
        raise DocumentationLocaleMutationError(
            f"updates[{update_index}].locale must be one of {sorted(_TARGET_LOCALES)!r}, got {locale!r}"
        )
    catalogue = _required_string(raw_update, "catalogue", f"updates[{update_index}]")
    source_sha256 = _required_digest(raw_update, "source_sha256", f"updates[{update_index}]")
    catalogue_sha256 = _required_digest(raw_update, "catalogue_sha256", f"updates[{update_index}]")
    raw_messages, raw_remove_stale, raw_remove_obsolete = _manifest_target_lists(raw_update, update_index)
    if not raw_messages and not raw_remove_stale and not raw_remove_obsolete:
        raise DocumentationLocaleMutationError(
            f"updates[{update_index}] must contain messages, remove_stale, or remove_obsolete entries"
        )
    catalogue_key = (locale, catalogue)
    if catalogue_key in seen_catalogues:
        raise DocumentationLocaleMutationError(f"duplicate catalogue update: {locale}/{catalogue}")
    seen_catalogues.add(catalogue_key)
    messages: list[ManifestMessage] = []
    seen_messages: set[tuple[str, str]] = set()
    for message_index, raw_message in enumerate(raw_messages):
        _append_manifest_message(message_index, raw_message, update_index, locale, catalogue, messages, seen_messages)
    remove_stale = _parse_stale_targets(
        raw_remove_stale,
        field="remove_stale",
        update_index=update_index,
        locale=locale,
        catalogue=catalogue,
    )
    remove_obsolete = _parse_stale_targets(
        raw_remove_obsolete,
        field="remove_obsolete",
        update_index=update_index,
        locale=locale,
        catalogue=catalogue,
    )
    _validate_stale_message_overlap(messages, remove_stale, locale, catalogue)
    updates.append(
        ManifestUpdate(
            locale=locale,
            catalogue=catalogue,
            source_sha256=source_sha256,
            catalogue_sha256=catalogue_sha256,
            messages=tuple(messages),
            remove_stale=remove_stale,
            remove_obsolete=remove_obsolete,
        )
    )


def _append_manifest_message(
    message_index: int,
    raw_message: object,
    update_index: int,
    locale: str,
    catalogue: str,
    messages: list[ManifestMessage],
    seen_messages: set[tuple[str, str]],
) -> None:
    """Append manifest message."""
    if not isinstance(raw_message, dict):
        raise DocumentationLocaleMutationError(
            f"updates[{update_index}].messages[{message_index}] must contain an object"
        )
    prefix = f"updates[{update_index}].messages[{message_index}]"
    context = raw_message.get("msgctxt")
    if context is not None and not isinstance(context, str):
        raise DocumentationLocaleMutationError(f"{prefix}.msgctxt must be a string or null")
    msgid = _required_string(raw_message, "msgid", prefix)
    expected = _required_string(raw_message, "expected_msgstr", prefix)
    replacement = _required_string(raw_message, "msgstr", prefix)
    expected_fuzzy = _optional_bool(raw_message, "expected_fuzzy", False, prefix)
    clear_fuzzy = _optional_bool(raw_message, "clear_fuzzy", False, prefix)
    if not replacement.strip():
        raise DocumentationLocaleMutationError(f"{prefix}.msgstr must not be blank")
    message_key = (context or "", msgid)
    if message_key in seen_messages:
        raise DocumentationLocaleMutationError(f"duplicate message target in {locale}/{catalogue}: {msgid!r}")
    seen_messages.add(message_key)
    messages.append(
        ManifestMessage(
            context=context,
            msgid=msgid,
            expected=expected,
            replacement=replacement,
            expected_fuzzy=expected_fuzzy,
            clear_fuzzy=clear_fuzzy,
        )
    )


def _manifest_target_lists(
    raw_update: dict[str, object], update_index: int
) -> tuple[list[object], list[object], list[object]]:
    """Manifest target lists."""
    raw_messages = raw_update.get("messages")
    if raw_messages is None:
        raw_messages = []
    if not isinstance(raw_messages, list):
        raise DocumentationLocaleMutationError(f"updates[{update_index}].messages must be a list")
    raw_remove_stale = raw_update.get("remove_stale", [])
    if not isinstance(raw_remove_stale, list):
        raise DocumentationLocaleMutationError(f"updates[{update_index}].remove_stale must be a list")
    raw_remove_obsolete = raw_update.get("remove_obsolete", [])
    if not isinstance(raw_remove_obsolete, list):
        raise DocumentationLocaleMutationError(f"updates[{update_index}].remove_obsolete must be a list")
    return cast(
        "tuple[list[object], list[object], list[object]]", (raw_messages, raw_remove_stale, raw_remove_obsolete)
    )


def _validate_stale_message_overlap(
    messages: list[ManifestMessage], remove_stale: tuple[ManifestStale, ...], locale: str, catalogue: str
) -> None:
    """Refuse updates that replace and remove the same active identity."""
    message_keys = {(message.context or "", message.msgid, None) for message in messages}
    stale_keys = {(stale.context or "", stale.msgid, stale.msgid_plural) for stale in remove_stale}
    if message_keys & stale_keys:
        overlap = sorted(message_keys & stale_keys)
        raise DocumentationLocaleMutationError(
            f"message and remove_stale targets overlap in {locale}/{catalogue}: {overlap!r}"
        )
