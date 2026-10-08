"""Exact stale, obsolete, and fuzzy catalogue target validation."""

from __future__ import annotations

from pathlib import Path

from babel.messages.catalog import Catalog

from .locale_catalogue_io import _catalogue_messages, _manifest_stale_key, _message_key
from .locale_mutation_contracts import DocumentationLocaleMutationError, ManifestStale, ManifestUpdate


def _validate_stale_targets(
    catalogue: Catalog,
    pot: Catalog,
    targets: tuple[ManifestStale, ...],
    path: Path,
) -> set[tuple[str, str]]:
    """Validate explicitly authorized active identities absent from the POT."""
    active_keys = set(_catalogue_messages(catalogue))
    obsolete_keys = {_message_key(message) for message in catalogue.obsolete.values() if message.id}
    source_keys = set(_catalogue_messages(pot))
    allowed: set[tuple[str, str]] = set()
    for target in targets:
        identity = _manifest_stale_key(target.context, target.msgid, target.msgid_plural)
        if identity not in active_keys:
            if identity in obsolete_keys:
                raise DocumentationLocaleMutationError(
                    f"remove_stale gettext msgid is obsolete in {path}: {identity!r}; use remove_obsolete"
                )
            raise DocumentationLocaleMutationError(f"remove_stale gettext msgid is not active in {path}: {identity!r}")
        if identity in source_keys:
            raise DocumentationLocaleMutationError(
                f"remove_stale gettext msgid is still present in the POT for {path}: {identity!r}"
            )
        allowed.add(identity)
    return allowed


def _validate_obsolete_targets(
    catalogue: Catalog,
    targets: tuple[ManifestStale, ...],
    path: Path,
) -> set[tuple[str, str]]:
    """Validate exact identities in Babel's obsolete mapping."""
    obsolete_keys = {_message_key(message) for message in catalogue.obsolete.values() if message.id}
    allowed: set[tuple[str, str]] = set()
    for target in targets:
        identity = _manifest_stale_key(target.context, target.msgid, target.msgid_plural)
        if identity not in obsolete_keys:
            raise DocumentationLocaleMutationError(
                f"remove_obsolete gettext msgid is not present in the obsolete catalogue for {path}: {identity!r}"
            )
        allowed.add(identity)
    return allowed


def _validate_msgids(
    catalogue: Catalog,
    pot: Catalog,
    path: Path,
    *,
    allowed_stale: set[tuple[str, str]] | None = None,
    allowed_obsolete: set[tuple[str, str]] | None = None,
) -> None:
    """Refuse unlisted active-stale, obsolete, or source-drifted entries."""
    allowed_stale = set() if allowed_stale is None else allowed_stale
    allowed_obsolete = set() if allowed_obsolete is None else allowed_obsolete
    catalogue_keys = set(_catalogue_messages(catalogue))
    source_keys = set(_catalogue_messages(pot))
    missing = sorted(source_keys - catalogue_keys)
    stale = catalogue_keys - source_keys
    unlisted_stale = sorted(stale - allowed_stale)
    unexpected_allowed = sorted(allowed_stale - stale)
    if missing or unlisted_stale or unexpected_allowed:
        raise DocumentationLocaleMutationError(
            f"stale gettext msgids for {path}: missing={missing!r} "
            f"stale={unlisted_stale!r} unexpected_remove_stale={unexpected_allowed!r}"
        )
    obsolete_keys = {_message_key(message) for message in catalogue.obsolete.values() if message.id}
    unlisted_obsolete = sorted(obsolete_keys - allowed_obsolete)
    unexpected_obsolete = sorted(allowed_obsolete - obsolete_keys)
    if unlisted_obsolete or unexpected_obsolete:
        raise DocumentationLocaleMutationError(
            f"obsolete gettext msgids for {path}: {unlisted_obsolete!r} "
            f"unexpected_remove_obsolete={unexpected_obsolete!r}"
        )


def _validate_unlisted_fuzzy(catalogue: Catalog, update: ManifestUpdate, path: Path) -> None:
    """Refuse fuzzy entries unless the manifest explicitly names each one."""
    fuzzy_keys = {_message_key(message) for message in catalogue if message.id and message.fuzzy}
    listed_keys = {(message.context or "", message.msgid) for message in update.messages}
    listed_keys.update(
        _manifest_stale_key(stale.context, stale.msgid, stale.msgid_plural) for stale in update.remove_stale
    )
    unlisted = sorted(fuzzy_keys - listed_keys)
    if unlisted:
        raise DocumentationLocaleMutationError(f"unlisted fuzzy gettext msgids in {path}: {unlisted!r}")


def _remove_stale(catalogue: Catalog, targets: tuple[ManifestStale, ...], path: Path) -> int:
    """Delete explicitly authorized active messages absent from the POT."""
    if not targets:
        return 0
    active = _catalogue_messages(catalogue)
    for target in targets:
        identity = _manifest_stale_key(target.context, target.msgid, target.msgid_plural)
        message = active.get(identity)
        if message is None:
            raise DocumentationLocaleMutationError(
                f"remove_stale gettext msgid disappeared from active catalogue {path}: {identity!r}"
            )
        catalogue.delete(message.id, context=message.context)
    return len(targets)


def _remove_obsolete(catalogue: Catalog, targets: tuple[ManifestStale, ...], path: Path) -> int:
    """Delete only the exact Babel obsolete mappings named by the manifest."""
    if not targets:
        return 0
    obsolete = catalogue.obsolete
    for target in targets:
        identity = _manifest_stale_key(target.context, target.msgid, target.msgid_plural)
        obsolete_key = next(
            (key for key, candidate in obsolete.items() if candidate.id and _message_key(candidate) == identity),
            None,
        )
        if obsolete_key is None:
            raise DocumentationLocaleMutationError(
                f"remove_obsolete gettext msgid disappeared from {path}: {identity!r}"
            )
        del obsolete[obsolete_key]
    return len(targets)
