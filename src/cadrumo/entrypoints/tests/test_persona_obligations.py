"""Each canonical persona owes, and does not owe, what its hand-grounded expectations state, per year and period.

The expectations (``dev/fixtures/personas/<persona>/expectations.toml``) are
derived from the ledger and the law, never from a run. Each case materialises
the persona through production operations, reads its obligations through the
registered overview operations (the explanation of a modelo and the calendar of
its filing windows) and calculates the periods whose casillas the expectations
state. A mismatch is a product or expectation defect to be re-derived, never
copied: nothing here edits an expected value to agree with a run.

An expectation grounded ``unverified`` is a known gap and is not asserted. A
value stated only as named concepts, or per counterparty, carries no registry
casilla and is not re-derived here. A value that states a ``refusal`` asserts
that the application refuses the period with that error code; a casilla stated
``not_sourced`` asserts that the application does not yet carry the figure the
law gives; an obligation that states a ``calendar_advice`` asserts that the
calendar advises it instead of showing a window row.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path

import pytest

from ...application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ...application.modelo.revision_selection_operation import (
    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionProjection,
    ModeloWorkRevisionRequest,
)
from ...application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionSnapshotProjection,
    ModeloWorkRevisionSnapshotRequest,
)
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import PublicNamedScalar, restore_scalar
from ...application.overview.read_calendar_item_projection import OverviewCalendarEntrySnapshot
from ...application.overview.read_payload import OverviewCalendarRead, OverviewExplainRead
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...tests.personas import ExpectedObligation, Persona, YearEnvelope, persona_ids, read_persona, values_in_force
from .persona_materialisation import (
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

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@dataclass(frozen=True, slots=True)
class _Case:
    persona_id: str
    year: int

    @property
    def id(self) -> str:
        return f"{self.persona_id}-{self.year}"


@cache
def _personas() -> dict[str, Persona]:
    """Every persona of the catalogue, read under the registry's year envelope."""
    return {persona_id: read_persona(persona_id, envelope=_envelope()) for persona_id in persona_ids()}


def _asserted_obligations(persona: Persona) -> list[tuple[int, ExpectedObligation]]:
    envelope = _envelope()
    return [
        (item.year.resolve(envelope), item)
        for item in persona.expectations.obligations
        if item.grounding != "unverified"
    ]


@cache
def _envelope() -> YearEnvelope:
    """The registry's supported filing-year envelope."""
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _cases(select: Callable[[Persona], set[int]]) -> list[pytest.ParameterSet]:
    return [
        pytest.param(_Case(persona_id, year), id=_Case(persona_id, year).id)
        for persona_id, persona in _personas().items()
        for year in sorted(select(persona))
    ]


def _obligation_years(persona: Persona) -> set[int]:
    return {year for year, _item in _asserted_obligations(persona)}


def _value_years(persona: Persona) -> set[int]:
    envelope = _envelope()
    return {
        year
        for year, value in values_in_force(persona.expectations.values, envelope)
        if (value.casillas or value.not_sourced or value.refusal is not None) and value.grounding != "unverified"
    }


def _scope(persona: Persona) -> ReplayScope:
    """The history scope when the persona holds returns or observations of earlier years, else the full ledger."""
    return (
        ReplayScope.HISTORY
        if persona.filed_returns or persona.calculated_returns or persona.local_observations or persona.aeat_filings
        else ReplayScope.FULL
    )


def _read(world: PersonaWorld, request: OverviewReadRequest) -> OverviewReadProjection:
    return run_operation(world, OVERVIEW_READ_DEFINITION_IDS[request.kind], request, OverviewReadProjection)


def _next_business_day(day: date) -> date:
    following = day + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return following


