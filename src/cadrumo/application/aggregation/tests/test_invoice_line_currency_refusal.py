"""An invoice line that would be silently dropped for unresolved currency REFUSES.

A `Notice` advisory beside a smaller declared figure is still a green exit code over an
under-declared return. An unconverted foreign-currency invoice line that would be silently
dropped from a declared figure REFUSES the whole calculation rather than excluding the line
and reporting it non-blockingly.

Companion to ``test_currency_conversion_pipeline_parity.py``: that module
proves the CONVERTED-figure path (a resolved fx_rate) is correct. This module
proves the UNRESOLVED-rate path is a hard stop, for both invoice-line-reading
resolvers this defect class touched: the M303 general IVA screen
(``modelo_bindings.py``) and Modelo 369 OSS/IOSS (``_oss_ioss.py``). OSS/IOSS
also gets a second refusal for the same "real declarable operation, one
required fact missing" shape: an unclassifiable IVA rate tier
(``rate_kind``).

Anti-tautology: every assertion below is on ``exc_info.value.translated_message``
-- the exact locale key, a cause-unique marker only this guard emits -- and on
``exc_info.value.context``, never on "an exception was raised" alone. Two
sibling guards in these functions could plausibly fire first (deduction
authority missing, category/counterparty mismatch); asserting only "it
raised" would not distinguish this guard from those.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import TransactionKind
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import InvoiceKind, IvaRateKind
from ...exchange_rate_provider import bind_exchange_rate_provider_factory
from ..errors import AggregationValidationError
from ..modelo_bindings_invoice_iva import screened_invoice_line_observations
from ..oss_ioss_resolver import candidate_for_invoice_line

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _pinned_operation() -> PinnedAuthorityOperation:
    """The session lease this module scopes every test to."""
    scoped = governed_facts_in_scope()
    assert isinstance(scoped, PinnedAuthorityOperation)
    return scoped


_DEVENGO = date(_YEAR, 2, 10)
_PERIOD_LAST_DAY = date(_YEAR, 3, 31)


class _PeriodCloseQuote:
    """A rate authority that publishes at most the period's last day; its parsing has its own tests."""

    rate_source_id = "ecb_reference"

    def __init__(self, rate: Decimal | None) -> None:
        self._rate = rate

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        del currency
        if self._rate is None or rate_date != _PERIOD_LAST_DAY:
            return EurRateLookup(
                status=EurRateLookupStatus.MISSING_RATE, rate_date=rate_date, source=self.rate_source_id
            )
        return EurRateLookup(
            status=EurRateLookupStatus.FOUND,
            rate_date=rate_date,
            source=self.rate_source_id,
            rate=self._rate,
            observation_date=rate_date,
        )


def _unconverted_gbp_invoice(*, line_count: int = 1) -> Invoice:
    """A GBP invoice whose fx_rate was never resolved -- genuinely unconvertible."""
    base_per_line = Decimal("500.00")
    iva_per_line = Decimal("105.00")
    lines = tuple(
        InvoiceLine(
            description=f"Servicio {index + 1}",
            quantity=Decimal("1"),
            unit_price=base_per_line,
            subtotal=base_per_line,
            iva_rate=IvaRate.from_registry("RATE_21"),
            iva_amount=iva_per_line,
        )
        for index in range(line_count)
    )
    base_total = base_per_line * line_count
    iva_total = iva_per_line * line_count
    return Invoice.model_validate(
        {
            "bucket_id": "refusal-bucket",
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-2025-GBP-118",
            "issued_at": _DEVENGO,
            "counterparty_name": "UK Client Ltd",
            "counterparty_tax_id": "GB123456789",
            "counterparty_country": "GB",
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": base_total + iva_total,
            "currency": "GBP",
            "lines": lines,
            "payment_status": PaymentStatus.PAID,
        },
    )


def test_modelo_bindings_refuses_on_an_unconverted_line() -> None:
    """The M303 general IVA screen raises, it does not silently exclude."""
    invoice = _unconverted_gbp_invoice()
    with pytest.raises(AggregationValidationError) as exc_info:
        screened_invoice_line_observations(
            invoice, devengo_date=_DEVENGO, deduction_authority=None, operation=_pinned_operation()
        )
    assert exc_info.value.translated_message == "aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"
    context = exc_info.value.context
    assert context is not None, "the refusal must carry its context, not just a message"
    assert context["invoice_number"] == "INV-2025-GBP-118"
    assert context["currency"] == "GBP"


