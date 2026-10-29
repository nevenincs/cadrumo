"""The indexed reconciliation suggester returns exactly what comparing every pair returns.

The oracle below is the all-pairs algorithm, written out in full: every unlinked
invoice against every unlinked transaction, with the direction, settlement,
tolerance, counterparty and score rule applied to each pair. The generated
catalogues are dense in the cases an amount index can get wrong: many equal
amounts, amounts at and just past the tolerance on both sides, mixed decimal
exponents, retenciones, every direction, foreign currencies, dates across year
edges, already-linked records and empty sides.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import (
    ROUND_05UP,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
    localcontext,
)
from pathlib import Path
from typing import TypeVar

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ...iva.schema import InvoiceKind
from ...transactions.enums import BusinessClassification, TransactionDirection
from ...transactions.models import Transaction, TransactionCatalogue
from ...transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..catalogue import InvoiceCatalogue
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine
from ..service import ReconciliationSuggestion, suggest_reconciliations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CENT = Decimal("0.01")
_SEEDS = tuple(range(24))
_TOLERANCES = (
    Decimal("0"),
    Decimal("0.005"),
    Decimal("0.0100"),
    Decimal("0.02"),
    Decimal("1"),
    Decimal("-0.01"),
    Decimal("100000"),
)
#: Offsets from an invoice's settlement: exact, inside, on and just past the
#: default one-cent tolerance on both sides.
_OFFSETS = tuple(
    Decimal(text) for text in ("0", "0.005", "-0.005", "0.01", "-0.01", "0.0100001", "-0.0100001", "0.011", "-0.02")
)
_COUNTERPARTIES = (
    "Beta Logistica SL",
    "BETA LOGISTICA",
    "beta",
    "Gamma Servicios SA",
    "  gamma servicios sa  ",
    "Delta",
    "",
    "   ",
    None,
)
_CURRENCIES = ("EUR", "USD", "GBP")
_DIRECTIONS = tuple(TransactionDirection)

_T = TypeVar("_T")


class _Picker:
    """Deterministic draws from a seed, so every generated world is reproducible."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._draws = 0

    def _next(self) -> int:
        self._draws += 1
        digest = hashlib.blake2b(f"{self._seed}:{self._draws}".encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big")

    def randint(self, low: int, high: int) -> int:
        return low + self._next() % (high - low + 1)

    def chance(self, numerator: int, denominator: int) -> bool:
        return self._next() % denominator < numerator

    def choice(self, options: Sequence[_T]) -> _T:
        return options[self._next() % len(options)]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _all_pairs_oracle(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    amount_tolerance: Decimal = _CENT,
) -> tuple[ReconciliationSuggestion, ...]:
    unmatched = [invoice for invoice in invoices.values() if not invoice.linked_transaction_ids]
    unlinked = [transaction for transaction in transactions.values() if transaction.invoice_id is None]
    suggestions: list[ReconciliationSuggestion] = []
    for invoice in unmatched:
        expected = (
            TransactionDirection.INCOMING if invoice.kind is InvoiceKind.ISSUED else TransactionDirection.OUTGOING
        )
        settlement = invoice.grand_total - (invoice.retention_amount or Decimal("0"))
        for transaction in unlinked:
            if transaction.direction is not expected:
                continue
            if not abs(transaction.raw.amount - settlement) <= amount_tolerance:
                continue
            invoice_name = invoice.counterparty_name.strip().lower()
            tx_name = transaction.raw.counterparty
            counterparty_match = False
            if tx_name is not None and invoice_name:
                tx_normalised = tx_name.strip().lower()
                counterparty_match = bool(tx_normalised) and (
                    invoice_name in tx_normalised or tx_normalised in invoice_name
                )
            score = Decimal("0.5") * 1
            score += Decimal("0.5") * (1 if counterparty_match else 0)
            suggestions.append(
                ReconciliationSuggestion(
                    invoice_id=invoice.invoice_id,
                    transaction_id=transaction.transaction_id,
                    amount_match=True,
                    counterparty_match=counterparty_match,
                    score=score,
                ),
            )
    suggestions.sort(key=lambda s: (-s.score, s.invoice_id, s.transaction_id))
    return tuple(suggestions)


def _exact(suggestions: tuple[ReconciliationSuggestion, ...]) -> tuple[tuple[str, str, bool, bool, str], ...]:
    """Every field, with the score's exact decimal text, in emitted order."""
    return tuple(
        (s.invoice_id, s.transaction_id, s.amount_match, s.counterparty_match, str(s.score)) for s in suggestions
    )


def _invoice(
    *,
    number: str,
    kind: InvoiceKind,
    base: Decimal,
    retention: Decimal | None,
    counterparty: str,
    currency: str,
    issued_at: date,
    linked: tuple[str, ...],
) -> Invoice:
    iva = (base * Decimal("0.21")).quantize(_CENT, rounding=ROUND_HALF_UP)
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": number,
            "issued_at": issued_at,
            "counterparty_name": counterparty,
            "counterparty_tax_id": "B92000025",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": iva,
            "grand_total": base + iva,
            "currency": currency,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicio",
                        "quantity": Decimal("1"),
                        "unit_price": base,
                        "subtotal": base,
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": iva,
                    },
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "retention_amount": retention,
            "linked_transaction_ids": linked,
        },
    )


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    direction: TransactionDirection,
    counterparty: str | None,
    currency: str,
    booked: date,
    invoice_id: str | None,
) -> Transaction:
    payload: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id=provider_id,
            booked_date=booked,
            value_date=booked,
            amount=amount,
            currency=currency,
            counterparty=counterparty,
            description="movimiento",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="c" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(booked.year, booked.month, booked.day, 9, 0, tzinfo=UTC),
                provider_name="CSV provider",
            ),
            raw_fields={"Concepto": provider_id},
        ),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
    }
    if invoice_id is not None:
        payload["invoice_id"] = invoice_id
    return Transaction.model_validate(payload)


