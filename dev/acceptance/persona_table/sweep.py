"""Collector of the persona table: replays each persona under each supported horizon and runs its returns.

This module is not a test of the suite. ``python -m dev.acceptance.persona_table run``
names it explicitly to pytest, which collects it in spite of its name; the
suite never does. Each case replays one persona with the registry horizon
moved to one supported year and takes every return it owes through create,
calculate, verify, fichero-BOE export and local filing, appending one JSON row per return
to the file ``PERSONA_TABLE_OUT`` names. A case fails only when the runner
itself breaks; a red return is a row, not a failed case.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path

import pytest

from cadrumo.application.modelo.export_projection import ModeloExportPublicResultV3
from cadrumo.application.modelo.operation_shared import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
from cadrumo.application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from cadrumo.application.modelo.work_verification_contracts import (
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from cadrumo.application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from cadrumo.application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from cadrumo.application.operations.public_scalar import restore_scalar
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    enter_return_work_inputs,
    materialised_persona,
    run_operation,
    settle_operation,
    state_offered_statements,
)
from cadrumo.entrypoints.tests.persona_rental_carries import attest_pending_rental_carries
from cadrumo.entrypoints.tests.persona_work_income_statements import states_for
from cadrumo.tests.personas import ExpectedValue, Persona, PersonaCatalogueError, persona_ids, read_persona

from .calendar_sweep import calendar_observations
from .counterparties import DESIGNS, counterparty_mismatches, is_compared
from .export_check import export_layout, export_reason
from .planner import (
    MODELOS_ENV,
    REASON_LIMIT,
    YEARS_ENV,
    PreparedReturn,
    listed,
    plan_rows,
    prepare_return,
    refusal_at_calculate,
    refusal_row,
    refusal_text,
    registry_envelope,
    replay_scope,
    stage_order_in_use,
    stated_refusal,
    stated_values,
)
from .roles import StatedCasilla, compared, differing, mismatch_text, revision_identities
from .row_figures import merge_row_figures, on_form_casillas, row_figures, split_figures
from .rows import (
    PlannedRow,
    Stage,
    TableRow,
    canonical_figures,
    not_owed_stage,
    not_run,
    replay_horizons,
    stage_refusal_codes,
    write_rows,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

OUT_ENV = "PERSONA_TABLE_OUT"
PERSONAS_ENV = "PERSONA_TABLE_PERSONAS"

_CALCULATED = frozenset({Stage.PASSED, Stage.CALCULATED})

__all__ = [
    "MODELOS_ENV",
    "OUT_ENV",
    "PERSONAS_ENV",
    "YEARS_ENV",
    "Lifecycle",
    "PreparedReturn",
    "cases",
    "holds_calculation",
    "plan_rows",
    "prepare_return",
    "record_statements",
    "replay_scope",
    "run_lifecycle",
    "run_return",
    "stated_values",
    "statements_needing_calculation",
]


@cache
def _persona(persona_id: str) -> Persona:
    return read_persona(persona_id, envelope=registry_envelope())


def cases() -> list[pytest.ParameterSet]:
    """One case per persona and horizon that has a selected return to run, under the environment's filters."""
    wanted = listed(PERSONAS_ENV)
    return [
        pytest.param(persona_id, horizon, id=f"{persona_id}@{horizon}")
        for persona_id in persona_ids()
        if not wanted or persona_id in wanted
        for horizon in replay_horizons(registry_envelope())
        if plan_rows(persona_id, horizon)[1]
    ]


def _blocking_findings(verified: ModeloWorkVerifyPublicResultV2) -> str:
    return ", ".join(
        f"{finding.kind} {finding.casilla_id or finding.expectation_id or '-'} "
        f"{finding.message_locale_key.rsplit('.', 1)[-1]}"
        for finding in verified.verification.report.findings
        if str(finding.severity) == "blocking"
    )


