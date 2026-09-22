"""Exercise one asset claim through installed M130/M100 calculation and XML export.

This is deliberately a small companion to the income-tax CLI journey.  It
reuses that journey's installed-process adapter and profile fixture rather
than creating a second acceptance CLI protocol.  The asset facts and the
financial oracle remain specific to AS12.
"""

from __future__ import annotations

import argparse
import json
import secrets
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from dev.acceptance.income_tax.cli_journey import (
    JourneyError,
    command_result,
    ingest_income_fixture,
)
from dev.acceptance.income_tax.scenario import IncomeTaxScenario, build_scenario
from dev.acceptance.income_tax.tui_journey import LocalXsdValidationEvidence, validate_modelo_100_xsd
from dev.acceptance.installed_cli import InstalledCli

_YEAR = 2025
_ASSET_AMOUNT = Decimal("300.00")


@dataclass(frozen=True, slots=True)
class AssetOverlayOracle:
    """Independent control and exactly-one-claim overlay expectations."""

    control: IncomeTaxScenario
    m130_q4_control_expenses: str
    m130_q4_asset_expenses: str
    m100_control_total_expenses: str
    m100_asset_total_expenses: str
    m100_control_material: str = "0.00"
    m100_asset_material: str = "300.00"
    m100_intangible: str = "0.00"


def _asset_overlay_oracle() -> AssetOverlayOracle:
    """Overlay one €300 claim on the established four-quarter income fixture."""
    control = build_scenario(_YEAR)
    q4 = control.quarter_oracle[-1]
    return AssetOverlayOracle(
        control=control,
        m130_q4_control_expenses=_money(q4.cumulative_expenses),
        m130_q4_asset_expenses=_money(q4.cumulative_expenses + _ASSET_AMOUNT),
        m100_control_total_expenses=_money(control.annual_oracle.deductible_expenses),
        m100_asset_total_expenses=_money(control.annual_oracle.deductible_expenses + _ASSET_AMOUNT),
    )


