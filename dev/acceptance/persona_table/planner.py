"""Planner of the persona table: which returns a persona's replay runs, and how one is readied for calculation.

This module has no side effect at import: it builds no plan and reads no authority until a function of it is
called, so a surface can import it without the cost, or the failure, of collecting the table's cases. The
collector, which parametrizes every persona and horizon, is ``sweep``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import cache

from cadrumo.application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import binding_source_modelo
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    attest_before_first_calculation,
    filing_key,
    run_operation,
    settle_operation,
    year_envelope,
)
from cadrumo.entrypoints.tests.persona_prior_carries import attest_prior_carries
from cadrumo.tests.personas import ExpectedValue, Persona, YearEnvelope

from .cli_column.world_report import StatementKind
from .counterparties import is_compared
from .rows import PlannedRow, Stage, TableRow, in_force, is_unsupported, owed_rows, replayed, select
from .unchecked import persona_at

MODELOS_ENV = "PERSONA_TABLE_MODELOS"
YEARS_ENV = "PERSONA_TABLE_YEARS"

STAGE_ORDER_ENV = "PERSONA_TABLE_STAGE_ORDER"
STAGE_ORDERS = ("legacy", "lifecycle")
"""``legacy`` files a granted verification inside the verify stage, before the export; ``lifecycle`` files after it."""
DEFAULT_STAGE_ORDER = "legacy"
"""The order a run takes when none is named; the one place to change to move the table to the lifecycle order."""

REASON_LIMIT = 900
"""The longest reason a row keeps."""

_SETTLED = re.compile(r"^(?P<definition>\S+) settled (?P<condition>\S+) \((?P<code>[^)]*)\)")


def listed(name: str) -> tuple[str, ...]:
    """The comma-separated items the environment variable ``name`` holds, empty when it is unset."""
    return tuple(item.strip() for item in os.environ.get(name, "").split(",") if item.strip())


def stage_order_in_use() -> str:
    """The stage order the run's environment names, or the default; an unknown name is refused."""
    order = os.environ.get(STAGE_ORDER_ENV, "").strip() or DEFAULT_STAGE_ORDER
    if order not in STAGE_ORDERS:
        raise ValueError(f"{STAGE_ORDER_ENV} is {order!r}; expected one of {', '.join(STAGE_ORDERS)}")
    return order


@cache
def registry_envelope() -> YearEnvelope:
    """The supported-year envelope of the bundled authority."""
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


@cache
def persona_under_horizon(persona_id: str, horizon: int) -> Persona:
    """The persona as the replay under ``horizon`` reads it; see :func:`.unchecked.persona_at`."""
    return persona_at(persona_id, horizon, registry_envelope())


@cache
def source_returns(modelo: str) -> frozenset[str]:
    """Every modelo whose return a revision of ``modelo`` reads, as its bindings and dependency classifications declare.

    This is the registry's binding and dependency graph, one edge deep: a Modelo 303 that carries a credit from an
    earlier period or reads the Modelo 390 summary names those modelos, and a Modelo 100 that reads withholdings
    names the withholding returns. It can name ``modelo`` itself when a revision reads its own earlier period.
    """
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


def plan_rows(persona_id: str, horizon: int) -> tuple[list[PlannedRow], frozenset[tuple[str, str, int, str]]]:
    """The rows the replay runs, in chain order, and the keys of the selected rows it writes.

    Each planned row names, in ``sources_returns``, the modelos whose returns it reads.
    """
    rows = owed_rows(persona_under_horizon(persona_id, horizon), horizon, registry_envelope())
    selected = select(rows, modelos=listed(MODELOS_ENV), years=tuple(int(year) for year in listed(YEARS_ENV)))
    replay = replayed(rows, selected, source_returns)
    return [replace(row, sources_returns=tuple(sorted(source_returns(row.modelo)))) for row in replay], frozenset(
        row.key for row in selected
    )


def stated_values(persona: Persona, envelope: YearEnvelope, plan: PlannedRow) -> list[ExpectedValue]:
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


def replay_scope(persona: Persona) -> ReplayScope:
    """The records scope when the persona holds a return history, else the full ledger.

    The table takes every return of the history through calculate, verify,
    export and local filing itself, in chain order, so the replay records only
    what those returns read.
    """
    if persona.filed_returns or persona.calculated_returns or persona.local_observations or persona.aeat_filings:
        return ReplayScope.RECORDS
    return ReplayScope.FULL


@dataclass(frozen=True, slots=True)
class PreparedReturn:
    """A return the table has created and readied for its first calculation."""

    work_unit_id: str
    request: ModeloWorkCalculateRequest
    """The calculate request the table submits, carrying a Modelo 303's joint-return and annual-summary evidence."""


