"""Real-behavior tests for the :data:`VerificationReportId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ValidationError

from .._ids import VerificationReportId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Holder(BaseModel):
    verification_report_id: VerificationReportId


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"verification-report-payload").hexdigest()
    assert _Holder(verification_report_id=digest).verification_report_id == digest


def test_rejects_uppercase_hex() -> None:
    with pytest.raises(ValidationError):
        _Holder(verification_report_id="A" * 64)


def test_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        _Holder(verification_report_id="a" * 63)


def test_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        _Holder(verification_report_id="g" * 64)
