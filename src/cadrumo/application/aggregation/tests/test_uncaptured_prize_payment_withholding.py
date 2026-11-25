"""A paid prize the ledger records and no capture declares holds Modelo 111 back.

The premios block of Modelo 111 (casillas 13 to 15) is filled only from a
captured prize allocation. A movement the operator classified as a paid prize
and never captured would otherwise leave those casillas at zero with nothing
said, so an absent prize would read as a proven absence of prizes.

The quarter is synthetic: a contest prize of 1000.00 paid on 30 May with the 19
per cent retención of 190.00 held back (RIRPF arts. 75.2.c, 75.3.f and 99.1),
so the bank paid 810.00 to the winner.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingSourceKind, RetencionScheme
from ....core.money.rounding import round_to_cents
from ....core.period import Period
from ....domain.calculations.registry.retenciones_bindings import RetencionesAggregationProvider
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.retencion_facts import load_premios_retencion_terms
from ..modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..retencion_observations_repository import RetencionObservationPorts
from ..retenciones import RetencionObservation
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .received_invoice_withholding_support import EmptyRetencionStore, invoice_catalogue_ports, paying_movement

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
_PRIZE = Decimal("1000.00")
_PRIZE_RETENCION = Decimal("190.00")
_WINNER_NIF = "00002500G"
_WINNER_NAME = "Ganadora Sintetica"
_GROSS = Decimal("2500.00")
_IRPF = Decimal("375.00")
_EMPLOYEE_NIF = "00001500M"


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return tuple(support.years)


def _prize_payment(year: int, *, irpf_category: str | None = "premios") -> Transaction:
    return paying_movement(
        f"PREMIO-{year}-0530",
        date(year, 5, 30),
        cash=_PRIZE - _PRIZE_RETENCION,
        irpf_category=irpf_category,
    )


class _Store:
    """A per-perceptor retención store serving one fixed window."""

    def __init__(self, observations: tuple[RetencionObservation, ...]) -> None:
        self._observations = observations

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        """Return the held rows for any window of the modelo asked for."""
        del modelo, period
        return self._observations

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        """Return no annual row."""
        del source_modelo, filing_year
        return ()

    def load_source_observations_through_year(
        self, source_modelo: str, last_filing_year: int
    ) -> tuple[RetencionObservation, ...]:
        """Return no annual row."""
        del source_modelo, last_filing_year
        return ()


def _captured_prize(transaction_id: str, *, year: int) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=transaction_id,
        perceptor_nif=_WINNER_NIF,
        perceptor_name=_WINNER_NAME,
        scheme=RetencionScheme("premios"),
        taxable_base=_PRIZE,
        retencion_amount=_PRIZE_RETENCION,
        accrued_on=date(year, 5, 30).isoformat(),
    )


def _captured_payroll(year: int) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"payroll-{year}-0530",
        perceptor_nif=_EMPLOYEE_NIF,
        perceptor_name="Empleada Sintetica",
        scheme=RetencionScheme("rendimientos_trabajo"),
        taxable_base=_GROSS,
        retencion_amount=_IRPF,
        accrued_on=date(year, 5, 30).isoformat(),
    )


def _resolve(
    year: int,
    *,
    movements: TransactionCatalogue,
    stored: tuple[RetencionObservation, ...] = (),
) -> tuple[CalculationSourceResolution, dict[str, str]]:
    snapshot = published_snapshot("111", filing_year=year, period="2T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_Store(stored) if stored else EmptyRetencionStore()),
        invoice_catalogue=invoice_catalogue_ports(build_invoice_catalogue(()), movements),
    )
    resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            modelo="111",
            filing_year=year,
            period=Period.from_year_and_code(year, "2T"),
            revision=snapshot.revision,
        )
    )
    targets = {
        str(binding.id): str(binding.provider.target_casilla_id)
        for binding in snapshot.revision.bindings
        if isinstance(binding.provider, RetencionesAggregationProvider)
    }
    return resolution, targets


def _casillas(
    resolution: CalculationSourceResolution, targets: dict[str, str]
) -> dict[str, Decimal | str | int | bool]:
    return {targets[str(binding_id)]: value for binding_id, value in resolution.binding_values.items()}


@pytest.mark.parametrize("year", _supported_years())
def test_a_premios_movement_with_no_capture_holds_the_quarter_back(year: int) -> None:
    """The premios casillas stay unresolved and the finding names the capture, instead of reading zero."""
    prize = _prize_payment(year)

    resolution, _ = _resolve(year, movements=TransactionCatalogue.from_transactions((prize,)))

    assert resolution.binding_values == {}
    assert resolution.unresolved_binding_ids
    assert [
        (item.reason, item.fact.sentence if item.fact is not None else None) for item in resolution.diagnostics
    ] == [("source_domain_not_ready", CalculationNoteSentence.PRIZE_PAYMENT_WITHHOLDING_UNCAPTURED)]
    fact = resolution.diagnostics[0].fact
    assert fact is not None
    assert dict(fact.values) == {"row_date": date(year, 5, 30).isoformat(), "amount": str(_PRIZE - _PRIZE_RETENCION)}


@pytest.mark.parametrize("year", _supported_years())
def test_an_uncaptured_prize_beside_a_captured_payslip_is_not_read_as_no_prize(year: int) -> None:
    """The quarter's other evidence must not let the missing prize pass as a premios zero."""
    prize = _prize_payment(year)
    payroll = paying_movement(f"NOMINA-{year}-0530", date(year, 5, 30), cash=_GROSS - _IRPF, irpf_category=None)

    resolution, targets = _resolve(
        year,
        movements=TransactionCatalogue.from_transactions((prize, payroll)),
        stored=(_captured_payroll(year),),
    )

    casillas = _casillas(resolution, targets)
    assert [item.fact.sentence if item.fact is not None else None for item in resolution.diagnostics] == [
        CalculationNoteSentence.PRIZE_PAYMENT_WITHHOLDING_UNCAPTURED
    ]
    assert (casillas["01"], casillas["02"], casillas["03"]) == (Decimal("1"), _GROSS, _IRPF)


