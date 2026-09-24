"""Refusal of a saved calculation that stores a scalar input for a detail-row casilla.

A casilla an export record fills once per detail row has no single value, so
calculate refuses a scalar input for one. A revision saved before that refusal
may still carry such an input with no registry-grounded observation. Verify and
amend both read stored inputs, so both run this one gate before trusting them.
"""

from __future__ import annotations

from ...core.authority_grade import RegistryAuthorityGrade
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import StoredRowFieldScalarInputError


def refuse_stored_row_field_scalar_inputs(
    revision: CalculationRevision,
    *,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse a saved revision holding a scalar input for a casilla an export record fills per row.

    Raises:
        StoredRowFieldScalarInputError: When ``revision`` stores such an input;
            the error names the casillas, the revision and the work unit to
            recalculate.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    stored = sorted(
        set(revision.input_values_by_casilla_id).intersection(row_field_template_records_by_casilla(snapshot.revision))
    )
    if stored:
        raise StoredRowFieldScalarInputError(
            translated_message="errors.refused.refused_modelo_stored_row_field_input",
            context={
                "casilla_ids": ",".join(stored),
                "calculation_revision_id": revision.calculation_revision_id,
                "work_unit_id": work_unit.work_unit_id,
            },
        )


__all__ = ["refuse_stored_row_field_scalar_inputs"]