def test_modelo_bindings_does_not_refuse_a_converted_invoice() -> None:
    """Anti-tautology: an ordinary EUR invoice never trips this guard."""
    line = InvoiceLine(
        description="Servicio nacional",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
        subtotal=Decimal("500.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("105.00"),
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": "refusal-bucket",
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-2025-EUR-1",
            "issued_at": _DEVENGO,
            "counterparty_name": "Cliente Nacional",
            "counterparty_tax_id": "12345678Z",
            "counterparty_country": "ES",
            "base_total": Decimal("500.00"),
            "iva_total": Decimal("105.00"),
            "grand_total": Decimal("605.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )
    observations = screened_invoice_line_observations(
        invoice, devengo_date=_DEVENGO, deduction_authority=None, operation=_pinned_operation()
    )
    assert len(observations) == 1


def _unconverted_pln_oss_line() -> tuple[Invoice, InvoiceLine]:
    base_total = Decimal("1000.00")
    iva_total = Decimal("210.00")
    line = InvoiceLine(
        description="Servicio B2C digital",
        quantity=Decimal("1"),
        unit_price=base_total,
        subtotal=base_total,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=iva_total,
        oss_rate_kind=IvaRateKind("general"),
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": "refusal-bucket",
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-OSS-REFUSAL-1",
            "issued_at": _DEVENGO,
            "counterparty_name": "Klient Sp. z o.o.",
            "counterparty_tax_id": "PL1234567890",
            "counterparty_country": "PL",
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": base_total + iva_total,
            "currency": "PLN",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime("union_scheme"),
            "oss_transaction_kind": TransactionKind("oss_union_services"),
        },
    )
    return invoice, line


def test_oss_ioss_refuses_on_an_unconverted_line() -> None:
    """End-to-end: OSS/IOSS is cross-border EU B2C, where a destination-currency
    invoice is the ORDINARY case -- the highest-probability trigger of the whole class.
    """
    invoice, line = _unconverted_pln_oss_line()
    with (
        bind_exchange_rate_provider_factory(lambda: _PeriodCloseQuote(None)),
        pytest.raises(AggregationValidationError) as exc_info,
    ):
        candidate_for_invoice_line(invoice, line, line_index=1, devengo_date=_DEVENGO, period_last_day=_PERIOD_LAST_DAY)
    assert exc_info.value.translated_message == "aggregation.oss_ioss.errors.invoice_line_currency_unconverted"
    context = exc_info.value.context
    assert context is not None, "the refusal must carry its context, not just a message"
    assert context["invoice_number"] == "INV-OSS-REFUSAL-1"
    assert context["currency"] == "PLN"


def test_oss_ioss_does_not_refuse_a_converted_invoice() -> None:
    """Anti-tautology: an OSS invoice whose period-close rate is published never trips the currency guard.

    Built from a fresh payload rather than ``invoice.model_dump()`` merged
    with overrides: the model distinguishes an ABSENT optional field from one
    explicitly present as ``None`` (``retention_rate`` et al.), and a dump
    always materialises the absent ones as ``None`` keys, which then fails
    strict re-validation. Spreading a dump back through ``model_validate`` is
    not a safe "clone with overrides" pattern on this model.
    """
    _, line = _unconverted_pln_oss_line()
    resolved = Invoice.model_validate(
        {
            "bucket_id": "refusal-bucket",
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-OSS-REFUSAL-1",
            "issued_at": _DEVENGO,
            "counterparty_name": "Klient Sp. z o.o.",
            "counterparty_tax_id": "PL1234567890",
            "counterparty_country": "PL",
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("210.00"),
            "grand_total": Decimal("1210.00"),
            "currency": "PLN",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime("union_scheme"),
            "oss_transaction_kind": TransactionKind("oss_union_services"),
        },
    )
    with bind_exchange_rate_provider_factory(lambda: _PeriodCloseQuote(Decimal("0.23"))):
        candidate = candidate_for_invoice_line(
            resolved, line, line_index=1, devengo_date=_DEVENGO, period_last_day=_PERIOD_LAST_DAY
        )
    assert candidate is not None
    assert candidate.base_amount == Decimal("1000.00") * Decimal("0.23")


def test_oss_ioss_refuses_on_an_unclassifiable_rate_kind() -> None:
    """A real OSS-eligible line whose IVA rate cannot be tiered REFUSES.

    ``NOT_SUBJECT`` is the one :class:`IvaRate` slot ``iva_rate_kind`` maps to
    ``None`` -- ``EXEMPT`` has its own real :class:`IvaRateKind("exempt")` tier
    and would not trip this guard.

    Same "real declarable operation, one required fact missing" shape as the
    currency guard, distinguished by its OWN cause-unique marker so the two
    guards cannot be confused for one another in a proof.
    """
    line = InvoiceLine(
        description="Servicio con tipo no clasificable",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
        subtotal=Decimal("500.00"),
        iva_rate=IvaRate.from_registry("NOT_SUBJECT"),
        iva_amount=Decimal("0.00"),
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": "refusal-bucket",
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-OSS-RATE-1",
            "issued_at": _DEVENGO,
            "counterparty_name": "Klient Sp. z o.o.",
            "counterparty_tax_id": "PL1234567890",
            "counterparty_country": "PL",
            "base_total": Decimal("500.00"),
            "iva_total": Decimal("0.00"),
            "grand_total": Decimal("500.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime("union_scheme"),
            "oss_transaction_kind": TransactionKind("oss_union_services"),
        },
    )
    with pytest.raises(AggregationValidationError) as exc_info:
        candidate_for_invoice_line(invoice, line, line_index=1, devengo_date=_DEVENGO, period_last_day=_PERIOD_LAST_DAY)
    assert exc_info.value.translated_message == "aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"
    context = exc_info.value.context
    assert context is not None
    assert context["invoice_number"] == "INV-OSS-RATE-1"


def test_oss_ioss_does_not_refuse_an_invoice_never_tagged_as_oss() -> None:
    """Not this guard's business: no oss_ioss_regime means no OSS operation at all.

    Converting the regime and destination eligibility gates into refusals
    would make Modelo 369 calculation fail on any bucket containing a single
    non-OSS invoice.
    """
    line = InvoiceLine(
        description="Servicio nacional",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
        subtotal=Decimal("500.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("105.00"),
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": "refusal-bucket",
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-NOT-OSS-1",
            "issued_at": _DEVENGO,
            "counterparty_name": "Cliente Nacional",
            "counterparty_tax_id": "12345678Z",
            "counterparty_country": "ES",
            "base_total": Decimal("500.00"),
            "iva_total": Decimal("105.00"),
            "grand_total": Decimal("605.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )
    candidate = candidate_for_invoice_line(
        invoice, line, line_index=1, devengo_date=_DEVENGO, period_last_day=_PERIOD_LAST_DAY
    )
    assert candidate is None
