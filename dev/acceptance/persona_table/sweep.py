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

import os
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
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
from cadrumo.domain.calculations.registry.bindings import binding_source_modelo
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.filing.errors import ModeloBuilderError
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    attest_before_first_calculation,
    filing_key,
    materialised_persona,
    run_operation,
    settle_operation,
    year_envelope,
)
from cadrumo.entrypoints.tests.persona_prior_carries import attest_prior_carries
from cadrumo.entrypoints.tests.persona_rental_carries import attest_pending_rental_carries
from cadrumo.tests.personas import (
    ExpectedValue,
    Persona,
    PersonaCatalogueError,
    YearEnvelope,
    persona_ids,
    read_persona,
)

from .calendar_sweep import calendar_observations
from .counterparties import DESIGNS, counterparty_mismatches, is_compared
from .export_readback import read_fields, readback_mismatches, readback_reason, unreadable_reason
from .export_text import check_export_text, violation_reason
from .roles import StatedCasilla, compared, differing, edition_identities, mismatch_text, revision_identities
from .row_figures import merge_row_figures, row_figures
from .rows import (
    PlannedRow,
    Stage,
    TableRow,
    canonical_figures,
    in_force,
    is_unsupported,
    not_owed_stage,
    not_run,
    owed_rows,
    replay_horizons,
    replayed,
    select,
    stage_refusal_codes,
    write_rows,
)
from .unchecked import persona_at

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

OUT_ENV = "PERSONA_TABLE_OUT"
PERSONAS_ENV = "PERSONA_TABLE_PERSONAS"
MODELOS_ENV = "PERSONA_TABLE_MODELOS"
YEARS_ENV = "PERSONA_TABLE_YEARS"

_SETTLED = re.compile(r"^(?P<definition>\S+) settled (?P<condition>\S+) \((?P<code>[^)]*)\)")
_REASON_LIMIT = 900
_CALCULATED = frozenset({Stage.PASSED, Stage.CALCULATED})


def _listed(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.environ.get(name, "").split(",") if item.strip())


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


@cache
def _persona(persona_id: str) -> Persona:
    return read_persona(persona_id, envelope=_envelope())


@cache
def _persona_at(persona_id: str, horizon: int) -> Persona:
    """The persona as the replay under ``horizon`` reads it; see :func:`.unchecked.persona_at`."""
    return persona_at(persona_id, horizon, _envelope())


@cache
def _sources(modelo: str) -> frozenset[str]:
    """Every modelo a revision of ``modelo`` reads, as its bindings and dependency classifications declare."""
    with bundled_indexed_authority().operation() as operation:
        revisions = [
            operation.revision(owner, revision_id) for owner, revision_id in operation.revision_ids() if owner == modelo
        ]
    return frozenset(
        {
            source
            for revision in revisions
            for binding in revision.bindings
            if (source := binding_source_modelo(binding)) is not None
        }
        | {
            classification.source_modelo
            for revision in revisions
            for classification in revision.dependency_classifications
        }
    )


def _plan(persona_id: str, horizon: int) -> tuple[list[PlannedRow], frozenset[tuple[str, str, int, str]]]:
    """The rows the replay runs, in chain order, and the keys of the selected rows it writes."""
    rows = owed_rows(_persona_at(persona_id, horizon), horizon, _envelope())
    selected = select(rows, modelos=_listed(MODELOS_ENV), years=tuple(int(year) for year in _listed(YEARS_ENV)))
    return replayed(rows, selected, _sources), frozenset(row.key for row in selected)


def _cases() -> list[pytest.ParameterSet]:
    wanted = _listed(PERSONAS_ENV)
    return [
        pytest.param(persona_id, horizon, id=f"{persona_id}@{horizon}")
        for persona_id in persona_ids()
        if not wanted or persona_id in wanted
        for horizon in replay_horizons(_envelope())
        if _plan(persona_id, horizon)[1]
    ]


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
    """Create, calculate, verify and export one return; the row records where it stopped and why.

    A return stated not owed is created, calculated and compared, then checked against the overview calendar
    instead of being verified, exported and filed.
    """
    world = materialised.world
    if filing_key(plan.modelo, plan.year, plan.period) in materialised.filings:
        return TableRow.from_plan(plan, Stage.HISTORY_FILED, verify=Stage.HISTORY_FILED)
    stating = next((value for value in values if value.refusal is not None), None)
    at_calculate = _refusal_at_calculate(stating)
    try:
        work_unit_id = _create(world, plan)
        if isinstance(work_unit_id, TableRow):
            return work_unit_id
        calculated = _calculate(materialised, plan, work_unit_id)
    except PersonaMaterialisationError as error:
        return _refused(plan, at_calculate, error)
    rows = row_figures(world, calculated)
    figures = _figures(calculated, rows)
    calculate, reasons = _compare(plan, values, at_calculate, calculated, rows)
    if not plan.owed:
        verify, not_owed_reason = _not_owed(materialised, plan)
        reasons += [not_owed_reason] if not_owed_reason else []
        return TableRow.from_plan(
            plan, calculate, verify=verify, reason=" | ".join(reasons)[:_REASON_LIMIT], figures=figures
        )
    revision_id = calculated.calculation_revision_id
    verify, verify_reason = _verify(world, work_unit_id, revision_id)
    export, export_detail, export_reason = _export(world, plan, values, exports, work_unit_id, revision_id)
    calculate, reasons = _with_counterparties(calculate, reasons, values, materialised.persona, plan, exports, export)
    reasons += [reason for reason in (verify_reason, export_reason) if reason]
    stage_reasons = {"verify": verify_reason, "export": export_reason}
    calculate = _at_stated_stage(stating, calculate, reasons, stage_reasons)
    return TableRow.from_plan(
        plan,
        calculate,
        verify=verify,
        export=export,
        reason=" | ".join(reasons)[:_REASON_LIMIT],
        export_detail=export_detail,
        figures=figures,
    )


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


