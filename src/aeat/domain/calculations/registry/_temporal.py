"""Temporal selection for registry-backed modelo revisions."""

from __future__ import annotations

from datetime import date

from ._errors import RegistrySnapshotError
from ._schema import ModeloDefinition, ModeloRevision


def select_revision(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> ModeloRevision:
    """Select exactly one revision for a filing period."""

    candidates = []
    for revision in modelo.revisions.values():
        if revision_id is not None and revision.id != revision_id:
            continue
        if not revision.period_selector.includes_year(filing_year):
            continue
        # Case-insensitive comparison is intentional: _resolve_period() in the
        # declaracion parser calls .upper() on every period string before it
        # reaches the registry, producing "ALTA"/"MODIFICACION"/"BAJA" for M036
        # whose canonical registry periods are lowercase.  All other period
        # formats ("0A", "1T".."4T", "01".."12") are case-invariant, so the
        # normalisation is harmless for them.  Downstream consumers receive the
        # caller-supplied period (the RegistrySnapshot stores it verbatim), not
        # the registry's canonical form, so no case-sensitive downstream
        # regression is possible from this comparison.
        if period.lower() not in {p.lower() for p in revision.period_selector.periods}:
            continue
        if on is not None and (revision.valid_from > on or (revision.valid_to is not None and revision.valid_to < on)):
            continue
        candidates.append(revision)
    if not candidates:
        raise RegistrySnapshotError(
            f"modelo {modelo.id}: no revision for year={filing_year!r} period={period!r} revision={revision_id!r}"
        )
    if len(candidates) > 1:
        ids = ", ".join(sorted(revision.id for revision in candidates))
        raise RegistrySnapshotError(f"modelo {modelo.id}: ambiguous revision selection: {ids}")
    return candidates[0]