def run_return(
    materialised: MaterialisedPersona,
    plan: PlannedRow,
    values: list[ExpectedValue],
    exports: Path,
    *,
    before_calculate: Callable[[PreparedReturn], None] | None = None,
) -> TableRow:
    """Create, calculate, verify, export and file one return; the row records where it stopped and why.

    A return stated not owed is created, calculated and compared, then checked against the overview calendar
    instead of being verified, exported and filed. ``before_calculate`` observes the prepared return before
    its first calculation, which is how a probe meets the state an operator meets before stating anything more.
    """
    world = materialised.world
    prepared = prepare_return(materialised, plan, values)
    if isinstance(prepared, TableRow):
        return prepared
    if before_calculate is not None:
        before_calculate(prepared)
    work_unit_id = prepared.work_unit_id
    stating = stated_refusal(values)
    at_calculate = refusal_at_calculate(stating)
    try:
        calculated = _calculate(materialised, plan, prepared)
    except PersonaMaterialisationError as error:
        return refusal_row(plan, at_calculate, error)
    rows = row_figures(world, calculated)
    figures, internal_figures = split_figures(
        _figures(calculated, rows),
        on_form_casillas(world.operation, str(calculated.unit.modelo), calculated.unit.revision_id),
    )
    calculate, reasons = _compare(plan, values, at_calculate, calculated, rows)
    if not plan.owed:
        verify, not_owed_reason = _not_owed(materialised, plan)
        reasons += [not_owed_reason] if not_owed_reason else []
        return TableRow.from_plan(
            plan,
            calculate,
            verify=verify,
            reason=" | ".join(reasons)[:REASON_LIMIT],
            figures=figures,
            internal_figures=internal_figures,
        )
    revision_id = calculated.calculation_revision_id
    lifecycle = run_lifecycle(world, plan, values, exports, work_unit_id, revision_id, stage_order=stage_order_in_use())
    calculate, reasons = _with_counterparties(
        calculate, reasons, values, materialised.persona, plan, exports, lifecycle.export
    )
    reasons += [
        reason for reason in (lifecycle.verify_reason, lifecycle.export_reason, lifecycle.file_reason) if reason
    ]
    stage_reasons = {"verify": lifecycle.verify_reason or lifecycle.file_reason, "export": lifecycle.export_reason}
    calculate = _at_stated_stage(stating, calculate, reasons, stage_reasons)
    return TableRow.from_plan(
        plan,
        calculate,
        verify=lifecycle.verify,
        export=lifecycle.export,
        reason=" | ".join(reasons)[:REASON_LIMIT],
        export_detail=lifecycle.export_detail,
        figures=figures,
        internal_figures=internal_figures,
    )


@dataclass(frozen=True, slots=True)
class Lifecycle:
    """What verify, export and local filing settled for one calculated return."""

    verify: Stage
    verify_reason: str
    export: Stage
    export_detail: str
    export_reason: str
    file_reason: str
    """The local filing outcome after the export; empty when nothing was filed or the legacy order filed in verify."""


def run_lifecycle(
    world: PersonaWorld,
    plan: PlannedRow,
    values: list[ExpectedValue],
    exports: Path,
    work_unit_id: str,
    revision_id: str,
    *,
    stage_order: str | None = None,
) -> Lifecycle:
    """Run verify, export and local filing in the ``stage_order`` named, else the one the environment names.

    ``lifecycle``: verify, then export, then filing, so that an export defect of a return is seen before the
    return is filed; filing depends only on the verification, whatever the export settled, so the quarterly chain
    still builds on it. ``legacy``: a granted verification is filed inside the verify stage, before the export
    runs, and the filing outcome is the verify stage's reason.
    """
    order = stage_order or stage_order_in_use()
    verify, verify_reason, verified = _verify(world, work_unit_id, revision_id)
    if order == "legacy":
        filed = _file_locally(world, work_unit_id, revision_id, verified) if verified is not None else ""
        export, export_detail, export_reason = _export(world, plan, values, exports, work_unit_id, revision_id)
        return Lifecycle(verify, verify_reason or filed, export, export_detail, export_reason, "")
    export, export_detail, export_reason = _export(world, plan, values, exports, work_unit_id, revision_id)
    file_reason = _file_locally(world, work_unit_id, revision_id, verified) if verified is not None else ""
    return Lifecycle(verify, verify_reason, export, export_detail, export_reason, file_reason)


def _figures(calculated: ModeloWorkCalculatePublicResultV3, rows: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """The non-zero casilla values the comparison reads: the public scalars with each single row's figure merged in."""
    scalars = {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}
    merged, _conflicts = merge_row_figures(scalars, rows)
    return canonical_figures(
        {key: _row_amount(value) if rows.get(key) is value else value for key, value in merged.items()}
    )


def _row_amount(figure: object) -> object:
    """A row figure as the number it prints, so it is canonical text like a public scalar's amount."""
    try:
        return Decimal(str(figure))
    except InvalidOperation:
        return figure


def _at_stated_stage(
    stating: ExpectedValue | None, calculate: Stage, reasons: list[str], stage_reasons: dict[str, str]
) -> Stage:
    """The calculate stage once a refusal stated at verify or export is checked against that stage alone.

    The refusal is expected only when the calculation completed and the stated stage settled with the stated
    code. A completed calculation whose stated stage did not refuse so is a refusal not raised, and the reason
    leads ``reasons``.
    """
    if stating is None or stating.refusal is None or stating.refusal_stage == "calculate":
        return calculate
    if calculate not in _CALCULATED:
        return calculate
    stage_reason = stage_reasons[stating.refusal_stage]
    if stating.refusal in stage_refusal_codes(stage_reason):
        return Stage.EXPECTED_REFUSAL
    reasons.insert(0, f"stated refusal {stating.refusal} not raised at {stating.refusal_stage}")
    return Stage.REFUSAL_NOT_RAISED


def _calculate(
    materialised: MaterialisedPersona, plan: PlannedRow, prepared: PreparedReturn
) -> ModeloWorkCalculatePublicResultV3:
    """Calculate the prepared return.

    A let property's row stands with its net yield withheld until its pending carry is stated; the statement
    is kept on the revision, so calculating again reads it.
    """
    world = materialised.world
    work_unit_id = prepared.work_unit_id
    calculated = run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        prepared.request,
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )
    if plan.modelo == "100" and attest_pending_rental_carries(materialised.persona, world, work_unit_id, plan.year):
        calculated = run_operation(
            world,
            MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            prepared.request,
            ModeloWorkCalculatePublicResultV3,
            subject=work_unit_id,
        )
    return calculated


def record_statements(materialised: MaterialisedPersona, plan: PlannedRow, prepared: PreparedReturn) -> None:
    """State what the persona's operator states on the prepared return, and stop before a plain calculation.

    These are the statements :func:`_calculate` makes around its calculations, through the same functions and
    operations: the values the persona gives (``enter_return_work_inputs``), its prior values and work-income
    statements (``state_offered_statements``) and a let property's pending carry
    (``attest_pending_rental_carries``). Each travels as a calculating edit, so the return holds a calculation
    once one was applied; :func:`holds_calculation` reads whether it does. A statement the work unit's form
    does not offer yet is not made.

    Raises:
        PersonaMaterialisationError: When an operation refuses a statement.
    """
    world = materialised.world
    work_unit_id = prepared.work_unit_id
    if world.work_inputs:
        enter_return_work_inputs(world, work_unit_id)
    state_offered_statements(
        world, modelo=plan.modelo, filing_year=plan.year, period=plan.period, work_unit_id=work_unit_id
    )
    if plan.modelo == "100":
        attest_pending_rental_carries(materialised.persona, world, work_unit_id, plan.year)


def statements_needing_calculation(materialised: MaterialisedPersona, plan: PlannedRow) -> tuple[str, ...]:
    """The kinds of statement the persona makes for the return that its form offers only on a calculated work unit.

    A Modelo 100 work-income statement is offered with the calculation's findings, and a let property's carry on
    the row the calculation emits; :func:`record_statements` makes neither on a work unit holding no calculation.
    """
    world = materialised.world
    kinds: list[str] = []
    if states_for(world.work_income_none_statements, world.envelope, modelo=plan.modelo, filing_year=plan.year):
        kinds.append("work_income_none")
    if plan.modelo == "100" and any(
        rental.pendiente_intereses_reparacion is not None for rental in materialised.persona.rental_properties
    ):
        kinds.append("rental_carries")
    return tuple(kinds)


def holds_calculation(world: PersonaWorld, work_unit_id: str) -> bool:
    """Whether the work unit holds a calculation, read from the edit baseline its form admits (false if none)."""
    form = run_operation(
        world,
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(
            profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.EN
        ),
        ModeloWorkbenchFormProjectionV1,
        subject=work_unit_id,
    )
    baseline = form.admitted_baseline
    return baseline is not None and baseline.to_baseline().current_calculation_revision_id is not None


def _compare(
    plan: PlannedRow,
    values: list[ExpectedValue],
    stated_refusal: str | None,
    calculated: ModeloWorkCalculatePublicResultV3,
    rows: Mapping[str, str],
) -> tuple[Stage, list[str]]:
    """The calculate stage against the stated values, and the reasons it is not a plain pass."""
    mismatches = _mismatches(values, calculated, plan.unchecked, rows) + _row_conflicts(calculated, rows)
    reasons: list[str] = []
    if stated_refusal is not None:
        calculate = Stage.REFUSAL_NOT_RAISED
        reasons.append(f"stated refusal {stated_refusal} not raised")
    elif not values:
        calculate = Stage.CALCULATED
    else:
        calculate = _value_stage(values, calculated, plan.unchecked, rows) if mismatches else Stage.PASSED
        if _row_conflicts(calculated, rows):
            calculate = Stage.MISMATCH
        reasons += ["; ".join(mismatches)] if mismatches else []
    unresolved = _unresolved(calculated)
    if unresolved:
        reasons.append(f"unresolved: {unresolved}")
    return calculate, reasons


def _differing(
    values: list[ExpectedValue],
    calculated: ModeloWorkCalculatePublicResultV3,
    unchecked: tuple[str, ...],
    rows: Mapping[str, str],
) -> list[tuple[StatedCasilla, object]]:
    """Each stated casilla, and each role resolved in the edition the calculation used, that it does not equal."""
    got = {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}
    got, _conflicts = merge_row_figures(got, rows)
    unit = calculated.unit
    casillas = revision_identities(unit.modelo, unit.revision_id) if any(value.roles for value in values) else ()
    return differing(compared(values, casillas, unchecked), got)


def _row_conflicts(calculated: ModeloWorkCalculatePublicResultV3, rows: Mapping[str, str]) -> list[str]:
    """Each casilla whose nonzero public scalar differs from the figure its single row holds."""
    scalars = {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}
    return merge_row_figures(scalars, rows)[1]


def _mismatches(
    values: list[ExpectedValue],
    calculated: ModeloWorkCalculatePublicResultV3,
    unchecked: tuple[str, ...],
    rows: Mapping[str, str],
) -> list[str]:
    """Each stated casilla or role the calculation does not equal."""
    return [mismatch_text(item, found) for item, found in _differing(values, calculated, unchecked, rows)]


def _value_stage(
    values: list[ExpectedValue],
    calculated: ModeloWorkCalculatePublicResultV3,
    unchecked: tuple[str, ...],
    rows: Mapping[str, str],
) -> Stage:
    """Mismatch when a stated casilla has another value; unresolved when every differing casilla has none."""
    found = _differing(values, calculated, unchecked, rows)
    return Stage.UNRESOLVED if all(value is None for _, value in found) else Stage.MISMATCH


def _unresolved(calculated: ModeloWorkCalculatePublicResultV3) -> str:
    """The bindings and casillas the calculation left unresolved."""
    return ", ".join(
        [f"binding {item.binding_id}" for item in calculated.unresolved_bindings]
        + [f"casilla {item.casilla_id} ({item.reason})" for item in calculated.unresolved_casillas]
    )


def _not_owed(materialised: MaterialisedPersona, plan: PlannedRow) -> tuple[Stage, str]:
    """The verify stage of a return stated not owed: whether the overview calendar suppresses it as not applicable.

    The calendar is read after the calculation, since an instalment's applicability can turn on the base stated on
    its own work unit. Nothing is verified, exported or filed.
    """
    world = materialised.world
    try:
        observations = calendar_observations(
            world,
            plan.persona,
            world.envelope,
            from_date=date(plan.year, 1, 1),
            to_date=date(plan.year + 1, 12, 31),
        )
    except PersonaMaterialisationError as error:
        return Stage.REFUSED, f"overview: {refusal_text(error)}"
    return not_owed_stage(observations, (plan.modelo, plan.year, plan.period))


def _verify(
    world: PersonaWorld, work_unit_id: str, revision_id: str
) -> tuple[Stage, str, ModeloWorkVerifyPublicResultV2 | None]:
    """The verify stage, its reason, and the granted verification the return is filed on, else none."""
    try:
        verified = run_operation(
            world,
            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=PERSONA_ACTOR),
            ModeloWorkVerifyPublicResultV2,
            subject=work_unit_id,
        )
    except PersonaMaterialisationError as error:
        return Stage.REFUSED, f"verify: {refusal_text(error)}", None
    if verified.granted_verificado_completo:
        return Stage.PASSED, "", verified
    return (
        Stage.INCOMPLETE,
        f"verify: {verified.completeness_status}; {verified.finding_count} findings; "
        f"blocking: {_blocking_findings(verified) or 'none'}",
        None,
    )


def _export_path(plan: PlannedRow, exports: Path) -> Path:
    return exports / f"{plan.persona}-{plan.modelo}-{plan.year}-{plan.period}.txt"


def _counterparty_mismatches(
    persona: Persona, plan: PlannedRow, values: list[ExpectedValue], output: Path
) -> list[str]:
    """Each stated counterparty value the written fichero does not give, read through the registry layout."""
    with bundled_indexed_authority().operation() as operation:
        layout = export_layout(operation, plan)
        return counterparty_mismatches(values, persona.identities, layout, output.read_bytes())


def _with_counterparties(
    calculate: Stage,
    reasons: list[str],
    values: list[ExpectedValue],
    persona: Persona,
    plan: PlannedRow,
    exports: Path,
    export: Stage,
) -> tuple[Stage, list[str]]:
    """The calculate stage once the written fichero has been compared with the counterparties the persona states."""
    if not any(is_compared(value) for value in values) or plan.modelo not in DESIGNS:
        return calculate, reasons
    if export is not Stage.PASSED:
        return calculate, [*reasons, "counterparties not compared: no fichero written"]
    mismatches = _counterparty_mismatches(persona, plan, values, _export_path(plan, exports))
    if not mismatches:
        return calculate, reasons
    return Stage.MISMATCH, [*reasons, "; ".join(mismatches)]


def _export(
    world: PersonaWorld,
    plan: PlannedRow,
    values: list[ExpectedValue],
    exports: Path,
    work_unit_id: str,
    revision_id: str,
) -> tuple[Stage, str, str]:
    """The export stage, what was written, and the reason it was not."""
    output = _export_path(plan, exports)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        exported = settle_operation(
            world,
            MODELO_EXPORT_OPERATION_DEFINITION_ID,
            ModeloExportRequest(
                calculation_revision_id=revision_id,
                output_path=str(output),
                artefact=ModeloExportArtefact.FICHERO_BOE,
                actor=PERSONA_ACTOR,
            ),
            subject=work_unit_id,
        )
    except PersonaMaterialisationError as error:
        return Stage.REFUSED, "", f"export: {refusal_text(error)}"
    if not isinstance(exported, ModeloExportPublicResultV3):
        return Stage.REFUSED, "", f"export: published {type(exported).__name__}, not ModeloExportPublicResultV3"
    detail = f"{exported.export_format}, {exported.byte_size} B, {exported.completeness}, {exported.evidence_status}"
    reason = export_reason(plan, values, output)
    if reason:
        return Stage.REFUSED, detail, reason
    return Stage.PASSED, detail, ""


def _file_locally(
    world: PersonaWorld, work_unit_id: str, revision_id: str, verified: ModeloWorkVerifyPublicResultV2
) -> str:
    """File a verified return locally, so the next quarter and the year's annual returns build on it.

    Local filing records a PRESENTADO revision whose AEAT status stays pending;
    nothing is submitted. A refusal is reported in the row and leaves the chain
    to show where it stops.
    """
    try:
        run_operation(
            world,
            MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
            ModeloWorkFileRequest(
                approval=ModeloWorkFileApproval(
                    calculation_revision_id=revision_id,
                    verification_report_id=verified.verification_report_id,
                ),
                actor=PERSONA_ACTOR,
            ),
            ModeloWorkFilePublicResultV2,
            subject=work_unit_id,
        )
    except PersonaMaterialisationError as error:
        return f"file: {refusal_text(error)}"
    return "filed locally"


@pytest.mark.parametrize(("persona_id", "horizon"), cases())
def test_persona_returns(tmp_path: Path, persona_id: str, horizon: int) -> None:
    """Replay one persona under one horizon and append a row for every return it owes there."""
    out = Path(os.environ[OUT_ENV])
    plans, emitted = plan_rows(persona_id, horizon)
    persona = _persona(persona_id)
    try:
        with materialised_persona(
            persona_id, tmp_path, replay_scope(persona), reuse=True, horizon=horizon
        ) as materialised:
            envelope = materialised.world.envelope
            for plan in plans:
                values = stated_values(materialised.persona, envelope, plan)
                row = run_return(materialised, plan, values, tmp_path / "exports")
                if plan.key in emitted:
                    write_rows(out, [row])
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        reason = f"replay under horizon {horizon}: {refusal_text(error)}"
        write_rows(out, [not_run(plan, reason) for plan in plans if plan.key in emitted])
