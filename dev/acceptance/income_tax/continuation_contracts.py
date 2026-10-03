"""Value-free installed income-tax continuation contracts and refusal identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, cast

_SCHEMA_VERSION = "income-01-installed-continuations-v1"


_Direction = Literal["cli_to_tui", "tui_to_cli"]


class InstalledContinuationError(RuntimeError):
    """Raised when either installed frontend cannot prove its continuation."""


@dataclass(frozen=True, slots=True)
class ContinuationPathReceipt:
    """Sanitized result for one ordered installed frontend continuation."""

    direction: _Direction
    status: Literal["proven"]
    year: int
    product_origin: str
    product_init_sha256: str
    handoff_state_sha256: str
    resumed_state_sha256: str
    completion_state_sha256: str
    transactions: int
    invoices: int
    links: int
    locally_filed_periods: tuple[str, ...]
    annual_xsd_valid: bool
    annual_xsd_error_count: int
    oracle_value_fingerprint: str
    unexercised: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a receipt with no credentials or financial values."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class InstalledContinuationEvidence:
    """Receipt for both independently isolated continuation directions."""

    schema_version: str
    status: Literal["proven"]
    paths: tuple[ContinuationPathReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe outer receipt."""
        return cast("dict[str, object]", asdict(self))
