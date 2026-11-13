"""A grupo mercantil mark sets the held preceding return aside for the preceding-period turnover.

LIS art. 101.3 measures the net turnover over the whole group when the entity
belongs to a grupo mercantil (casilla 00039), which the entity's own preceding
return does not show. The registry declares the mark on the carry. Marked, the
held return is set aside: the calculation refuses until the filer states the
figure, the statement is admitted although the return is held, and the clean
state blocks until it is stated. Unmarked, the held return supplies the figure
and a statement over it is refused.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production edit executor, calculation, clean-state evaluation and reader,
for every year of the support envelope whose edition declares the mark.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....application.calculations.cross_period_clean_state import (
    attestable_carry_binding_ids,
    evaluate_cross_period_clean_state,
)
from ....application.calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
)
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ....application.modelo.incn_periodo_anterior import (
    INCN_PERIODO_ANTERIOR_BINDING_ID,
    IncnPeriodoAnterior,
    IncnPeriodoAnteriorOrigin,
    IncnPeriodoAnteriorStores,
    resolve_incn_periodo_anterior,
)
from ....application.modelo.verification_cross_period import operator_value_attestations
from ....application.modelo.work_form_service import modelo_form_snapshot
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.binding_prior_value_rules import set_aside_binding_ids
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_preceding_m200_turnover

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "200"
_PERIOD = "0A"
_ENTITY = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="identity.legal_name", value="Test Company SL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
    UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
    UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
)
_HELD = Decimal("812345.67")
_GROUP = Decimal("14500000.00")


def _marks_by_year() -> dict[int, tuple[CasillaId, ...]]:
    with bundled_indexed_authority().operation() as operation:
        marks: dict[int, tuple[CasillaId, ...]] = {}
        for year in operation.supported_filing_years().years:
            snapshot = operation.snapshot(
                _MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
            )
            for binding in snapshot.revision.bindings:
                marked = binding.held_source_set_aside_when_marked
                if binding.id == INCN_PERIODO_ANTERIOR_BINDING_ID and marked is not None and len(marked) > 0:
                    marks[year] = marked
        return marks


_MARKS = _marks_by_year()
_YEARS = tuple(_MARKS)


def test_some_supported_year_declares_the_mark() -> None:
    assert _YEARS


@contextmanager
def _held_work(tmp_path: Path, year: int) -> Generator[SeededOperatorWork]:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path,
            modelo=_MODELO,
            filing_year=year,
            period_code=_PERIOD,
            extra_facts=_ENTITY,
            estimation_regime=None,
        ) as work,
    ):
        save_preceding_m200_turnover(
            CalculationObservationRepository(),
            filing_year=year,
            turnover=_HELD,
            captured_at=datetime(year, 1, 15, tzinfo=UTC),
        )
        yield work


def _marked(year: int) -> tuple[ModeloScalarEditIntentV1, ...]:
    return tuple(
        ModeloScalarEditIntentV1(
            address=ModeloEditScalarAddressV1(casilla_id=mark),
            kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
            value=Decimal("1"),
        )
        for mark in _MARKS[year]
    )


def _statements(work: SeededOperatorWork, *, turnover: Decimal | None) -> tuple[ModeloBindingEditIntentV1, ...]:
    """Zero for every other carry the profile offers a statement for, and ``turnover`` for the preceding turnover when given."""
    snapshot = modelo_form_snapshot(
        work.operation, work.work_unit.modelo, work.work_unit.filing_year, work.work_unit.period
    )
    offered = attestable_carry_binding_ids(
        snapshot,
        operation=work.operation,
        observation_repository=work.ports.observation_repository,
        filing_catalogue=work.ports.filing_repository.load(),
        work_catalogue=work.ports.work_unit_repository.load(),
    )
    others = tuple(
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=binding_id),
            kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
            value=Decimal("0"),
        )
        for binding_id in sorted(offered)
        if binding_id != INCN_PERIODO_ANTERIOR_BINDING_ID
    )
    if turnover is None:
        return others
    return (
        *others,
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=INCN_PERIODO_ANTERIOR_BINDING_ID),
            kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
            value=turnover,
        ),
    )


def _clean_state(work: SeededOperatorWork, *, stated: bool) -> CrossPeriodDependencyEvidence:
    """The preceding-turnover dependency as the clean state sees the current return, with or without its statements."""
    head = work.require_head()
    snapshot = modelo_form_snapshot(
        work.operation, work.work_unit.modelo, work.work_unit.filing_year, work.work_unit.period
    )
    verdict = evaluate_cross_period_clean_state(
        snapshot,
        operation=work.operation,
        bucket_id=work.work_unit.bucket_id,
        observation_repository=work.ports.observation_repository,
        filing_repository=work.ports.filing_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(),
        justificante_repository=JustificanteRepository(),
        taxpayer_tax_id="B00015016",
        operator_value_attestations=operator_value_attestations(head) if stated else {},
        work_catalogue=work.ports.work_unit_repository.load(),
        set_aside_binding_ids=set_aside_binding_ids(snapshot.revision, head.casilla_values),
    )
    (evidence,) = [
        item for item in verdict.dependencies if INCN_PERIODO_ANTERIOR_BINDING_ID in item.requirement.origin_ids
    ]
    return evidence


def _read(work: SeededOperatorWork, *, twelve_month_statement: Decimal | None = None) -> IncnPeriodoAnterior:
    """The preceding turnover as every consumer reads it, through the canonical reader."""
    return resolve_incn_periodo_anterior(
        work.work_unit.bucket_id,
        work.work_unit.filing_year,
        stores=IncnPeriodoAnteriorStores.from_calculation_ports(work.ports),
        activity_start_date=None,
        twelve_month_statement=twelve_month_statement,
    )


@pytest.mark.parametrize("year", _YEARS)
def test_unmarked_the_held_return_supplies_the_turnover_and_a_statement_over_it_is_refused(
    tmp_path: Path, year: int
) -> None:
    with _held_work(tmp_path, year) as work:
        calculated = work.apply(binding=_statements(work, turnover=None))
        assert calculated.refusal is None, calculated.refusal
        stated_over_held = work.apply(binding=_statements(work, turnover=_GROUP))
        set_aside = set_aside_binding_ids(
            modelo_form_snapshot(work.operation, work.work_unit.modelo, year, work.work_unit.period).revision,
            work.require_head().casilla_values,
        )
        evidence = _clean_state(work, stated=True)
        read = _read(work)

    assert stated_over_held.refusal is not None
    assert read.origin is IncnPeriodoAnteriorOrigin.HELD_RETURN
    assert read.value == _HELD
    assert set_aside == frozenset()
    # The held return's own filing-chain checks still apply; only the set-aside blocker is absent.
    assert CrossPeriodCleanStateBlocker.HELD_SOURCE_SET_ASIDE not in evidence.blockers


@pytest.mark.parametrize("year", _YEARS)
def test_marked_without_a_statement_the_calculation_refuses(tmp_path: Path, year: int) -> None:
    with _held_work(tmp_path, year) as work:
        refused = work.apply(scalar=_marked(year), binding=_statements(work, turnover=None))
        head = work.head()

    assert refused.refusal is not None
    assert refused.calculation_revision_id is None
    assert head is None


@pytest.mark.parametrize("year", _YEARS)
def test_marked_the_statement_is_admitted_over_the_held_return_and_settles_the_clean_state(
    tmp_path: Path, year: int
) -> None:
    with _held_work(tmp_path, year) as work:
        stated = work.apply(scalar=_marked(year), binding=_statements(work, turnover=_GROUP))
        assert stated.refusal is None, stated.refusal
        head = work.require_head()
        set_aside = set_aside_binding_ids(
            modelo_form_snapshot(work.operation, work.work_unit.modelo, year, work.work_unit.period).revision,
            head.casilla_values,
        )
        settled = _clean_state(work, stated=True)
        unstated = _clean_state(work, stated=False)
        # The entity's own twelve months are not the group's turnover either, so they never stand in.
        read = _read(work, twelve_month_statement=_HELD)

    assert set_aside == frozenset({INCN_PERIODO_ANTERIOR_BINDING_ID})
    assert Decimal(operator_value_attestations(head)[INCN_PERIODO_ANTERIOR_BINDING_ID].value) == _GROUP
    assert settled.clean
    assert CrossPeriodCleanStateBlocker.HELD_SOURCE_SET_ASIDE in unstated.blockers
    assert not unstated.clean
    assert read.origin is IncnPeriodoAnteriorOrigin.OPERATOR_STATEMENT
    assert read.value == _GROUP
