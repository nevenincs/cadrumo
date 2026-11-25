"""Which intra-community supplies Modelo 303 casilla 59 and Modelo 390 box 103 receive.

The Modelo 303 instructions define casilla 59, "Entregas intracomunitarias de
bienes y servicios", as the exempt LIVA art. 25 supplies of goods plus "el
importe de las prestaciones de servicios intracomunitarias del periodo de
liquidacion", and exclude those services from casilla 120. The Modelo 390
instructions word box 103 the same way for the year and exclude the services
from box 110. Neither leg carries a Spanish rate tier: the goods are exempt and
the services are not subject in Spain.

Each assertion runs through the real ledger IVA resolver, in every year of the
registry's support envelope, at the grade that year reaches. Distinct bases make
a leaked or dropped population visible on value.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    resolve_ledger_iva_aggregation_binding_values,
    unrouted_ledger_iva_quantities,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind

from ..compiler.loader import load_shared_catalogues
from .authored_edition_support import reachable_grade_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_M303_BOX_59 = "modelo-303-casilla-59-entregas-intracomunitarias-base"
_M390_BOX_103 = "modelo-390-volumen-entregas-intracomunitarias-base"

_GOODS_ZERO_BASE = Decimal("18400.00")
_GOODS_EXEMPT_BASE = Decimal("2350.00")
_SERVICES_ZERO_BASE = Decimal("6100.00")
_SERVICES_EXEMPT_BASE = Decimal("730.00")
_TIERED_GOODS_BASE = Decimal("911.00")
_TIERED_SERVICES_BASE = Decimal("457.00")
_NOT_SUBJECT_BY_NATURE_BASE = Decimal("1290.00")
_DOMESTIC_NOT_SUBJECT_BASE = Decimal("3333.00")

#: Quarterly periods at both ends of the year, so an in-year edition branch is reached.
_M303_PERIODS = ("1T", "4T")


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _revision(modelo_id: str, year: int, period: str) -> ModeloRevision:
    return reachable_grade_snapshot(modelo_id, year, period).revision


def _row(
    ledger_id: str,
    *,
    category: str,
    rate_kind: str,
    base: Decimal,
    on: date,
    applied_rate: Decimal | None = None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=on,
        category=IvaCategory(category),
        rate_kind=IvaRateKind(rate_kind),
        flow_direction=IvaFlowDirection.from_registry("repercutido"),
        base_amount=base,
        iva_amount=Decimal("0"),
        recargo_amount=Decimal("0"),
        applied_rate=applied_rate,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _intra_community_rows(on: date) -> tuple[IvaLedgerObservation, ...]:
    return (
        _row("goods-zero", category="intra_community_supply", rate_kind="zero", base=_GOODS_ZERO_BASE, on=on),
        _row("goods-exempt", category="intra_community_supply", rate_kind="exempt", base=_GOODS_EXEMPT_BASE, on=on),
        _row(
            "services-zero",
            category="intra_community_service_supply",
            rate_kind="zero",
            base=_SERVICES_ZERO_BASE,
            on=on,
        ),
        _row(
            "services-exempt",
            category="intra_community_service_supply",
            rate_kind="exempt",
            base=_SERVICES_EXEMPT_BASE,
            on=on,
        ),
    )


def _tiered_rows(on: date) -> tuple[IvaLedgerObservation, ...]:
    """Rows whose positive tier contradicts a category that bears no Spanish tier."""
    return (
        _row(
            "goods-general",
            category="intra_community_supply",
            rate_kind="general",
            base=_TIERED_GOODS_BASE,
            on=on,
            applied_rate=Decimal("0.21"),
        ),
        _row(
            "services-general",
            category="intra_community_service_supply",
            rate_kind="general",
            base=_TIERED_SERVICES_BASE,
            on=on,
            applied_rate=Decimal("0.21"),
        ),
    )


def _other_not_subject_rows(on: date) -> tuple[IvaLedgerObservation, ...]:
    return (
        _row(
            "not-subject-nature",
            category="operacion_no_sujeta",
            rate_kind="exempt",
            base=_NOT_SUBJECT_BY_NATURE_BASE,
            on=on,
        ),
        _row(
            "domestic-not-subject",
            category="domestic_not_subject",
            rate_kind="exempt",
            base=_DOMESTIC_NOT_SUBJECT_BASE,
            on=on,
        ),
    )


def _expected_goods_and_services() -> Decimal:
    return _GOODS_ZERO_BASE + _GOODS_EXEMPT_BASE + _SERVICES_ZERO_BASE + _SERVICES_EXEMPT_BASE


def _coordinates() -> tuple[tuple[str, int, str, str], ...]:
    rows: list[tuple[str, int, str, str]] = []
    for year in _supported_years():
        rows.extend(("303", year, period, _M303_BOX_59) for period in _M303_PERIODS)
        rows.append(("390", year, "0A", _M390_BOX_103))
    return tuple(rows)


@pytest.mark.parametrize(("modelo_id", "year", "period", "binding_id"), _coordinates())
def test_the_box_receives_the_goods_and_the_services_and_nothing_else(
    modelo_id: str,
    year: int,
    period: str,
    binding_id: str,
) -> None:
    """Exempt goods and intra-community services land; other not-subject operations do not."""
    on = date(year, 3, 15)
    rows = _intra_community_rows(on) + _other_not_subject_rows(on)

    resolved = resolve_ledger_iva_aggregation_binding_values(_revision(modelo_id, year, period), rows)

    assert resolved[binding_id] == _expected_goods_and_services(), (modelo_id, year, period)


@pytest.mark.parametrize(("modelo_id", "year", "period", "binding_id"), _coordinates())
def test_a_tiered_row_is_reported_unrouted_rather_than_declared(
    modelo_id: str,
    year: int,
    period: str,
    binding_id: str,
) -> None:
    """A positive tier on either category is a contradiction the screen reports, not a box value."""
    on = date(year, 3, 15)
    revision = _revision(modelo_id, year, period)
    tiered = _tiered_rows(on)

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, _intra_community_rows(on) + tiered)
    unrouted = {
        quantity.fact: {row.ledger_id for row in quantity.observations}
        for quantity in unrouted_ledger_iva_quantities(revision, tiered)
    }

    assert resolved[binding_id] == _expected_goods_and_services(), (modelo_id, year, period)
    assert unrouted.get("base_amount_sum") == {"goods-general", "services-general"}, (modelo_id, year, period)


@pytest.mark.parametrize("year", _supported_years())
def test_casilla_120_is_entered_by_the_operator_and_no_binding_draws_the_services_into_it(year: int) -> None:
    """The instructions keep intra-community services out of casilla 120."""
    for period in _M303_PERIODS:
        revision = _revision("303", year, period)
        casilla_120 = next(casilla for casilla in revision.casillas if casilla.id == "120")

        assert casilla_120.input_kind is not InputKind.BOUND, (year, period)
        assert casilla_120.binding is None, (year, period)


@pytest.mark.parametrize("year", _supported_years())
def test_the_quarterly_and_annual_boxes_select_one_population(year: int) -> None:
    """Casilla 59 summed over the quarters and box 103 must state the same supplies."""
    annual = _selector(_revision("390", year, "0A"), _M390_BOX_103)
    for period in _M303_PERIODS:
        quarterly = _selector(_revision("303", year, period), _M303_BOX_59)

        assert set(quarterly.categories) == set(annual.categories), (year, period)
        assert set(quarterly.rate_kinds) == set(annual.rate_kinds), (year, period)
        assert quarterly.flow_direction == annual.flow_direction, (year, period)


def _selector(revision: ModeloRevision, binding_id: str) -> LedgerIvaProvider:
    binding = next(item for item in revision.bindings if str(item.id) == binding_id)
    return LedgerIvaProvider.model_validate(binding.model_dump(mode="json")["provider"])
