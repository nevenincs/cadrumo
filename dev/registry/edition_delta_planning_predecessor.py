"""Select a candidate predecessor and report temporal blocking causes."""

from __future__ import annotations

from collections.abc import Sequence

from cadrumo.domain.calculations.registry.revision_order import revisions_coexist
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from . import edition_delta_assessment_lineage, edition_delta_source, edition_delta_types


def choose_predecessor(
    position: int,
    ordered: Sequence[ModeloRevision],
    source: edition_delta_source.EditionSource,
    *,
    reconsider_technical_roots: bool = False,
) -> tuple[str | None, edition_delta_types.PredecessorBasis, list[edition_delta_types.BlockedCause]]:
    """Pick the edition's storage predecessor (declared baseline, else adjacent revision) and any blocking causes."""
    storage_baseline = source.manifest.get("casilla_storage_baseline")
    if isinstance(storage_baseline, str):
        return storage_baseline, edition_delta_types.PredecessorBasis.STORAGE, []
    declared = source.manifest.get("predecessor")
    if isinstance(declared, str):
        return declared, edition_delta_types.PredecessorBasis.DECLARED, []
    if isinstance(declared, dict) and not (
        reconsider_technical_roots and edition_delta_assessment_lineage.technical_root(source.manifest)
    ):
        return None, edition_delta_types.PredecessorBasis.DECLARED_ROOT, []
    if position == 0:
        return None, edition_delta_types.PredecessorBasis.FIRST, []
    earlier, current = ordered[position - 1], ordered[position]
    causes: list[edition_delta_types.BlockedCause] = []
    if revisions_coexist(earlier, current):
        causes.append(edition_delta_types.BlockedCause.OVERLAPPING_PREDECESSOR)
    return str(earlier.id), edition_delta_types.PredecessorBasis.STORAGE, causes
