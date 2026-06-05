"""Real-behavior tests for the :data:`InvoiceId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ValidationError

from .._ids import InvoiceId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Holder(BaseModel):
    invoice_id: InvoiceId


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"invoice-payload").hexdigest()
    assert _Holder(invoice_id=digest).invoice_id == digest


def test_rejects_uppercase_hex() -> None:
    digest = hashlib.sha256(b"invoice-payload").hexdigest().upper()
    with pytest.raises(ValidationError):
        _Holder(invoice_id=digest)


def test_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        _Holder(invoice_id="a" * 63)
    with pytest.raises(ValidationError):
        _Holder(invoice_id="a" * 65)


def test_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        _Holder(invoice_id="g" * 64)
