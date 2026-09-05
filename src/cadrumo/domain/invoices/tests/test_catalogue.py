"""Unit tests for the invoice catalogue service layer."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.aggregation import IntracomOperationType
from ...iva.classification import InvoiceKind, TransactionKind
from ...iva.oss import OssIossRegime
from ...iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ..enums import (
    InvoiceClass,
    InvoiceLegalMention,
    InvoiceOperationDateRole,
    IvaRate,
    PaymentStatus,
)
from ..errors import (
    InvoiceCatalogueError,
    InvoiceLinkError,
    InvoiceNotFoundError,
    InvoicePersistenceError,
)
from ..models import Invoice, InvoiceCatalogue, InvoiceLine
from ..service import (
    find_unmatched,
    link_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_HEX64_A = "a" * 64
_HEX64_B = "b" * 64
_HEX64_C = "c" * 64


def _valid_invoice(
    *,
    invoice_number: str = "INV-001",
    kind: InvoiceKind = InvoiceKind.ISSUED,
    counterparty_name: str = "Cliente SL",
    counterparty_tax_id: str = "B12345674",
    counterparty_country: str = "ES",
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "Servicios",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
        },
    )


def _maximally_populated_invoice() -> Invoice:
    """Return an invoice carrying a non-default value in every defaultable field.

    A JSON round-trip re-parses each optional field from a string, so a
    save-drops-field or load-re-defaults-field regression is invisible against
    a fixture that left the field at its default. The one axis structurally
    absent here is the fx conversion stamp: it is refused on a EUR invoice, so
    :func:`_foreign_currency_invoice` carries it instead and both records ride
    the same catalogue.
    """
    line = InvoiceLine.model_validate(
        {
            "description": "Servicios de consultoría",
            "quantity": Decimal("10"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("1000.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("210.00"),
            "spending_category_id": "consultoria",
            "oss_rate_kind": IvaRateKind.GENERAL,
        },
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_class": InvoiceClass.RECTIFICATIVA,
            "series": "R",
            "rectifies_invoice_number": "F-2026-099",
            "invoice_number": "F-2026-100",
            "issued_at": date(2026, 4, 10),
            "operation_date": date(2026, 4, 8),
            "operation_date_role": InvoiceOperationDateRole.OPERATION_PERFORMED,
            "counterparty_name": "Consultora Ibérica SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "counterparty_identification_state": EUMemberState.ES,
            "bucket_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "issuer_address": "Calle Mayor 1, 28013 Madrid",
            "recipient_address": "Gran Vía 2, 28013 Madrid",
            "exemption_reference": "LIVA art. 20.Uno.26",
            "legal_mentions": (InvoiceLegalMention.CASH_ACCOUNTING_REGIME,),
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("210.00"),
            "grand_total": Decimal("1287.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PARTIALLY_PAID,
            "linked_transaction_ids": (_HEX64_A, _HEX64_B),
            "notes": "Factura con retención IRPF aplicable a profesional.",
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "operation_type": IntracomOperationType.S,
            "oss_ioss_regime": OssIossRegime.UNION_SCHEME,
            "oss_transaction_kind": TransactionKind.OSS_UNION_SERVICES,
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("150.00"),
            "recargo_amount": Decimal("52.00"),
            "suplido_amount": Decimal("25.00"),
            "payment_id": _HEX64_C,
            "created_at": datetime(2026, 5, 5, 9, 30, 0, tzinfo=UTC),
            "updated_at": datetime(2026, 6, 11, 16, 45, 30, tzinfo=UTC),
        },
    )


def _foreign_currency_invoice() -> Invoice:
    """Return a non-EUR invoice carrying the all-or-nothing fx conversion stamp."""
    line = InvoiceLine.model_validate(
        {
            "description": "Cloud hosting",
            "quantity": Decimal("1"),
            "unit_price": Decimal("200.00"),
            "subtotal": Decimal("200.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("42.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "F-2026-300",
            "issued_at": date(2026, 3, 14),
            "counterparty_name": "Hosting Inc",
            "counterparty_tax_id": "US987654321",
            "counterparty_country": "US",
            "base_total": Decimal("200.00"),
            "iva_total": Decimal("42.00"),
            "grand_total": Decimal("242.00"),
            "currency": "USD",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "fx_rate": Decimal("0.92"),
            "fx_rate_date": date(2026, 3, 14),
            "fx_rate_source": "ECB",
        },
    )


def test_persistence_round_trip_preserves_catalogue() -> None:
    """Serialising then deserialising should round-trip the full catalogue.

    Carries the maximally-populated and the fx-stamped records alongside the
    plain ones, so no optional field crosses the JSON boundary at its default.
    """
    catalogue = InvoiceCatalogue.from_invoices(
        [
            _valid_invoice(invoice_number="INV-001"),
            _valid_invoice(invoice_number="INV-002", kind=InvoiceKind.RECEIVED),
            _maximally_populated_invoice(),
            _foreign_currency_invoice(),
        ],
    )
    restored = InvoiceCatalogue.model_validate_json(catalogue.model_dump_json())
    assert restored == catalogue

    populated = next(invoice for invoice in restored if invoice.invoice_number == "F-2026-100")
    assert populated.series == "R"
    assert populated.rectifies_invoice_number == "F-2026-099"
    assert populated.counterparty_identification_state is EUMemberState.ES
    assert populated.issuer_address == "Calle Mayor 1, 28013 Madrid"
    assert populated.recipient_address == "Gran Vía 2, 28013 Madrid"
    assert populated.exemption_reference == "LIVA art. 20.Uno.26"
    assert populated.legal_mentions == (InvoiceLegalMention.CASH_ACCOUNTING_REGIME,)
    assert populated.operation_type is IntracomOperationType.S
    assert populated.oss_transaction_kind is TransactionKind.OSS_UNION_SERVICES
    assert populated.retention_amount == Decimal("150.00")
    assert populated.recargo_amount == Decimal("52.00")
    assert populated.suplido_amount == Decimal("25.00")
    assert populated.payment_id == _HEX64_C
    assert populated.created_at == datetime(2026, 5, 5, 9, 30, 0, tzinfo=UTC)
    assert populated.updated_at == datetime(2026, 6, 11, 16, 45, 30, tzinfo=UTC)
    assert populated.lines[0].oss_rate_kind is IvaRateKind.GENERAL
    assert populated.lines[0].spending_category_id == "consultoria"

    foreign = next(invoice for invoice in restored if invoice.invoice_number == "F-2026-300")
    assert foreign.fx_rate == Decimal("0.92")
    assert foreign.fx_rate_date == date(2026, 3, 14)
    assert foreign.fx_rate_source == "ECB"


def test_load_raises_typed_error_for_invalid_json() -> None:
    """Invalid JSON must surface a typed persistence error."""
    with pytest.raises(ValidationError, match=r"json|JSON|Invalid"):
        InvoiceCatalogue.model_validate_json("{not-valid")


def test_catalogue_get_returns_none_for_missing_id() -> None:
    """Missing IDs return None rather than raising."""
    catalogue = InvoiceCatalogue.from_invoices([_valid_invoice()])
    assert catalogue.get("missing") is None


def test_find_unmatched_filters_by_kind() -> None:
    """find_unmatched returns empty-link invoices, filtered by kind when requested."""
    hex_a = "a" * 64
    issued_unlinked = _valid_invoice(invoice_number="INV-001")
    issued_linked = _valid_invoice(invoice_number="INV-002", linked_transaction_ids=(hex_a,))
    received_unlinked = _valid_invoice(invoice_number="INV-003", kind=InvoiceKind.RECEIVED)
    catalogue = InvoiceCatalogue.from_invoices([issued_unlinked, issued_linked, received_unlinked])

    assert set(find_unmatched(catalogue)) == {issued_unlinked, received_unlinked}
    assert find_unmatched(catalogue, kind=InvoiceKind.ISSUED) == (issued_unlinked,)
    assert find_unmatched(catalogue, kind=InvoiceKind.RECEIVED) == (received_unlinked,)


def test_link_transaction_appends_id_and_returns_new_catalogue() -> None:
    """link_transaction must return a fresh catalogue with the transaction appended."""
    invoice = _valid_invoice()
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    hex_a = "a" * 64

    updated = link_transaction(catalogue, invoice.invoice_id, hex_a)
    assert updated is not catalogue
    original = catalogue.get(invoice.invoice_id)
    after = updated.get(invoice.invoice_id)
    assert original is not None and original.linked_transaction_ids == ()
    assert after is not None and after.linked_transaction_ids == (hex_a,)


def test_link_transaction_is_idempotent_on_duplicate() -> None:
    """Re-linking an already-present transaction returns a value-equal catalogue."""
    hex_a = "a" * 64
    invoice = _valid_invoice(linked_transaction_ids=(hex_a,))
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    updated = link_transaction(catalogue, invoice.invoice_id, hex_a)
    assert updated == catalogue


def test_link_transaction_rejects_invalid_request() -> None:
    """Invalid link requests must raise the typed service error."""
    # The error type is what distinguishes the two cases; the sentences that
    # used to carry that distinction are catalogue-rendered now.
    cases: tuple[tuple[str | None, str, type[Exception]], ...] = (
        (None, "not-hex", InvoiceLinkError),
        ("nonexistent", "a" * 64, InvoiceNotFoundError),
    )
    invoice = _valid_invoice()
    catalogue = InvoiceCatalogue.from_invoices([invoice])

    for invoice_id_override, transaction_id, expected_error in cases:
        invoice_id = invoice.invoice_id if invoice_id_override is None else invoice_id_override
        with pytest.raises(expected_error):
            link_transaction(catalogue, invoice_id, transaction_id)


def test_catalogue_rejects_mapping_with_mismatched_keys() -> None:
    """Mapping keys must match each nested invoice's ``invoice_id``."""
    invoice = _valid_invoice()
    payload = {"invoices": {"wrong-key": invoice}}
    with pytest.raises(ValidationError, match=r"invoice_id|key|mismatch"):
        InvoiceCatalogue.model_validate(payload)


