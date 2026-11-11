"""The rules a frontend reads as a generated projection are the ones their real owners apply."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Final

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.invoices.service import (
    INVOICE_MATCH_TOLERANCE,
    invoice_settling_direction,
    suggest_reconciliations,
)
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.classification_effects import takes_capital_good_acquisition
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue, derive_transaction_id
from ...aggregation.iva_ledger_classification import iva_ledger_missing_fact_reasons
from ..llm_classification import derive_iva_substrate
from ..preflight import HeldTransactionCatalogue, LedgerPreflightIssueReason, preflight_transaction_catalogue
from ..readiness_routes import IVA_DERIVABLE_REASONS, READINESS_REASON_FIELDS
from ..staged_check import check_stored_row
from ..staged_check_contracts import LedgerStagedCell, LedgerStagedRow, StageFieldName
from ..staged_identity import TRANSACTION_IDENTITY_FIELDS
from .preflight_test_support import BUCKET_ID, Q2_2026, preflight_transaction, raw_transaction

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MOVED: Final[dict[StageFieldName, str]] = {
    "amount": "99.00",
    "description": "another narrative",
    "value_date": date(_YEAR, 5, 1).isoformat(),
    "booked_date": date(_YEAR, 5, 2).isoformat(),
    "own_account_id": "account-2",
}


@pytest.fixture(autouse=True)
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _invoice(kind: InvoiceKind, gross: Decimal) -> Invoice:
    base = (gross / Decimal("1.21")).quantize(Decimal("0.01"))
    iva = gross - base
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": "F-1",
            "issued_at": date(_YEAR, 4, 1),
            "counterparty_name": "Proveedor S.L.",
            "counterparty_tax_id": "B00015073",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": iva,
            "grand_total": gross,
            "currency": "EUR",
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
        },
    )


def _invoices(*invoices: Invoice) -> InvoiceCatalogue:
    return InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice for invoice in invoices}})


@pytest.mark.parametrize(
    ("field", "change", "identity"),
    (
        ("amount", {"amount": Decimal("99.00")}, True),
        ("description", {"description": "another narrative"}, True),
        ("value_date", {"value_date": date(_YEAR, 5, 1)}, True),
        ("counterparty", {"counterparty": "Otro"}, False),
    ),
)
def test_an_identity_field_is_one_the_id_is_worked_out_from(
    field: str, change: dict[str, object], identity: bool
) -> None:
    raw = raw_transaction("identity")

    assert (derive_transaction_id(raw.model_copy(update=change)) != derive_transaction_id(raw)) is identity
    assert (field in TRANSACTION_IDENTITY_FIELDS) is identity


def test_binding_an_own_account_moves_the_id_and_the_field_says_so() -> None:
    raw = raw_transaction("identity")

    assert derive_transaction_id(raw, own_account_id="account-2") != derive_transaction_id(raw)
    assert "own_account_id" in TRANSACTION_IDENTITY_FIELDS


def test_a_booked_date_is_identity_when_no_value_date_stands_before_it() -> None:
    raw = raw_transaction("identity").model_copy(update={"value_date": None})
    moved = raw.model_copy(update={"booked_date": date(_YEAR, 5, 2)})

    assert derive_transaction_id(moved) != derive_transaction_id(raw)
    assert "booked_date" in TRANSACTION_IDENTITY_FIELDS


@pytest.mark.parametrize("field", sorted(TRANSACTION_IDENTITY_FIELDS))
def test_the_staged_check_names_only_identity_fields_as_new_identity(field: StageFieldName) -> None:
    stored = preflight_transaction("staged", direction=TransactionDirection.OUTGOING)
    answer = check_stored_row(
        LedgerStagedRow(
            transaction_id=stored.transaction_id, cells=(LedgerStagedCell(field=field, value=_MOVED[field]),)
        ),
        stored,
    )

    # A booked date behind a value date moves nothing: the id reads the value date first.
    assert answer.identity_fields == (() if field == "booked_date" else (field,))


@pytest.mark.parametrize(
    ("kind", "direction"),
    ((InvoiceKind.ISSUED, TransactionDirection.INCOMING), (InvoiceKind.RECEIVED, TransactionDirection.OUTGOING)),
)
def test_the_settling_direction_is_the_only_one_reconciliation_suggests(
    kind: InvoiceKind, direction: TransactionDirection
) -> None:
    assert invoice_settling_direction(kind) is direction
    rows = {
        moving: preflight_transaction(f"row-{moving.value}", direction=moving, amount=Decimal("121.00"))
        for moving in (TransactionDirection.INCOMING, TransactionDirection.OUTGOING)
    }

    suggested = suggest_reconciliations(
        _invoices(_invoice(kind, Decimal("121.00"))), TransactionCatalogue.from_transactions(tuple(rows.values()))
    )

    assert [suggestion.transaction_id for suggestion in suggested] == [rows[direction].transaction_id]


@pytest.mark.parametrize(
    ("distance", "suggested"),
    ((INVOICE_MATCH_TOLERANCE, True), (INVOICE_MATCH_TOLERANCE + Decimal("0.01"), False)),
)
def test_the_match_tolerance_is_where_reconciliation_stops_suggesting(distance: Decimal, suggested: bool) -> None:
    row = preflight_transaction(
        "near",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00") + distance,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    answer = suggest_reconciliations(
        _invoices(_invoice(InvoiceKind.RECEIVED, Decimal("121.00"))), TransactionCatalogue.from_transactions((row,))
    )

    assert bool(answer) is suggested


def _deducting_row(direction: TransactionDirection) -> Transaction:
    row = preflight_transaction(
        f"deducting-{direction.value}",
        direction=direction,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    return Transaction.model_validate(
        row.model_dump()
        | {
            "deduction_fact_kind": "domestic_current",
            "deduction_provenance": {
                "authority": "invoice_evidence",
                "source_locator": "invoice:REC-2026-1",
                "evidence_digest": "a" * 64,
            },
        }
    )


@pytest.mark.parametrize("direction", (TransactionDirection.INCOMING, TransactionDirection.OUTGOING))
def test_only_a_purchase_can_bear_the_cuota_of_a_capital_good(
    direction: TransactionDirection, operation: PinnedAuthorityOperation
) -> None:
    report = preflight_transaction_catalogue(
        invoices=(),
        movement_reader=HeldTransactionCatalogue(TransactionCatalogue.from_transactions(())),
        cash_accounting_enrolled=False,
        bucket_id=BUCKET_ID,
        period=Q2_2026,
        transactions=TransactionCatalogue.from_transactions((_deducting_row(direction),)),
        operation=operation,
    )
    inadmissible = LedgerPreflightIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION in {
        issue.reason for issue in report.issues
    }

    assert takes_capital_good_acquisition(direction) is (not inadmissible)


def test_a_transfer_is_never_the_purchase_of_a_capital_good() -> None:
    assert not takes_capital_good_acquisition(TransactionDirection.INTERNAL_TRANSFER)


def test_a_derivable_reason_is_one_the_derivation_answers(operation: PinnedAuthorityOperation) -> None:
    rate, base, amount, derivable, _note = derive_iva_substrate(
        IvaCategory("domestic_general"),
        gross=Decimal("121.00"),
        on_date=date(_YEAR, 4, 5),
        operation=operation,
    )
    assert derivable
    missing = preflight_transaction(
        "derive",
        amount=Decimal("121.00"),
        iva_category=IvaCategory("domestic_general"),
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    found = {LedgerPreflightIssueReason(reason.value) for reason in iva_ledger_missing_fact_reasons(missing)}
    assert found == IVA_DERIVABLE_REASONS
    filled = Transaction.model_validate(
        missing.model_dump() | {"iva_rate": rate, "taxable_base": base, "iva_amount": amount}
    )
    assert not iva_ledger_missing_fact_reasons(filled)
    assert {READINESS_REASON_FIELDS[reason] for reason in IVA_DERIVABLE_REASONS} == {
        "taxable_base",
        "iva_amount",
        "iva_rate",
    }


def test_every_reason_a_field_puts_right_names_a_field_a_movement_stages() -> None:
    assert set(READINESS_REASON_FIELDS) >= IVA_DERIVABLE_REASONS
    assert LedgerPreflightIssueReason.UNSUPPORTED_PERIOD not in READINESS_REASON_FIELDS
