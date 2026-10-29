"""An authenticated stored catalogue reads to what full validation reads, minus one re-derivation.

The stored form is what the repository writes: a fully validated catalogue
dumped to JSON. A read through :func:`decode_authenticated_invoice_catalogue`
must return, invoice for invoice, the same values, JSON and set fields as
:class:`InvoiceCatalogue` full validation of those bytes. It skips exactly one
check, re-deriving the stored invoice id; every dated registry rule, the
totals and every structural constraint still refuse. Nothing outside the
entry point reaches that skip.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ...iva.schema import InvoiceKind
from ..catalogue import InvoiceCatalogue, StoredInvoiceCatalogue, decode_authenticated_invoice_catalogue
from ..errors import InvoiceValidationError
from ..models import Invoice
from .invoice_catalogue_seed import SeedCase, fields_set, seed_payload, seed_payloads

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with _indexed_authority_for_test().operation():
        yield


_BUCKET: Final = "00000000-0000-4000-8000-0000000000aa"


def _rich_payloads() -> list[dict[str, object]]:
    """Invoices carrying the optional facts the statute seed does not rotate through."""
    payloads: list[dict[str, object]] = []
    exempt_supply = seed_payload(
        SeedCase(
            900,
            date(2025, 5, 5),
            ("EXEMPT",),
            counterparty=("DE123456789", "DE"),
            extra={
                "iva_category": "intra_community_supply",
                "counterparty_identification_state": "de",
                "operation_type": "E",
                "legal_mentions": ["REVERSE_CHARGE"],
                "exemption_reference": "Art. 25 LIVA",
                "bucket_id": _BUCKET,
            },
        )
    )
    payloads.append(exempt_supply)
    payloads.append(
        seed_payload(
            SeedCase(
                901,
                date(2025, 6, 6),
                ("RATE_21",),
                kind="received",
                extra={
                    "provenance": {
                        "source_path": "facturas.csv",
                        "source_sha256": "c" * 64,
                        "source_row_index": 4,
                        "source_format": "csv",
                        "ingested_at": "2025-06-07T08:09:10+00:00",
                        "provider_name": "bulk-invoice-import",
                    },
                    "payment_id": "D" * 64,
                    "issuer_address": "  Calle Mayor 1, Madrid  ",
                    "recipient_address": "Avenida Diagonal 2, Barcelona",
                    "is_subvencion_ayuda": False,
                    "outside_economic_activity": True,
                },
            )
        )
    )
    payloads.append(
        seed_payload(
            SeedCase(
                902,
                date(2025, 8, 8),
                ("RATE_21",),
                extra={
                    "collected_on_behalf_of_tax_id": "B12345674",
                    "collected_on_behalf_of_name": "Colegiado Ejemplo",
                    "payment_status": "PARTIALLY_PAID",
                    "operation_date_role": "",
                },
            )
        )
    )
    return payloads


def _stored_json(payloads: list[dict[str, object]]) -> str:
    """Return the bytes the repository would store for ``payloads``: validated, then dumped."""
    invoices = [Invoice.model_validate_json(json.dumps(payload)) for payload in payloads]
    catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})
    assert len(catalogue) == len(payloads), "seeded invoices must not collide on identity"
    return catalogue.model_dump_json()


_STORED_DOCUMENT: Final = TypeAdapter(dict[str, dict[str, dict[str, object]]])


def _stored_records(stored: str) -> dict[str, dict[str, object]]:
    return _STORED_DOCUMENT.validate_json(stored)["invoices"]


def _seeds() -> list[list[dict[str, object]]]:
    """The statute seed, the rich invoices, and three reordered strided subsets of both."""
    everything = seed_payloads() + _rich_payloads()
    variants = [seed_payloads(), _rich_payloads()]
    for offset, stride in ((0, 2), (1, 3), (2, 5)):
        variants.append(list(reversed(everything[offset::stride])))
    return variants


@pytest.mark.parametrize("seed_index", range(5))
def test_an_authenticated_read_equals_full_validation_of_the_same_bytes(seed_index: int) -> None:
    """Values, JSON, set fields and order agree with full validation for every invoice."""
    stored = _stored_json(_seeds()[seed_index])
    full = InvoiceCatalogue.model_validate_json(stored)
    trusted = decode_authenticated_invoice_catalogue(_stored_records(stored))

    assert trusted.invoice_ids() == tuple(full.invoices)
    assert len(trusted) == len(full)
    for invoice_id in trusted.invoice_ids():
        read = trusted.require(invoice_id)
        expected = full.invoices[invoice_id]
        assert read == expected
        assert read.model_dump_json() == expected.model_dump_json()
        assert fields_set(read) == fields_set(expected)
        assert trusted.get(invoice_id) == expected
    assert trusted.values() == tuple(full.values())
    for kind in InvoiceKind:
        assert trusted.values(kind=kind) == tuple(invoice for invoice in full.values() if invoice.kind is kind)


def test_the_rich_seed_reaches_the_facts_the_statute_seed_does_not() -> None:
    """The parity above means nothing for a field no seeded invoice sets."""
    invoices = list(InvoiceCatalogue.model_validate_json(_stored_json(_rich_payloads())).values())
    assert any(invoice.counterparty_identification_state is not None for invoice in invoices)
    assert any(invoice.legal_mentions for invoice in invoices)
    assert any(invoice.iva_category is not None for invoice in invoices)
    assert any(invoice.provenance is not None for invoice in invoices)
    assert any(invoice.collected_on_behalf_of_tax_id is not None for invoice in invoices)
    assert any(invoice.bucket_id == _BUCKET for invoice in invoices)


def _one_stored_record(case: SeedCase) -> tuple[str, dict[str, object]]:
    records = _stored_records(_stored_json([seed_payload(case)]))
    ((invoice_id, record),) = records.items()
    return invoice_id, record


def test_the_stored_id_is_not_re_derived_but_every_other_path_derives_it() -> None:
    """The one skipped check: an id no longer derived from its fields reads only through the entry point."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    record["invoice_number"] = "PASS-9999"

    read = decode_authenticated_invoice_catalogue({invoice_id: record}).require(invoice_id)
    assert read.invoice_id == invoice_id
    assert read.invoice_number == "PASS-9999"

    derived = "invoice_id must match the stable hash derived from identity fields"
    with pytest.raises(ValidationError, match=derived):
        Invoice.model_validate(record)
    with pytest.raises(ValidationError, match=derived):
        Invoice.model_validate(record, context={"authenticated": True})
    with pytest.raises(ValidationError, match=derived):
        Invoice.model_validate_json(json.dumps(record))
    with pytest.raises(ValidationError, match=derived):
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": {invoice_id: record}}))


