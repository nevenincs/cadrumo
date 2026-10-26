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
sets ``clear_fuzzy: true``.  Active stale catalogue entries can be removed
only by an exact identity in the update's ``remove_stale`` list; Babel
obsolete entries use the separate ``remove_obsolete`` list, including when an
obsolete identity is also active in the current POT."""

from __future__ import annotations

from pathlib import Path

from dev._paths import REPO_ROOT
from dev.locales.write_guard import catalogue_write_guard

from .locale_catalogue_paths import _source_pages
from .locale_catalogue_preparation import _prepare_catalogue_update
from .locale_manifest import _parse_updates, _read_manifest
from .locale_mutation_contracts import _SCHEMA_VERSION, PreparedCatalogue


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
    prepared: list[PreparedCatalogue] = []
    requested_messages = sum(len(update.messages) for update in updates)

    # One shared lock spans read, validation, and publication. Every catalogue
    # is fully prepared before any write, so a later refusal leaves the batch
    # untouched.
    with catalogue_write_guard(locale_root) as guard:
        for update in updates:
            _prepare_catalogue_update(update, locale_root, docs_root, source_pages, guard, prepared)

        if not dry_run:
            for item in prepared:
                if item.rendered != item.original:
                    guard.write_text(item.path, item.rendered)

    return _manifest_result(prepared, requested_messages, dry_run)


def _manifest_result(prepared: list[PreparedCatalogue], requested_messages: int, dry_run: bool) -> dict[str, object]:
    """Manifest result."""
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
        "removed_obsolete_messages": sum(item.removed_obsolete_messages for item in prepared),
        "written_catalogues": 0 if dry_run else changed_catalogues,
    }
