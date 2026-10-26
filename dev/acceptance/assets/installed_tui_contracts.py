"""Value-free activity-asset TUI acceptance receipts and stage identities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type InstalledAssetTuiJourney = Literal[
    "probe",
    "home",
    "profile",
    "profile_ready",
    "ledger",
    "asset_screen",
    "asset_method_lifecycle",
    "asset_readback",
    "asset_cli_readback",
]


class InstalledAssetTuiError(RuntimeError):
    """A public installed-TUI boundary did not reach its expected stage."""

    def __init__(self, message: str, *, stage: str, diagnostic: dict[str, object] | None = None) -> None:
        """Keep one public failed-stage identity and optional safe surface state."""
        super().__init__(message)
        self.stage = stage
        self.diagnostic = diagnostic


@dataclass(frozen=True, slots=True)
class InstalledAssetTuiReceipt:
    """Sanitized stage result from one installed product process."""

    schema_version: str
    status: Literal["running", "proven", "failed"]
    stage: str
    product_origin: str
    product_init_sha256: str
    completed_stages: tuple[str, ...]
    launcher_exit_code: int | None = None
    diagnostic: dict[str, object] | None = None
    assertions: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt without synthetic taxpayer facts."""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "stage": self.stage,
            "product_origin": self.product_origin,
            "product_init_sha256": self.product_init_sha256,
            "completed_stages": self.completed_stages,
            "launcher_exit_code": self.launcher_exit_code,
            "diagnostic": self.diagnostic,
            "assertions": self.assertions,
        }


@dataclass(frozen=True, slots=True)
class _PublicAssetActionTransition:
    """Safe public state observed around one keyboard asset action."""

    button_id: str
    result_before: str
    result_after_activation: str
    button_disabled_before: bool