@pytest.mark.parametrize("case", _cases(_obligation_years))
def test_the_overview_resolves_the_obligations_a_persona_has_and_lacks(tmp_path: Path, case: _Case) -> None:
    persona = _personas()[case.persona_id]
    envelope = _envelope()
    obligations = [item for year, item in _asserted_obligations(persona) if year == case.year]
    deadlines = [
        item
        for item in persona.expectations.deadlines
        if item.year.resolve(envelope) == case.year and item.grounding != "unverified"
    ]

    problems: list[str] = []
    entries: dict[tuple[str, str], OverviewCalendarEntrySnapshot] = {}
    advised: set[tuple[str, str]] = set()
    verdicts: dict[str, tuple[ApplicabilityVerdict, bool]] = {}
    with materialised_persona(case.persona_id, tmp_path, _scope(persona), reuse=True) as materialised:
        world = materialised.world
        try:
            calendar_read = _read(
                world,
                OverviewReadRequest(
                    profile_id=world.profile_id,
                    kind=OverviewReadKind.CALENDAR,
                    output_language=OutputLanguage.ES,
                    from_date=date(case.year, 1, 1),
                    to_date=date(case.year + 1, 12, 31),
                ),
            ).payload
        except PersonaMaterialisationError as error:
            problems.append(f"the calendar read was refused: {error}")
        else:
            assert isinstance(calendar_read, OverviewCalendarRead)
            assert calendar_read.calendar is not None
            entries = {
                (entry.modelo, entry.period.rsplit(" ", 1)[-1]): entry
                for entry in calendar_read.calendar.entries
                if entry.filing_year == case.year
            }
            advised = {(item.modelo, item.reason.value) for item in calendar_read.calendar.coverage.advised}
        for item in obligations:
            try:
                explained = _read(
                    world,
                    OverviewReadRequest(
                        profile_id=world.profile_id,
                        kind=OverviewReadKind.EXPLAIN,
                        output_language=OutputLanguage.ES,
                        modelo=item.modelo,
                        year=case.year,
                    ),
                ).payload
            except PersonaMaterialisationError as error:
                problems.append(f"Modelo {item.modelo}: the explanation was refused: {error}")
                continue
            assert isinstance(explained, OverviewExplainRead)
            verdicts[item.modelo] = (explained.explanation.verdict, explained.explanation.applicable)

    for item in obligations:
        expected_verdict = (
            (ApplicabilityVerdict.INCOMPLETE, False)
            if item.applicable == "unknown"
            else (ApplicabilityVerdict.APPLICABLE, True)
            if item.applicable
            else (ApplicabilityVerdict.NOT_APPLICABLE, False)
        )
        if item.modelo in verdicts and verdicts[item.modelo] != expected_verdict:
            problems.append(
                f"Modelo {item.modelo} {case.year}: explanation says {verdicts[item.modelo]}, "
                f"expected {expected_verdict} ({item.legal_ref})"
            )
        # A modelo the persona must file has a window row for each period; one it lacks, or cannot decide, has none.
        if item.calendar_advice is not None:
            if (item.modelo, item.calendar_advice) not in advised:
                problems.append(
                    f"Modelo {item.modelo} {case.year}: calendar does not advise {item.calendar_advice} "
                    f"({item.legal_ref})"
                )
            problems.extend(
                f"Modelo {item.modelo} {case.year} {period}: calendar row present, expected the "
                f"{item.calendar_advice} advice instead ({item.legal_ref})"
                for period in item.periods
                if (item.modelo, period) in entries
            )
        elif entries or not any("calendar read was refused" in each for each in problems):
            problems.extend(
                f"Modelo {item.modelo} {case.year} {period}: calendar row {'absent' if item.applicable is True else 'present'}, "
                f"expected {'present' if item.applicable is True else 'absent'} ({item.legal_ref})"
                for period in item.periods
                if ((item.modelo, period) in entries) != (item.applicable is True)
            )
    for deadline in deadlines:
        entry = entries.get((deadline.modelo, deadline.period))
        statutory_end = deadline.statutory_end.resolve(envelope)
        if entry is None:
            problems.append(
                f"Modelo {deadline.modelo} {case.year} {deadline.period}: no window for the stated deadline"
            )
        elif entry.closes_on != statutory_end and entry.adjusted_closes_on != _next_business_day(statutory_end):
            problems.append(
                f"Modelo {deadline.modelo} {case.year} {deadline.period}: window closes {entry.closes_on} "
                f"(adjusted {entry.adjusted_closes_on}), statute gives {statutory_end} ({deadline.legal_ref})"
            )
    assert not problems, "\n".join(problems)


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _m303_evidence(
    world: PersonaWorld, *, work_unit_id: str, year: int, period: str
) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    """The ordinary Modelo 303 filing facts: no joint return, and the Modelo 390 attestation in the fourth quarter."""
    if period != "4T":
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


