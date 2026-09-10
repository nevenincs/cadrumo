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
from .schema import REVISION_GOVERNANCE_FIELDS

_REVIEW_STATUS_FIELD = "review_status"
_PENDING_REVIEW = "pending_review"

#: The governance keys that make up a review CLAIM. Authorship is the one stamp
#: field that says nothing about coverage; every other governance field,
#: including any added later, is withdrawn with the claim rather than carried
#: onto a full copy it never covered.
_REVIEW_CLAIM_FIELDS = REVISION_GOVERNANCE_FIELDS - {"engineered_by"}


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

    A review stamp does not survive materialisation. A delta edition's review
    covers the rows it states, judged against the predecessor it names; the full
    copy names no predecessor and states every row, including the ones that
    reviewer never read, so the claim cannot move onto it. The table therefore
    declares ``review_status = "pending_review"`` and none of the reviewer, date
    or scope keys, and ``withdrawn_review_status`` records the status the
    edition declared so a caller can report what was set aside. Authorship is
    kept: who built the rows is unchanged by where they are written. An edition
    that states every row keeps its stamp, because its table is its review's
    whole scope.
    """

    modelo_id: str
    revision_id: str
    table: Mapping[str, object]
    inherits_from: str | None
    label_origins: tuple[str | None, ...] | None
    withdrawn_review_status: str | None = None


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
    declared_status = materialised.get(_REVIEW_STATUS_FIELD, _PENDING_REVIEW)
    table = {
        key: value
        for key, value in materialised.items()
        if key != _PREDECESSOR_FIELD and key not in _REVIEW_CLAIM_FIELDS
    }
    table[_REVIEW_STATUS_FIELD] = _PENDING_REVIEW
    return MaterialisedEdition(
        modelo_id=modelo_id,
        revision_id=revision_id,
        table=table,
        inherits_from=predecessor,
        label_origins=resolution.label_origins.get(revision_id),
        withdrawn_review_status=None if declared_status == _PENDING_REVIEW else str(declared_status),
    )
