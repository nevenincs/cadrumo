"""A manual row's identity must not move because the command gained a field it does not use.

The manual source hash folds the whole add command. It is recorded on every
manual row's provenance, and a keyless row's provider id -- and therefore its
content-addressed ``transaction_id`` -- is built from it. When the command
grew ``investment_asset_id``, every command started hashing an extra ``null``
and every ordinary keyless movement was re-addressed although none of its
content had changed.

The pinned digests below were produced by the manual-add builder as it stood
before the command carried an investment-asset link, for the same commands and
the same clock. They are the independent reference: a command that does not use
a later optional field must still hash, and still be addressed, exactly as it
was. The same pins are what redden this module when another optional field is
added to the command without being listed among the fields the hash omits while
absent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.hashing import content_hash_hex
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ..actions_common import command_matches_current
from ..actions_manual import _SOURCE_HASH_FIELDS_OMITTED_WHEN_ABSENT, _source_sha256, _transaction_from_command
from ..models import ManualLedgerTransactionCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"
_OCCURRED_AT = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)

_PINNED_KEYLESS_SOURCE_SHA256 = "dedf4604c4542ee0a9a217d0a98051379ea06a9a9b41630c3e8831e7c1db04d4"
_PINNED_KEYLESS_TRANSACTION_ID = "86e6744ebe5d8e82f4215fa0da243d77cb31b25af457dd6e569eff88783d87d5"
_PINNED_KEYED_SOURCE_SHA256 = "598855e8eea79bce477d0b46a59a4fba0d33cc21dd8fee7e0d1d48ae49569d1f"
_PINNED_KEYED_TRANSACTION_ID = "e65504b57030bdb2519ffbd54c874d5347fba2cd2df72e23b9c38d44544b37c7"


def _keyless_command(**overrides: object) -> ManualLedgerTransactionCommand:
    """Return the minimal keyless add the keyless pins were taken from."""
    return ManualLedgerTransactionCommand.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "booked_date": date(2026, 5, 2),
            "amount": Decimal("121.00"),
            "direction": TransactionDirection.OUTGOING,
            "description": "material oficina",
            **overrides,
        },
    )


def _keyed_command(**overrides: object) -> ManualLedgerTransactionCommand:
    """Return the keyed add, every other earlier optional field populated, the keyed pins were taken from."""
    return ManualLedgerTransactionCommand.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "booked_date": date(2026, 5, 2),
            "value_date": date(2026, 5, 3),
            "amount": Decimal("121.00"),
            "currency": "EUR",
            "direction": TransactionDirection.OUTGOING,
            "counterparty": "Proveedor Sintetico SL",
            "description": "material oficina",
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.75"),
            "category_id": "material_oficina",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "recargo_amount": Decimal("0"),
            "irpf_category": "rendimientos.actividades",
            "usage_ratio_id": "usage.oficina",
            "prorrata_reference": "prorrata.2026",
            "purchase_invoice_evidence_id": "evidence.invoice.0001",
            "attachment_ids": ("attach.0001",),
            "notes": "compra de material",
            "iva_category": IvaCategory("domestic_general"),
            "counterparty_country": "ES",
            "prorrata_sector_id": "sector-1",
            "actor": "operator-A",
            "source_command": "aeat app ledger add",
            "idempotency_key": "pin-key-0001",
            "classified_by_override": "rule:material",
            "source_jurisdiction": "ES",
            "group_label": "oficina",
            **overrides,
        },
    )


def test_a_keyless_row_without_an_asset_link_keeps_its_earlier_identity() -> None:
    """Hash, provider id and transaction id all equal what the earlier builder produced."""
    transaction = _transaction_from_command(_keyless_command(), occurred_at=_OCCURRED_AT)

    assert transaction.raw.provenance.source_sha256 == _PINNED_KEYLESS_SOURCE_SHA256
    assert transaction.raw.provider_transaction_id == (
        f"manual:{_BUCKET_ID}:{_OCCURRED_AT.isoformat()}:{_PINNED_KEYLESS_SOURCE_SHA256}"
    )
    assert transaction.transaction_id == _PINNED_KEYLESS_TRANSACTION_ID


def test_a_keyed_row_without_an_asset_link_keeps_its_earlier_provenance_hash() -> None:
    """A keyed row's id is clock-free, but the hash on its provenance is still identity."""
    transaction = _transaction_from_command(_keyed_command(), occurred_at=_OCCURRED_AT)

    assert transaction.raw.provenance.source_sha256 == _PINNED_KEYED_SOURCE_SHA256
    assert transaction.raw.provider_transaction_id == f"manual:{_BUCKET_ID}:pin-key-0001"
    assert transaction.transaction_id == _PINNED_KEYED_TRANSACTION_ID


