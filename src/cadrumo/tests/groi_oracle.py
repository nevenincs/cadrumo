"""AEAT GROI Spanish-ROI verification oracle policy.

GROI is the Spanish-counterparty sibling of the NIF-IVA VIES-proxy surface.
The canonical checker flow owns its behavior; this module declares only the
GROI catalogue identity and read-only endpoint policy.
"""

from __future__ import annotations

from typing import override

from pydantic import AnyUrl

from ..core.config import Settings
from ..domain.calculations.registry.checker_oracle_flow import CheckerDriver, CheckerOperationPlan, CheckerOracle
from ..domain.calculations.registry.ids import OracleId
from ..domain.calculations.registry.live_parity import LiveParityCatalogue, OracleEnvironment, OracleSurfaceKind

GROI_ORACLE_ID: OracleId = "aeat-groi-spanish-roi-checker"


class GroiOracle(CheckerOracle):
    """Policy declaration for AEAT's read-only Spanish ROI checker."""

    surface_label = "GROI"
    expected_blank_message = "GROI expected values must not contain blanks"

    def __init__(self, *, driver: CheckerDriver | None = None) -> None:
        """Construct the oracle, optionally injecting a checker driver for replay."""
        super().__init__(driver=driver)

    @property
    @override
    def oracle_id(self) -> OracleId:
        """Return the stable catalogue identifier for this checker surface."""
        return GROI_ORACLE_ID

    @property
    @override
    def surface_kind(self) -> OracleSurfaceKind:
        """Classify this surface as an EU IVA identifier checker."""
        return "iva_id_check"

    @override
    def _default_operation_plan(self) -> CheckerOperationPlan:
        """Declare the AEAT GROI form endpoint."""
        return CheckerOperationPlan(
            preflight_urls=(AnyUrl(Settings.external_constants().aeat.oracles.groi_check),),
            open_action="open-groi-form",
        )


def register_default(
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> None:
    """Register the GROI policy under the requested environment."""
    catalogue.register(GroiOracle(), environment=environment)


__all__ = ["GROI_ORACLE_ID", "GroiOracle", "register_default"]
