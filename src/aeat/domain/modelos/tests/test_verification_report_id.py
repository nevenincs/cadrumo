"""Real-behavior tests for the :data:`VerificationReportId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model
from .._ids import VerificationReportId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Holder = single_field_model("verification_report_id", VerificationReportId)


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"verification-report-payload").hexdigest()
    assert _Holder(verification_report_id=digest).verification_report_id == digest


@pytest.mark.parametrize(
    "digest",
    (
        pytest.param("A" * 64, id="uppercase-hex"),
        pytest.param("a" * 63, id="wrong-length"),
        pytest.param("g" * 64, id="non-hex-characters"),
    ),
)
def test_rejects_invalid_sha256_digest(digest: str) -> None:
    with pytest.raises(ValidationError):
        _Holder(verification_report_id=digest)