def prepare_return(
    materialised: MaterialisedPersona,
    plan: PlannedRow,
    values: list[ExpectedValue],
    *,
    left: frozenset[StatementKind] = frozenset(),
) -> PreparedReturn | TableRow:
    """Create one return and state everything the table states before its first calculation.

    The result is the world the calculate operation meets, or the row of a return that stopped first: one the
    history already filed, one whose create or whose statements were refused, or one whose refusal the persona
    states. A caller that does not calculate takes the prepared return and its request from here. The statements
    are those of :func:`state_before_first_calculation`, then :func:`build_calculation_request`, in that order.
    ``left`` names the kinds of statement a caller leaves unstated because an operator states them in another
    surface; none is left by default.
    """
    world = materialised.world
    if filing_key(plan.modelo, plan.year, plan.period) in materialised.filings:
        return TableRow.from_plan(plan, Stage.HISTORY_FILED, verify=Stage.HISTORY_FILED)
    at_calculate = refusal_at_calculate(stated_refusal(values))
    try:
        work_unit_id = _create(world, plan)
        if isinstance(work_unit_id, TableRow):
            return work_unit_id
        state_before_first_calculation(materialised, plan, work_unit_id, left=left)
        request = build_calculation_request(materialised, plan, work_unit_id)
    except PersonaMaterialisationError as error:
        return refusal_row(plan, at_calculate, error)
    return PreparedReturn(work_unit_id=work_unit_id, request=request)


def state_before_first_calculation(
    materialised: MaterialisedPersona,
    plan: PlannedRow,
    work_unit_id: str,
    *,
    left: frozenset[StatementKind] = frozenset(),
) -> None:
    """State what the first calculation of a created return needs beforehand; build no request.

    A Modelo 100 first states the persona's pending carries of earlier ejercicios that no earlier return in the
    profile supplies, through the operations the calculation's refusal names. Every return then states the prior
    figures the persona attests for it (``attest_before_first_calculation``), where the world records any, since
    its calculation refuses while a required source return is neither held nor stated. The Modelo 390 exemption
    attestation of a Modelo 303 is not made here; :func:`build_calculation_request` makes it. A kind named in
    ``left`` is not stated.
    """
    world = materialised.world
    if plan.modelo == "100" and StatementKind.PRIOR_CARRIES not in left:
        attest_prior_carries(materialised.persona, world, work_unit_id, plan.year)
    if StatementKind.PRIOR_VALUE not in left:
        attest_before_first_calculation(
            world, modelo=plan.modelo, year=plan.year, period=plan.period, work_unit_id=work_unit_id
        )


def build_calculation_request(
    materialised: MaterialisedPersona, plan: PlannedRow, work_unit_id: str
) -> ModeloWorkCalculateRequest:
    """The request that calculates a created return, after :func:`state_before_first_calculation`.

    A Modelo 303 carries its joint-return and annual-summary evidence: in the last quarter of the year it first
    makes the Modelo 390 exemption attestation the persona's world records, which is the one statement this step
    makes. Any other return makes none.
    """
    evidence = None
    if plan.modelo == "303":
        evidence = _m303_evidence(
            materialised.world,
            work_unit_id=work_unit_id,
            year=plan.year,
            period=plan.period,
            last_period=last_owed_period(materialised.persona, plan),
        )
    return ModeloWorkCalculateRequest(
        work_unit_id=work_unit_id, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=evidence
    )


def stated_refusal(values: list[ExpectedValue]) -> ExpectedValue | None:
    """The first stated value that names a refusal, if the persona states one for the return."""
    return next((value for value in values if value.refusal is not None), None)


def refusal_at_calculate(stating: ExpectedValue | None) -> str | None:
    """The stated refusal when the persona states it at calculate, else none."""
    return stating.refusal if stating is not None and stating.refusal_stage == "calculate" else None


def refusal_code(error: BaseException) -> str:
    """The condition code a settled operation's error names, empty when it does not name one."""
    match = _SETTLED.match(str(error))
    return str(match["code"]) if match else ""


def refusal_text(error: BaseException) -> str:
    """The error as a row's reason: the operation, how it settled, its code and its detail."""
    match = _SETTLED.match(str(error))
    if match is None:
        return f"{type(error).__name__}: {error}"[:REASON_LIMIT]
    detail = str(error)[match.end() :].removeprefix(": ")
    head = f"{match['definition']} {match['condition']} {match['code']}"
    return (head if detail == "no detail" else f"{head} :: {detail}")[:REASON_LIMIT]


def refusal_row(plan: PlannedRow, stated: str | None, error: PersonaMaterialisationError) -> TableRow:
    """The row of a return refused before it calculated: expected when the persona states that refusal."""
    code = refusal_code(error)
    if stated is not None and stated == code:
        return TableRow.from_plan(plan, Stage.EXPECTED_REFUSAL, reason=refusal_text(error))
    stage = Stage.UNSUPPORTED if is_unsupported(code) else Stage.REFUSED
    return TableRow.from_plan(plan, stage, reason=refusal_text(error))


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
        return TableRow.from_plan(plan, Stage.REFUSED, reason=f"create refused: {outcome.reason}"[:REASON_LIMIT])
    return outcome.unit.work_unit_id


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


def owed_periods(persona: Persona, plan: PlannedRow) -> set[str]:
    """Every period the persona owes of the planned return's modelo; the year's last one carries the annual facts."""
    periods = {
        item_period
        for item in persona.expectations.obligations
        if item.modelo == plan.modelo
        for item_period in item.periods
    }
    return periods or {plan.period}


def last_owed_period(persona: Persona, plan: PlannedRow) -> str:
    """The year's last quarterly period the persona owes of the planned return's modelo, else the return's own."""
    return max((period for period in owed_periods(persona, plan) if period.endswith("T")), default=plan.period)
