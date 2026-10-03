"""Observe installed income-tax lifecycle and independent quarterly artifact readback."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .financial_contracts import _EDIT_SECONDS
from .financial_navigation import _open_work
from .installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
)
from .scenario import QuarterlyOracle
from .tui_contracts import TuiJourneyError
from .tui_lifecycle_contract import installed_lifecycle_contract
from .tui_navigation import (
    acknowledge_export_result,
    open_workbench_export,
    wait_for_tui_refresh,
)
from .tui_operation_controls import activate_tui_operation, confirm_assumed_values
from .tui_readback import workbench_notice
from .tui_selectors import WORKBENCH_NOTICE

if TYPE_CHECKING:
    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen

    from .tui_contracts import InstalledTuiContract


def _m130_expected(oracle: QuarterlyOracle) -> dict[str, str]:
    """Return independently computed M130 casillas in rendered money form."""
    return {
        "01": f"{oracle.cumulative_income:.2f}",
        "02": f"{oracle.cumulative_expenses:.2f}",
        "03": f"{oracle.cumulative_net:.2f}",
        "04": f"{oracle.twenty_percent:.2f}",
        "05": f"{oracle.prior_positive_results:.2f}",
        "06": f"{oracle.cumulative_withholding:.2f}",
        "07": f"{oracle.partial_result:.2f}",
        "13": f"{oracle.low_income_reduction:.2f}",
        "19": f"{oracle.payment:.2f}",
    }


async def _run_lifecycle(
    pilot: Any,
    *,
    export_path: Path,
    work_unit_id: str,
    calculate: bool = True,
) -> tuple[str, ...]:
    """Run calculate, verify, recording the filing and export through the declaration's workbench.

    Each action opens the declaration afresh, so its result is read from a
    workbench notice no earlier action wrote.  When the workbench offers to
    confirm assumed values before verifying, they are confirmed, reviewed and
    applied first, as a filer must.
    """
    contract = installed_lifecycle_contract(
        profile_selection_id="#manager-status",
        ledger_capture_id="#ledger-import-confirm",
        invoice_link_id="#ledger-reconciliation-confirm",
        work_create_id="#declarations-calendar-agenda",
    )
    completed: list[str] = []
    if calculate:
        await _open_work(pilot, work_unit_id=work_unit_id)
        terminal = await activate_tui_operation(pilot, binding=contract.calculate)
        if terminal.outcome.value != "proven":
            raise InstalledTuiChildError("modelo.work.calculate did not reach a succeeded terminal")
        await wait_for_tui_refresh(pilot, binding=contract.calculate)
        completed.append(contract.calculate.operation_id)
    for binding in (contract.verify, contract.local_file):
        await _open_work(pilot, work_unit_id=work_unit_id)
        if binding is contract.verify and await _confirm_assumed_values(pilot, contract=contract):
            completed.append(contract.apply.operation_id)
            await _open_work(pilot, work_unit_id=work_unit_id)
        terminal = await activate_tui_operation(pilot, binding=binding)
        if terminal.outcome.value != "proven":
            raise InstalledTuiChildError(f"{binding.operation_id} did not reach a succeeded terminal")
        await wait_for_tui_refresh(pilot, binding=binding)
        completed.append(binding.operation_id)
    await _open_work(pilot, work_unit_id=work_unit_id)
    await open_workbench_export(pilot, output_path=str(export_path))
    terminal = await activate_tui_operation(pilot, binding=contract.export)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("modelo.export did not reach a succeeded terminal")
    await acknowledge_export_result(pilot)
    completed.append(contract.export.operation_id)
    return tuple(completed)


def _parse_m130_artifact(*, path: Path, year: int, period: str, expected: dict[str, str]) -> dict[str, str]:
    """Independently parse one TUI export through its installed registry layout."""
    from decimal import Decimal

    from cadrumo.core.export_layout_format import ExportLayoutFormat
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.domain.calculations.registry.export_parse import parse_export_payload

    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot("130", filing_year=year, period=period).revision
        layout = next(item for item in revision.export_layouts if item.format is ExportLayoutFormat.FIXED_WIDTH)
        parsed = parse_export_payload(layout, path.read_bytes())
    by_casilla = {str(item.casilla_id): item.value for item in parsed.casillas}
    actual = {casilla: f"{Decimal(str(by_casilla.get(casilla))):.2f}" for casilla in expected}
    if actual != expected:
        raise InstalledTuiChildError("installed Modelo 130 artifact did not match the independent oracle")
    return actual


def _workbench_notice(workbench: ModeloWorkbenchScreen) -> str:
    from textual.widgets import Static

    return str(workbench.query_one(WORKBENCH_NOTICE, Static).render()).strip()


async def _confirm_assumed_values(pilot: Any, *, contract: InstalledTuiContract) -> bool:
    """Confirm, review and apply the assumed values the workbench offers to confirm; whether it offered any."""
    try:
        terminal = await confirm_assumed_values(pilot, binding=contract.apply, seconds=_EDIT_SECONDS)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error
    if terminal is None:
        return False
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError(
            f"confirming the assumed values ended {terminal.terminal_condition}: {workbench_notice(pilot)[:200]!r}",
            diagnostic=public_surface_diagnostic(pilot),
        )
    return True
