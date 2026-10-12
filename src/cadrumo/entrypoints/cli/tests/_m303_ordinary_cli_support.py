"""Secure ordinary-2025 Modelo 303 input helpers for real CLI tests.

Every period asks the joint-return election; only the last settlement period of
the year (4T or 12) asks the Modelo 390 exemption and so takes an attestation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ....tests.cli_envelope import unwrap_schema_envelope
from .cli_runner import invoke_cached_cli

_OBSERVED_AT_BY_LAST_PERIOD = {
    "4T": "2025-12-31T12:00:00+00:00",
    "12": "2025-12-31T12:00:00+00:00",
}


def joint_return_options(*, joint_return_elected: bool = True) -> tuple[str, ...]:
    """Return the one explicit answer every Modelo 303 period asks."""
    return ("--joint-return-elected" if joint_return_elected else "--no-joint-return-elected",)


@dataclass(frozen=True)
class OrdinaryM303SecureEvidence:
    """CLI-safe identities returned by the encrypted attestation command."""

    attachment_id: str
    sha256: str

    def calculate_options(self, *, joint_return_elected: bool = True) -> tuple[str, ...]:
        """Return the last-period answers: the joint-return election and the split secure identifiers."""
        return (
            *joint_return_options(joint_return_elected=joint_return_elected),
            "--m303-exonerado-390-attachment-id",
            self.attachment_id,
            "--m303-exonerado-390-sha256",
            self.sha256,
        )


def admit_ordinary_m303_secure_evidence(*, period: Literal["4T", "12"] = "4T") -> OrdinaryM303SecureEvidence:
    """Admit one real 2025 last-period non-applicability attestation."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "attest-m303-exonerado-390",
            "--year",
            "2025",
            "--period",
            period,
            "--observed-at",
            _OBSERVED_AT_BY_LAST_PERIOD[period],
        ]
    )
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    attachment_id = payload["attachment_id"]
    sha256 = payload["sha256"]
    assert isinstance(attachment_id, str) and len(attachment_id) == 64
    assert isinstance(sha256, str) and len(sha256) == 64
    assert attachment_id == sha256
    assert "attachment:" not in result.output
    assert "profile_witness" not in result.output
    return OrdinaryM303SecureEvidence(attachment_id=attachment_id, sha256=sha256)


__all__ = ["OrdinaryM303SecureEvidence", "admit_ordinary_m303_secure_evidence", "joint_return_options"]
