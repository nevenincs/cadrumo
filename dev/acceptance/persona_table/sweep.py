"""Collector of the persona table: replays each persona under each supported horizon and runs its returns.

This module is not a test of the suite. ``python -m dev.acceptance.persona_table run``
names it explicitly to pytest, which collects it in spite of its name; the
suite never does. Each case replays one persona with the registry horizon
moved to one supported year and takes every return it owes through create,
calculate, verify and fichero-BOE export, appending one JSON row per return
to the file ``PERSONA_TABLE_OUT`` names. A case fails only when the runner
itself breaks; a red return is a row, not a failed case.
"""

from __future__ import annotations

import dataclasses
import os
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path

import pytest

from cadrumo.application.modelo.export_projection import ModeloExportPublicResultV3
from cadrumo.application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from cadrumo.application.modelo.operation_shared import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
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
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.public_scalar import restore_scalar
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    filing_key,
    materialised_persona,
    run_operation,
    settle_operation,
    year_envelope,
)
from cadrumo.tests.personas import (
    ExpectedValue,
    Persona,
    PersonaCatalogueError,
    YearEnvelope,
    persona_ids,
    read_persona,
)

from .counterparties import DESIGNS, counterparty_mismatches, is_compared
from .rows import (
    PlannedRow,
    Stage,
    TableRow,
    ended,
    in_force,
    is_unsupported,
    not_run,
    planned_rows,
    replay_horizons,
    select,
    write_rows,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

OUT_ENV = "PERSONA_TABLE_OUT"
PERSONAS_ENV = "PERSONA_TABLE_PERSONAS"
MODELOS_ENV = "PERSONA_TABLE_MODELOS"
YEARS_ENV = "PERSONA_TABLE_YEARS"

_SETTLED = re.compile(r"^(?P<definition>\S+) settled (?P<condition>\S+) \((?P<code>[^)]*)\)")
_REASON_LIMIT = 900


def _listed(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.environ.get(name, "").split(",") if item.strip())


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


@cache
def _persona(persona_id: str) -> Persona:
    return read_persona(persona_id, envelope=_envelope())


def _plan(persona_id: str, horizon: int) -> list[PlannedRow]:
    persona, envelope = _persona(persona_id), _envelope()
    today = persona.as_of.resolve(dataclasses.replace(envelope, horizon=horizon))
    rows = ended(planned_rows(persona, horizon, envelope), today)
    return select(rows, modelos=_listed(MODELOS_ENV), years=tuple(int(year) for year in _listed(YEARS_ENV)))


def _cases() -> list[pytest.ParameterSet]:
    wanted = _listed(PERSONAS_ENV)
    return [
        pytest.param(persona_id, horizon, id=f"{persona_id}@{horizon}")
        for persona_id in persona_ids()
        if not wanted or persona_id in wanted
        for horizon in replay_horizons(_envelope())
        if _plan(persona_id, horizon)
    ]


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _code(error: BaseException) -> str:
    match = _SETTLED.match(str(error))
    return str(match["code"]) if match else ""


def _short(error: BaseException) -> str:
    match = _SETTLED.match(str(error))
    if match is None:
        return f"{type(error).__name__}: {error}"[:_REASON_LIMIT]
    detail = str(error)[match.end() :].removeprefix(": ")
    head = f"{match['definition']} {match['condition']} {match['code']}"
    return (head if detail == "no detail" else f"{head} :: {detail}")[:_REASON_LIMIT]


def _values(persona: Persona, envelope: YearEnvelope, plan: PlannedRow) -> list[ExpectedValue]:
    """The persona's stated values in force for the planned return, under the replay's envelope.

    A value stated per counterparty is taken only for a return whose type-2 record is compared.
    """
    return [
        value
        for year, value in in_force(persona.expectations.values, envelope)
        if (value.counterparty is None or is_compared(value))
        and value.modelo == plan.modelo
        and value.period == plan.period
        and year == plan.year
    ]


def _m303_evidence(
    world: PersonaWorld, *, work_unit_id: str, year: int, period: str, last_period: str
) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    """No joint return, and in the year's last period the Modelo 390 attestation the persona's world records."""
    if period != last_period:
        return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False)
    attestation = ModeloWorkM303AttestationRequest(
        profile_id=world.profile_id,
        work_unit_id=work_unit_id,
        observed_at=datetime(year, 12, 31, 12, tzinfo=UTC),
        actor=PERSONA_ACTOR,
    )
    attested = run_operation(
        world,
        MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        attestation,
        ModeloWorkM303AttestationPublicResultV2,
        subject=attestation.subject_ref,
    )
    return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id=attested.attachment_id,
        m303_exonerado_390_sha256=attested.sha256,
    )


def _blocking_findings(verified: ModeloWorkVerifyPublicResultV2) -> str:
    return ", ".join(
        f"{finding.kind} {finding.casilla_id or finding.expectation_id or '-'} "
        f"{finding.message_locale_key.rsplit('.', 1)[-1]}"
        for finding in verified.verification.report.findings
        if str(finding.severity) == "blocking"
    )


def _run_return(
    materialised: MaterialisedPersona, plan: PlannedRow, values: list[ExpectedValue], exports: Path
) -> TableRow:
    """Create, calculate, verify and export one return; the row records where it stopped and why."""
    world = materialised.world
    if filing_key(plan.modelo, plan.year, plan.period) in materialised.filings:
        return TableRow.from_plan(plan, Stage.HISTORY_FILED, verify=Stage.HISTORY_FILED)
    stated_refusal = next((value.refusal for value in values if value.refusal is not None), None)
    try:
        work_unit_id = _create(world, plan)
        if isinstance(work_unit_id, TableRow):
            return work_unit_id
        calculated = _calculate(materialised, plan, work_unit_id)
    except PersonaMaterialisationError as error:
        return _refused(plan, stated_refusal, error)
    calculate, reasons = _compare(values, stated_refusal, calculated)
    revision_id = calculated.calculation_revision_id
    verify, verify_reason = _verify(world, work_unit_id, revision_id)
    export, export_detail, export_reason = _export(world, plan, exports, work_unit_id, revision_id)
    calculate, reasons = _with_counterparties(calculate, reasons, values, materialised.persona, plan, exports, export)
    reasons += [reason for reason in (verify_reason, export_reason) if reason]
    return TableRow.from_plan(
        plan,
        calculate,
        verify=verify,
        export=export,
        reason=" | ".join(reasons)[:_REASON_LIMIT],
        export_detail=export_detail,
    )


def _refused(plan: PlannedRow, stated_refusal: str | None, error: PersonaMaterialisationError) -> TableRow:
    """The row of a return refused before it calculated: expected when the persona states that refusal."""
    code = _code(error)
    if stated_refusal is not None and stated_refusal == code:
        return TableRow.from_plan(plan, Stage.EXPECTED_REFUSAL, reason=_short(error))
    stage = Stage.UNSUPPORTED if is_unsupported(code) else Stage.REFUSED
    return TableRow.from_plan(plan, stage, reason=_short(error))


def _create(world: PersonaWorld, plan: PlannedRow) -> str | TableRow:
    """The new work unit's id, or the row of a create that published no work unit."""
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo=plan.modelo,
            period=PublicPeriod(filing_year=plan.year, code=plan.period),
            actor=PERSONA_ACTOR,
        ),
    )
    if not isinstance(created, ModeloWorkCreateProjection):
        return TableRow.from_plan(plan, Stage.REFUSED, reason=f"create published {type(created).__name__}")
    outcome = created.outcome
    if not isinstance(outcome, ModeloWorkCreateSuccess):
        return TableRow.from_plan(plan, Stage.REFUSED, reason=f"create refused: {outcome.reason}"[:_REASON_LIMIT])
    return outcome.unit.work_unit_id


def _calculate(
    materialised: MaterialisedPersona, plan: PlannedRow, work_unit_id: str
) -> ModeloWorkCalculatePublicResultV3:
    """Calculate the work unit; a Modelo 303 carries its joint-return and annual-summary evidence."""
    world = materialised.world
    evidence = None
    if plan.modelo == "303":
        last_period = max(
            (p for p in _owed_periods(materialised.persona, plan) if p.endswith("T")), default=plan.period
        )
        evidence = _m303_evidence(
            world, work_unit_id=work_unit_id, year=plan.year, period=plan.period, last_period=last_period
        )
    return run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        ModeloWorkCalculateRequest(
            work_unit_id=work_unit_id, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=evidence
        ),
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )


def _compare(
    values: list[ExpectedValue], stated_refusal: str | None, calculated: ModeloWorkCalculatePublicResultV3
) -> tuple[Stage, list[str]]:
    """The calculate stage against the stated values, and the reasons it is not a plain pass."""
    mismatches = _mismatches(values, calculated)
    reasons: list[str] = []
    if stated_refusal is not None:
        calculate = Stage.REFUSAL_NOT_RAISED
        reasons.append(f"stated refusal {stated_refusal} not raised")
    elif not values:
        calculate = Stage.CALCULATED
    else:
        calculate = Stage.MISMATCH if mismatches else Stage.PASSED
        reasons += ["; ".join(mismatches)] if mismatches else []
    unresolved = _unresolved(calculated)
    if unresolved:
        reasons.append(f"unresolved: {unresolved}")
    return calculate, reasons


