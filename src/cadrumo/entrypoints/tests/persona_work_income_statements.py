"""The statement a persona makes that the work-income boxes no payer certificate fills hold nothing.

A Modelo 100 resting on a work-income record cannot state the employer's
pension and dependency contributions, the patrimonio protegido contribution or
other imputed work income: no payer certificate carries them, and leaving one
out could lower the tax. The work form offers the filer one statement that
they hold nothing. A persona's ``[[work_income_none_statements]]`` make it, for
the ejercicios they name, through the same form read, edit baseline and guarded
edit that the filer's own frontend uses; a persona that states nothing makes
none, so the declaration meets the application's own findings.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from ...application.modelo.absence_statement_submission import absence_statement_submission
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...tests.personas import WorkIncomeNoneStatement, YearEnvelope
from .persona_prior_values import PriorValueAttestationError, SettleOperation

_MODELO = "100"


def states_for(
    statements: Sequence[WorkIncomeNoneStatement], envelope: YearEnvelope, *, modelo: str, filing_year: int
) -> bool:
    """Whether the persona states the work income of the Modelo 100 of ``filing_year`` is none."""
    return modelo == _MODELO and any(item.ejercicio.resolve(envelope) == filing_year for item in statements)


def state_work_income_none(
    statements: Sequence[WorkIncomeNoneStatement],
    *,
    envelope: YearEnvelope,
    profile_id: UUID,
    modelo: str,
    filing_year: int,
    work_unit_id: str,
    settle: SettleOperation,
) -> bool:
    """Submit the statement the form offers for the return, when the persona makes it; whether it was applied.

    Nothing is submitted where the form offers no such statement: the return rests on no
    work-income record, or the statement was made already. The caller recalculates after a submission.
    """
    if not states_for(statements, envelope, modelo=modelo, filing_year=filing_year):
        return False
    form = settle(
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(profile_id=profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.EN),
        subject=work_unit_id,
    )
    if not isinstance(form, ModeloWorkbenchFormProjectionV1):
        raise PriorValueAttestationError(f"{work_unit_id}: the workbench form read published no projection")
    attestations = form.form.form.carry_attestations
    family = AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED
    if form.admitted_baseline is None or not any(item.family is family for item in attestations):
        return False
    submission = absence_statement_submission(form.admitted_baseline.to_baseline(), attestations, family=family)
    operator_input = ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
    )
    applied = settle(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, operator_input, subject=work_unit_id)
    if not isinstance(applied, ModeloEditApplyPublicResultV1):
        raise PriorValueAttestationError(f"{work_unit_id}: the work-income statement published no edit receipt")
    return True


__all__ = ["state_work_income_none", "states_for"]
