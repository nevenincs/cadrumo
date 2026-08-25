"""Evidence add is idempotent when the caller asks, additive when it does not.

Both halves are load-bearing and they fail in opposite directions, which is why
neither can be inferred from the other.

Without a key the verb must stay ADDITIVE: the same invoice PDF can legitimately
be attached twice as two distinct pieces of evidence, and a guard that collapsed
them would destroy a real distinction. With a key it must be GUARDED: the CLI's
operator is an autonomous agent that retries, so a non-retry-safe creating
mutation silently double-writes, and a duplicated evidence record inflates every
downstream aggregation that reads it.

The defect this closes is small at one document per invocation and corrupting at
a thousand: a directory-ingest or resumable batch verb multiplies records on
every re-run, which is why record identity is a PREREQUISITE for batch work
rather than a tidiness item.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

import pytest

from ..evidence import (
    MediaKind,
    derive_keyed_purchase_invoice_evidence_id,
    derive_purchase_invoice_evidence_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _EvidenceIdFields(TypedDict):
    """The content half of the evidence-id inputs, minus ``created_at``.

    Declared so the splat below carries its real shape. It previously went
    through a ``dict[str, object]`` behind a type-ignore, which suppressed the
    one thing worth checking here: that the fields held constant across the two
    calls are the fields the id actually derives from. A drift in the
    signature would otherwise stay invisible.
    """

    bucket_id: str
    source_sha256: str
    media_kind: MediaKind
    supplier: str | None
    invoice_number: str | None
    invoice_date: str | None
    taxable_base: Decimal | None
    iva_rate: Decimal | None
    iva_amount: Decimal | None
    notes: str


_BUCKET = "f4e3be8f-a3ee-48a6-9cec-bee20131ddcd"  # was 'bucket-idem'


def test_the_keyed_id_is_clock_free_so_a_retry_resolves_to_the_same_record() -> None:
    """Two derivations at different instants must agree.

    This is the whole mechanism. An id that folds the clock mints a new record
    on every retry, which is precisely the breach the codified rule names: the
    record's identity must be clock-free and the timestamp a non-identity
    last-seen body field.
    """
    first = derive_keyed_purchase_invoice_evidence_id(bucket_id=_BUCKET, idempotency_key="ingest-2024-11-15-001")
    second = derive_keyed_purchase_invoice_evidence_id(bucket_id=_BUCKET, idempotency_key="ingest-2024-11-15-001")

    assert first == second
    assert len(first) == 16


def test_a_different_key_or_bucket_yields_a_different_record() -> None:
    """The key scopes to its bucket; two keys are two records.

    Guards the opposite failure from the one above: a derivation that ignored
    its inputs would also be stable across retries, and would collapse every
    caller onto one id.
    """
    base = derive_keyed_purchase_invoice_evidence_id(bucket_id=_BUCKET, idempotency_key="k1")

    assert derive_keyed_purchase_invoice_evidence_id(bucket_id=_BUCKET, idempotency_key="k2") != base
    assert derive_keyed_purchase_invoice_evidence_id(bucket_id="other", idempotency_key="k1") != base


def test_the_keyless_derivation_still_folds_the_clock_deliberately() -> None:
    """The additive path is unchanged, and that is a decision rather than an omission.

    Its docstring states that two evidence records for the same file must keep
    distinct ids, and the disambiguator exists to preserve that case rather than
    to collapse a retry. Dropping the clock here -- the naive reading of the
    idempotency rule -- would silently merge genuine duplicates. The fix was to
    ADD the key, not to remove the clock, and this pins that the removal did not
    happen by accident.
    """
    from datetime import UTC, datetime

    fields: _EvidenceIdFields = {
        "bucket_id": _BUCKET,
        "source_sha256": "a" * 64,
        "media_kind": MediaKind.PDF,
        "supplier": "ESB12345674",
        "invoice_number": "F-1",
        "invoice_date": "2024-11-15",
        "taxable_base": None,
        "iva_rate": None,
        "iva_amount": None,
        "notes": "",
    }
    early = derive_purchase_invoice_evidence_id(created_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC), **fields)
    later = derive_purchase_invoice_evidence_id(created_at=datetime(2024, 11, 15, 9, 1, tzinfo=UTC), **fields)

    assert early != later, "the keyless path is deliberately additive; two instants are two records"


def test_a_same_key_readd_with_divergent_content_names_every_changed_field() -> None:
    """The conflict must compare EVERY persisted field, not a subset.

    A no-op that matches on a subset silently drops whatever changed in the
    fields it did not inspect -- an under-declaration wearing an idempotency
    guard's clothes. The close review of this rule's origin campaign caught
    exactly that, on a field the match had omitted.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from ..evidence import PurchaseInvoiceEvidence, _divergent_evidence_fields

    stamp = datetime(2024, 11, 15, 9, 0, tzinfo=UTC)
    prior = PurchaseInvoiceEvidence(
        evidence_id="ev-1",
        bucket_id=_BUCKET,
        source_path="invoice.pdf",
        source_sha256="a" * 64,
        attachment_id="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="ESB12345674",
        invoice_number="F-1",
        invoice_date="2024-11-15",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        notes="original",
        created_at=stamp,
        updated_at=stamp,
    )

    unchanged = _divergent_evidence_fields(
        prior,
        source_sha256="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="ESB12345674",
        invoice_number="F-1",
        invoice_date="2024-11-15",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        notes="original",
    )
    assert unchanged == (), "an identical re-add diverges on nothing"

    # Change two fields far apart in the record, including the notes field a
    # subset-match would be most tempted to skip.
    divergent = _divergent_evidence_fields(
        prior,
        source_sha256="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="ESB12345674",
        invoice_number="F-1",
        invoice_date="2024-11-15",
        taxable_base=Decimal("250.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        notes="corrected",
    )
    assert set(divergent) == {"taxable_base", "notes"}


def test_every_caller_supplied_field_is_covered_by_the_conflict_comparison() -> None:
    """Anti-tautology: the comparison must reach every field a re-add can change.

    Without this the divergence test above passes while the comparison silently
    omits a field, and the omission stays invisible until a real re-add drops a
    real value. The expected set is derived from the record model rather than a
    hand-kept list, so a field added later fails HERE instead of slipping
    through -- which is the failure mode a hand-kept list always eventually has.

    Identity, provenance and lifecycle fields are excluded because the caller
    does not re-supply them on an add; they are outcomes, not inputs.
    """
    import inspect

    from ..evidence import PurchaseInvoiceEvidence, _divergent_evidence_fields

    not_caller_supplied = {
        "evidence_id",
        "bucket_id",
        "source_path",
        "attachment_id",
        "created_at",
        "updated_at",
        "linked_invoice_ids",
        "linked_transaction_ids",
    }
    caller_supplied = set(PurchaseInvoiceEvidence.model_fields) - not_caller_supplied
    source = inspect.getsource(_divergent_evidence_fields)

    missing = sorted(name for name in caller_supplied if f'"{name}"' not in source)
    assert missing == [], f"the conflict comparison must cover every caller-supplied field; missing: {missing}"
