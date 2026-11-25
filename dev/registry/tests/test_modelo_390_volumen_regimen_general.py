"""Modelo 390 box [99] draws the year's regimen-general supply bases from the ledger.

Box [99] "Operaciones en regimen general" had no binding, so it resolved to zero
and box [108], the annual volumen de operaciones, lost every domestic taxable
supply. The instructions define [99] as the year's supplies in regimen general,
excluding the IVA itself and the populations of [103], [104], [105], [110] and
[125], and including the zero-rated supplies.

Real-behaviour: every edition the support envelope reaches, loaded from source
through the real registry authority, resolved by the real
``ledger_iva_aggregation`` resolver over real :class:`IvaLedgerObservation`
rows, and [108] computed by the real formula runtime. No mocks, stubs, skips or
xfail.

Non-tautology: each expected figure is summed in this module from the fixture
rows it tags as regimen-general supplies, not read from a registry run. The
parity test then holds [99] to an independent route over the same ledger: the
four quarterly Modelo 303 base rungs, resolved from the quarterly revisions,
whose selectors this change does not touch.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.iva_deduction_fact import IvaDeductionFactKind
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.iva_cash_accounting_vocabulary import (
    require_iva_cash_accounting_treatment,
)
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from dev.registry.compiler.authority import compiled_bundled_authority

from .ledger_iva_aggregation_support import ledger_iva_aggregation_deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_BINDING: Final = "modelo-390-volumen-regimen-general-base"
_CASILLA_99: Final = validated_casilla_id("iva.anual.volumen.regimen-general", surface="_CASILLA_99")
_CASILLA_103: Final = validated_casilla_id("iva.anual.volumen.entregas-intracomunitarias", surface="_CASILLA_103")
_CASILLA_108: Final = validated_casilla_id("iva.anual.volumen.total", surface="_CASILLA_108")
_QUARTERS: Final = (1, 2, 3, 4)
_YEARS: Final = filing_year_envelope().years

# The Modelo 390 bindings that read the filed Modelo 303 quarters rather than
# the ledger. These scenarios file no quarter, so each is pinned to zero; none
# of them is an operand of the volumen boxes.
_PRIOR_303_BINDINGS: Final = (
    "modelo-390-bienes-inversion-regularizacion-casilla-63",
    "modelo-390-prev-303-cuota-devengada-total",
    "modelo-390-prev-303-cuota-deducible-total",
    "modelo-390-prev-303-resultado-regimen-general",
    "modelo-390-prev-303-compensacion-ultimo-periodo",
    "modelo-390-prev-303-compensacion-generada-ejercicio-no-97",
)


@dataclass(frozen=True)
class _Row:
    """One fixture line and whether the instructions put it in box [99]."""

    observation: IvaLedgerObservation
    in_regimen_general: bool


def _quarter_day(year: int, quarter: int) -> date:
    return date(year, quarter * 3 - 1, 15)


def _supply(
    ledger_id: str,
    *,
    day: date,
    category: str,
    rate_kind: str,
    rate: str | None,
    base: str,
    recargo: str = "0",
    cash_treatment: str = "none",
) -> IvaLedgerObservation:
    applied = Decimal(rate) if rate is not None else None
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=day,
        category=IvaCategory(category),
        exemption_article=None,
        rate_kind=IvaRateKind(rate_kind),
        flow_direction=IvaFlowDirection.from_registry("repercutido"),
        base_amount=Decimal(base),
        iva_amount=(Decimal(base) * applied).quantize(Decimal("0.01")) if applied is not None else Decimal("0"),
        recargo_amount=Decimal(recargo),
        applied_rate=applied,
        cash_accounting_treatment=require_iva_cash_accounting_treatment(cash_treatment, effective_date=day),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _purchase(ledger_id: str, *, day: date, base: str) -> IvaLedgerObservation:
    kind = IvaDeductionFactKind.from_registry("domestic_current")
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=day,
        category=IvaCategory("domestic_general"),
        exemption_article=None,
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("soportado"),
        base_amount=Decimal(base),
        iva_amount=(Decimal(base) * Decimal("0.21")).quantize(Decimal("0.01")),
        applied_rate=Decimal("0.21"),
        deduction_fact_kind=kind,
        deduction_provenance=ledger_iva_aggregation_deduction_provenance(kind, source_locator=f"invoice:{ledger_id}"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _quarter_rows(year: int, quarter: int) -> tuple[_Row, ...]:
    """One quarter of a ledger whose bases are distinct across tiers and quarters.

    No base equals another or the sum of two, so a selector that drops a tier,
    takes a neighbour's population or counts a row twice misses on value.
    """
    day = _quarter_day(year, quarter)
    step = Decimal(quarter)
    return (
        _Row(
            _supply(
                f"q{quarter}-general",
                day=day,
                category="domestic_general",
                rate_kind="general",
                rate="0.21",
                base=str(Decimal("4100.00") + step * Decimal("13.00")),
            ),
            True,
        ),
        _Row(
            _supply(
                f"q{quarter}-reducido",
                day=day,
                category="domestic_reduced",
                rate_kind="reduced",
                rate="0.10",
                base=str(Decimal("1730.00") + step * Decimal("7.00")),
            ),
            True,
        ),
        _Row(
            _supply(
                f"q{quarter}-superreducido",
                day=day,
                category="domestic_super_reduced",
                rate_kind="super_reduced",
                rate="0.04",
                base=str(Decimal("590.00") + step * Decimal("3.00")),
            ),
            True,
        ),
        _Row(_purchase(f"q{quarter}-compra", day=day, base="2600.00"), False),
    )


def _regimen_general_base(rows: Iterable[_Row]) -> Decimal:
    return sum((row.observation.base_amount for row in rows if row.in_regimen_general), Decimal("0"))


def _snapshot(modelo: str, year: int, period: str) -> RegistrySnapshot:
    """The edition the year selects, at the grade it declares.

    A year past the newest filing-grade edition is served at a lower grade, and
    the binding must still resolve there.
    """
    authority = compiled_bundled_authority()
    selected = select_revision(
        authority.modelo(modelo),
        filing_year=year,
        period=period,
        support=authority.catalogues.supported_filing_years,
    )
    assert selected.authority_grade is not None, f"Modelo {modelo} {year} {period} declares no authority grade"
    return authority.snapshot(modelo, filing_year=year, period=period, grade=selected.authority_grade)


def _m390(year: int) -> ModeloRevision:
    return _snapshot("390", year, "0A").revision


_DOMESTIC_REGIMEN_GENERAL: Final = frozenset(
    {"domestic_general", "domestic_reduced", "domestic_super_reduced", "domestic_zero"}
)


def _is_regimen_general_base_rung(selector: LedgerIvaProvider) -> bool:
    return (
        str(selector.flow_direction) == "repercutido"
        and str(selector.fact) == "base_amount_sum"
        and {str(category) for category in selector.categories} <= _DOMESTIC_REGIMEN_GENERAL
        and IvaLedgerObservationRole.SETTLEMENT in selector.observation_roles
    )


def _m303_regimen_general_base_bindings(revision: ModeloRevision) -> tuple[str, ...]:
    """The quarterly return's bound regimen-general base rungs, read from its own selectors."""
    bound = {str(casilla.binding) for casilla in revision.casillas if casilla.input_kind is InputKind.BOUND}
    return tuple(
        str(binding.id)
        for binding in revision.bindings
        if str(binding.id) in bound
        and isinstance(binding.provider, LedgerIvaProvider)
        and _is_regimen_general_base_rung(binding.provider)
    )


