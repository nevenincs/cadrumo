"""Conflict-safe, Babel-aware mutations for documentation PO catalogues.

The runtime locale writer operates on YAML leaves. Documentation translations
are gettext messages instead, so they need a separate writer that understands
message identity, fuzzy state, and the formatting tokens embedded in a source
message. This module is deliberately a service rather than a CLI: the docs
i18n command can expose it without giving callers a second raw-text write path.

Manifest schema ``1`` is a JSON object with an ``updates`` list. Each update
contains ``locale``, a POSIX ``catalogue`` path relative to
``docs/locales/<locale>/LC_MESSAGES``, the SHA-256 digests of the current source
page and PO file, and a ``messages`` list. Each message carries ``msgid``,
``expected_msgstr``, and the replacement ``msgstr``; ``msgctxt`` is optional.
Every update is validated before the first write. Writes use the shared locale
lock and atomic write guard, and a dry run performs all validation without
publishing bytes.

Fuzzy replacements must opt into their current fuzzy state with
``expected_fuzzy: true``.  A replacement clears that state only when it also
sets ``clear_fuzzy: true``.  Stale catalogue entries can be removed only by an
exact identity in the update's ``remove_stale`` list; every other source/PO
drift remains a refusal.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po, write_po

from cadrumo.core.i18n.render import extract_placeholders
from dev._paths import REPO_ROOT, UTF_8
from dev.locales._write_guard import catalogue_write_guard

_SCHEMA_VERSION: Final[int] = 1
_TARGET_LOCALES: Final[frozenset[str]] = frozenset({"ca", "es", "hu"})
_SHA256: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}\Z")
_INLINE_LITERAL: Final[re.Pattern[str]] = re.compile(r"`([^`\r\n]+)`")
_RST_ROLE: Final[re.Pattern[str]] = re.compile(r":[A-Za-z][A-Za-z0-9_-]*:")
_PYTHON_PERCENT: Final[re.Pattern[str]] = re.compile(
    r"%(?:\([A-Za-z_][A-Za-z0-9_]*\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+|\.\*)?(?:[hlL])?[diouxXeEfFgGcrsa%]"
)


class DocumentationLocaleMutationError(ValueError):
    """Raised when a docs translation manifest cannot be applied safely."""


@dataclass(frozen=True)
class _ManifestMessage:
    """One validated message replacement from the manifest."""

    context: str | None
    msgid: str
    expected: str
    replacement: str
    expected_fuzzy: bool
    clear_fuzzy: bool


@dataclass(frozen=True)
class _ManifestStale:
    """One exact stale catalogue identity scheduled for removal."""

    context: str | None
    msgid: str
    msgid_plural: str | None


@dataclass(frozen=True)
class _ManifestUpdate:
    """One validated catalogue update from the manifest."""

    locale: str
    catalogue: str
    source_sha256: str
    catalogue_sha256: str
    messages: tuple[_ManifestMessage, ...]
    remove_stale: tuple[_ManifestStale, ...]


@dataclass
class _PreparedCatalogue:
    """A validated in-memory Babel catalogue waiting for publication."""

    path: Path
    original: str
    rendered: str
    changed_messages: int
    cleared_fuzzy_messages: int
    removed_stale_messages: int


def apply_manifest(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    dry_run: bool,
) -> dict[str, object]:
    """Validate and apply one documentation translation manifest.

    Args:
        path: JSON manifest path. Paths inside the manifest are resolved only
            beneath the repository's documentation locale root.
        repo_root: Repository root containing the ``docs/`` tree. The default
            keeps direct callers anchored to the checked-out repository while
            allowing isolated callers to exercise the same real path rules.
        dry_run: Validate and render all updates without writing any catalogue.

    Returns:
        Stable counts describing the validated batch. ``changed_messages`` is
        the number of requested values that differ from their current values;
        ``cleared_fuzzy_messages`` and ``removed_stale_messages`` count the
        explicit state changes; ``written_catalogues`` is zero for a dry run.

    Raises:
        DocumentationLocaleMutationError: If the manifest, source, catalogue,
            message identity, digest, or formatting contract is invalid.
    """
    manifest = _read_manifest(path)
    updates = _parse_updates(manifest)
    docs_root = repo_root / "docs"
    locale_root = docs_root / "locales"
    source_pages = _source_pages(docs_root)
    prepared: list[_PreparedCatalogue] = []
    requested_messages = sum(len(update.messages) for update in updates)

    # One shared lock spans read, validation, and publication. Every catalogue
    # is fully prepared before any write, so a later refusal leaves the batch
    # untouched.
    with catalogue_write_guard(locale_root) as guard:
        for update in updates:
            catalogue_path, source_path, pot_path = _resolve_update_paths(
                update,
                locale_root=locale_root,
                docs_root=docs_root,
                source_pages=source_pages,
            )
            source_digest = _sha256_path(source_path)
            if source_digest != update.source_sha256:
                raise DocumentationLocaleMutationError(
                    f"source digest mismatch for docs/{source_path.relative_to(docs_root).as_posix()}: "
                    f"expected {update.source_sha256}, got {source_digest}"
                )
            raw_catalogue = catalogue_path.read_bytes()
            catalogue_digest = hashlib.sha256(raw_catalogue).hexdigest()
            if catalogue_digest != update.catalogue_sha256:
                raise DocumentationLocaleMutationError(
                    f"catalogue digest mismatch for {catalogue_path.relative_to(docs_root).as_posix()}: "
                    f"expected {update.catalogue_sha256}, got {catalogue_digest}"
                )
            catalogue_text = guard.read_text(catalogue_path)
            catalogue = _parse_catalogue(catalogue_text, update.locale, catalogue_path)
            pot = _parse_catalogue(pot_path.read_text(encoding=UTF_8), "en", pot_path)
            allowed_stale = _validate_stale_targets(catalogue, pot, update.remove_stale, catalogue_path)
            _validate_msgids(catalogue, pot, catalogue_path, allowed_stale=allowed_stale)
            _validate_unlisted_fuzzy(catalogue, update, catalogue_path)
            changed_messages, cleared_fuzzy_messages = _apply_messages(
                catalogue, update.messages, catalogue_path
            )
            removed_stale_messages = _remove_stale(catalogue, update.remove_stale, catalogue_path)
            rendered = _render_catalogue(catalogue)
            prepared.append(
                _PreparedCatalogue(
                    path=catalogue_path,
                    original=catalogue_text,
                    rendered=rendered,
                    changed_messages=changed_messages,
                    cleared_fuzzy_messages=cleared_fuzzy_messages,
                    removed_stale_messages=removed_stale_messages,
                )
            )

        if not dry_run:
            for item in prepared:
                if item.rendered != item.original:
                    guard.write_text(item.path, item.rendered)

    changed_messages = sum(item.changed_messages for item in prepared)
    changed_catalogues = sum(item.rendered != item.original for item in prepared)
    return {
        "schema_version": _SCHEMA_VERSION,
        "dry_run": dry_run,
        "catalogues": len(prepared),
        "requested_messages": requested_messages,
        "changed_messages": changed_messages,
        "unchanged_messages": requested_messages - changed_messages,
        "cleared_fuzzy_messages": sum(item.cleared_fuzzy_messages for item in prepared),
        "removed_stale_messages": sum(item.removed_stale_messages for item in prepared),
        "written_catalogues": 0 if dry_run else changed_catalogues,
    }


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
    return payload


def _parse_updates(payload: dict[str, object]) -> tuple[_ManifestUpdate, ...]:
    """Validate manifest records and reject duplicate catalogue/message targets."""
    raw_updates = cast(list[object], payload["updates"])
    updates: list[_ManifestUpdate] = []
    seen_catalogues: set[tuple[str, str]] = set()
    for update_index, raw_update in enumerate(raw_updates):
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
        raw_messages = raw_update.get("messages")
        if raw_messages is None:
            raw_messages = []
        if not isinstance(raw_messages, list):
            raise DocumentationLocaleMutationError(f"updates[{update_index}].messages must be a list")
        raw_remove_stale = raw_update.get("remove_stale", [])
        if not isinstance(raw_remove_stale, list):
            raise DocumentationLocaleMutationError(f"updates[{update_index}].remove_stale must be a list")
        if not raw_messages and not raw_remove_stale:
            raise DocumentationLocaleMutationError(
                f"updates[{update_index}] must contain messages or remove_stale entries"
            )
        catalogue_key = (locale, catalogue)
        if catalogue_key in seen_catalogues:
            raise DocumentationLocaleMutationError(f"duplicate catalogue update: {locale}/{catalogue}")
        seen_catalogues.add(catalogue_key)
        messages: list[_ManifestMessage] = []
        seen_messages: set[tuple[str, str]] = set()
        for message_index, raw_message in enumerate(raw_messages):
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
                _ManifestMessage(
                    context=context,
                    msgid=msgid,
                    expected=expected,
                    replacement=replacement,
                    expected_fuzzy=expected_fuzzy,
                    clear_fuzzy=clear_fuzzy,
                )
            )
        remove_stale: list[_ManifestStale] = []
        seen_stale: set[tuple[str, str, str | None]] = set()
        for stale_index, raw_stale in enumerate(raw_remove_stale):
            if not isinstance(raw_stale, dict):
                raise DocumentationLocaleMutationError(
                    f"updates[{update_index}].remove_stale[{stale_index}] must contain an object"
                )
            prefix = f"updates[{update_index}].remove_stale[{stale_index}]"
            stale_context = raw_stale.get("msgctxt")
            if stale_context is not None and not isinstance(stale_context, str):
                raise DocumentationLocaleMutationError(f"{prefix}.msgctxt must be a string or null")
            stale_msgid = _required_string(raw_stale, "msgid", prefix)
            stale_plural = raw_stale.get("msgid_plural")
            if stale_plural is not None and not isinstance(stale_plural, str):
                raise DocumentationLocaleMutationError(f"{prefix}.msgid_plural must be a string or null")
            if stale_plural == "":
                raise DocumentationLocaleMutationError(f"{prefix}.msgid_plural must not be blank")
            stale_key = _manifest_stale_key(stale_context, stale_msgid, stale_plural)
            if stale_key in seen_stale:
                raise DocumentationLocaleMutationError(
                    f"duplicate stale target in {locale}/{catalogue}: {stale_key!r}"
                )
            seen_stale.add(stale_key)
            remove_stale.append(
                _ManifestStale(
                    context=stale_context,
                    msgid=stale_msgid,
                    msgid_plural=stale_plural,
                )
            )
        message_keys = {(message.context or "", message.msgid, None) for message in messages}
        stale_keys = set(seen_stale)
        if message_keys & stale_keys:
            overlap = sorted(message_keys & stale_keys)
            raise DocumentationLocaleMutationError(
                f"message and remove_stale targets overlap in {locale}/{catalogue}: {overlap!r}"
            )
        updates.append(
            _ManifestUpdate(
                locale=locale,
                catalogue=catalogue,
                source_sha256=source_sha256,
                catalogue_sha256=catalogue_sha256,
                messages=tuple(messages),
                remove_stale=tuple(remove_stale),
            )
        )
    return tuple(updates)


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


def _source_pages(docs_root: Path) -> dict[str, Path]:
    """Return the authorized PO-to-source page mapping from the i18n owner."""
    from .i18n import user_scope_source_pages

    return {Path(page).with_suffix(".po").as_posix(): docs_root / page for page in user_scope_source_pages(docs_root)}


def _resolve_update_paths(
    update: _ManifestUpdate,
    *,
    locale_root: Path,
    docs_root: Path,
    source_pages: dict[str, Path],
) -> tuple[Path, Path, Path]:
    """Resolve one catalogue and its source/template without path widening."""
    relative = Path(update.catalogue)
    if (
        relative.is_absolute()
        or "\\" in update.catalogue
        or not update.catalogue.endswith(".po")
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise DocumentationLocaleMutationError(
            f"catalogue path must be a normalized POSIX .po path below LC_MESSAGES: {update.catalogue!r}"
        )
    expected_root = (locale_root / update.locale / "LC_MESSAGES").resolve()
    catalogue_path = (expected_root / relative).resolve()
    try:
        catalogue_path.relative_to(expected_root)
    except ValueError as exc:
        raise DocumentationLocaleMutationError(f"catalogue path escapes LC_MESSAGES: {update.catalogue!r}") from exc
    if update.catalogue not in source_pages:
        raise DocumentationLocaleMutationError(
            f"catalogue is not an authorized user-scope page for {update.locale}: {update.catalogue!r}"
        )
    source_path = source_pages[update.catalogue].resolve()
    pot_path = (locale_root / "pot" / relative.with_suffix(".pot")).resolve()
    if not catalogue_path.is_file():
        raise DocumentationLocaleMutationError(f"catalogue is missing: {catalogue_path}")
    if not source_path.is_file():
        raise DocumentationLocaleMutationError(f"source page is missing: {source_path}")
    if not pot_path.is_file():
        raise DocumentationLocaleMutationError(f"POT template is missing; run docs-generate-catalogs: {pot_path}")
    try:
        source_path.relative_to(docs_root.resolve())
        pot_path.relative_to((locale_root / "pot").resolve())
    except ValueError as exc:
        raise DocumentationLocaleMutationError("docs translation path escapes the repository") from exc
    return catalogue_path, source_path, pot_path


def _sha256_path(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_catalogue(text: str, locale: str, path: Path) -> Catalog:
    """Parse one PO/POT file with Babel and normalize parser failures."""
    try:
        return read_po(io.StringIO(text), locale=locale, abort_invalid=True)
    except (OSError, UnicodeError, ValueError) as exc:
        raise DocumentationLocaleMutationError(f"cannot parse gettext catalogue {path}: {exc}") from exc


def _message_key(message: Message) -> tuple[str, str]:
    """Return a context-aware stable identity for a Babel message."""
    message_id = message.id
    identity = "\x04".join(message_id) if isinstance(message_id, tuple) else message_id
    return message.context or "", identity


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


def _validate_stale_targets(
    catalogue: Catalog,
    pot: Catalog,
    targets: tuple[_ManifestStale, ...],
    path: Path,
) -> set[tuple[str, str]]:
    """Validate every explicitly authorized stale identity before mutation."""
    catalogue_keys = _all_message_keys(catalogue)
    source_keys = _all_message_keys(pot)
    allowed: set[tuple[str, str]] = set()
    for target in targets:
        identity = _manifest_stale_key(target.context, target.msgid, target.msgid_plural)
        if identity not in catalogue_keys:
            raise DocumentationLocaleMutationError(
                f"remove_stale gettext msgid is not present in {path}: {identity!r}"
            )
        if identity in source_keys:
            raise DocumentationLocaleMutationError(
                f"remove_stale gettext msgid is still present in the POT for {path}: {identity!r}"
            )
        allowed.add(identity)
    return allowed


def _validate_msgids(
    catalogue: Catalog,
    pot: Catalog,
    path: Path,
    *,
    allowed_stale: set[tuple[str, str]] | None = None,
) -> None:
    """Refuse unlisted stale, obsolete, or source-drifted catalogue entries."""
    allowed_stale = set() if allowed_stale is None else allowed_stale
    catalogue_keys = _all_message_keys(catalogue)
    source_keys = _all_message_keys(pot)
    missing = sorted(source_keys - catalogue_keys)
    stale = sorted(catalogue_keys - source_keys)
    unlisted_stale = sorted(stale - allowed_stale)
    unexpected_allowed = sorted(allowed_stale - stale)
    if missing or unlisted_stale or unexpected_allowed:
        raise DocumentationLocaleMutationError(
            f"stale gettext msgids for {path}: missing={missing!r} "
            f"stale={unlisted_stale!r} unexpected_remove_stale={unexpected_allowed!r}"
        )
    obsolete = getattr(catalogue, "obsolete", {})
    if isinstance(obsolete, dict):
        obsolete_keys = sorted(_message_key(message) for message in obsolete.values() if message.id)
        unlisted_obsolete = sorted(set(obsolete_keys) - allowed_stale)
        if unlisted_obsolete:
            raise DocumentationLocaleMutationError(
                f"obsolete gettext msgids for {path}: {unlisted_obsolete!r}"
            )


def _validate_unlisted_fuzzy(catalogue: Catalog, update: _ManifestUpdate, path: Path) -> None:
    """Refuse fuzzy entries unless the manifest explicitly names each one."""
    fuzzy_keys = {_message_key(message) for message in catalogue if message.id and message.fuzzy}
    listed_keys = {
        (message.context or "", message.msgid)
        for message in update.messages
    }
    listed_keys.update(
        _manifest_stale_key(stale.context, stale.msgid, stale.msgid_plural)
        for stale in update.remove_stale
    )
    unlisted = sorted(fuzzy_keys - listed_keys)
    if unlisted:
        raise DocumentationLocaleMutationError(f"unlisted fuzzy gettext msgids in {path}: {unlisted!r}")


def _apply_messages(
    catalogue: Catalog,
    updates: tuple[_ManifestMessage, ...],
    path: Path,
) -> tuple[int, int]:
    """Validate identities, conflicts, and formatting before mutating messages."""
    active = _catalogue_messages(catalogue)
    obsolete = getattr(catalogue, "obsolete", {})
    obsolete_keys = (
        {_message_key(message) for message in obsolete.values() if isinstance(obsolete, dict) and message.id}
        if isinstance(obsolete, dict)
        else set()
    )
    changed = 0
    cleared_fuzzy = 0
    for update in updates:
        identity = (update.context or "", update.msgid)
        if identity in obsolete_keys:
            raise DocumentationLocaleMutationError(f"obsolete gettext msgid in {path}: {identity!r}")
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


def _remove_stale(catalogue: Catalog, targets: tuple[_ManifestStale, ...], path: Path) -> int:
    """Delete explicitly authorized stale active or obsolete messages."""
    if not targets:
        return 0
    active = _catalogue_messages(catalogue)
    obsolete = getattr(catalogue, "obsolete", {})
    for target in targets:
        identity = _manifest_stale_key(target.context, target.msgid, target.msgid_plural)
        message = active.get(identity)
        if message is not None:
            catalogue.delete(message.id, context=message.context)
            continue
        if not isinstance(obsolete, dict):
            raise DocumentationLocaleMutationError(f"remove_stale gettext msgid disappeared from {path}: {identity!r}")
        obsolete_key = next(
            (key for key, candidate in obsolete.items() if candidate.id and _message_key(candidate) == identity),
            None,
        )
        if obsolete_key is None:
            raise DocumentationLocaleMutationError(f"remove_stale gettext msgid disappeared from {path}: {identity!r}")
        del obsolete[obsolete_key]
    return len(targets)


def _validate_format_contract(
    msgid: str,
    current: str,
    replacement: str,
    path: Path,
    identity: tuple[str, str],
) -> None:
    """Require production placeholders and inline documentation tokens to survive."""
    source_placeholders = extract_placeholders(msgid)
    target_placeholders = extract_placeholders(replacement)
    if source_placeholders != target_placeholders:
        raise DocumentationLocaleMutationError(
            f"placeholder mismatch in {path} for {identity!r}: "
            f"source={sorted(source_placeholders)!r} target={sorted(target_placeholders)!r}"
        )
    source_percent = _percent_placeholders(msgid)
    target_percent = _percent_placeholders(replacement)
    if source_percent != target_percent:
        raise DocumentationLocaleMutationError(
            f"percent placeholder mismatch in {path} for {identity!r}: "
            f"source={sorted(source_percent)!r} target={sorted(target_percent)!r}"
        )
    source_inline = _inline_tokens(msgid)
    target_inline = _inline_tokens(replacement)
    if source_inline != target_inline:
        raise DocumentationLocaleMutationError(
            f"inline backtick role/literal mismatch in {path} for {identity!r}: "
            f"source={source_inline!r} target={target_inline!r}"
        )
    # The ``current`` argument is intentionally part of the validator's public
    # call contract: conflicts are checked before format validation, and this
    # assertion keeps accidental future callers from validating another source.
    if not isinstance(current, str):
        raise DocumentationLocaleMutationError(f"non-text gettext translation in {path} for {identity!r}")


def _percent_placeholders(value: str) -> frozenset[str]:
    """Return Python percent-format tokens, excluding the literal ``%%``."""
    return frozenset(candidate for candidate in _PYTHON_PERCENT.findall(value) if candidate != "%%")


def _inline_tokens(value: str) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    """Return exact inline literals, roles, and backtick count."""
    return (
        tuple(sorted(_INLINE_LITERAL.findall(value))),
        tuple(sorted(_RST_ROLE.findall(value))),
        value.count("`"),
    )


def _render_catalogue(catalogue: Catalog) -> str:
    """Render a Babel catalogue while retaining its existing order and header."""
    output = io.BytesIO()
    write_po(output, catalogue, sort_output=False, sort_by_file=False, ignore_obsolete=False)
    return output.getvalue().decode(UTF_8)


__all__ = ["DocumentationLocaleMutationError", "apply_manifest"]
