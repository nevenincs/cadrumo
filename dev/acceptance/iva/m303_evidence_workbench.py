"""Installed M303 verification, typed resultado and export workbench observations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
)
from dev.acceptance.income_tax.tui_contracts import TuiJourneyError
from dev.acceptance.income_tax.tui_lifecycle_contract import installed_lifecycle_contract
from dev.acceptance.income_tax.tui_navigation import (
    acknowledge_export_result,
    open_workbench_export,
)
from dev.acceptance.income_tax.tui_operation_controls import activate_tui_operation, confirm_assumed_values

from .m303_evidence_contracts import _RESULTADO_CASILLA, TuiOutcome
from .m303_evidence_navigation import _await_workbench_refresh, open_work
from .m303_evidence_projection import resultado_matches_oracle
from .m303_evidence_refusals import _visible_refusal

if TYPE_CHECKING:
    pass


async def _verify(pilot: Any, *, work_unit_id: str) -> TuiOutcome:
    """Verify from the workbench, first confirming, reviewing and applying any assumed values it offers to confirm."""
    contract = installed_lifecycle_contract()
    verify = contract.verify
    await open_work(pilot, work_unit_id=work_unit_id)
    try:
        confirmed = await confirm_assumed_values(pilot, binding=contract.apply, maximum_polls=6000)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error
    if confirmed is not None:
        if confirmed.terminal_condition != "succeeded":
            raise InstalledTuiChildError(
                f"installed TUI M303 confirmation of assumed values ended {confirmed.terminal_condition}: "
                f"{_visible_refusal(pilot)}"
            )
        await open_work(pilot, work_unit_id=work_unit_id)
    terminal = await activate_tui_operation(pilot, binding=verify)
    if terminal.terminal_condition != "succeeded":
        raise InstalledTuiChildError(
            f"installed TUI M303 verification ended {terminal.terminal_condition}: {_visible_refusal(pilot)}"
        )
    await _await_workbench_refresh(pilot, binding=verify)
    return TuiOutcome(step="verify", terminal_condition=terminal.terminal_condition, visible_notice_key=None)


async def _workbench_resultado(pilot: Any, *, work_unit_id: str) -> tuple[str | None, bool]:
    """Read ``iva.resultado`` off the workbench's form: its origin, and whether its value equals the oracle."""
    from cadrumo.application.modelo.work_form_models import address_key

    form = (await open_work(pilot, work_unit_id=work_unit_id)).form
    if form is None:
        raise InstalledTuiChildError("installed workbench lost its form", diagnostic=public_surface_diagnostic(pilot))
    field = next((item for item in form.fields() if address_key(item.address) == ("casilla", _RESULTADO_CASILLA)), None)
    if field is None:
        return None, False
    return field.origin.value, resultado_matches_oracle(field.value)


async def _attempt_export(pilot: Any, *, work_unit_id: str, output_path: str) -> TuiOutcome:
    """Run the official export through the workbench's export dialog and classify its public terminal result."""
    binding = installed_lifecycle_contract().export
    await open_work(pilot, work_unit_id=work_unit_id)
    try:
        await open_workbench_export(pilot, output_path=output_path)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error
    terminal = await activate_tui_operation(pilot, binding=binding)
    if terminal.terminal_condition == "succeeded":
        await acknowledge_export_result(pilot)
    return TuiOutcome(step="export", terminal_condition=terminal.terminal_condition, visible_notice_key=None)