def _mismatches(values: list[ExpectedValue], calculated: ModeloWorkCalculatePublicResultV3) -> list[str]:
    """Each stated casilla the calculation does not equal."""
    got = {item.key: restore_scalar(item.value) for item in calculated.calculation.casilla_values}
    return [
        f"c{casilla} exp {amount} got {got.get(casilla)}"
        for value in values
        for casilla, amount in value.casillas
        if _decimal(got.get(casilla)) != _decimal(amount)
    ]


def _unresolved(calculated: ModeloWorkCalculatePublicResultV3) -> str:
    """The bindings and casillas the calculation left unresolved."""
    return ", ".join(
        [f"binding {item.binding_id}" for item in calculated.unresolved_bindings]
        + [f"casilla {item.casilla_id} ({item.reason})" for item in calculated.unresolved_casillas]
    )


def _verify(world: PersonaWorld, work_unit_id: str, revision_id: str) -> tuple[Stage, str]:
    """The verify stage and its reason; a granted verification is then filed locally."""
    try:
        verified = run_operation(
            world,
            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=PERSONA_ACTOR),
            ModeloWorkVerifyPublicResultV2,
            subject=work_unit_id,
        )
    except PersonaMaterialisationError as error:
        return Stage.REFUSED, f"verify: {_short(error)}"
    if verified.granted_verificado_completo:
        return Stage.PASSED, _file_locally(world, work_unit_id, revision_id, verified)
    return Stage.INCOMPLETE, (
        f"verify: {verified.completeness_status}; {verified.finding_count} findings; "
        f"blocking: {_blocking_findings(verified) or 'none'}"
    )


def _export_path(plan: PlannedRow, exports: Path) -> Path:
    return exports / f"{plan.persona}-{plan.modelo}-{plan.year}-{plan.period}.txt"


def _counterparty_mismatches(
    persona: Persona, plan: PlannedRow, values: list[ExpectedValue], output: Path
) -> list[str]:
    """Each stated counterparty value the written fichero does not give, read through the registry layout."""
    with bundled_indexed_authority().operation() as operation:
        layout = _export_layout(operation, plan)
        return counterparty_mismatches(values, persona.identities, layout, output.read_bytes())


def _export_layout(operation: PinnedAuthorityOperation, plan: PlannedRow) -> ExportLayoutDefinition:
    """The fixed-width layout of the revision the law selects for the planned return."""
    revision = operation.revision_for_context(plan.modelo, filing_year=plan.year, period=plan.period)
    return operation.revision_with_export_layouts(plan.modelo, revision.id).export_layouts[0]


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
    world: PersonaWorld, plan: PlannedRow, exports: Path, work_unit_id: str, revision_id: str
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
        return Stage.REFUSED, "", f"export: {_short(error)}"
    if not isinstance(exported, ModeloExportPublicResultV3):
        return Stage.REFUSED, "", f"export: published {type(exported).__name__}, not ModeloExportPublicResultV3"
    detail = f"{exported.export_format}, {exported.byte_size} B, {exported.completeness}, {exported.evidence_status}"
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
        return f"file: {_short(error)}"
    return "filed locally"


def _owed_periods(persona: Persona, plan: PlannedRow) -> set[str]:
    """Every period the persona owes of the planned return's modelo; the year's last one carries the annual facts."""
    periods = {
        item_period
        for item in persona.expectations.obligations
        if item.modelo == plan.modelo
        for item_period in item.periods
    }
    return periods or {plan.period}


def _scope(persona: Persona) -> ReplayScope:
    """The records scope when the persona holds a return history, else the full ledger.

    The table takes every return of the history through calculate, verify,
    export and local filing itself, in chain order, so the replay records only
    what those returns read.
    """
    if persona.filed_returns or persona.calculated_returns or persona.local_observations or persona.aeat_filings:
        return ReplayScope.RECORDS
    return ReplayScope.FULL


@pytest.mark.parametrize(("persona_id", "horizon"), _cases())
def test_persona_returns(tmp_path: Path, persona_id: str, horizon: int) -> None:
    """Replay one persona under one horizon and append a row for every return it owes there."""
    out = Path(os.environ[OUT_ENV])
    plans = _plan(persona_id, horizon)
    persona = _persona(persona_id)
    try:
        with materialised_persona(persona_id, tmp_path, _scope(persona), reuse=True, horizon=horizon) as materialised:
            envelope = materialised.world.envelope
            for plan in plans:
                values = _values(materialised.persona, envelope, plan)
                write_rows(out, [_run_return(materialised, plan, values, tmp_path / "exports")])
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        write_rows(out, [not_run(plan, f"replay under horizon {horizon}: {_short(error)}") for plan in plans])