def _edge_date(rng: _Picker) -> date:
    """A date on, before or after a year boundary, or anywhere in the year."""
    anchor = date(rng.choice((2024, 2025, 2026)), 1, 1)
    return anchor + timedelta(days=rng.choice((-1, 0, 1, rng.randint(-200, 200))))


def _world(seed: int) -> tuple[InvoiceCatalogue, TransactionCatalogue]:
    rng = _Picker(seed)
    # A small base pool makes many invoices share one settlement figure.
    bases = [Decimal(rng.randint(500, 40_000)).scaleb(-2) for _ in range(rng.randint(1, 4))]
    invoices: list[Invoice] = []
    for idx in range(rng.randint(1, 14)):
        base = rng.choice(bases)
        retention = rng.choice((None, None, Decimal("0"), (base * Decimal("0.15")).quantize(_CENT)))
        linked = ("f" * 63 + format(idx % 16, "x"),) if rng.chance(15, 100) else ()
        invoices.append(
            _invoice(
                number=f"P-{seed}-{idx:03d}",
                kind=rng.choice((InvoiceKind.ISSUED, InvoiceKind.RECEIVED)),
                base=base,
                retention=retention,
                counterparty=rng.choice([name for name in _COUNTERPARTIES if name is not None and name.strip()]),
                currency=rng.choice(_CURRENCIES),
                issued_at=_edge_date(rng),
                linked=linked,
            ),
        )
    settlements = [invoice.grand_total - (invoice.retention_amount or Decimal("0")) for invoice in invoices]
    transactions: list[Transaction] = []
    # Every eighth world has no transactions at all.
    for idx in range(0 if seed % 8 == 7 else rng.randint(1, 60)):
        if rng.chance(4, 5):
            amount = rng.choice(settlements) + rng.choice(_OFFSETS)
            # Same value, different exponent: 12.30, 12.3 and 12.300 sort as equals.
            amount = rng.choice((amount, amount.normalize(), amount.quantize(Decimal("0.0000001"))))
        else:
            amount = Decimal(rng.randint(0, 60_000)).scaleb(-2)
        transactions.append(
            _transaction(
                provider_id=f"row-{seed}-{idx:03d}",
                amount=amount,
                direction=rng.choice(_DIRECTIONS),
                counterparty=rng.choice(_COUNTERPARTIES),
                currency=rng.choice(_CURRENCIES),
                booked=_edge_date(rng),
                invoice_id=(rng.choice(invoices).invoice_id if rng.chance(15, 100) else None),
            ),
        )
    return (
        InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice for invoice in invoices}}),
        TransactionCatalogue.from_transactions(transactions),
    )


@dataclass
class _Exercised:
    """What the generated worlds actually reached, so the parity claim is not vacuous."""

    suggestions: int = 0
    with_counterparty: int = 0
    without_counterparty: int = 0
    invoices_with_several: int = 0
    transactions_with_several: int = 0
    linked_invoices: int = 0
    linked_transactions: int = 0
    empty_transaction_sides: int = 0
    boundary_distances: set[Decimal] = field(default_factory=set)

    def record(
        self,
        invoices: InvoiceCatalogue,
        transactions: TransactionCatalogue,
        suggestions: tuple[ReconciliationSuggestion, ...],
    ) -> None:
        self.suggestions += len(suggestions)
        self.with_counterparty += sum(1 for s in suggestions if s.counterparty_match)
        self.without_counterparty += sum(1 for s in suggestions if not s.counterparty_match)
        per_invoice = [s.invoice_id for s in suggestions]
        per_transaction = [s.transaction_id for s in suggestions]
        self.invoices_with_several += sum(1 for key in set(per_invoice) if per_invoice.count(key) > 1)
        self.transactions_with_several += sum(1 for key in set(per_transaction) if per_transaction.count(key) > 1)
        self.linked_invoices += sum(1 for invoice in invoices.values() if invoice.linked_transaction_ids)
        self.linked_transactions += sum(1 for tx in transactions.values() if tx.invoice_id is not None)
        self.empty_transaction_sides += int(len(transactions) == 0)
        for s in suggestions:
            invoice = invoices.invoices[s.invoice_id]
            settlement = invoice.grand_total - (invoice.retention_amount or Decimal("0"))
            self.boundary_distances.add(abs(transactions.transactions[s.transaction_id].raw.amount - settlement))