def _quarterly_303_base(year: int, quarter: int, rows: Iterable[_Row]) -> Decimal:
    """One quarter's Modelo 303 regimen-general bases, through that quarter's own revision."""
    revision = _snapshot("303", year, f"{quarter}T").revision
    rungs = _m303_regimen_general_base_bindings(revision)
    assert rungs, f"Modelo 303 {year} {quarter}T binds no regimen-general base rung"
    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, (row.observation for row in rows)))
    return sum((resolved.get(rung, Decimal("0")) for rung in rungs), Decimal("0"))


@pytest.mark.parametrize("year", _YEARS)
def test_box_99_equals_the_summed_quarterly_303_bases(year: int) -> None:
    """[99] states the same regimen-general bases as the four quarterly 303s summed."""
    quarterly = {quarter: _quarter_rows(year, quarter) for quarter in _QUARTERS}
    annual_rows = tuple(row for rows in quarterly.values() for row in rows)
    expected = _regimen_general_base(annual_rows)

    annual = dict(resolve_ledger_iva_aggregation_binding_values(_m390(year), (row.observation for row in annual_rows)))
    quarterly_total = sum(
        (_quarterly_303_base(year, quarter, rows) for quarter, rows in quarterly.items()), Decimal("0")
    )

    assert quarterly_total == expected
    assert annual[_BINDING] == expected


@pytest.mark.parametrize("year", _YEARS)
def test_box_99_is_bound_on_every_supported_year(year: int) -> None:
    """The casilla is bound, not a manual box that silently resolves to zero."""
    casilla = {casilla.id: casilla for casilla in _m390(year).casillas}[_CASILLA_99]
    assert casilla.input_kind is InputKind.BOUND
    assert str(casilla.binding) == _BINDING


