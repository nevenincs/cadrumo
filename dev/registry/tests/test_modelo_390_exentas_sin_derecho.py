"""Modelo 390 box [105] draws the year's exempt supplies without the right to deduct from the ledger.

Box [105] "Operaciones exentas sin derecho a deduccion" was a manual box: a
taxpayer whose whole activity is exempt under LIVA art. 20 (a dentist, an
academy) exported a volumen de operaciones without it unless the figure was
typed in. It is now bound to the canonical ``ledger_iva_aggregation`` resolver
over the domestic exempt category, the same sin derecho category the prorrata
output-volume vocabulary declares. The box takes every art. 20 exemption the
instructions name; which of those articles the prorrata denominator counts is a
separate, article-level question the vocabulary answers for the prorrata alone.

External authority: the AEAT Modelo 303 instructions word the annual casilla
83 as "se hara constar el importe de las operaciones exentas sin derecho a
deduccion, como las mencionadas en el articulo 20 de la Ley del IVA", the
wording the Modelo 390 instructions give box [105], and exclude from the
annual volume "las operaciones realizadas desde establecimientos permanentes
situados fuera del territorio de aplicacion del Impuesto" (LIVA art.
104.Tres.1). The record design prints the box on page 6 of every bundled
edition.

Non-tautology: the oracle is four independently stated quarterly bases whose
sum is written out, not read from a registry formula. A selector that dropped
an apartado of art. 20, admitted a taxable or zero-rated row, or kept a row
operated from a foreign permanent establishment lands on a different figure.

Real-behaviour: the published authority, the real resolver over real
:class:`IvaLedgerObservation` rows, and the real fixed-width codec. No mocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.prorrata_exclusions import Art104TresExclusion
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_selector_utils import provider_member
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    LedgerIvaProvider,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.prorrata_volume_catalogue import resolve_prorrata_volume_catalogue
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_grade_exercises, filing_year_envelope
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaExemptionArticle, IvaLedgerObservationRole, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_BINDING_ID = "modelo-390-volumen-exentas-sin-derecho-deduccion-base"
_CASILLA_ID = "iva.anual.volumen.exentas-sin-derecho-deduccion"

# A dental practice's four quarterly exempt bases (LIVA art. 20.Uno.14). Their
# sum, written out rather than computed by the code under test, is the oracle.
_QUARTER_BASES = (Decimal("18000.00"), Decimal("17500.00"), Decimal("16650.00"), Decimal("20500.00"))
_ANNUAL_ORACLE = Decimal("72650.00")


def _revision(year: int) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.snapshot(
            "390", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
        ).revision


def _exempt_row(
    ledger_id: str,
    *,
    year: int,
    month: int,
    base: Decimal,
    article: str = "art_20_uno_14",
    exclusion: str | None = None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=date(year, month, 15),
        category=IvaCategory("domestic_exempt"),
        exemption_article=IvaExemptionArticle(article),
        rate_kind=IvaRateKind("exempt"),
        flow_direction=IvaFlowDirection.from_registry("repercutido"),
        base_amount=base,
        iva_amount=Decimal("0"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        art_104_tres_exclusion=None if exclusion is None else Art104TresExclusion(exclusion),
    )


def _dental_year(year: int) -> tuple[IvaLedgerObservation, ...]:
    return tuple(
        _exempt_row(f"dental-q{quarter}", year=year, month=3 * quarter, base=base)
        for quarter, base in enumerate(_QUARTER_BASES, start=1)
    )


def _resolved_box(year: int, rows: tuple[IvaLedgerObservation, ...]) -> Decimal:
    return dict(resolve_ledger_iva_aggregation_binding_values(_revision(year), rows))[_BINDING_ID]


def test_the_oracle_is_the_sum_of_the_stated_quarters() -> None:
    assert sum(_QUARTER_BASES, Decimal(0)) == _ANNUAL_ORACLE


@pytest.mark.parametrize("year", filing_grade_exercises("390"))
def test_an_exempt_dental_practice_fills_box_105_with_its_annual_exempt_base(year: int) -> None:
    assert _resolved_box(year, _dental_year(year)) == _ANNUAL_ORACLE


@pytest.mark.parametrize("year", filing_grade_exercises("390"))
def test_every_art_20_apartado_reaches_the_box(year: int) -> None:
    """The instructions ask for every art. 20 operation, so no apartado is filtered out."""
    rows = (
        _exempt_row("teaching", year=year, month=2, base=Decimal("1200.00"), article="art_20_uno_8"),
        _exempt_row("other-art-20", year=year, month=5, base=Decimal("340.00"), article="art_20_other"),
    )
    assert _resolved_box(year, rows) == Decimal("1540.00")


@pytest.mark.parametrize("year", filing_grade_exercises("390"))
def test_a_supply_operated_from_a_foreign_permanent_establishment_stays_out(year: int) -> None:
    rows = (
        *_dental_year(year),
        _exempt_row(
            "foreign-pe", year=year, month=7, base=Decimal("9900.00"), exclusion="foreign_permanent_establishment"
        ),
    )
    assert _resolved_box(year, rows) == _ANNUAL_ORACLE


@pytest.mark.parametrize("year", filing_grade_exercises("390"))
def test_a_non_habitual_financial_operation_stays_in_for_box_106_to_subtract(year: int) -> None:
    """[108] adds [105] and subtracts [106]; leaving the row out of [105] too would subtract it twice."""
    rows = (
        *_dental_year(year),
        _exempt_row(
            "non-habitual",
            year=year,
            month=8,
            base=Decimal("4000.00"),
            article="art_20_other",
            exclusion="non_habitual_real_estate_or_financial",
        ),
    )
    assert _resolved_box(year, rows) == _ANNUAL_ORACLE + Decimal("4000.00")


@pytest.mark.parametrize("year", filing_grade_exercises("390"))
def test_a_taxable_or_zero_rated_supply_does_not_reach_the_box(year: int) -> None:
    taxable = IvaLedgerObservation(
        ledger_id="taxable",
        transaction_date=date(year, 4, 10),
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("repercutido"),
        base_amount=Decimal("5000.00"),
        iva_amount=Decimal("1050.00"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )
    export = IvaLedgerObservation(
        ledger_id="export",
        transaction_date=date(year, 4, 11),
        category=IvaCategory("export_third_country_zero_rated"),
        rate_kind=IvaRateKind("zero"),
        flow_direction=IvaFlowDirection.from_registry("repercutido"),
        base_amount=Decimal("2500.00"),
        iva_amount=Decimal("0"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )
    assert _resolved_box(year, (*_dental_year(year), taxable, export)) == _ANNUAL_ORACLE


@pytest.mark.parametrize("year", filing_grade_exercises("390"))
def test_the_box_selects_the_prorrata_sin_derecho_categories(year: int) -> None:
    """The box selects the sin derecho category the prorrata vocabulary declares."""
    revision = _revision(year)
    binding = next(binding for binding in revision.bindings if binding.id == _BINDING_ID)
    selector = provider_member(binding, LedgerIvaProvider)
    with bundled_indexed_authority().operation() as operation:
        catalogue = resolve_prorrata_volume_catalogue(effective_date=date(year, 12, 31), authority=operation)
    assert frozenset(selector.categories) == catalogue.sin_derecho


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_box_105_is_bound_and_round_trips_through_the_export_record(year: int) -> None:
    """Every supported year renders the bound box to its design slot and reads the same amount back."""
    revision = _revision(year)
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_ID)
    assert casilla.number == "105"
    assert casilla.binding == _BINDING_ID
    fields = [
        field
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for field in record.fields
        if field.casilla_id == _CASILLA_ID
    ]
    assert len(fields) == 1, f"box [105] must have exactly one export slot in {year}"
    wire = render_fixed_width_export_field(fields[0], _ANNUAL_ORACLE)
    assert len(wire) == fields[0].length
    assert parse_fixed_width_export_field(fields[0], wire) == _ANNUAL_ORACLE
