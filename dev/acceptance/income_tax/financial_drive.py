"""Ordered installed income-tax financial capture and lifecycle observation stages."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from cadrumo.core.hashing import sha256_file

from .financial_artifacts import validate_annual_artifact
from .financial_edits import apply_annual_edits
from .financial_invoices import capture_invoice, reconcile_invoice
from .financial_lifecycle import m130_expected, parse_m130_artifact, run_lifecycle
from .financial_navigation import create_calendar_work, work_ids_by_period
from .financial_profile import configure_profile
from .financial_progress import record_stage
from .financial_transactions import (
    classify_transaction,
    financial_transactions_transaction_row_ids,
    import_transactions,
)
from .installed_tui_child import (
    InstalledTuiChildError,
)
from .scenario import IncomeTaxScenario

if TYPE_CHECKING:
    pass


async def _capture_and_reconcile_income_facts(pilot: Any, scenario: IncomeTaxScenario, scratch: Path) -> None:
    """Capture and reconcile income facts."""
    record_stage(scratch, "entries")
    transaction_row_ids = await financial_transactions_transaction_row_ids(pilot, scenario=scenario)
    if len(transaction_row_ids) != len(scenario.income) + len(scenario.expenses):
        raise InstalledTuiChildError("installed Entries count did not match the imported scenario")
    for index, item in enumerate((*scenario.income, *scenario.expenses), start=1):
        record_stage(scratch, f"classify-{index}")
        await classify_transaction(
            pilot,
            transaction_id=transaction_row_ids[item.transaction_id],
            item=item,
        )
    for index, item in enumerate((*scenario.income, *scenario.expenses), start=1):
        record_stage(scratch, f"invoice-{index}")
        await capture_invoice(pilot, item=item)
    for index, item in enumerate((*scenario.income, *scenario.expenses), start=1):
        record_stage(scratch, f"reconcile-{index}")
        await reconcile_invoice(pilot, transaction_id=item.transaction_id, invoice_id=item.invoice_id)


async def _observe_quarterly_financial_lifecycle(
    pilot: Any,
    scenario: IncomeTaxScenario,
    scratch: Path,
    year: int,
    work_unit_ids: dict[str, str],
    operations: list[str],
    financial_values: dict[str, str],
    artifact_hashes: list[str],
) -> None:
    """Observe quarterly financial lifecycle."""
    for oracle in scenario.quarter_oracle:
        record_stage(scratch, f"quarter-{oracle.period}")
        export_path = scratch / f"modelo-130-{year}-{oracle.period}.boe"
        expected = m130_expected(oracle)
        completed = await run_lifecycle(
            pilot,
            export_path=export_path,
            work_unit_id=work_unit_ids[oracle.period],
        )
        operations.extend(completed)
        observed = parse_m130_artifact(
            path=export_path,
            year=year,
            period=oracle.period,
            expected=expected,
        )
        financial_values.update({f"130.{oracle.period}.{key}": value for key, value in observed.items()})
        artifact_hashes.append(sha256_file(export_path))


async def _observe_annual_financial_lifecycle(
    pilot: Any,
    scenario: IncomeTaxScenario,
    scratch: Path,
    year: int,
    work_unit_ids: dict[str, str],
    operations: list[str],
    financial_values: dict[str, str],
    artifact_hashes: list[str],
    annual_xsd_validation: dict[str, object],
    workspace_root: Path,
) -> None:
    """Observe annual financial lifecycle."""
    record_stage(scratch, "annual-calendar")
    await create_calendar_work(pilot, modelo="100", year=year, period="0A")
    annual_ids = await work_ids_by_period(pilot, year=year)
    annual_work_id = annual_ids.get("0A")
    if annual_work_id is None:
        raise InstalledTuiChildError("calendar creation did not expose annual Modelo 100 work")
    work_unit_ids["0A"] = annual_work_id
    record_stage(scratch, "annual-edit")
    await apply_annual_edits(pilot, work_unit_id=annual_work_id)
    operations.append("modelo.edit.apply")
    annual_export = scratch / f"modelo-100-{year}-0A.xml"
    record_stage(scratch, "annual-lifecycle")
    operations.extend(
        await run_lifecycle(pilot, export_path=annual_export, work_unit_id=annual_work_id, calculate=False)
    )
    schema_candidates = tuple(
        (workspace_root / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files").glob(
            f"*-100-esquema-xsd-ejercicio-{year}-*.xsd"
        )
    )
    if len(schema_candidates) != 1:
        raise InstalledTuiChildError("the selected annual revision has no unambiguous official XSD")
    record_stage(scratch, "annual-validation")
    annual_values, validation = validate_annual_artifact(
        xml_path=annual_export, xsd_path=schema_candidates[0], scenario=scenario
    )
    financial_values.update({f"100.0A.{key}": value for key, value in annual_values.items()})
    annual_xsd_validation.update(validation)
    artifact_hashes.append(sha256_file(annual_export))


async def drive_financial_journey(
    pilot: Any,
    scenario: IncomeTaxScenario,
    scratch: Path,
    year: int,
    csv_path: Path,
    work_unit_ids: dict[str, str],
    operations: list[str],
    financial_values: dict[str, str],
    artifact_hashes: list[str],
    annual_xsd_validation: dict[str, object],
    workspace_root: Path,
) -> None:
    """Drive ordered visible setup, capture and lifecycle stages over caller-held observations."""
    record_stage(scratch, "profile")
    await configure_profile(pilot, scenario=scenario)
    record_stage(scratch, "calendar-quarterly")
    for period in ("1T", "2T", "3T", "4T"):
        await create_calendar_work(pilot, modelo="130", year=year, period=period)
    record_stage(scratch, "import")
    await import_transactions(pilot, csv_path=csv_path)
    await _capture_and_reconcile_income_facts(pilot, scenario, scratch)
    work_unit_ids.update(await work_ids_by_period(pilot, year=year))
    if set(work_unit_ids) != {"1T", "2T", "3T", "4T"}:
        raise InstalledTuiChildError("calendar creation did not expose all four quarterly declaration rows")
    await _observe_quarterly_financial_lifecycle(
        pilot, scenario, scratch, year, work_unit_ids, operations, financial_values, artifact_hashes
    )
    await _observe_annual_financial_lifecycle(
        pilot,
        scenario,
        scratch,
        year,
        work_unit_ids,
        operations,
        financial_values,
        artifact_hashes,
        annual_xsd_validation,
        workspace_root,
    )
    pilot.app.exit()
