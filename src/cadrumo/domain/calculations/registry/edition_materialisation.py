"""The complete raw revision table one edition of a directory-mode modelo stands for.

An edition that names a predecessor states only the casillas that are new or
that differ; the loader resolves the rest from the predecessor chain. Tooling
that copies, stages or rewrites a single edition must therefore work from the
resolved edition, never from the rows the edition happens to state, or it
presents a fragment as a complete edition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ._loader_internals import (
    _PREDECESSOR_FIELD,
    _load_modelo_manifest,
    _load_modelo_revisions,
    _materialise_revisions,
)
from ._toml_helpers import as_toml_table
from .errors import RegistryLoadError
from .loader_cache import validate_modelo_directory_source


@dataclass(frozen=True, slots=True)
class MaterialisedEdition:
    """One edition resolved into the full-copy raw revision table it stands for.

    ``table`` has the shape a ``[revisions."<id>"]`` table declares on disk and
    carries no named predecessor, so written back as the edition's only source
    it validates without any other edition present. ``inherits_from`` is the
    predecessor the edition names, or ``None`` for an edition that states every
    row itself, whose table is then exactly the declared one.

    ``label_origins`` is aligned with the table's casilla rows: for each row,
    the edition that last stated it, or ``None`` where this edition states it.
    Casilla labels are catalogued per edition, so an inherited row's text lives
    under its origin edition's key; tooling that writes the edition out as a
    full copy needs the origins to carry those labels with it. It is ``None``
    when the edition inherits nothing.
    """

    modelo_id: str
    revision_id: str
    table: Mapping[str, object]
    inherits_from: str | None
    label_origins: tuple[str | None, ...] | None


def materialise_edition(modelo_directory: Path, revision_id: str) -> MaterialisedEdition:
    """Resolve one edition of a directory-mode modelo into its complete raw revision table.

    Every edition of the modelo is read, because the predecessor graph is
    validated as a whole and an edition's inherited rows come from its chain.
    The resolution is the loader's own; nothing here merges rows.

    Raises:
        RegistryLoadError: When the modelo tree is malformed, ``revision_id`` is
            not one of its editions, the predecessor graph is invalid (including
            a named predecessor that is absent from the tree), or the chain
            cannot be resolved without a guess.
    """
    resolved = modelo_directory.resolve()
    validate_modelo_directory_source(resolved)
    manifest = _load_modelo_manifest(resolved)
    modelo_table = as_toml_table(manifest.get("modelo"))
    modelo_id = None if modelo_table is None else modelo_table.get("id")
    if not isinstance(modelo_id, str):
        raise RegistryLoadError(f"{resolved}: manifest.toml must declare a string [modelo].id")
    raw_revisions = _load_modelo_revisions(resolved)
    if revision_id not in raw_revisions:
        raise RegistryLoadError(
            f"{resolved}: modelo {modelo_id!r} has no edition {revision_id!r}; editions are {sorted(raw_revisions)!r}",
        )
    declared = as_toml_table(raw_revisions[revision_id])
    if declared is None:
        raise RegistryLoadError(f"{resolved}: revision {revision_id!r} must be a table")
    resolution = _materialise_revisions(resolved, modelo_id, raw_revisions)
    materialised = as_toml_table(resolution.revisions[revision_id])
    if materialised is None:
        raise RegistryLoadError(f"{resolved}: revision {revision_id!r} must be a table")
    predecessor = declared.get(_PREDECESSOR_FIELD)
    if not isinstance(predecessor, str):
        return MaterialisedEdition(
            modelo_id=modelo_id,
            revision_id=revision_id,
            table=materialised,
            inherits_from=None,
            label_origins=None,
        )
    return MaterialisedEdition(
        modelo_id=modelo_id,
        revision_id=revision_id,
        table={key: value for key, value in materialised.items() if key != _PREDECESSOR_FIELD},
        inherits_from=predecessor,
        label_origins=resolution.label_origins.get(revision_id),
    )
