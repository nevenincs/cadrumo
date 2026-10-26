"""Prepare every catalogue under the shared publication guard."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dev._paths import UTF_8
from dev.locales.write_guard import CatalogueWriteGuard

from .locale_catalogue_io import _parse_catalogue, _render_catalogue
from .locale_catalogue_messages import _apply_messages
from .locale_catalogue_paths import _resolve_update_paths, _sha256_path
from .locale_catalogue_targets import (
    _remove_obsolete,
    _remove_stale,
    _validate_msgids,
    _validate_obsolete_targets,
    _validate_stale_targets,
    _validate_unlisted_fuzzy,
)
from .locale_mutation_contracts import DocumentationLocaleMutationError, ManifestUpdate, PreparedCatalogue


def _prepare_catalogue_update(
    update: ManifestUpdate,
    locale_root: Path,
    docs_root: Path,
    source_pages: dict[str, Path],
    guard: CatalogueWriteGuard,
    prepared: list[PreparedCatalogue],
) -> None:
    """Prepare catalogue update."""
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
    allowed_obsolete = _validate_obsolete_targets(catalogue, update.remove_obsolete, catalogue_path)
    _validate_msgids(
        catalogue,
        pot,
        catalogue_path,
        allowed_stale=allowed_stale,
        allowed_obsolete=allowed_obsolete,
    )
    _validate_unlisted_fuzzy(catalogue, update, catalogue_path)
    changed_messages, cleared_fuzzy_messages = _apply_messages(catalogue, update.messages, catalogue_path)
    removed_stale_messages = _remove_stale(catalogue, update.remove_stale, catalogue_path)
    removed_obsolete_messages = _remove_obsolete(catalogue, update.remove_obsolete, catalogue_path)
    rendered = _render_catalogue(catalogue)
    prepared.append(
        PreparedCatalogue(
            path=catalogue_path,
            original=catalogue_text,
            rendered=rendered,
            changed_messages=changed_messages,
            cleared_fuzzy_messages=cleared_fuzzy_messages,
            removed_stale_messages=removed_stale_messages,
            removed_obsolete_messages=removed_obsolete_messages,
        )
    )
