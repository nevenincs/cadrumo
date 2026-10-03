"""Run the admitted installed income-tax financial journey and retain value-free receipts."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .financial_contracts import _SCHEMA_VERSION, FinancialChildReceipt
from .financial_drive import _drive_financial_journey
from .financial_navigation import _open_destination, _open_work, _work_ids_by_period
from .financial_transactions import _transaction_csv, _transaction_row_ids
from .installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    register_profile_through_installed_tui,
    select_public_data_table_row,
    write_installed_tui_failure_receipt,
)
from .scenario import build_scenario
from .tui_continuation_evidence import canonical_financial_value_fingerprint
from .tui_navigation import (
    wait_for_workbench,
)

if TYPE_CHECKING:
    pass


def run_financial_child(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    year: int,
    scratch: Path,
) -> FinancialChildReceipt:
    """Run visible setup, capture, lifecycle actions, then a fresh-session readback."""
    scenario = build_scenario(year)
    product = installed_product_evidence(workspace_root=workspace_root)
    csv_path = _transaction_csv(scenario=scenario, directory=scratch)
    work_unit_ids: dict[str, str] = {}
    operations: list[str] = []
    financial_values: dict[str, str] = {}
    artifact_hashes: list[str] = []
    annual_xsd_validation: dict[str, object] = {}

    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition
    from cadrumo.entrypoints.tui.launcher import main

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    async def drive(pilot: Any) -> None:
        await _drive_financial_journey(
            pilot,
            scenario,
            scratch,
            year,
            csv_path,
            work_unit_ids,
            operations,
            financial_values,
            artifact_hashes,
            annual_xsd_validation,
            workspace_root,
        )

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive),
    )
    if exit_code != 0:
        raise InstalledTuiChildError(f"installed financial launcher returned {exit_code}")
    if set(work_unit_ids) != {"1T", "2T", "3T", "4T", "0A"}:
        raise InstalledTuiChildError("installed financial run did not retain quarterly and annual work identities")

    observed: list[str] = []

    async def readback(pilot: Any) -> None:
        rows = await _transaction_row_ids(pilot, scenario=scenario)
        if len(rows) != 8:
            raise InstalledTuiChildError("fresh installed TUI session lost imported transaction rows")
        await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
        await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="reconciliation")
        from textual.widgets import DataTable

        suggestions = query_public_selector(pilot, "#ledger-suggestions", DataTable)
        inconsistencies = query_public_selector(pilot, "#ledger-inconsistencies", DataTable)
        if suggestions.row_count or inconsistencies.row_count:
            raise InstalledTuiChildError("fresh installed TUI session did not preserve the invoice links")
        reopened = await _work_ids_by_period(pilot, year=year)
        if reopened != work_unit_ids:
            raise InstalledTuiChildError("fresh installed TUI session did not preserve annual and quarterly work")
        await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
        await select_public_data_table_row(
            pilot=pilot,
            table_selector="#declarations-list",
            row_key=work_unit_ids["4T"],
        )
        await wait_for_workbench(pilot)
        await _open_work(pilot, work_unit_id=work_unit_ids["0A"])
        observed.append("financial-work-and-links-reopened")
        pilot.app.exit()

    readback_exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=readback),
    )
    if readback_exit_code != 0 or observed != ["financial-work-and-links-reopened"]:
        raise InstalledTuiChildError("fresh installed session did not reopen the persisted income work")
    return FinancialChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        year=year,
        transaction_imports=1,
        invoice_forms=len(scenario.income) + len(scenario.expenses),
        reconciliation_links=len(scenario.income) + len(scenario.expenses),
        calendar_work=("m130-1t", "m130-2t", "m130-3t", "m130-4t", "m100-0a"),
        lifecycle_operations=tuple(operations),
        canonical_value_fingerprint=canonical_financial_value_fingerprint(values=financial_values),
        artifact_sha256s=tuple(artifact_hashes),
        annual_xsd_validation=annual_xsd_validation,
        fresh_session_readback=hashlib.sha256("|".join(observed).encode("utf-8")).hexdigest(),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the installed INCOME-01 TUI financial child.")
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--profile-label", default="income-tui-financial")
    parser.add_argument("--year", type=int, default=date.today().year - 1)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the child and write only its sanitized receipt."""
    args = _parser().parse_args(argv)
    try:
        receipt = run_financial_child(
            workspace_root=args.workspace_root,
            profile_label=args.profile_label,
            passphrase=read_passphrase_from_stdin(),
            year=args.year,
            scratch=args.scratch,
        )
    except InstalledTuiChildError as error:
        write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA_VERSION, error=error)
        return 2
    except Exception as error:
        trace = error.__traceback__
        frames: list[str] = []
        while trace is not None:
            if Path(trace.tb_frame.f_code.co_filename).name in {
                "installed_tui_financial_child.py",
                "installed_tui_child.py",
            }:
                frames.append(trace.tb_frame.f_code.co_name)
            trace = trace.tb_next
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(
                f"unexpected installed TUI failure: {type(error).__name__} at {','.join(frames[-4:])}"
            ),
        )
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
