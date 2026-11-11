"""Secure ordinary Modelo 303 input helpers for real CLI tests.

Every period asks the joint-return election; only the last settlement period of
the year (4T or 12) asks the Modelo 390 exemption and so takes an attestation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from .cli_fixture_worlds import invoke_joined_cli


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


def admit_ordinary_m303_secure_evidence(
    *, filing_year: int, period: Literal["4T", "12"] = "4T"
) -> OrdinaryM303SecureEvidence:
    """Admit one real last-period non-applicability attestation for the caller's ``filing_year``.

    The attestation is observed at the close of that year's last settlement period, so
    the caller names the year of the return it calculates and that period must already
    have ended: an observation dated in the future is refused, as it is for an operator,
    and an attestation for another year answers nothing.
    """
    observed_at = datetime(filing_year, 12, 31, 12, tzinfo=UTC).isoformat()
    result = invoke_joined_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "attest-m303-exonerado-390",
            "--year",
            str(filing_year),
            "--period",
            period,
            "--observed-at",
            observed_at,
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
