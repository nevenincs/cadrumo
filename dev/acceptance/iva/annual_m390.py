"""Installed annual Modelo 390 calculation and verification observations."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from dev.acceptance.installed_cli import InstalledCli

from .annual_contracts import ANNUAL_PERIOD
from .annual_projection import decimal_casilla
from .cli_journey import (
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    required_id,
    required_text,
    result,
    run,
)
from .filing_year import IvaJourneyYear


def calculate_and_verify_m390(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, journey_year: IvaJourneyYear
) -> tuple[str, str, str, str, dict[str, Decimal]]:
    created = result(
        run(
            cli,
            receipts,
            artifact,
            (
                *("app", "modelo", "work", "create", "--modelo", "390"),
                *("--year", str(journey_year.year), "--period", ANNUAL_PERIOD),
            ),
            result_keys=("work_unit_id",),
        )
    )
    work_id = required_id(created, "work_unit_id")
    calculated = result(
        run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "calculate", work_id),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError("Modelo 390 calculate did not confirm a saved revision")
    revision_id = required_id(calculated, "calculation_revision_id")
    values = {
        "devengada": decimal_casilla(calculated, "iva.anual.cuota-devengada-total"),
        "deducible": decimal_casilla(calculated, "iva.anual.cuota-deducible-total"),
        "resultado": decimal_casilla(calculated, "iva.anual.resultado-regimen-general"),
        "reconciled_devengada": decimal_casilla(calculated, "iva.anual.reconciliacion.devengada-303"),
        "reconciled_deducible": decimal_casilla(calculated, "iva.anual.reconciliacion.deducible-303"),
        "reconciled_resultado": decimal_casilla(calculated, "iva.anual.reconciliacion.resultado-303"),
    }
    expected = {
        "devengada": Decimal("1470.00"),
        "deducible": Decimal("105.00"),
        "resultado": Decimal("1365.00"),
        "reconciled_devengada": Decimal("1470.00"),
        "reconciled_deducible": Decimal("105.00"),
        "reconciled_resultado": Decimal("1365.00"),
    }
    if values != expected:
        raise IvaCliJourneyError(f"independent Modelo 390 oracle mismatch: expected {expected}, got {values}")
    verified = result(
        run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    report_id, status = (
        required_id(verified, "verification_report_id"),
        required_text(verified, "completeness_status"),
    )
    if (
        verified.get("calculation_revision_id") != revision_id
        or verified.get("granted_verificado_completo") is not True
    ):
        raise IvaCliJourneyError("Modelo 390 verify did not prove the annual reconciliation complete")
    return work_id, revision_id, report_id, status, values