def _refusal_at_calculate(stating: ExpectedValue | None) -> str | None:
    """The stated refusal when the persona states it at calculate, else none."""
    return stating.refusal if stating is not None and stating.refusal_stage == "calculate" else None


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
    """Calculate the work unit; a Modelo 303 carries its joint-return and annual-summary evidence.

    A Modelo 100 first states the persona's pending carries of earlier ejercicios that no earlier return in the
    profile supplies, through the operations the calculation's refusal names. A return the operator enters nothing on
    first states the prior figures the persona attests for it, since its calculation refuses while a required source
    return is neither held nor stated.
    """
    world = materialised.world
    if plan.modelo == "100":
        attest_prior_carries(materialised.persona, world, work_unit_id, plan.year)
    attest_before_first_calculation(
        world, modelo=plan.modelo, year=plan.year, period=plan.period, work_unit_id=work_unit_id
    )
    evidence = None
    if plan.modelo == "303":
        last_period = max(
            (p for p in _owed_periods(materialised.persona, plan) if p.endswith("T")), default=plan.period
        )
        evidence = _m303_evidence(
            world, work_unit_id=work_unit_id, year=plan.year, period=plan.period, last_period=last_period
        )
    request = ModeloWorkCalculateRequest(
        work_unit_id=work_unit_id, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=evidence
    )
    calculated = run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        request,
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )
    # A let property's row stands with its net yield withheld until its pending carry is stated; the statement
    # is kept on the revision, so calculating again reads it.
    if plan.modelo == "100" and attest_pending_rental_carries(materialised.persona, world, work_unit_id, plan.year):
        calculated = run_operation(
            world,
            MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            request,
            ModeloWorkCalculatePublicResultV3,
            subject=work_unit_id,
        )
    return calculated


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
        return Stage.REFUSED, f"overview: {_short(error)}"
    return not_owed_stage(observations, (plan.modelo, plan.year, plan.period))


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
        return Stage.REFUSED, "", f"export: {_short(error)}"
    if not isinstance(exported, ModeloExportPublicResultV3):
        return Stage.REFUSED, "", f"export: published {type(exported).__name__}, not ModeloExportPublicResultV3"
    detail = f"{exported.export_format}, {exported.byte_size} B, {exported.completeness}, {exported.evidence_status}"
    text_reason = _text_reason(plan, output)
    if text_reason:
        return Stage.REFUSED, detail, text_reason
    readback = _readback_reason(plan, values, output)
    if readback:
        return Stage.REFUSED, detail, readback
    return Stage.PASSED, detail, ""


def _readback_reason(plan: PlannedRow, values: list[ExpectedValue], output: Path) -> str:
    """The stated casilla values the written fichero carries with another value, or empty when it agrees.

    A file the registry parser cannot read is itself an export defect, reported as the reason.
    """
    casillas = edition_identities(plan.modelo, plan.year, plan.period)
    with bundled_indexed_authority().operation() as operation:
        layout = _export_layout(operation, plan)
        try:
            parsed = read_fields(
                layout,
                output.read_bytes(),
                modelo=plan.modelo,
                year=plan.year,
                period=plan.period,
                operation=operation,
            )
        except (RegistryError, ModeloBuilderError) as error:
            return unreadable_reason(error)
    return readback_reason(readback_mismatches(values, casillas, plan.unchecked, parsed))


def _text_reason(plan: PlannedRow, output: Path) -> str:
    """The first character-rule violation of the written fichero against its design, or empty when clean."""
    with bundled_indexed_authority().operation() as operation:
        layout = _export_layout(operation, plan)
        return violation_reason(check_export_text(layout, output.read_bytes()))


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
    plans, emitted = _plan(persona_id, horizon)
    persona = _persona(persona_id)
    try:
        with materialised_persona(persona_id, tmp_path, _scope(persona), reuse=True, horizon=horizon) as materialised:
            envelope = materialised.world.envelope
            for plan in plans:
                values = _values(materialised.persona, envelope, plan)
                row = _run_return(materialised, plan, values, tmp_path / "exports")
                if plan.key in emitted:
                    write_rows(out, [row])
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        reason = f"replay under horizon {horizon}: {_short(error)}"
        write_rows(out, [not_run(plan, reason) for plan in plans if plan.key in emitted])
