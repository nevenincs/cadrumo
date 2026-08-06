"""Real-behavior tests for the :data:`InvoiceId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_holder
from .._ids import InvoiceId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Holder = single_field_holder("invoice_id", InvoiceId)


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"invoice-payload").hexdigest()
    holder = _Holder.build(digest)
    assert _Holder.value_of(holder) == digest


def test_rejects_noncanonical_digest_shapes() -> None:
    cases: tuple[tuple[str, str], ...] = (
        ("uppercase-hex", hashlib.sha256(b"invoice-payload").hexdigest().upper()),
        ("too-short", "a" * 63),
        ("too-long", "a" * 65),
        ("non-hex", "g" * 64),
    )

    for case_id, raw_id in cases:
        try:
            _Holder.build(raw_id)
        except ValidationError:
            continue
        pytest.fail(f"{case_id}: expected ValidationError")