def _calculated_casillas(materialised: MaterialisedPersona, modelo: str, year: int, period: str) -> dict[str, object]:
    """The casilla values the application holds for one return, or the operation's refusal as ``{"refusal": reason}``."""
    world = materialised.world
    key = filing_key(modelo, year, period)
    revision_id = materialised.filings.get(key) or materialised.calculations.get(key)
    try:
        if revision_id is not None:
            selected = run_operation(
                world,
                MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
                ModeloWorkRevisionRequest(profile_id=world.profile_id, calculation_revision_id=revision_id),
                ModeloWorkRevisionProjection,
            )
            snapshot = run_operation(
                world,
                MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
                ModeloWorkRevisionSnapshotRequest(profile_id=world.profile_id, calculation_revision_id=revision_id),
                ModeloWorkRevisionSnapshotProjection,
                subject=selected.unit.work_unit_id,
            )
            values: tuple[PublicNamedScalar, ...] = snapshot.calculation.casilla_values
        else:
            created = settle_operation(
                world,
                MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
                ModeloWorkCreateRequest(
                    profile_id=world.profile_id,
                    modelo=modelo,
                    period=PublicPeriod(filing_year=year, code=period),
                    actor=PERSONA_ACTOR,
                ),
            )
            outcome = getattr(created, "outcome", None)
            if not isinstance(outcome, ModeloWorkCreateSuccess):
                return {"refusal": f"work creation refused: {outcome}"}
            work_unit_id = outcome.unit.work_unit_id
            calculated = run_operation(
                world,
                MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                ModeloWorkCalculateRequest(
                    work_unit_id=work_unit_id,
                    actor=PERSONA_ACTOR,
                    ordinary_m303_filing_evidence=(
                        _m303_evidence(world, work_unit_id=work_unit_id, year=year, period=period)
                        if modelo == "303"
                        else None
                    ),
                ),
                ModeloWorkCalculatePublicResultV3,
                subject=work_unit_id,
            )
            values = calculated.calculation.casilla_values
    except PersonaMaterialisationError as error:
        return {"refusal": str(error)}
    return {item.key: restore_scalar(item.value) for item in values}


@pytest.mark.parametrize("case", _cases(_value_years))
def test_the_application_calculates_the_casillas_a_persona_expects(tmp_path: Path, case: _Case) -> None:
    persona = _personas()[case.persona_id]
    envelope = _envelope()
    stated = [
        value
        for year, value in values_in_force(persona.expectations.values, envelope)
        if (value.casillas or value.not_sourced or value.refusal is not None)
        and value.grounding != "unverified"
        and year == case.year
    ]
    expected = {
        (value.modelo, value.period): {casilla: _decimal(amount) for casilla, amount in value.casillas}
        for value in stated
    }
    legal_refs = {(value.modelo, value.period): value.legal_ref for value in stated}
    refusals = {(value.modelo, value.period): value.refusal for value in stated if value.refusal is not None}
    not_sourced = {
        (value.modelo, value.period): {casilla: _decimal(amount) for casilla, amount in value.not_sourced}
        for value in stated
    }

    problems: list[str] = []
    with materialised_persona(case.persona_id, tmp_path, _scope(persona), reuse=True) as materialised:
        for (modelo, period), casillas in expected.items():
            calculated = _calculated_casillas(materialised, modelo, case.year, period)
            where = f"Modelo {modelo} {case.year} {period} ({legal_refs[modelo, period]})"
            if (refusal := refusals.get((modelo, period))) is not None:
                if refusal not in str(calculated.get("refusal", "")):
                    problems.append(
                        f"{where}: expected the stated refusal {refusal}, got "
                        f"{calculated.get('refusal', 'a calculation')}"
                    )
                continue
            if "refusal" in calculated:
                problems.append(f"{where}: calculation refused: {calculated['refusal']}")
                continue
            problems.extend(
                f"{where} casilla {casilla}: expected {amount}, got {actual}"
                for casilla, amount in casillas.items()
                if (actual := _decimal(calculated[casilla]) if casilla in calculated else None) != amount
            )
            problems.extend(
                f"{where} casilla {casilla}: now carries the law's {amount}; compare it instead of stating it not sourced"
                for casilla, amount in not_sourced[modelo, period].items()
                if casilla in calculated and _decimal(calculated[casilla]) == amount
            )
    assert not problems, "\n".join(problems)
