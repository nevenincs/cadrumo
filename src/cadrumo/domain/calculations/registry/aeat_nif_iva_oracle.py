"""AEAT NIF-IVA verification oracle policy.

This surface verifies other-EU IVA identifiers through AEAT's VIES-proxy
form.  Its executable checker behavior, observation model, driver contract,
and deterministic replay all live in :mod:`._checker_oracle_flow`.
"""

from __future__ import annotations

from typing import override

from pydantic import AnyUrl

from ....core.config import Settings
from .checker_oracle_flow import CheckerDriver, CheckerOperationPlan, CheckerOracle
from .ids import OracleId
from .live_parity import LiveParityCatalogue, OracleEnvironment, OracleSurfaceKind

ORACLE_ID: OracleId = "aeat-nif-iva-checker"


class AeatNifIvaCheckerOracle(CheckerOracle):
    """Policy declaration for AEAT's read-only other-EU IVA checker."""

    surface_label = "AEAT NIF-IVA"
    expected_blank_message = "AEAT NIF-IVA expected values must not contain blanks"

    def __init__(self, *, driver: CheckerDriver | None = None) -> None:
        """Construct the oracle, optionally injecting a checker driver for replay."""
        super().__init__(driver=driver)

    @property
    @override
    def oracle_id(self) -> OracleId:
        """Return the stable catalogue identifier for this checker surface."""
        return ORACLE_ID

    @property
    @override
    def surface_kind(self) -> OracleSurfaceKind:
        """Classify this surface as an EU IVA identifier checker."""
        return "iva_id_check"

    @override
    def _default_operation_plan(self) -> CheckerOperationPlan:
        """Declare the AEAT session-entry and NIF-IVA form endpoints."""
        constants = Settings.external_constants()
        return CheckerOperationPlan(
            preflight_urls=(
                AnyUrl(f"{constants.aeat.domains.sede}{constants.aeat.help_pages.nif_iva_landing}"),
                AnyUrl(constants.aeat.oracles.nif_iva_verification),
            ),
            open_action="open-nif-iva-form",
        )


def register_default(
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> None:
    """Register the AEAT NIF-IVA policy under the requested environment."""
    catalogue.register(AeatNifIvaCheckerOracle(), environment=environment)


__all__ = ["ORACLE_ID", "AeatNifIvaCheckerOracle", "register_default"]
