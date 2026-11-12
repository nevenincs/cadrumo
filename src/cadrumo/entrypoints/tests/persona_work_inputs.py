"""The casilla values a persona's operator enters on a return because no record the application holds produces them.

A persona's ``[[work_inputs]]`` are entered as an operator enters them: through
the registered ``modelo.edit.apply`` operation, one typed value per casilla,
against the baseline the workbench form read admits, before the return is first
calculated. The edit recalculates the return with them, so a calculation that
refuses without such a value reads it; the application's own refusal of a
value stands. The edit carries no field for where a value comes from, so the
persona's ``sources`` and ``reason`` stay in the catalogue and reach no record.

The catalogue reader cannot read the registry, so the checks that need it run
here. A value is given by a registry identity and resolved in the edition the
law selects for the return: only a casilla that edition leaves to the operator
may be given, and a given casilla is never one an expectation of the same
return names.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_models import (
    ModeloEditMutationFamily,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...tests.personas import Persona, WorkInput, YearEnvelope
from .persona_prior_values import SettleOperation


class WorkInputError(RuntimeError):
    """A work input the registry does not leave to the operator, or the operations did not answer as needed."""


def _role_casillas(revision: ModeloRevision, key: str) -> tuple[str, ...]:
    """The casillas a role key names: by ``continuidad_id``, else by ``semantic_role``."""
    matches = [str(casilla.id) for casilla in revision.casillas if casilla.continuidad_id == key] or [
        str(casilla.id) for casilla in revision.casillas if casilla.semantic_role == key
    ]
    return tuple(matches)


def _edition(operation: PinnedAuthorityOperation, modelo: str, year: int, period: str) -> ModeloRevision | None:
    """The edition the law selects for the return, or ``None`` where the registry selects none."""
    try:
        return operation.revision_for_context(modelo, filing_year=year, period=period)
    except RegistryError:
        return None


def resolved_casillas(revision: ModeloRevision, entry: WorkInput, *, where: str) -> tuple[tuple[str, str], ...]:
    """The casilla each given role names in ``revision``, with its value; a role the edition lacks gives nothing.

    A role naming several casillas of the edition is refused as ambiguous.
    """
    resolved: list[tuple[str, str]] = []
    for role, amount in entry.roles:
        named = _role_casillas(revision, role)
        if len(named) > 1:
            raise WorkInputError(
                f"{where}: role {role} names several casillas in edition {revision.id} ({', '.join(named)}), "
                "so which one the value is entered on is ambiguous"
            )
        resolved.extend((casilla, amount) for casilla in named)
    return tuple(resolved)


def check_work_inputs(persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation) -> None:
    """Refuse a given role no edition declares, one the return's edition computes, or one asserted back.

    Each role must name a casilla in at least one authored edition of the
    modelo, whatever the envelope, so a misspelt role is refused while a role a
    later edition declares stays admitted under a lower horizon. In the edition the law
    selects for the return, a role naming several casillas is ambiguous, and
    the casilla it names must be one the operator enters and no expectation of
    the return names, by casilla id or by role. A role the selected edition
    does not declare is left unentered there, so the calculation refuses on
    its own terms; so is a return the registry selects no edition for.
    """
    for entry in persona.work_inputs:
        year = entry.year.resolve(envelope)
        where = f"{persona.id} work input Modelo {entry.modelo} {entry.year} {entry.period}"
        editions = [
            operation.revision(entry.modelo, revision_id)
            for modelo, revision_id in operation.revision_ids()
            if modelo == entry.modelo
        ]
        for role, _ in entry.roles:
            if not any(_role_casillas(edition, role) for edition in editions):
                raise WorkInputError(f"{where}: role {role} names no casilla in any edition of Modelo {entry.modelo}")
        revision = _edition(operation, entry.modelo, year, entry.period)
        if revision is None:
            continue
        declared = {str(casilla.id): casilla for casilla in revision.casillas}
        targets = {str(formula.target_casilla_id) for formula in revision.formulas}
        given = {casilla for casilla, _ in resolved_casillas(revision, entry, where=where)}
        for casilla in sorted(given):
            definition = declared[casilla]
            if definition.input_kind is not InputKind.MANUAL or casilla in targets:
                raise WorkInputError(
                    f"{where}: edition {revision.id} supplies casilla {casilla} itself "
                    f"({definition.input_kind.value}{', a formula target' if casilla in targets else ''}); "
                    "only a casilla the operator enters may be given"
                )
        for value in persona.expectations.values:
            if (value.modelo, value.year.resolve(envelope), value.period) != (entry.modelo, year, entry.period):
                continue
            for casilla, _ in (*value.casillas, *value.not_sourced):
                if casilla in given:
                    raise WorkInputError(
                        f"{where}: gives casilla {casilla}, which an expectation of the return states; "
                        "a given value is never asserted back"
                    )
            for key, _ in value.roles:
                named = _role_casillas(revision, key)
                if len(named) > 1:
                    raise WorkInputError(
                        f"{where}: the expected role {key} names several casillas in edition {revision.id} "
                        f"({', '.join(named)}), so whether it asserts a given back is ambiguous"
                    )
                if named and named[0] in given:
                    raise WorkInputError(
                        f"{where}: gives casilla {named[0]}, which the expected role {key} names in edition "
                        f"{revision.id}; a given value is never asserted back"
                    )


def work_inputs_for(
    entries: Sequence[WorkInput], envelope: YearEnvelope, *, modelo: str, year: int, period: str
) -> WorkInput | None:
    """The block that gives values for the return of ``modelo``, ``year`` and ``period``, if any."""
    return next(
        (
            entry
            for entry in entries
            if entry.modelo == modelo and entry.period == period and entry.year.resolve(envelope) == year
        ),
        None,
    )


def enter_work_inputs(
    entries: Sequence[WorkInput],
    *,
    envelope: YearEnvelope,
    operation: PinnedAuthorityOperation,
    profile_id: UUID,
    work_unit_id: str,
    settle: SettleOperation,
) -> bool:
    """Enter the values the persona gives for a return not yet calculated; whether an edit was applied.

    Nothing is entered on a return that already holds a calculation: the values
    were entered before its first one and each later calculation replays them.
    Each role is entered on the casilla it names in the return's edition; a role
    the edition does not declare is not entered, and a return with nothing to
    enter is left to its calculation without asking the edit to admit it. Every resolved casilla is
    submitted, so a value the application does not take is refused by the edit
    itself.
    """
    if not entries:
        return False
    form = settle(
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(profile_id=profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.EN),
        subject=work_unit_id,
    )
    if not isinstance(form, ModeloWorkbenchFormProjectionV1):
        raise WorkInputError(f"{work_unit_id}: the workbench form read published no projection")
    declaration = form.form.form
    entry = work_inputs_for(
        entries, envelope, modelo=declaration.modelo, year=declaration.filing_year, period=declaration.period.code
    )
    if entry is None:
        return False
    revision = _edition(operation, entry.modelo, declaration.filing_year, entry.period)
    casillas = () if revision is None else resolved_casillas(revision, entry, where=work_unit_id)
    if not casillas:
        return False
    if form.admitted_baseline is None:
        raise WorkInputError(f"{work_unit_id}: the declaration admits no edit: {form.admission_refusal}")
    baseline = form.admitted_baseline.to_baseline()
    if baseline.current_calculation_revision_id is not None:
        return False
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=tuple(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=casilla),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=Decimal(amount),
            )
            for casilla, amount in casillas
        ),
    )
    operator_input = ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
    )
    applied: BaseModel | None = settle(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, operator_input, subject=work_unit_id)
    if not isinstance(applied, ModeloEditApplyPublicResultV1):
        raise WorkInputError(f"{work_unit_id}: the entered values published no edit receipt")
    return True


__all__ = ["WorkInputError", "check_work_inputs", "enter_work_inputs", "resolved_casillas", "work_inputs_for"]