@dataclass(frozen=True, slots=True)
class AssetExportEvidence:
    """Value-bearing evidence is limited to the synthetic asset oracle."""

    executable: str
    authority_root: str
    storage_root: str
    asset_id: str
    claim_id: str
    forecast_amount: str
    m130_q4_income: str
    m130_q4_expenses: str
    m100_activity_income: str
    m100_material_amortization: str
    m100_intangible_amortization: str
    export_path: str
    xsd_validation: LocalXsdValidationEvidence

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt."""
        return cast("dict[str, object]", asdict(self))


def _asset_revision_json() -> str:
    """Return the minimal primary-purchase shape the accepted contract supports."""
    return json.dumps(
        {
            "asset_id": "acceptance-low-value-material-2025",
            "revision_number": 1,
            "acquisition": {
                "observed_transaction_id": "a" * 64,
                "invoice_evidence_id": "synthetic-new-material-invoice",
                "evidence_fingerprint": "b" * 64,
            },
            "acquisition_shape": "primary_purchase",
            "asset_kind": "material",
            "basis": {
                "stage": "business_allocated",
                "basis_amount": "300.00",
                "prior_allocation_provenance": "synthetic acceptance allocation",
            },
            "in_service_date": "2025-01-01",
            "opening_history": {"status": "known", "accumulated_amount": "0.00"},
        },
        separators=(",", ":"),
    )


def _selection_json() -> str:
    """Request the published low-value branch with explicit taxpayer evidence."""
    return json.dumps(
        {
            "regime": "normal",
            "asset_kind": "material",
            "authority_class_key": "mobiliario",
            "method": "low_value_free",
            "free_depreciation_election": {
                "election_reference": "synthetic-explicit-low-value-election",
                "new_material_evidence_reference": "synthetic-new-material-invoice",
                "unit_acquisition_value": "300.00",
                "requested_amount": "300.00",
            },
        },
        separators=(",", ":"),
    )


def _money(value: object) -> str:
    return f"{Decimal(str(value)):.2f}"


def _m130_work(cli: InstalledCli, *, period: str) -> str:
    created = command_result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "130",
                "--year",
                str(_YEAR),
                "--period",
                period,
                "--revision",
                "2019-y-siguientes",
                "--by",
                "assets-acceptance",
            )
        )
    )
    return str(created["work_unit_id"])


def _calculate_and_file_m130(
    cli: InstalledCli,
    *,
    control_income: str,
    control_expenses: str,
    period: str,
    asset_expense_delta: str = "0.00",
) -> tuple[str, str]:
    work_id = _m130_work(cli, period=period)
    calculation = command_result(cli.run(("app", "modelo", "work", "calculate", work_id, "--by", "assets-acceptance")))
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError("Modelo 130 returned no casilla map")
    typed_values = cast("dict[str, object]", values)
    income_value = typed_values.get("01")
    expense_value = typed_values.get("02")
    if income_value is None or expense_value is None:
        raise JourneyError("Modelo 130 returned no income/expense amounts")
    income = _money(income_value)
    expenses = _money(expense_value)
    expected_expenses = _money(Decimal(control_expenses) + Decimal(asset_expense_delta))
    if income != control_income or expenses != expected_expenses:
        raise JourneyError(
            f"Modelo 130 {period} independent totals mismatch: "
            f"income={income} (expected {control_income}), expenses={expenses} (expected {expected_expenses})"
        )
    revision_id = str(calculation["calculation_revision_id"])
    verified = command_result(cli.run(("app", "modelo", "work", "verify", revision_id, "--by", "assets-acceptance")))
    if verified.get("granted_verificado_completo") is not True:
        raise JourneyError(f"Modelo 130 {period} did not verify complete")
    cli.run(
        (
            "app",
            "modelo",
            "work",
            "file",
            revision_id,
            "--by",
            "assets-acceptance",
            "--notes",
            "Synthetic local pending filing only; not sent to AEAT",
        )
    )
    return income, expenses


def _calculate_export_m100(
    cli: InstalledCli, *, oracle: AssetOverlayOracle, output_dir: Path, report_stage: Callable[[str], None]
) -> tuple[str, str, str, Path]:
    report_stage("m100.create")
    created = command_result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "100",
                "--year",
                str(_YEAR),
                "--period",
                "0A",
                "--revision",
                str(_YEAR),
                "--by",
                "assets-acceptance",
            )
        )
    )
    work_id = str(created["work_unit_id"])
    report_stage("m100.calculate")
    calculation = command_result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "calculate",
                work_id,
                "--casilla",
                "0001=declarante",
                "--casilla",
                "0165=declarante",
                "--casilla",
                "0166=A05",
                "--binding",
                "renta-modelo-100-estimacion-directa-es-normal=1",
                "--binding",
                "renta-certificado-trabajo-retenciones=0",
                "--by",
                "assets-acceptance",
            )
        )
    )
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError("Modelo 100 returned no casilla map")
    typed_values = cast("dict[str, object]", values)
    income_value = typed_values.get("0171")
    ordinary_expense_value = typed_values.get("0218")
    material_value = typed_values.get("0208")
    intangible_value = typed_values.get("0227")
    if income_value is None or ordinary_expense_value is None or material_value is None or intangible_value is None:
        raise JourneyError("Modelo 100 returned no ordinary-income/asset destination values")
    income = _money(income_value)
    ordinary_expenses = _money(ordinary_expense_value)
    material = _money(material_value)
    intangible = _money(intangible_value)
    expected_income = _money(oracle.control.annual_oracle.activity_income)
    expected_ordinary_expenses = oracle.m100_asset_total_expenses
    if (
        income != expected_income
        or ordinary_expenses != expected_ordinary_expenses
        or material != oracle.m100_asset_material
        or intangible != oracle.m100_intangible
    ):
        raise JourneyError(
            "Modelo 100 total-expense/material-destination composition mismatch: "
            f"income={income}, ordinary_expenses={ordinary_expenses}, material={material}, intangible={intangible}"
        )
    # 0218 is the composed total-expense field; 0208 separately classifies the
    # same one effective material claim. This is a destination projection, not
    # a second basis-consuming deduction.
    revision_id = str(calculation["calculation_revision_id"])
    report_stage("m100.verify")
    verified = command_result(cli.run(("app", "modelo", "work", "verify", revision_id, "--by", "assets-acceptance")))
    if verified.get("granted_verificado_completo") is not True:
        raise JourneyError("Modelo 100 did not verify complete")
    target = output_dir / "modelo-100-2025-asset.xml"
    report_stage("m100.export")
    cli.run(("app", "modelo", "export", work_id, "--output", str(target), "--by", "assets-acceptance"))
    if not target.is_file() or target.stat().st_size == 0:
        raise JourneyError("Modelo 100 export did not write an XML artifact")
    return income, material, intangible, target


def run_asset_export_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    output_dir: Path,
    xsd_path: Path,
    report_stage: Callable[[str], None] = lambda _stage: None,
) -> AssetExportEvidence:
    """Run the supported asset claim to M130/M100/export chain in one new store."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise JourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    cli = InstalledCli(
        executable, storage_root=storage_root, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
    )
    report_stage("profile.create")
    cli.create_profile(year=_YEAR)
    oracle = _asset_overlay_oracle()
    report_stage("ledger.ingest_control")
    ingest_income_fixture(cli, year=_YEAR)
    report_stage("asset.create")
    created = command_result(cli.run(("app", "ledger", "actividad-asset", "create", _asset_revision_json())))
    asset_id = str(created["revisions"][0]["asset_id"])
    report_stage("asset.forecast")
    forecast = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "actividad-asset",
                "forecast",
                asset_id,
                "--selection-json",
                _selection_json(),
                "--covered-from",
                "2025-01-01",
                "--covered-until",
                "2026-01-01",
            )
        )
    )
    if _money(forecast.get("amount")) != "300.00":
        raise JourneyError("published low-value authority did not produce the EUR 300 charge")
    report_stage("asset.claim")
    claim = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "actividad-asset",
                "claim",
                json.dumps(forecast, separators=(",", ":")),
                "--creating-operation",
                "assets-acceptance.record-claim",
            )
        )
    )
    claim_id = str(claim["claim"]["claim_id"])
    report_stage("asset.filing_handoff")
    handoff = command_result(
        cli.run(("app", "ledger", "actividad-asset", "filing-handoff", "--tax-year", "2025", "--m130-period", "4T"))
    )
    material_m100 = handoff.get("material_m100")
    material_m130 = handoff.get("material_m130")
    if not isinstance(material_m100, dict) or not isinstance(material_m130, dict):
        raise JourneyError("asset filing handoff did not return material claim projections")
    m100_projection = cast("dict[str, object]", material_m100)
    m130_projection = cast("dict[str, object]", material_m130)
    m100_amount = m100_projection.get("amount")
    m130_amount = m130_projection.get("amount")
    if m100_amount is None or m130_amount is None:
        raise JourneyError("asset filing handoff did not return material claim amounts")
    if _money(m100_amount) != "300.00" or _money(m130_amount) != "300.00":
        raise JourneyError("asset filing handoff did not preserve the single effective claim")
    if m100_projection.get("claim_ids") != [claim_id] or m130_projection.get("claim_ids") != [claim_id]:
        raise JourneyError("asset filing handoff did not reference the recorded claim exactly once")
    for control_quarter in oracle.control.quarter_oracle[:-1]:
        report_stage(f"m130.{control_quarter.period}")
        _calculate_and_file_m130(
            cli,
            period=control_quarter.period,
            control_income=_money(control_quarter.cumulative_income),
            control_expenses=_money(control_quarter.cumulative_expenses),
        )
    control_q4 = oracle.control.quarter_oracle[-1]
    report_stage("m130.4T")
    q4_income, q4_expenses = _calculate_and_file_m130(
        cli,
        period=control_q4.period,
        control_income=_money(control_q4.cumulative_income),
        control_expenses=oracle.m130_q4_control_expenses,
        asset_expense_delta=_money(_ASSET_AMOUNT),
    )
    annual_income, material, intangible, xml_path = _calculate_export_m100(
        cli, oracle=oracle, output_dir=output_dir, report_stage=report_stage
    )
    report_stage("m100.xsd_validate")
    validation = validate_modelo_100_xsd(xml_path=xml_path, xsd_path=xsd_path)
    if not validation.xsd_valid:
        raise JourneyError(f"Modelo 100 XML failed local official XSD validation: {validation.error_identities}")
    report_stage("completed")
    return AssetExportEvidence(
        executable=str(cli.executable),
        authority_root=str(cli.authority_root),
        storage_root=str(cli.storage_root),
        asset_id=asset_id,
        claim_id=claim_id,
        forecast_amount="300.00",
        m130_q4_income=q4_income,
        m130_q4_expenses=q4_expenses,
        m100_activity_income=annual_income,
        m100_material_amortization=material,
        m100_intangible_amortization=intangible,
        export_path=str(xml_path),
        xsd_validation=validation,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--xsd", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--stage-receipt", required=True, type=Path)
    return parser


def _write_stage_receipt(path: Path, stage: str) -> None:
    """Persist the last entered bounded stage for a supervised installed run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stage": stage}, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one asset export journey and save a compact receipt."""
    args = _parser().parse_args(argv)
    _write_stage_receipt(args.stage_receipt, "started")
    evidence = run_asset_export_journey(
        executable=args.cli,
        authority_root=args.authority_root,
        storage_root=args.storage_root,
        output_dir=args.output_dir,
        xsd_path=args.xsd,
        report_stage=lambda stage: _write_stage_receipt(args.stage_receipt, stage),
    )
    rendered = json.dumps(evidence.to_dict(), indent=2, sort_keys=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(f"{rendered}\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover - module execution wrapper
    raise SystemExit(main())
