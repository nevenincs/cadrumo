"""Installed CLI continuation readback and ordered completion observations."""

from __future__ import annotations

from pathlib import Path
from typing import TypeGuard

from dev.acceptance.installed_cli import InstalledCli

from .cli_journey import (
    calculate_m100,
    calculate_m130_work,
    command_result,
    verify_and_file_m130,
)
from .continuation_contracts import InstalledContinuationError
from .continuation_state import _state
from .continuation_storage import _annual_schema
from .financial_artifacts import _validate_annual_artifact
from .financial_lifecycle import _m130_expected, _parse_m130_artifact
from .scenario import build_scenario
from .tui_contracts import ContinuationStateEvidence


def _require_public_invoice_links(invoices: dict[str, object]) -> None:
    """Require public invoice links."""
    invoice_rows = invoices.get("rows")
    if (
        invoices.get("count") != 8
        or not isinstance(invoice_rows, list)
        or any(
            not isinstance(row, dict)
            or not isinstance(row.get("linked_transaction_ids"), list)
            or len(row["linked_transaction_ids"]) != 1
            for row in invoice_rows
        )
    ):
        raise InstalledContinuationError("installed CLI invoice list did not publicly reproduce eight invoice links")


def _is_requested_quarter_work(unit: object, year: int) -> TypeGuard[dict[str, object]]:
    """Select only the public quarterly work rows for the requested filing year."""
    return bool(isinstance(unit, dict) and unit.get("modelo") == "130" and unit.get("filing_year") == year)


def _public_work_period(unit: dict[str, object], year: int, selected: dict[str, dict[str, object]]) -> str:
    """Refuse ambiguous public period and work identities before adding the row."""
    period_value = unit.get("period")
    period = (
        period_value.get("code") if isinstance(period_value, dict) and period_value.get("filing_year") == year else None
    )
    work_id = unit.get("work_unit_id")
    if not isinstance(period, str) or not isinstance(work_id, str) or not work_id or period in selected:
        raise InstalledContinuationError("installed CLI work list has ambiguous Modelo 130 public work identities")
    return period


def _public_work_units(cli: InstalledCli, *, year: int) -> dict[str, dict[str, object]]:
    """Read the four partial work units from the installed CLI list surface."""
    listing = command_result(cli.run(("app", "modelo", "work", "list")))
    units = listing.get("work_units")
    if not isinstance(units, list):
        raise InstalledContinuationError("installed CLI work list returned no public work-unit collection")
    selected: dict[str, dict[str, object]] = {}
    for unit in units:
        if not _is_requested_quarter_work(unit, year):
            continue
        period = _public_work_period(unit, year, selected)
        selected[period] = unit
    if set(selected) != {"1T", "2T", "3T", "4T"}:
        raise InstalledContinuationError("installed CLI work list did not publicly reproduce the four-unit handoff")
    return selected


def _cli_public_readback(cli: InstalledCli, *, generation: str, year: int) -> ContinuationStateEvidence:
    ledger = command_result(cli.run(("app", "ledger", "list")))
    rows = ledger.get("rows")
    if not isinstance(rows, list) or len(rows) != 8:
        raise InstalledContinuationError("installed CLI ledger list did not publicly reproduce eight transactions")
    invoices = command_result(cli.run(("app", "ledger", "invoice", "list")))
    _require_public_invoice_links(invoices)
    units = _public_work_units(cli, year=year)
    q1 = units["1T"]
    if not isinstance(q1.get("filed_calculation_revision_id"), str) or not isinstance(
        q1.get("current_filing_record_id"), str
    ):
        raise InstalledContinuationError("installed CLI work list did not publicly prove the Q1 local filing")
    periods = tuple(sorted(units))
    return _state(generation=generation, year=year, periods=periods, filed=("1T",), annual_exported=False)


def _cli_complete(
    *, cli: InstalledCli, workspace_root: Path, output_dir: Path, generation: str, year: int
) -> tuple[ContinuationStateEvidence, dict[str, object]]:
    existing_units = _public_work_units(cli, year=year)
    for oracle in build_scenario(year).quarter_oracle[1:]:
        work_id = str(existing_units[oracle.period]["work_unit_id"])
        _actual, revision = calculate_m130_work(cli, work_id=work_id, oracle=oracle)
        verify_and_file_m130(cli, revision_id=revision, period=oracle.period)
    annual = calculate_m100(cli, year=year, output_dir=output_dir)
    if annual.get("export_execution") != "proven":
        diagnostic = annual.get("diagnostic_code")
        raise InstalledContinuationError(
            "installed CLI did not export Modelo 100 for XSD validation"
            + (f"; diagnostic_code={diagnostic}" if isinstance(diagnostic, str) else "")
        )
    xml_path = output_dir / f"modelo-100-{year}-0A.xml"
    _values, validation = _validate_annual_artifact(
        xml_path=xml_path, xsd_path=_annual_schema(workspace_root, year), scenario=build_scenario(year)
    )
    if validation.get("xsd_valid") is not True:
        raise InstalledContinuationError("installed CLI Modelo 100 export failed official XSD validation")
    return _state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T", "0A"),
        filed=("1T", "2T", "3T", "4T"),
        annual_exported=True,
    ), validation


def _assert_cli_q1_public_artifact(*, cli: InstalledCli, output_dir: Path, year: int) -> None:
    """Export and independently compare the already-filed Q1 public artifact."""
    q1 = _public_work_units(cli, year=year)["1T"]
    work_id = q1["work_unit_id"]
    if not isinstance(work_id, str):
        raise InstalledContinuationError("installed CLI Q1 work has no public work identity")
    artifact = output_dir / f"modelo-130-{year}-1T-readback.boe"
    cli.run(("app", "modelo", "export", work_id, "--output", str(artifact), "--by", "income-acceptance"))
    _parse_m130_artifact(
        path=artifact,
        year=year,
        period="1T",
        expected=_m130_expected(build_scenario(year).quarter_oracle[0]),
    )
