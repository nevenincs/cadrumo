"""The export section's fragment-directory grammar.

One revision section is authored under two directory names, and the difference
is not cosmetic: ``export/`` is the generator-owned tree and carries the
generation provenance manifest, while ``export_layouts/`` is hand-authored and
never does.  Both merge into the ``export_layouts`` section.

This lives in its own module because both the fragment-name validator in
``loader_cache`` and the section grammar in ``loader_grammar`` need it, and
those two already form an import edge; a consumer that spells the alias or the
manifest filename itself disagrees with the loader the moment either changes.
"""

from __future__ import annotations

from pathlib import Path

#: The one section whose fragment directory is not spelled like its field.
#: ``export/`` holds the generator-owned tree and carries
#: :data:`GENERATED_EXPORT_PROVENANCE_FILENAME`; ``export_layouts/`` holds a
#: hand-authored one and never does. Both merge into the ``export_layouts``
#: section, so the alias lives here once rather than being re-derived at every
#: boundary that walks a revision directory.
EXPORT_SECTION_DIRECTORY_NAMES: frozenset[str] = frozenset({"export", "export_layouts"})
GENERATED_EXPORT_DIRECTORY_NAME: str = "export"
GENERATED_EXPORT_PROVENANCE_FILENAME: str = "_generation.provenance.json"


def revision_section_for_directory(directory_name: str) -> str:
    """Return the revision section a fragment directory declares.

    Every section directory is named for its field except the generator-owned
    export tree, which is spelled ``export``.  Resolving that here keeps one
    answer: a consumer that spells the alias itself will disagree with the
    loader the moment the mapping changes.
    """
    if directory_name == GENERATED_EXPORT_DIRECTORY_NAME:
        return "export_layouts"
    return directory_name


def is_generated_export_provenance(entry: Path, revision_root: Path) -> bool:
    """Whether ``entry`` is the generator's provenance manifest for ``revision_root``.

    The one non-TOML artefact a revision fragment tree may carry, and only
    inside the generator-owned ``export/`` directory: a hand-authored
    ``export_layouts/`` tree has no generation to attest.
    """
    return (
        entry.name == GENERATED_EXPORT_PROVENANCE_FILENAME
        and entry.parent == revision_root / GENERATED_EXPORT_DIRECTORY_NAME
    )


__all__ = [
    "EXPORT_SECTION_DIRECTORY_NAMES",
    "GENERATED_EXPORT_DIRECTORY_NAME",
    "GENERATED_EXPORT_PROVENANCE_FILENAME",
    "is_generated_export_provenance",
    "revision_section_for_directory",
]
