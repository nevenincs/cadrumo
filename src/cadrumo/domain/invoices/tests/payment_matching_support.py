"""The invoices, movements and recorded answers the payment-matching desktop recording holds."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Final

from ...iva.schema import InvoiceKind
from ...transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...transactions.models import Transaction
from ...transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine
from ..payment_matching import invoice_choices, link_differences, movement_choices, suggest_payments
from ..service import invoice_settlement

ISSUED: Final = date(2026, 10, 1)
PARTY: Final = "Papeleria Trazo SL"


def day(offset: int, origin: date = ISSUED) -> str:
    return date.fromordinal(origin.toordinal() + offset).isoformat()


def build_invoice(
    number: str,
    *,
    kind: str = "received",
    issued: str = "2026-10-01",
    party: str = PARTY,
    tax_id: str | None = "B00015073",
    base: str = "30.00",
    retention: str | None = None,
    currency: str = "EUR",
    linked: tuple[str, ...] = (),
) -> Invoice:
    """An invoice at 21 % IVA over ``base``, so its total is ``base`` plus a cuota rounded to the cent."""
    amount = Decimal(base)
    cuota = (amount * Decimal("0.21")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Invoice.model_validate(
        {
            "kind": InvoiceKind(kind),
            "invoice_number": number,
            "issued_at": date.fromisoformat(issued),
            "counterparty_name": party,
            "counterparty_tax_id": tax_id,
            "counterparty_country": "ES",
            "base_total": amount,
            "iva_total": cuota,
            "grand_total": amount + cuota,
            "currency": currency,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios",
                        "quantity": Decimal(1),
                        "unit_price": amount,
                        "subtotal": amount,
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": cuota,
                    },
                ),
            ),
            "payment_status": PaymentStatus.PENDING,
            "retention_rate": None if retention is None else Decimal("0.15"),
            "retention_amount": None if retention is None else Decimal(retention),
            "linked_transaction_ids": linked,
        },
    )


def build_movement(
    name: str,
    *,
    amount: str = "36.30",
    direction: str = "OUTGOING",
    on: str = "2026-10-03",
    description: str = "TRANSFERENCIA",
    counterparty: str | None = None,
    currency: str = "EUR",
    state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    invoice_id: str | None = None,
) -> Transaction:
    moment = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    raw = RawTransaction(
        provider_transaction_id=name,
        booked_date=date.fromisoformat(on),
        value_date=None,
        amount=Decimal(amount),
        currency=currency,
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path("synthetic.csv"),
            source_sha256="0" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=moment,
            provider_name="synthetic",
        ),
        raw_fields={},
    )
    stored = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection(direction),
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": moment,
            "modified_at": moment,
        }
    )
    return stored.model_copy(update={"lifecycle_state": state, "invoice_id": invoice_id})


def movement_names(*movements: Transaction) -> dict[str, str]:
    return {movement.transaction_id: movement.raw.provider_transaction_id for movement in movements}


def _scenario_invoices(scenario: Mapping[str, Any]) -> dict[str, Invoice]:
    return {
        entry["number"]: build_invoice(
            entry["number"],
            **{key: value for key, value in entry.items() if key not in {"number", "linked"}},
            linked=("b" * 64,) if entry.get("linked") else (),
        )
        for entry in scenario["invoices"]
    }


def recorded_scenario(question: Mapping[str, Any]) -> dict[str, Any]:
    """The scenario ``question`` states with the totals, settlements and answers the rules give it."""
    invoices = _scenario_invoices(question)
    return {
        **question,
        "totals": {number: str(invoice.grand_total) for number, invoice in invoices.items()},
        "settlements": {number: str(invoice_settlement(invoice)) for number, invoice in invoices.items()},
        "answer": scenario_answer(question),
    }


def scenario_answer(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """What the suggestions, choices and judgements of ``scenario`` come to under the rules."""
    invoices = _scenario_invoices(scenario)
    movements = {
        entry["name"]: build_movement(
            entry["name"],
            **{key: value for key, value in entry.items() if key not in {"name", "state", "cited"}},
            state=TransactionLifecycleState(entry.get("state", "ACTIVE")),
            invoice_id="a" * 64 if entry.get("cited") else None,
        )
        for entry in scenario["movements"]
    }
    names = movement_names(*movements.values())
    numbers = {invoice.invoice_id: number for number, invoice in invoices.items()}
    staged = {movements[name].transaction_id: invoices[number].invoice_id for name, number in scenario["staged"]}
    focus = scenario.get("focus", {})
    weighed = [invoice for number, invoice in invoices.items() if focus.get("invoice") in (None, number)]
    found = suggest_payments(movements.values(), weighed, staged=staged)
    wanted = movements[focus["movement"]].transaction_id if "movement" in focus else None

    def pair(one: Any) -> dict[str, Any]:
        return {
            "movement": names[one.transaction.transaction_id],
            "invoice": numbers[one.invoice.invoice_id],
            "number": one.number,
            "gap": one.gap,
            "counterparty": one.counterparty,
        }

    answer: dict[str, Any] = {
        "suggestions": [
            {
                **pair(one.pair),
                "ambiguous": one.ambiguous,
                "ties": [pair(tie) for tie in one.ties],
                "others": [pair(other) for other in one.others],
            }
            for one in found
            if wanted in (None, one.pair.transaction.transaction_id)
        ],
        "invoice_choices": None,
        "movement_choices": None,
    }
    if "movement" in focus:
        answer["invoice_choices"] = [
            {
                "invoice": numbers[choice.invoice.invoice_id],
                "settles": choice.settles,
                "staged_for": None if choice.staged_for is None else names[choice.staged_for],
                "linked": choice.linked,
            }
            for choice in invoice_choices(movements[focus["movement"]], invoices.values(), staged=staged)
        ]
    if "invoice" in focus:
        answer["movement_choices"] = [
            {"movement": names[choice.transaction.transaction_id], "settles": choice.settles}
            for choice in movement_choices(invoices[focus["invoice"]], movements.values(), staged=frozenset(staged))
        ]
    if "judge" in scenario:
        answer["judgements"] = [
            {
                "movement": movement_name,
                "invoice": number,
                "found": True,
                "mismatches": [
                    {
                        "kind": difference.kind,
                        "difference": None if difference.difference is None else str(difference.difference),
                        "movement": difference.movement_currency,
                        "invoice": difference.invoice_currency,
                        "count": difference.count,
                    }
                    for difference in link_differences(movements[movement_name], invoices[number])
                ],
            }
            for movement_name, number in scenario["judge"]
        ]
    return answer
