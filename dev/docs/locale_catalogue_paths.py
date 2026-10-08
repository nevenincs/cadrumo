"""Authorized documentation catalogue paths and source digests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .locale_mutation_contracts import DocumentationLocaleMutationError, ManifestUpdate


def _source_pages(docs_root: Path) -> dict[str, Path]:
    """Return the authorized PO-to-source page mapping from the i18n owner."""
    from .i18n import user_scope_source_pages

    return {Path(page).with_suffix(".po").as_posix(): docs_root / page for page in user_scope_source_pages(docs_root)}


def _resolve_update_paths(
    update: ManifestUpdate,
    *,
    locale_root: Path,
    docs_root: Path,
    source_pages: dict[str, Path],
) -> tuple[Path, Path, Path]:
    """Resolve one catalogue and its source/template without path widening."""
    relative = _validated_catalogue_relative(update)
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


def _validated_catalogue_relative(update: ManifestUpdate) -> Path:
    """Validated catalogue relative."""
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
    return relative
