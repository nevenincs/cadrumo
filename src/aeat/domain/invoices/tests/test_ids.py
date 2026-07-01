"""Real-behavior tests for the :data:`InvoiceId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model
from .._ids import InvoiceId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Holder = single_field_model("invoice_id", InvoiceId)


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"invoice-payload").hexdigest()
    assert _Holder(invoice_id=digest).invoice_id == digest


@pytest.mark.parametrize(
    "raw_id",
    [
        hashlib.sha256(b"invoice-payload").hexdigest().upper(),
        "a" * 63,
        "a" * 65,
        "g" * 64,
    ],
    ids=("uppercase-hex", "too-short", "too-long", "non-hex"),
)
def test_rejects_noncanonical_digest_shapes(raw_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder(invoice_id=raw_id)
