"""A charged recargo de equivalencia must be base x the dated art. 161 rate, within one cent.

LIVA arts. 160 and 161 fix the recargo: its base is the IVA base and its cuota
that base times the rate published for the line's IVA rate on its date. A
charged row whose recorded recargo departs by more than a cent is refused;
within the cent the recorded figure is declared, as the IVA cuota screen treats
its cuota. A purchase is never screened. Expected figures are worked by hand,
not read from the code: 1000.00 at 5.2 % is 52.00, at 1.4 % is 14.00, at 0.5 %
is 5.00, and the labores del tabaco rate of 1.75 % gives 17.50.

Real-behaviour: real :class:`Transaction` rows through the real classifier and
the published registry authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.recargo_equivalencia import IVA_RECARGO_FACT_ID
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import IvaLedgerAggregationIssueReason
from ..modelo_bindings_iva import selected_scope_iva_evidence_diagnostics
from .iva_authority_support import aggregate_iva_ledger_observations
from .iva_ledger_row_support import aggregate_row, uncategorised_purchase_row, uncategorised_sale_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = tuple(filing_year_envelope().years)
_BASE = Decimal("1000.00")
_DEPARTS = IvaLedgerAggregationIssueReason.RECARGO_DEPARTS_FROM_PUBLISHED_RATE.value
_UNMODELLED = IvaLedgerAggregationIssueReason.RECARGO_RATE_UNMODELLED.value
_TOBACCO = IvaLedgerAggregationIssueReason.RECARGO_TOBACCO_RUNG_UNSUPPORTED.value
_RECARGO_REASONS = {_DEPARTS, _UNMODELLED, _TOBACCO}

#: The cuota and the art. 161 recargo of a 1000.00 base at each ordinary IVA rate.
_ORDINARY = (
    ("0.21", "210.00", "52.00"),
    ("0.10", "100.00", "14.00"),
    ("0.04", "40.00", "5.00"),
)

#: The cuota and the transitional recargo of a 1000.00 base at each transitional IVA rate,
#: worked from RDL 20/2022 art. 72 and RDL 4/2024 art. 1 by hand.
_TRANSITIONAL = {
    Decimal("0.05"): ("50.00", "6.20"),
    Decimal("0.00"): ("0.00", "0.00"),
    Decimal("0.075"): ("75.00", "10.00"),
    Decimal("0.02"): ("20.00", "2.60"),
}


def _sale(on: date, *, rate: str, cuota: str, recargo: str) -> Transaction:
    return uncategorised_sale_row(
        "row-recargo",
        booked=on,
        base=_BASE,
        iva_rate=Decimal(rate),
        iva_amount=Decimal(cuota),
        recargo_amount=Decimal(recargo),
    )


def _aggregate(row: Transaction, on: date) -> tuple[tuple[Decimal, ...], list[str]]:
    observations, reasons = aggregate_row(row, Period.from_year_and_code(on.year, f"{(on.month - 1) // 3 + 1}T"))
    return tuple(observation.recargo_amount for observation in observations), reasons


def _transitional_windows() -> tuple[tuple[Decimal, date], ...]:
    """Every dated transitional pairing the registry publishes inside the support envelope."""
    with bundled_indexed_authority().operation() as operation:
        variants = operation.governed_fact(IVA_RECARGO_FACT_ID).variants
    windows: list[tuple[Decimal, date]] = []
    for variant in variants:
        if variant.valid_to is None or variant.valid_from is None or variant.valid_from.year not in _YEARS:
            continue
        selectors = {selector.name: selector.value for selector in variant.selectors}
        windows.append((Decimal(str(selectors["applied_rate"])), variant.valid_from))
    return tuple(windows)


_WINDOWS = _transitional_windows()


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize(("rate", "cuota", "recargo"), _ORDINARY)
def test_a_recargo_at_the_published_rate_is_declared_in_every_supported_year(
    year: int, rate: str, cuota: str, recargo: str
) -> None:
    on = date(year, 11, 6)
    recargos, reasons = _aggregate(_sale(on, rate=rate, cuota=cuota, recargo=recargo), on)
    assert reasons == []
    assert recargos == (Decimal(recargo),)


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("recargo", ["52.01", "51.99"])
def test_a_recargo_within_a_cent_keeps_the_recorded_figure(year: int, recargo: str) -> None:
    on = date(year, 11, 6)
    recargos, reasons = _aggregate(_sale(on, rate="0.21", cuota="210.00", recargo=recargo), on)
    assert reasons == []
    assert recargos == (Decimal(recargo),)


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize(
    ("rate", "cuota", "recargo"),
    [
        # One hundredth beyond the cent, on both sides of 52.00.
        ("0.21", "210.00", "52.02"),
        ("0.21", "210.00", "51.98"),
        # A general-rate sale carrying the reduced recargo.
        ("0.21", "210.00", "14.00"),
        # A reduced-rate sale carrying the general recargo.
        ("0.10", "100.00", "52.00"),
    ],
)
def test_a_recargo_beyond_a_cent_is_refused_and_not_declared(year: int, rate: str, cuota: str, recargo: str) -> None:
    on = date(year, 11, 6)
    recargos, reasons = _aggregate(_sale(on, rate=rate, cuota=cuota, recargo=recargo), on)
    assert recargos == ()
    assert reasons == [_DEPARTS]


def test_the_envelope_reaches_a_transitional_window_with_a_worked_figure() -> None:
    assert _WINDOWS, "the support envelope reaches no transitional recargo window"
    assert {rate for rate, _ in _WINDOWS} <= set(_TRANSITIONAL), "a published window has no hand-worked figure"


@pytest.mark.parametrize(("rate", "on"), _WINDOWS)
def test_a_transitional_recargo_follows_its_own_window(rate: Decimal, on: date) -> None:
    cuota, recargo = _TRANSITIONAL[rate]
    recargos, reasons = _aggregate(_sale(on, rate=str(rate), cuota=cuota, recargo=recargo), on)
    assert reasons == []
    assert recargos == (Decimal(recargo),)


@pytest.mark.parametrize(("rate", "on"), _WINDOWS)
def test_the_ordinary_recargo_on_a_transitional_rate_is_refused(rate: Decimal, on: date) -> None:
    cuota, _ = _TRANSITIONAL[rate]
    recargos, reasons = _aggregate(_sale(on, rate=str(rate), cuota=cuota, recargo="14.00"), on)
    assert recargos == ()
    assert reasons == [_DEPARTS]


def test_a_recargo_on_a_rate_the_registry_pairs_with_none_stays_unresolved() -> None:
    # The 0 % food window closed on 2024-09-30, so the horizon year publishes no
    # recargo for a 0 % sale: a recargo recorded on one is never priced.
    on = date(filing_year_envelope().horizon, 11, 6)
    recargos, reasons = _aggregate(_sale(on, rate="0.00", cuota="0.00", recargo="1.00"), on)
    assert recargos == ()
    assert reasons == [_UNMODELLED]


@pytest.mark.parametrize("year", _YEARS)
def test_the_tobacco_recargo_is_unresolved_rather_than_refused_or_folded_into_the_general_rung(year: int) -> None:
    on = date(year, 11, 6)
    recargos, reasons = _aggregate(_sale(on, rate="0.21", cuota="210.00", recargo="17.50"), on)
    assert recargos == ()
    assert reasons == [_TOBACCO]


@pytest.mark.parametrize("year", _YEARS)
def test_a_purchase_keeps_the_recargo_its_supplier_charged(year: int) -> None:
    on = date(year, 11, 6)
    row = uncategorised_purchase_row(
        "row-purchase",
        booked=on,
        base=_BASE,
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("210.00"),
        recargo_amount=Decimal("14.00"),
    )
    _, reasons = _aggregate(row, on)
    assert _RECARGO_REASONS.isdisjoint(reasons)


@pytest.mark.parametrize("language", [language.value for language in OutputLanguage])
def test_the_refusal_reaches_the_operator_with_its_figures_and_provision(language: str) -> None:
    on = date(filing_year_envelope().horizon, 11, 6)
    row = _sale(on, rate="0.21", cuota="210.00", recargo="14.00")
    catalogue = TransactionCatalogue.model_validate({"transactions": {row.transaction_id: row}})
    with override_settings(cadrumo_output_language=language):
        issues = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(on.year, "4T")).issues
        (diagnostic,) = selected_scope_iva_evidence_diagnostics(issues, resolver_id="ledger_iva_aggregation")
    assert diagnostic.message_language is OutputLanguage(language)
    for figure in ("14.00 EUR", "1000.00 EUR", "21%", "5.2%", "52.00 EUR", on.isoformat(), "art. 161"):
        assert figure in diagnostic.message, figure


def test_the_spanish_refusal_reads_as_one_sentence() -> None:
    on = date(filing_year_envelope().horizon, 11, 6)
    row = _sale(on, rate="0.21", cuota="210.00", recargo="14.00")
    catalogue = TransactionCatalogue.model_validate({"transactions": {row.transaction_id: row}})
    with override_settings(cadrumo_output_language="es"):
        (issue,) = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(on.year, "4T")).issues
    assert issue.detail == (
        "El recargo de equivalencia 14.00 EUR repercutido sobre la base 1000.00 EUR al tipo de IVA del 21% "
        f"no coincide con el 5.2% que la ley asocia a ese tipo el {on.isoformat()} (art. 161, art. 23.Seis), "
        "que da 52.00 EUR. Corrige la fila o emite una factura rectificativa."
    )
