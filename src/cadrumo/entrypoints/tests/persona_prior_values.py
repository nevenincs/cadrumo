"""The figures a persona states for earlier returns the application does not hold.

A persona's ``[[attested_prior_values]]`` are operator statements of a value a
return reads from an earlier return, for the case where that earlier return
lies outside what the application can hold. The replay submits one through the
registered ``modelo.edit.apply`` operation as the operator's attestation of the
prior value, never as a plain override. It submits only what the application
itself offers: the edit admission offers the attestation for a binding only
while the application holds no work unit, filing record or observation of the
source, so a held source governs and the entry is left unsubmitted. The
attestation is keyed on the return's work unit rather than on a calculation,
so a return whose calculation refuses until the figure is stated is attested
before it is ever calculated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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
)
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from ...application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...domain.calculations.registry.errors import RegistryError
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
    ) -> BaseModel | None:
        """Submit ``payload`` against ``subject`` and settle it; an edit's operator input is staged as its operand."""
        ...


def entries_on(
    entries: Sequence[AttestedPriorValue], envelope: YearEnvelope, *, modelo: str, filing_year: int, period: str
) -> tuple[AttestedPriorValue, ...]:
    """The entries that state a figure for the return of ``modelo``, ``filing_year`` and ``period``."""
    return tuple(
        entry
        for entry in entries
        if entry.modelo == modelo and entry.period == period and entry.year.resolve(envelope) == filing_year
    )


def check_prior_value_bindings(
    entries: Sequence[AttestedPriorValue], envelope: YearEnvelope, operation: PinnedAuthorityOperation
) -> None:
    """Refuse a stated figure whose binding the return's selected registry edition does not declare.

    A binding the edition declares whose source the application holds is left
    unsubmitted by the replay; a binding id the edition does not declare at all
    can never be offered, so it is a stale or misspelt statement and is refused
    here, before any calculation. A return the registry selects no edition for
    is left to its own calculation refusal. An entry that states ``where_declared``
    is skipped, without a refusal, for an edition that does not declare its binding.
    """
    for entry in entries:
        year = entry.year.resolve(envelope)
        try:
            revision = operation.revision_for_context(entry.modelo, filing_year=year, period=entry.period)
        except RegistryError:
            continue
        if entry.binding not in revision_bindings_by_id(revision) and not entry.where_declared:
            raise PriorValueAttestationError(
                f"Modelo {entry.modelo} {year} {entry.period}: attested binding {entry.binding} "
                f"is not a binding of edition {revision.id}"
            )


def entries_for(
    entries: Sequence[AttestedPriorValue], envelope: YearEnvelope, calculated: ModeloWorkCalculatePublicResultV3
) -> tuple[AttestedPriorValue, ...]:
    """The entries that state a figure for the return ``calculated`` is."""
    unit = calculated.unit
    return entries_on(entries, envelope, modelo=unit.modelo, filing_year=unit.filing_year, period=unit.period.code)


@dataclass(frozen=True, slots=True)
class PriorValueAttestation:
    """What one return's attestation submitted."""

    applied: ModeloEditApplyPublicResultV1 | None
    """The edit receipt of the submitted attestations, which recalculated the return; ``None`` when none was offered."""
    unoffered: tuple[str, ...]
    """The bindings of the return's entries the admitted baseline does not offer the attestation on."""


def attest_return_prior_values(
    entries: Sequence[AttestedPriorValue],
    *,
    envelope: YearEnvelope,
    profile_id: UUID,
    work_unit_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    settle: SettleOperation,
) -> PriorValueAttestation:
    """Submit the attestation of each entry of one return's work unit the application offers.

    The work unit need not hold a calculation: the attestation travels as a
    calculating edit, so the return is calculated with the stated figures
    whether or not it was calculated before. Nothing is submitted for an entry
    whose binding the admitted baseline does not offer the attestation on; it is
    named in :attr:`PriorValueAttestation.unoffered`.
    """
    matching = entries_on(entries, envelope, modelo=modelo, filing_year=filing_year, period=period)
    if not matching:
        return PriorValueAttestation(applied=None, unoffered=())
    form = settle(
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(profile_id=profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.EN),
        subject=work_unit_id,
    )
    if not isinstance(form, ModeloWorkbenchFormProjectionV1):
        raise PriorValueAttestationError(f"{work_unit_id}: the workbench form read published no projection")
    if form.admitted_baseline is None:
        return PriorValueAttestation(applied=None, unoffered=tuple(entry.binding for entry in matching))
    baseline = form.admitted_baseline.to_baseline()
    offered = {
        surface.binding_id
        for surface in baseline.permitted_surface
        if isinstance(surface, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE in surface.allowed_intents
    }
    unoffered = tuple(entry.binding for entry in matching if entry.binding not in offered)
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
        return PriorValueAttestation(applied=None, unoffered=unoffered)
    submission = ModeloEditSubmissionV1(
        baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, binding_intents=intents
    )
    operator_input = ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
    )
    applied = settle(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, operator_input, subject=work_unit_id)
    if not isinstance(applied, ModeloEditApplyPublicResultV1):
        raise PriorValueAttestationError(f"{work_unit_id}: the attestation published no edit receipt")
    return PriorValueAttestation(applied=applied, unoffered=unoffered)


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
    unit = calculated.unit
    attested = attest_return_prior_values(
        entries,
        envelope=envelope,
        profile_id=profile_id,
        work_unit_id=calculated.work_unit_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period.code,
        settle=settle,
    )
    return attested.applied is not None


__all__ = [
    "PriorValueAttestation",
    "PriorValueAttestationError",
    "SettleOperation",
    "attest_prior_values",
    "attest_return_prior_values",
    "check_prior_value_bindings",
    "entries_for",
    "entries_on",
]