@pytest.mark.parametrize("year", _YEARS)
def test_exempt_reverse_charge_and_other_volumen_rows_stay_out_of_box_99(year: int) -> None:
    """Only the taxpayer's own regimen-general supplies reach [99].

    Every excluded population the instructions name is present, each with a
    base no included row carries: [103], [104], [105], [110], the supplier
    side of an inversion-del-sujeto-pasivo supply for [125], the
    criterio-de-caja supplies of [653] and an input. A zero-rated domestic
    supply is included, and so is the base of a supply carrying recargo while
    the recargo itself is not.
    """
    day = _quarter_day(year, _QUARTERS[1])
    rows = (
        _Row(
            _supply("general", day=day, category="domestic_general", rate_kind="general", rate=None, base="5300.00"),
            True,
        ),
        _Row(_supply("tipo-cero", day=day, category="domestic_zero", rate_kind="zero", rate=None, base="410.00"), True),
        _Row(
            _supply(
                "con-recargo",
                day=day,
                category="domestic_general",
                rate_kind="general",
                rate=None,
                base="1200.00",
                recargo="62.40",
            ),
            True,
        ),
        _Row(
            _supply("exenta-105", day=day, category="domestic_exempt", rate_kind="exempt", rate=None, base="770.00"),
            False,
        ),
        _Row(
            _supply(
                "entrega-103", day=day, category="intra_community_supply", rate_kind="zero", rate=None, base="880.00"
            ),
            False,
        ),
        _Row(
            _supply(
                "exportacion-104",
                day=day,
                category="export_third_country_zero_rated",
                rate_kind="zero",
                rate=None,
                base="930.00",
            ),
            False,
        ),
        _Row(
            _supply(
                "no-sujeta-110", day=day, category="operacion_no_sujeta", rate_kind="exempt", rate=None, base="1040.00"
            ),
            False,
        ),
        _Row(
            _supply(
                "isp-125",
                day=day,
                category="domestic_reverse_charge",
                rate_kind="general",
                rate=None,
                base="1150.00",
            ),
            False,
        ),
        _Row(
            _supply(
                "criterio-caja-653",
                day=day,
                category="domestic_general",
                rate_kind="general",
                rate=None,
                base="1370.00",
                cash_treatment="taxpayer_regime",
            ),
            False,
        ),
        _Row(_purchase("compra", day=day, base="1490.00"), False),
    )
    resolved = dict(resolve_ledger_iva_aggregation_binding_values(_m390(year), (row.observation for row in rows)))
    assert resolved[_BINDING] == _regimen_general_base(rows)


@pytest.mark.parametrize("year", _YEARS)
def test_app_qa_shaped_ledger_gives_99_and_108(year: int) -> None:
    """A ledger shaped like the APP-QA dataset gives [99] 17000.00 and [108] 20000.00.

    Four quarterly 21 % sales, one exempt intra-Community supply and the
    quarterly purchases. [108] is the instructions' sum of the volumen boxes, so
    with every other addend empty it is the [99] bases plus the [103] base.
    """
    sales = tuple(
        _Row(
            _supply(
                f"venta-q{quarter}",
                day=_quarter_day(year, quarter),
                category="domestic_general",
                rate_kind="general",
                rate="0.21",
                base="4250.00",
            ),
            True,
        )
        for quarter in _QUARTERS
    )
    intra_community = _Row(
        _supply(
            "entrega-intracomunitaria",
            day=_quarter_day(year, _QUARTERS[2]),
            category="intra_community_supply",
            rate_kind="zero",
            rate=None,
            base="3000.00",
        ),
        False,
    )
    purchases = tuple(
        _Row(_purchase(f"compra-q{quarter}", day=_quarter_day(year, quarter), base="2550.00"), False)
        for quarter in _QUARTERS
    )
    rows = (*sales, intra_community, *purchases)
    expected_99 = _regimen_general_base(rows)
    expected_108 = expected_99 + intra_community.observation.base_amount

    snapshot = _snapshot("390", year, "0A")
    binding_values: dict[str, Decimal] = {
        **dict.fromkeys(_PRIOR_303_BINDINGS, Decimal("0")),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, (row.observation for row in rows)),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        binding_values=binding_values,
        date_context={"filing_period": date(year + 1, 1, 30)},
    )

    assert expected_99 == Decimal("17000.00")
    assert expected_108 == Decimal("20000.00")
    assert result.values[_CASILLA_99] == expected_99
    assert result.values[_CASILLA_103] == intra_community.observation.base_amount
    assert result.values[_CASILLA_108] == expected_108
