"""The interim refusal of an export that rests on savings occurrences.

The official design writes each savings occurrence as a per-position detail
record under the interest and dividend boxes. Until the export places those
records, a return whose calculation rested on any occurrence is refused at
export. The trigger is the calculation's own recorded provenance, never a box
value, so a return with no occurrence exports as before. Calculation and
verification never read this gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.calculation_revision_sources import capital_mobiliario_occurrence_refs
from .export_contracts import ModeloExportSavingsDetailRecordsUnwritableError
from .preconditions import build_modelo_precondition_failure_for_scenario

if TYPE_CHECKING:
    from ...domain.modelos.calculation_revision import CalculationRevision

__all__ = ["require_savings_detail_records_exportable"]


def require_savings_detail_records_exportable(revision: CalculationRevision) -> None:
    """Refuse the export of a :class:`CalculationRevision` that rested on savings occurrences.

    Raises:
        ModeloExportSavingsDetailRecordsUnwritableError: When the calculation recorded any occurrence.
    """
    occurrences = capital_mobiliario_occurrence_refs(row.source_ref for row in revision.source_provenance)
    if not occurrences:
        return
    raise ModeloExportSavingsDetailRecordsUnwritableError(
        translated_message="application.modelo.errors.export_savings_detail_records_unwritable",
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "occurrence_count": len(occurrences),
        },
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.export",
            scenario_id="modelo.export.savings_detail_records.unwritable",
            evidence_id="modelo.export.savings_detail_records",
            evidence_values={
                "calculation_revision_id": revision.calculation_revision_id,
                "occurrence_count": len(occurrences),
                "writable": False,
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )
