"""Development-only materialisation of raw directory-mode modelo editions.

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

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ._loader_internals import (
    _PREDECESSOR_FIELD,
    _load_modelo_manifest,
    _load_modelo_revisions,
    _materialise_revisions,
)
from ._toml_helpers import as_toml_table
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

    Edge-local casilla attestations are projected into their validated row
    claims before the predecessor is removed. A sidecar whose evidence cannot
    be represented inline without loss is refused, not silently dropped.

    Review metadata survives materialisation unchanged. It records what was
    examined, including any historical comparison reference, rather than the
    physical inheritance edge being removed here.
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
        RegistryLoadError: When a predecessor-dependent attestation has no
            lossless inline representation in the detached edition.
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
    table = {key: value for key, value in materialised.items() if key != _PREDECESSOR_FIELD}
    if table.get("lineage_attestations"):
        table = _inline_lineage_claims(resolved, revision_id, table)
    return MaterialisedEdition(
        modelo_id=modelo_id,
        revision_id=revision_id,
        table=table,
        inherits_from=predecessor,
        label_origins=resolution.label_origins.get(revision_id),
        withdrawn_review_status=None,
    )


def _inline_lineage_claims(modelo_directory: Path, revision_id: str, table: dict[str, object]) -> dict[str, object]:
    """Detach validated casilla claims without losing their evidence ownership.

    The public loader validates the exact edge and projects its claims onto the
    typed rows. Reuse that projection rather than interpreting raw sidecars.
    Only a lossless inline representation can replace an edge-local sidecar:
    other families, or evidence citing different references from its row, need
    an explicit representation contract before they can be detached.
    """
    from .loader import load_modelo_directory

    revision = load_modelo_directory(modelo_directory).revisions[revision_id]
    rows_by_lineage = {str(row.continuidad_id): row for row in revision.casillas if row.continuidad_id is not None}
    claims: dict[str, dict[str, object]] = {}
    for attestation in revision.lineage_attestations:
        if attestation.family != "casillas":
            raise RegistryLoadError(
                f"{modelo_directory}: edition {revision_id!r} cannot detach lineage attestation "
                f"for family {attestation.family!r}, which has no inline lineage claim representation"
            )
        row = rows_by_lineage[attestation.identity]
        if row.legal_refs != attestation.legal_refs or row.source_refs != attestation.source_refs:
            raise RegistryLoadError(
                f"{modelo_directory}: edition {revision_id!r} cannot detach lineage attestation "
                f"for {attestation.identity!r} without losing its distinct legal_refs or source_refs"
            )
        claims[attestation.identity] = row.model_dump(
            include={"continuidad_origin", "continuidad_evidence"}, mode="json", exclude_none=True
        )
    rows = table.get("casillas", ())
    if not isinstance(rows, tuple | list):
        raise RegistryLoadError(f"{modelo_directory}: edition {revision_id!r} casillas must be an array")
    projected_rows = []
    for raw_row in rows:
        row = as_toml_table(raw_row)
        if row is None:
            raise RegistryLoadError(f"{modelo_directory}: edition {revision_id!r} casilla must be a table")
        projected_rows.append({**row, **claims.get(str(row.get("continuidad_id")), {})})
    return {
        **{key: value for key, value in table.items() if key != "lineage_attestations"},
        "casillas": tuple(projected_rows),
    }