@pytest.mark.parametrize("year", _supported_years())
def test_the_same_movement_captured_fills_the_premios_block_and_says_nothing(year: int) -> None:
    """A captured prize is declared, so the quarter carries the prize and no finding."""
    prize = _prize_payment(year)

    resolution, targets = _resolve(
        year,
        movements=TransactionCatalogue.from_transactions((prize,)),
        stored=(_captured_prize(prize.transaction_id, year=year),),
    )

    casillas = _casillas(resolution, targets)
    assert resolution.diagnostics == ()
    assert (casillas["13"], casillas["14"], casillas["15"]) == (Decimal("1"), _PRIZE, _PRIZE_RETENCION)


@pytest.mark.parametrize("year", _supported_years())
def test_a_prize_payment_too_small_to_bear_retencion_says_nothing(year: int) -> None:
    """A prize whose base the payment cannot place above the exclusion threshold bears no retención."""
    terms = load_premios_retencion_terms(effective_date=date(year, 5, 30))
    # The largest payment whose implied base reaches the threshold exactly, which does not exceed it.
    at_threshold = round_to_cents(terms.exclusion_threshold_eur * (Decimal("1") - terms.rate))
    small = paying_movement(f"PREMIO-{year}-0531", date(year, 5, 30), cash=at_threshold, irpf_category="premios")

    resolution, _ = _resolve(
        year,
        movements=TransactionCatalogue.from_transactions((small,)),
        stored=(_captured_payroll(year),),
    )

    assert resolution.diagnostics == ()


@pytest.mark.parametrize("year", _supported_years())
def test_a_quarter_with_no_premios_movement_keeps_its_zero(year: int) -> None:
    """Without a paid prize the premios casillas are a proven zero, and nothing is said about them."""
    payroll = paying_movement(f"NOMINA-{year}-0530", date(year, 5, 30), cash=_GROSS - _IRPF, irpf_category=None)

    resolution, targets = _resolve(
        year,
        movements=TransactionCatalogue.from_transactions((payroll,)),
        stored=(_captured_payroll(year),),
    )

    casillas = _casillas(resolution, targets)
    assert resolution.diagnostics == ()
    assert (casillas["13"], casillas["14"], casillas["15"]) == (Decimal("0"), Decimal("0"), Decimal("0"))
    assert (casillas["01"], casillas["02"], casillas["03"]) == (Decimal("1"), _GROSS, _IRPF)