def test_a_stored_view_cannot_be_built_outside_the_entry_point() -> None:
    """Constructing the view directly would trust records no store authenticated."""
    with pytest.raises(TypeError, match="decode_authenticated_invoice_catalogue"):
        StoredInvoiceCatalogue({})
    with pytest.raises(TypeError, match="decode_authenticated_invoice_catalogue"):
        StoredInvoiceCatalogue({}, _authenticated=object())


def _refusal_of(invoice_id: str, record: dict[str, object]) -> str:
    with pytest.raises((ValidationError, InvoiceValidationError)) as caught:
        decode_authenticated_invoice_catalogue({invoice_id: record}).require(invoice_id)
    return str(caught.value)


def test_a_rate_not_in_force_on_the_devengo_date_is_still_refused() -> None:
    """Dated registry rules are kept: a 2 % line on a 2025 devengo date refuses."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2024, 11, 15), ("RATE_2",)))
    record["issued_at"] = "2025-02-03"

    assert "line rate RATE_2 was not in force on 2025-02-03" in _refusal_of(invoice_id, record)


def test_totals_that_do_not_reconstitute_are_still_refused() -> None:
    """The totals reconstitution is kept."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    record["grand_total"] = str(Decimal(str(record["grand_total"])) + Decimal("1.00"))

    assert "grand_total must equal base_total + iva_total" in _refusal_of(invoice_id, record)


def test_registry_vocabulary_and_identifier_rules_are_still_refused() -> None:
    """An undeclared category and a failed NIF checksum refuse on the authenticated read too."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    unknown_category = {**record, "iva_category": "not_a_registry_category"}
    assert "iva_category must be an IvaCategory" in _refusal_of(invoice_id, unknown_category)

    bad_checksum = {**record, "counterparty_tax_id": "B12345670"}
    assert "counterparty_tax_id" in _refusal_of(invoice_id, bad_checksum)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("base_total", "-1.00", "invoice totals must be non-negative"),
        ("kind", "sideways", "kind must be an InvoiceKind"),
        ("payment_status", "MAYBE", "payment_status must be a PaymentStatus"),
        ("issued_at", "not-a-date", "is not a valid ISO-8601 date"),
        ("lines", [], "invoice must carry at least one line"),
        ("invoice_id", "not-hex", "invoice_id"),
        ("unexpected_field", "x", "Extra inputs are not permitted"),
    ],
)
def test_structural_refusals_still_fire_on_an_authenticated_read(field: str, value: object, expected: str) -> None:
    """Types, enum membership and field constraints are unaffected by the skipped re-derivation."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    record[field] = value

    assert expected in _refusal_of(invoice_id, record)


