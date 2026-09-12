"""Public grammar facts shared by the mutable registry loader and its fixtures."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import collection_shaped_fields

from .loader_cache import fragment_sort_key


def _compute_revision_section_fields() -> frozenset[str]:
    """Return ModeloRevision fields that are per-section fragment content."""
    return frozenset({"completeness_manifest", *collection_shaped_fields(ModeloRevision)})


REVISION_SECTION_FIELDS: frozenset[str] = _compute_revision_section_fields()
"""Revision fields whose values belong in directory-mode section fragments."""


def revision_section_fragment_paths(section_dirs: tuple[Path, ...]) -> tuple[Path, ...]:
    """Collect every section directory's fragments, refusing an empty section."""
    fragments: list[Path] = []
    for section_dir in section_dirs:
        section_fragments = scan_directory(section_dir, pattern="*.toml", select=DirectoryEntryKind.FILES)
        if not section_fragments:
            raise RegistryLoadError(f"{section_dir}: revision section fragment directory contains no TOML fragments")
        fragments.extend(section_fragments)
    return tuple(sorted(fragments, key=fragment_sort_key))


__all__ = ["REVISION_SECTION_FIELDS", "revision_section_fragment_paths"]