def test_catalogue_refuses_a_payload_without_the_invoices_wrapper() -> None:
    """A catalogue serialized without its canonical wrapper must refuse.

    The bare ``{invoice_id: invoice}`` shape is not something this codebase
    writes -- :meth:`InvoiceCatalogue.model_dump` always emits the wrapper --
    so accepting it would read a mapping whose keys no writer established to
    be invoice ids as though it were a catalogue.
    """
    invoice = _valid_invoice()

    with pytest.raises(ValidationError, match=r"must carry its entries under the 'invoices' key"):
        InvoiceCatalogue.model_validate({invoice.invoice_id: invoice})


def test_catalogue_accepts_the_canonical_wrapper() -> None:
    """The wrapped payload the catalogue itself emits must hydrate."""
    invoice = _valid_invoice()

    catalogue = InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice}})

    assert catalogue.invoices == {invoice.invoice_id: invoice}


def test_catalogue_accepts_construction_with_no_entries() -> None:
    """An empty mapping is the no-field construction, not a wrapper-less payload.

    Pydantic hands the before-validator the field kwargs, which for
    ``InvoiceCatalogue()`` is an empty mapping. It is accepted deliberately:
    it carries no entry that could be mis-keyed, and it hydrates to the same
    empty catalogue the canonical wrapper would.
    """
    assert len(InvoiceCatalogue()) == 0
    assert len(InvoiceCatalogue.model_validate({})) == 0
    assert InvoiceCatalogue() == InvoiceCatalogue.model_validate({"invoices": {}})


def test_from_invoices_keys_the_catalogue_by_invoice_id() -> None:
    """The explicit construction API builds the keyed mapping from an iterable."""
    first = _valid_invoice(invoice_number="INV-001")
    second = _valid_invoice(invoice_number="INV-002", kind=InvoiceKind.RECEIVED)

    catalogue = InvoiceCatalogue.from_invoices([first, second])

    assert set(catalogue.invoices) == {first.invoice_id, second.invoice_id}
    assert catalogue.get(first.invoice_id) == first


def test_from_invoices_refuses_a_duplicate_invoice_id() -> None:
    """The iterable arm's duplicate refusal is live behaviour, not incidental."""
    invoice = _valid_invoice()

    with pytest.raises(ValidationError, match=r"duplicate invoice_id"):
        InvoiceCatalogue.from_invoices([invoice, invoice])


def test_catalogue_error_hierarchy_reachable() -> None:
    """Error subclasses must be catchable through a single parent."""
    with pytest.raises(InvoiceCatalogueError, match=r"surface test"):
        raise InvoicePersistenceError("surface test")