def test_the_pins_would_catch_an_absent_field_folded_in_as_null() -> None:
    """The defect the omission prevents is visible to the pins, so they are not vacuous.

    Hashing the command's full dump -- the absent asset link included as ``null``
    -- is exactly what re-addressed every keyless row. It must disagree with the
    earlier digest, or the pin above could not tell the two projections apart.
    """
    command = _keyless_command()
    folding_every_field = content_hash_hex({**command.model_dump(mode="json"), "occurred_at": _OCCURRED_AT.isoformat()})

    assert command.investment_asset_id is None
    assert folding_every_field != _PINNED_KEYLESS_SOURCE_SHA256
    assert _source_sha256(command, occurred_at=_OCCURRED_AT) == _PINNED_KEYLESS_SOURCE_SHA256


def test_a_present_asset_link_distinguishes_the_hash_and_the_keyless_identity() -> None:
    """Omission applies only to absence: a linked asset is content, and so is which asset."""
    first = _transaction_from_command(_keyless_command(investment_asset_id="bi-0001"), occurred_at=_OCCURRED_AT)
    second = _transaction_from_command(_keyless_command(investment_asset_id="bi-0002"), occurred_at=_OCCURRED_AT)

    assert first.raw.provenance.source_sha256 != _PINNED_KEYLESS_SOURCE_SHA256
    assert first.transaction_id != _PINNED_KEYLESS_TRANSACTION_ID
    assert first.raw.provenance.source_sha256 != second.raw.provenance.source_sha256
    assert first.transaction_id != second.transaction_id
    assert first.investment_asset_id == "bi-0001"


def test_a_present_asset_link_changes_a_keyed_rows_provenance_hash_but_not_its_key_identity() -> None:
    """The key names the logical add; the hash still records what the add carried."""
    linked = _transaction_from_command(_keyed_command(investment_asset_id="bi-0001"), occurred_at=_OCCURRED_AT)

    assert linked.raw.provenance.source_sha256 != _PINNED_KEYED_SOURCE_SHA256
    assert linked.transaction_id == _PINNED_KEYED_TRANSACTION_ID


def test_a_keyed_retry_that_only_adds_an_asset_link_is_not_a_no_op() -> None:
    """The idempotency match still sees the asset link, so a same-key retry carrying it conflicts."""
    stored = _transaction_from_command(_keyed_command(), occurred_at=_OCCURRED_AT)

    assert command_matches_current(_keyed_command(), stored)
    assert not command_matches_current(_keyed_command(investment_asset_id="bi-0001"), stored)


def test_every_omitted_field_is_an_optional_command_field_defaulting_to_none() -> None:
    """Omitting a field while ``None`` is lossless only when ``None`` is its default absence."""
    fields = ManualLedgerTransactionCommand.model_fields

    assert set(fields) >= _SOURCE_HASH_FIELDS_OMITTED_WHEN_ABSENT, sorted(_SOURCE_HASH_FIELDS_OMITTED_WHEN_ABSENT)
    for name in _SOURCE_HASH_FIELDS_OMITTED_WHEN_ABSENT:
        assert not fields[name].is_required(), name
        assert fields[name].default is None, name
