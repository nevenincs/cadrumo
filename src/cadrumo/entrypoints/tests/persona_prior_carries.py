"""State a persona's pending Modelo 100 carries of earlier ejercicios through the operations the refusal's door names.

A Modelo 100 reads the carries still pending from previous ejercicios from the
previous return. Where the profile holds no such
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


def statement_families(persona: Persona) -> dict[tuple[str, str], AbsenceAttestationFamily]:
    """Each statement's family token as the registry's family member, refusing a token that is not one.

    The persona loader cannot import the domain, so this is where the tokens it
    read are checked against the members :class:`AbsenceAttestationFamily` has.
    """
    families: dict[tuple[str, str], AbsenceAttestationFamily] = {}
    for item in persona.prior_carries:
        try:
            families[(str(item.year), item.family)] = AbsenceAttestationFamily(item.family)
        except ValueError:
            known = [member.value for member in AbsenceAttestationFamily]
            raise PersonaMaterialisationError(
                f"{persona.id}: prior_carries family {item.family!r} is not one of {known}"
            ) from None
    return families


def _statements(persona: Persona, world: PersonaWorld, year: int) -> dict[AbsenceAttestationFamily, PriorCarries]:
    """The persona's statements for the Modelo 100 of ``year``, by the family each one names."""
    families = statement_families(persona)
    return {
        families[(str(item.year), item.family)]: item
        for item in persona.prior_carries
        if item.year.resolve(world.envelope) == year
    }


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
    statements: Mapping[AbsenceAttestationFamily, PriorCarries],
    form_read: ModeloWorkbenchFormProjectionV1,
) -> ModeloEditSubmissionV1 | None:
    """One intent per open carry of a family the persona names: the stated amount, else the statement of none.

    A carry of a family no statement names is left open. ``None`` when no open
    carry belongs to a named family.
    """
    intents: list[ModeloBindingEditIntentV1] = []
    for attestation in form_read.form.form.carry_attestations:
        statement = statements.get(attestation.family)
        if statement is None:
            continue
        open_carries = tuple(sorted(set(attestation.binding_ids)))
        amounts = _box_amounts(world, year, open_carries, statement) if statement.pending else {}
        for binding_id in open_carries:
            address = ModeloEditBindingAddressV1(binding_id=binding_id)
            if binding_id in amounts:
                intents.append(
                    ModeloBindingEditIntentV1(
                        address=address, kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, value=amounts[binding_id]
                    )
                )
            else:
                intents.append(
                    ModeloBindingEditIntentV1(address=address, kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT)
                )
    if not intents:
        return None
    return ModeloEditSubmissionV1(
        baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, binding_intents=tuple(intents)
    )


def attest_prior_carries(persona: Persona, world: PersonaWorld, work_unit_id: str, year: int) -> tuple[BindingId, ...]:
    """State the persona's pending carries on the created Modelo 100 of ``year``, before it is calculated.

    The form read admits the edit baseline and names the carries no earlier
    return supplies; the staged intents are checked by the edit preflight, then
    applied by the guarded edit, which calculates the declaration with them.
    Returns the carries answered, empty when the persona states nothing for
    ``year``, every carry of the families it names is already supplied, or the
    form holds no open carry of those families; nothing is then submitted beyond
    the form read.

    Raises:
        PersonaMaterialisationError: When a statement names a family the registry
            does not have, the form admits no edit, the check
            refuses or blocks the staged intents, or the apply does not succeed.
    """
    statements = _statements(persona, world, year)
    if not statements:
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
    submission = _submission(world, year, form_read.admitted_baseline.to_baseline(), statements, form_read)
    if submission is None:
        return ()
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


__all__ = ["attest_prior_carries", "statement_families"]
