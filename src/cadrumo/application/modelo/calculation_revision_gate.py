"""Single application gate for persisted calculation-revision coordinates."""

from __future__ import annotations

from ...domain.modelos.calculation_revision import CalculationRevision
from ..calculations.revision_carry_gate import revision_carry_outcome
from .action_errors import WorkUnitRevisionDivergenceError


def require_calculation_revision_coordinates_current(revision: CalculationRevision) -> None:
    """Refuse a persisted calculation whose producing registry coordinate diverges."""
    outcome = revision_carry_outcome(revision.registry_snapshot_ref)
    if not outcome.refused:
        return
    snapshot_ref = revision.registry_snapshot_ref
    raise WorkUnitRevisionDivergenceError(
        translated_message="application.modelo.errors.work_unit_revision_divergence",
        context={
            "work_unit_id": revision.work_unit_id,
            "modelo": str(snapshot_ref.modelo),
            "filing_year": str(snapshot_ref.modelo_year),
            "period": str(snapshot_ref.period),
            "work_unit_revision": str(snapshot_ref.revision_id),
            "law_revision": str(outcome.selected_revision_id or "unresolvable"),
        },
    )


__all__ = ["require_calculation_revision_coordinates_current"]
