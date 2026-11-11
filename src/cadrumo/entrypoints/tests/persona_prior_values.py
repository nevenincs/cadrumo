"""The figures a persona states for earlier returns the application does not hold.

A persona's ``[[attested_prior_values]]`` are operator statements of a value a
return reads from an earlier return, for the case where that earlier return
lies outside what the application can hold. The replay submits one through the
registered ``modelo.edit.apply`` operation as the operator's attestation of the
prior value, never as a plain override. It submits only what the application
itself offers: the edit admission offers the attestation for a binding only
while the application holds no work unit, filing record or observation of the
source, so a held source governs and the entry is left unsubmitted.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditMutationFamily,
    ModeloEditSubmissionV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from ...application.modelo.edit_operator_input import (
    ModeloEditOperatorInputV2,
    PreparedModeloEditOperand,
    prepare_modelo_edit_operand,
)
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from ...application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...core.external_constants import OutputLanguage
from ...tests.personas import AttestedPriorValue, YearEnvelope


class PriorValueAttestationError(RuntimeError):
    """The registered operations did not answer an attestation the way the replay needs."""


class SettleOperation(Protocol):
    """Settle one registered operation of the persona's profile and return its public result."""

    def __call__(
        self,
        definition_id: str,
        payload: BaseModel,
        *,
        subject: str | None = None,
        operand: PreparedModeloEditOperand | None = None,
    ) -> BaseModel | None:
        """Submit ``payload`` against ``subject``, binding ``operand`` to the operation, and settle it."""
        ...


def entries_for(
    entries: Sequence[AttestedPriorValue], envelope: YearEnvelope, calculated: ModeloWorkCalculatePublicResultV3
) -> tuple[AttestedPriorValue, ...]:
    """The entries that state a figure for the return ``calculated`` is."""
    unit = calculated.unit
    return tuple(
        entry
        for entry in entries
        if entry.modelo == unit.modelo
        and entry.period == unit.period.code
        and entry.year.resolve(envelope) == unit.filing_year
    )


def attest_prior_values(
    entries: Sequence[AttestedPriorValue],
    *,
    envelope: YearEnvelope,
    profile_id: UUID,
    calculated: ModeloWorkCalculatePublicResultV3,
    settle: SettleOperation,
) -> bool:
    """Submit the attestation of each entry of the calculated return the application offers; whether any was applied.

    Nothing is submitted for an entry whose binding the admitted baseline does
    not offer the attestation on: the application then holds the source, and
    the source governs. The caller recalculates after a submission.
    """
    matching = entries_for(entries, envelope, calculated)
    if not matching:
        return False
    work_unit_id = calculated.work_unit_id
    form = settle(
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(profile_id=profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.EN),
        subject=work_unit_id,
    )
    if not isinstance(form, ModeloWorkbenchFormProjectionV1):
        raise PriorValueAttestationError(f"{work_unit_id}: the workbench form read published no projection")
    if form.admitted_baseline is None:
        return False
    baseline = form.admitted_baseline.to_baseline()
    offered = {
        surface.binding_id
        for surface in baseline.permitted_surface
        if isinstance(surface, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE in surface.allowed_intents
    }
    intents = tuple(
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=entry.binding),
            kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
            value=entry.value,
        )
        for entry in matching
        if entry.binding in offered
    )
    if not intents:
        return False
    submission = ModeloEditSubmissionV1(
        baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, binding_intents=intents
    )
    prepared = prepare_modelo_edit_operand(
        definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        profile_id=profile_id,
        subject_ref=work_unit_id,
        input_json=ModeloEditOperatorInputV2(
            submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
        ).model_dump_json(),
    )
    applied = settle(
        MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, prepared.request, subject=work_unit_id, operand=prepared
    )
    if not isinstance(applied, ModeloEditApplyPublicResultV1):
        raise PriorValueAttestationError(f"{work_unit_id}: the attestation published no edit receipt")
    return True


__all__ = ["PriorValueAttestationError", "SettleOperation", "attest_prior_values", "entries_for"]
