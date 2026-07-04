"""Real-behavior tests for the :data:`VerificationReportId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ValidationError

from ....tests.fixtures.identity_holder import single_field_model
from .._ids import VerificationReportId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Holder = single_field_model("verification_report_id", VerificationReportId)


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"verification-report-payload").hexdigest()
    holder = _Holder(verification_report_id=digest)
    assert getattr(holder, "verification_report_id") == digest


def test_rejects_invalid_sha256_digest() -> None:
    for digest in ("A" * 64, "a" * 63, "g" * 64):
        with pytest.raises(ValidationError):
            _Holder(verification_report_id=digest)
