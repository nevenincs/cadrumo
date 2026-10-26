"""Application-owned certificate-health projection contracts.

Real certificate registration, secure source persistence, and PKCS#12 probing
are exercised by the profile-persistence adapter tests. This inward module
keeps the typed health projection rules local to the auth application.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..operator_results import CertificateSourceCheckEntry
from ..probes import ProviderProbeResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("invalid_result", ("", "ok", "OK", "not-a-verdict"))
def test_certificate_source_check_entry_refuses_noncanonical_probe_verdicts(invalid_result: str) -> None:
    """The operator projection cannot widen the closed provider-probe result enum."""
    with pytest.raises(ValidationError, match="result"):
        CertificateSourceCheckEntry(
            name="personal",
            certificate_path="C:/certificates/personal.p12",
            result=invalid_result,
            summary="certificate verdict",
        )


def test_certificate_source_check_entry_preserves_probe_verdict_json_value() -> None:
    """A canonical verdict remains typed in memory and serializes as its wire value."""
    entry = CertificateSourceCheckEntry(
        name="personal",
        certificate_path="C:/certificates/personal.p12",
        result=ProviderProbeResult.OK,
        summary="certificate valid",
    )

    assert entry.result is ProviderProbeResult.OK
    assert entry.model_dump(mode="json")["result"] == ProviderProbeResult.OK.value
