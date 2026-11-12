"""State a persona's pending Modelo 100 carries of earlier ejercicios through the operations the refusal's door names.

A Modelo 100 reads the negative general bases still pending from the four
previous ejercicios from the previous return. Where the profile holds no such
return, as for the return of the support floor, the calculation refuses with
``REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED`` and its door is
``operator.modelo.work.attest_prior_carries``. That command reads the
declaration's form, stages one intent per carry the form names, checks it and
applies it through the guarded edit; this helper does the same through the same
registered operations, with what the persona states in ``[[prior_carries]]``.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...application.modelo.absence_statement_submission import absence_statement_submission
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditRefusedV1,
    ModeloEditSubmissionV1,
)
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.workbench_operations import (
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloEditPreflightProjectionV1,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.binding_targets import casillas_by_binding
from ...domain.calculations.registry.ids import BindingId
from ...tests.personas import Persona, PriorCarries
from .persona_materialisation import PersonaMaterialisationError, PersonaWorld, run_operation

_MODELO = "100"
_PERIOD = "0A"
#: The language the statement is read and checked in; it changes words only, never what is staged.
_LANGUAGE = OutputLanguage.ES


def _statement(persona: Persona, world: PersonaWorld, year: int) -> PriorCarries | None:
    """The persona's statement for the Modelo 100 of ``year``, or ``None`` when it states none."""
    return next((item for item in persona.prior_carries if item.year.resolve(world.envelope) == year), None)


def _box_amounts(
    world: PersonaWorld, year: int, open_carries: tuple[BindingId, ...], statement: PriorCarries
) -> Mapping[BindingId, Decimal]:
    """The amount stated for each open carry, read through the boxes the year's registry revision feeds from it."""
    revision = world.operation.snapshot(
        _MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    fed = casillas_by_binding(revision)
    stated = dict(statement.pending)
    amounts: dict[BindingId, Decimal] = {}
    for binding_id in open_carries:
        found = {stated[str(box)] for box in fed.get(binding_id, ()) if str(box) in stated}
        if len(found) > 1:
            raise PersonaMaterialisationError(f"{binding_id}: its boxes are stated with different amounts")
        if found:
            amounts[binding_id] = found.pop()
    return amounts


def _submission(
    world: PersonaWorld,
    year: int,
    baseline: ModeloEditBaselineV1,
    statement: PriorCarries,
    form_read: ModeloWorkbenchFormProjectionV1,
) -> ModeloEditSubmissionV1:
    """One intent per open carry: the stated amount where the persona states one, else the statement of none."""
    attestations = form_read.form.form.carry_attestations
    if not statement.pending:
        return absence_statement_submission(
            baseline, attestations, family=AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
        )
    open_carries = tuple(sorted({binding_id for item in attestations for binding_id in item.binding_ids}))
    amounts = _box_amounts(world, year, open_carries, statement)
    return ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        binding_intents=tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                value=amounts[binding_id],
            )
            if binding_id in amounts
            else ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
            )
            for binding_id in open_carries
        ),
    )


def attest_prior_carries(persona: Persona, world: PersonaWorld, work_unit_id: str, year: int) -> tuple[BindingId, ...]:
    """State the persona's pending carries on the created Modelo 100 of ``year``, before it is calculated.

    The form read admits the edit baseline and names the carries no earlier
    return supplies; the staged intents are checked by the edit preflight, then
    applied by the guarded edit, which calculates the declaration with them.
    Returns the carries answered, empty when the persona states nothing for
    ``year`` or every carry is already supplied, in which case nothing is
    submitted beyond the form read.

    Raises:
        PersonaMaterialisationError: When the form admits no edit, the check
            refuses or blocks the staged intents, or the apply does not succeed.
    """
    statement = _statement(persona, world, year)
    if statement is None:
        return ()
    form_read = run_operation(
        world,
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=_LANGUAGE),
        ModeloWorkbenchFormProjectionV1,
        subject=work_unit_id,
    )
    if not form_read.form.form.carry_attestations:
        return ()
    if form_read.admitted_baseline is None:
        raise PersonaMaterialisationError(f"{work_unit_id}: the form admitted no edit: {form_read.admission_refusal}")
    submission = _submission(world, year, form_read.admitted_baseline.to_baseline(), statement, form_read)
    staged = ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=_LANGUAGE
    )
    review = run_operation(
        world,
        MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
        staged,
        ModeloEditPreflightProjectionV1,
        subject=work_unit_id,
    )
    if isinstance(review.outcome, ModeloEditRefusedV1) or any(finding.blocking for finding in review.findings):
        raise PersonaMaterialisationError(f"{work_unit_id}: the check refused the stated carries: {review}")
    run_operation(
        world, MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, staged, ModeloEditApplyPublicResultV1, subject=work_unit_id
    )
    return tuple(intent.address.binding_id for intent in submission.binding_intents)


__all__ = ["attest_prior_carries"]
