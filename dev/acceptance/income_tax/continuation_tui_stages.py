"""Ordered visible partial handoff, resumption and annual completion stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .continuation_state import continuation_state
from .continuation_storage import annual_schema
from .continuation_tui_observations import assert_tui_partial_readback, export_visible_m130
from .financial_artifacts import validate_annual_artifact
from .financial_edits import apply_annual_edits
from .financial_invoices import capture_invoice, reconcile_invoice
from .financial_lifecycle import m130_expected, parse_m130_artifact, run_lifecycle
from .financial_navigation import create_calendar_work, work_ids_by_period
from .financial_profile import configure_profile
from .financial_transactions import (
    classify_transaction,
    financial_transactions_transaction_row_ids,
    import_transactions,
    transaction_csv,
)
from .installed_tui_child import (
    InstalledTuiChildError,
)
from .scenario import IncomeTaxScenario
from .tui_contracts import ContinuationStateEvidence


async def resume_visible_partial_workflow(
    pilot: Any, scenario: IncomeTaxScenario, scratch: Path, generation: str, year: int
) -> tuple[ContinuationStateEvidence | None, str | None]:
    """Read and independently export the CLI handoff before continuing in the TUI."""
    try:
        works = await assert_tui_partial_readback(pilot=pilot, scenario=scenario, year=year)
        await export_visible_m130(
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
    handoff = continuation_state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    return handoff, None


async def prepare_visible_partial_workflow(
    pilot: Any, scenario: IncomeTaxScenario, scratch: Path, generation: str, year: int
) -> ContinuationStateEvidence:
    """Capture the TUI facts and leave exactly the Q1 partial filing boundary."""
    await configure_profile(pilot, scenario=scenario)
    csv_path = transaction_csv(scenario=scenario, directory=scratch)
    await import_transactions(pilot, csv_path=csv_path)
    rows = await financial_transactions_transaction_row_ids(pilot, scenario=scenario)
    if len(rows) != 8:
        raise InstalledTuiChildError("installed TUI Entries did not expose all eight transactions")
    for item in (*scenario.income, *scenario.expenses):
        await classify_transaction(pilot, transaction_id=rows[item.transaction_id], item=item)
        await capture_invoice(pilot, item=item)
        await reconcile_invoice(pilot, transaction_id=item.transaction_id, invoice_id=item.invoice_id)
    for period in ("1T", "2T", "3T", "4T"):
        await create_calendar_work(pilot, modelo="130", year=year, period=period)
    works = await work_ids_by_period(pilot, year=year)
    q1_export = scratch / f"modelo-130-{year}-1T.boe"
    await run_lifecycle(pilot, export_path=q1_export, work_unit_id=works["1T"])
    parse_m130_artifact(
        path=q1_export,
        year=year,
        period="1T",
        expected=m130_expected(scenario.quarter_oracle[0]),
    )
    handoff = continuation_state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    return handoff


async def complete_visible_workflow(
    pilot: Any, scenario: IncomeTaxScenario, scratch: Path, generation: str, year: int, workspace_root: Path
) -> tuple[ContinuationStateEvidence, dict[str, object]]:
    """Complete the remaining quarters and independently validate the annual export."""
    works = await work_ids_by_period(pilot, year=year)
    for oracle in scenario.quarter_oracle[1:]:
        artifact = scratch / f"modelo-130-{year}-{oracle.period}.boe"
        await run_lifecycle(pilot, export_path=artifact, work_unit_id=works[oracle.period])
        parse_m130_artifact(path=artifact, year=year, period=oracle.period, expected=m130_expected(oracle))
    await create_calendar_work(pilot, modelo="100", year=year, period="0A")
    works = await work_ids_by_period(pilot, year=year)
    await apply_annual_edits(pilot, work_unit_id=works["0A"])
    annual_export = scratch / f"modelo-100-{year}-0A.xml"
    await run_lifecycle(pilot, export_path=annual_export, work_unit_id=works["0A"], calculate=False)
    _values, validation = validate_annual_artifact(
        xml_path=annual_export, xsd_path=annual_schema(workspace_root, year), scenario=scenario
    )
    if validation.get("xsd_valid") is not True:
        raise InstalledTuiChildError("installed TUI Modelo 100 export failed official XSD validation")
    completion = continuation_state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T", "0A"),
        filed=("1T", "2T", "3T", "4T"),
        annual_exported=True,
    )
    return completion, validation