def test_indexed_suggestions_equal_the_all_pairs_oracle_over_seeds() -> None:
    exercised = _Exercised()
    for seed in _SEEDS:
        invoices, transactions = _world(seed)

        default = suggest_reconciliations(invoices, transactions)
        expected_default = _all_pairs_oracle(invoices, transactions)
        assert _exact(default) == _exact(expected_default), f"seed {seed}, default tolerance"
        assert default == expected_default, f"seed {seed}, default tolerance"
        exercised.record(invoices, transactions, expected_default)

        for tolerance in _TOLERANCES:
            indexed = suggest_reconciliations(invoices, transactions, amount_tolerance=tolerance)
            expected = _all_pairs_oracle(invoices, transactions, tolerance)
            assert _exact(indexed) == _exact(expected), f"seed {seed}, tolerance {tolerance}"

    assert exercised.suggestions > 100
    assert exercised.with_counterparty > 0
    assert exercised.without_counterparty > 0
    assert exercised.invoices_with_several > 0
    assert exercised.transactions_with_several > 0
    assert exercised.linked_invoices > 0
    assert exercised.linked_transactions > 0
    assert exercised.empty_transaction_sides > 0
    # The default tolerance was met exactly on the boundary and inside it.
    assert {Decimal("0"), Decimal("0.005"), Decimal("0.01")} <= exercised.boundary_distances


def test_a_pair_just_past_the_tolerance_is_refused_on_both_sides() -> None:
    invoice = _invoice(
        number="EDGE-1",
        kind=InvoiceKind.RECEIVED,
        base=Decimal("100.00"),
        retention=None,
        counterparty="Beta Logistica SL",
        currency="EUR",
        issued_at=date(2025, 12, 31),
        linked=(),
    )
    amounts = ("120.99", "120.9899999", "121.00", "121.01", "121.0100001", "121.000")
    transactions = TransactionCatalogue.from_transactions(
        [
            _transaction(
                provider_id=f"edge-{text}",
                amount=Decimal(text),
                direction=TransactionDirection.OUTGOING,
                counterparty="BETA",
                currency="EUR",
                booked=date(2026, 1, 1),
                invoice_id=None,
            )
            for text in amounts
        ],
    )
    invoices = InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice}})

    suggestions = suggest_reconciliations(invoices, transactions)

    matched = sorted(transactions.transactions[s.transaction_id].raw.amount for s in suggestions)
    assert matched == [Decimal("120.99"), Decimal("121.00"), Decimal("121.000"), Decimal("121.01")]
    assert _exact(suggestions) == _exact(_all_pairs_oracle(invoices, transactions))


@pytest.mark.parametrize(
    "rounding",
    [ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING, ROUND_DOWN, ROUND_UP, ROUND_05UP],
)
def test_parity_holds_when_the_decimal_context_rounds_the_difference(rounding: str) -> None:
    """A three-digit context rounds ``amount - settlement``; the index must still agree."""
    for seed in _SEEDS[:8]:
        invoices, transactions = _world(seed)
        with localcontext() as context:
            context.prec = 3
            context.rounding = rounding
            for tolerance in (Decimal("0"), _CENT, Decimal("0.05"), Decimal("1"), Decimal("10")):
                indexed = suggest_reconciliations(invoices, transactions, amount_tolerance=tolerance)
                expected = _all_pairs_oracle(invoices, transactions, tolerance)
                assert _exact(indexed) == _exact(expected), f"seed {seed}, {rounding}, tolerance {tolerance}"


def test_empty_and_fully_linked_sides_suggest_nothing() -> None:
    invoices, transactions = _world(3)
    empty_invoices = InvoiceCatalogue.model_validate({"invoices": {}})
    empty_transactions = TransactionCatalogue.from_transactions([])

    assert suggest_reconciliations(empty_invoices, transactions) == ()
    assert suggest_reconciliations(invoices, empty_transactions) == ()
    assert suggest_reconciliations(empty_invoices, empty_transactions) == ()

    linked_invoices = InvoiceCatalogue.model_validate(
        {
            "invoices": {
                invoice.invoice_id: Invoice.model_validate(
                    {**invoice.model_dump(mode="python"), "linked_transaction_ids": ("e" * 64,)},
                )
                for invoice in invoices.values()
            },
        },
    )
    assert suggest_reconciliations(linked_invoices, transactions) == ()