def test_a_missing_required_field_and_a_missing_id_are_refused() -> None:
    """A record the store returns incomplete is refused rather than completed by derivation."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    without_name = {key: value for key, value in record.items() if key != "counterparty_name"}
    assert "counterparty_name" in _refusal_of(invoice_id, without_name)

    without_id = {key: value for key, value in record.items() if key != "invoice_id"}
    assert "invoice_id" in _refusal_of(invoice_id, without_id)


def test_a_record_keyed_by_another_id_is_refused() -> None:
    """The catalogue key must be the invoice's own id."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    wrong_key = "0" * 64

    with pytest.raises(InvoiceValidationError, match=f"does not match invoice_id '{invoice_id}'"):
        decode_authenticated_invoice_catalogue({wrong_key: record}).require(wrong_key)


def test_a_read_validates_only_the_invoices_it_returns() -> None:
    """One malformed record refuses a read that returns it and no read that does not."""
    stored = _stored_records(
        _stored_json(
            [
                seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",))),
                seed_payload(SeedCase(2, date(2025, 7, 7), ("RATE_21",), kind="received")),
            ]
        )
    )
    (issued_id, issued), (received_id, received) = stored.items()
    received["lines"] = []
    catalogue = decode_authenticated_invoice_catalogue({issued_id: issued, received_id: received})

    assert catalogue.require(issued_id).invoice_id == issued_id
    assert [invoice.invoice_id for invoice in catalogue.values(kind=InvoiceKind.ISSUED)] == [issued_id]
    with pytest.raises(ValidationError, match="invoice must carry at least one line"):
        catalogue.require(received_id)
    with pytest.raises(ValidationError, match="invoice must carry at least one line"):
        catalogue.values()
    with pytest.raises(ValidationError, match="invoice must carry at least one line"):
        catalogue.values(kind=InvoiceKind.RECEIVED)
    assert catalogue.get("f" * 64) is None


def test_a_malformed_kind_refuses_a_filtered_list_instead_of_dropping_out() -> None:
    """Only a record of another valid kind is passed over unvalidated."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    record["kind"] = "ISSUED"
    catalogue = decode_authenticated_invoice_catalogue({invoice_id: record})

    with pytest.raises(ValidationError, match="kind must be an InvoiceKind"):
        catalogue.values(kind=InvoiceKind.RECEIVED)


def test_attributed_buckets_are_read_from_every_record_without_validation() -> None:
    """The ownership guard sees a record no read returns, and refuses a non-text bucket id."""
    invoice_id, record = _one_stored_record(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    other_id, other = _one_stored_record(SeedCase(2, date(2025, 7, 7), ("RATE_21",)))
    record["bucket_id"] = f"  {_BUCKET} "
    other["lines"] = []
    catalogue = decode_authenticated_invoice_catalogue({invoice_id: record, other_id: other})
    assert catalogue.attributed_bucket_ids() == frozenset({_BUCKET})

    other["bucket_id"] = 7
    with pytest.raises(InvoiceValidationError, match="bucket_id must be a string"):
        decode_authenticated_invoice_catalogue({other_id: other}).attributed_bucket_ids()


def test_lifecycle_stamps_keep_their_utc_typing() -> None:
    """A naive stamp is refused; an aware one reads back as the same instant."""
    invoice_id, record = _one_stored_record(
        SeedCase(1, date(2025, 7, 7), ("RATE_21",), extra={"created_at": "2025-07-07T10:00:00+00:00"})
    )
    assert decode_authenticated_invoice_catalogue({invoice_id: record}).require(invoice_id).created_at == datetime(
        2025, 7, 7, 10, tzinfo=UTC
    )
    record["created_at"] = "2025-07-07T10:00:00"
    assert "created_at" in _refusal_of(invoice_id, record)
