"""Ordered visible partial handoff, resumption and annual completion stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .continuation_state import _state
from .continuation_storage import _annual_schema
from .continuation_tui_observations import _assert_tui_partial_readback, _export_visible_m130
from .financial_artifacts import _validate_annual_artifact
from .financial_edits import _apply_annual_edits
from .financial_invoices import _capture_invoice, _reconcile_invoice
from .financial_lifecycle import _m130_expected, _parse_m130_artifact, _run_lifecycle
from .financial_navigation import _create_calendar_work, _work_ids_by_period
from .financial_profile import _configure_profile
from .financial_transactions import _classify_transaction, _import_transactions, _transaction_csv, _transaction_row_ids
from .installed_tui_child import (
    InstalledTuiChildError,
)
from .scenario import IncomeTaxScenario
from .tui_contracts import ContinuationStateEvidence


async def _resume_visible_partial_workflow(
    pilot: Any, scenario: IncomeTaxScenario, scratch: Path, generation: str, year: int
) -> tuple[ContinuationStateEvidence | None, str | None]:
    """Read and independently export the CLI handoff before continuing in the TUI."""
    try:
        works = await _assert_tui_partial_readback(pilot=pilot, scenario=scenario, year=year)
        await _export_visible_m130(
            pilot=pilot,
            export_path=scratch / f"modelo-130-{year}-1T-readback.boe",
            work_unit_id=works["1T"],
            year=year,
            period="1T",
        )
    except InstalledTuiChildError as error:
        readback_error = str(error)
        pilot.app.exit()
        return None, readback_error
    except Exception as error:
        readback_error = f"unexpected continuation readback failure: {type(error).__name__}"
        pilot.app.exit()
        return None, readback_error
    handoff = _state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    return handoff, None


async def _prepare_visible_partial_workflow(
    pilot: Any, scenario: IncomeTaxScenario, scratch: Path, generation: str, year: int
) -> ContinuationStateEvidence:
    """Capture the TUI facts and leave exactly the Q1 partial filing boundary."""
    await _configure_profile(pilot, scenario=scenario)
    csv_path = _transaction_csv(scenario=scenario, directory=scratch)
    await _import_transactions(pilot, csv_path=csv_path)
    rows = await _transaction_row_ids(pilot, scenario=scenario)
    if len(rows) != 8:
        raise InstalledTuiChildError("installed TUI Entries did not expose all eight transactions")
    for item in (*scenario.income, *scenario.expenses):
        await _classify_transaction(pilot, transaction_id=rows[item.transaction_id], item=item)
        await _capture_invoice(pilot, item=item)
        await _reconcile_invoice(pilot, transaction_id=item.transaction_id, invoice_id=item.invoice_id)
    for period in ("1T", "2T", "3T", "4T"):
        await _create_calendar_work(pilot, modelo="130", year=year, period=period)
    works = await _work_ids_by_period(pilot, year=year)
    q1_export = scratch / f"modelo-130-{year}-1T.boe"
    await _run_lifecycle(pilot, export_path=q1_export, work_unit_id=works["1T"])
    _parse_m130_artifact(
        path=q1_export,
        year=year,
        period="1T",
        expected=_m130_expected(scenario.quarter_oracle[0]),
    )
    handoff = _state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    return handoff


async def _complete_visible_workflow(
    pilot: Any, scenario: IncomeTaxScenario, scratch: Path, generation: str, year: int, workspace_root: Path
) -> tuple[ContinuationStateEvidence, dict[str, object]]:
    """Complete the remaining quarters and independently validate the annual export."""
    works = await _work_ids_by_period(pilot, year=year)
    for oracle in scenario.quarter_oracle[1:]:
        artifact = scratch / f"modelo-130-{year}-{oracle.period}.boe"
        await _run_lifecycle(pilot, export_path=artifact, work_unit_id=works[oracle.period])
        _parse_m130_artifact(path=artifact, year=year, period=oracle.period, expected=_m130_expected(oracle))
    await _create_calendar_work(pilot, modelo="100", year=year, period="0A")
    works = await _work_ids_by_period(pilot, year=year)
    await _apply_annual_edits(pilot, work_unit_id=works["0A"])
    annual_export = scratch / f"modelo-100-{year}-0A.xml"
    await _run_lifecycle(pilot, export_path=annual_export, work_unit_id=works["0A"], calculate=False)
    _values, validation = _validate_annual_artifact(
        xml_path=annual_export, xsd_path=_annual_schema(workspace_root, year), scenario=scenario
    )
    if validation.get("xsd_valid") is not True:
        raise InstalledTuiChildError("installed TUI Modelo 100 export failed official XSD validation")
    completion = _state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T", "0A"),
        filed=("1T", "2T", "3T", "4T"),
        annual_exported=True,
    )
    return completion, validation
