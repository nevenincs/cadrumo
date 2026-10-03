"""Drive the admitted withholding declaration controls without composing product services."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dev.acceptance.income_tax.financial_navigation import open_work, wait_for_refreshed_home
from dev.acceptance.income_tax.installed_tui_child import InstalledTuiChildError, wait_for_public_selector
from dev.acceptance.income_tax.tui_lifecycle_contract import installed_lifecycle_contract
from dev.acceptance.income_tax.tui_navigation import (
    acknowledge_export_result,
    open_workbench_export,
    wait_for_tui_refresh,
)
from dev.acceptance.income_tax.tui_operation_controls import activate_tui_operation, confirm_assumed_values

from .installed_tui_seed import WithholdingWork


async def _home(pilot: Any) -> None:
    """Dismiss public child screens so Home obtains a fresh runtime projection."""
    for _ in range(12):
        if pilot.app.screen.query("#home-agenda"):
            await wait_for_refreshed_home(pilot, polls=900)
            return
        await pilot.press("escape")
        await pilot.pause()
    raise InstalledTuiChildError("installed withholding journey could not return to Home")


async def open_withholding_work(pilot: Any, target: WithholdingWork) -> None:
    """Reach the work unit by its visible public declaration row key."""
    await _home(pilot)
    await open_work(pilot, work_unit_id=target.work_unit_id)


async def assert_capture_unavailable(pilot: Any) -> None:
    """Require a populated palette to withhold the unavailable capture route.

    The declarations destination is a positive readiness control; an empty
    palette cannot masquerade as a truthful withholding admission refusal.
    No hidden routing callback or private destination factory is invoked.
    """
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    await _home(pilot)
    await pilot.press("ctrl+p")
    withholding = tr("tui.search.destination.withholding")
    declarations = tr("tui.search.destination.declarations")
    for _ in range(180):
        await pilot.pause()
        try:
            options = pilot.app.screen.query_one(OptionList)
            search = pilot.app.screen.query_one(Input)
        except NoMatches:
            continue
        offered = {
            getattr(getattr(options.get_option_at_index(i), "hit", None), "text", None)
            for i in range(options.option_count)
        }
        if withholding in offered:
            raise InstalledTuiChildError("installed palette offered the unavailable withholding capture route")
        if declarations in offered:
            break
    else:
        raise InstalledTuiChildError("installed withholding refusal check never observed a populated palette")
    search.value = "withholding"
    for _ in range(30):
        await pilot.pause(0.1)
        options = pilot.app.screen.query_one(OptionList)
        if any(
            getattr(getattr(options.get_option_at_index(i), "hit", None), "text", None) == withholding
            for i in range(options.option_count)
        ):
            raise InstalledTuiChildError("installed palette search offered unavailable withholding capture")
    await pilot.press("escape")


async def run_work_lifecycle(pilot: Any, target: WithholdingWork, *, export_path: Path) -> tuple[str, ...]:
    """Calculate, confirm, verify, export and then record a local filing.

    Current TUI progress offers recording only after an export made from the
    current calculation. Quarterly local records then supply the annual
    relation; recording never claims live submission or AEAT acceptance.
    """
    contract = installed_lifecycle_contract()
    completed: list[str] = []
    await open_withholding_work(pilot, target)
    for binding in (contract.calculate,):
        terminal = await activate_tui_operation(pilot, binding=binding)
        if terminal.outcome.value != "proven":
            raise InstalledTuiChildError(f"{binding.operation_id} did not reach a succeeded terminal")
        await wait_for_tui_refresh(pilot, binding=binding)
        completed.append(binding.operation_id)
    await open_withholding_work(pilot, target)
    confirmation = await confirm_assumed_values(pilot, binding=contract.apply)
    if confirmation is not None:
        if confirmation.outcome.value != "proven":
            raise InstalledTuiChildError("installed withholding assumed-value confirmation did not succeed")
        completed.append(contract.apply.operation_id)
        await open_withholding_work(pilot, target)
    terminal = await activate_tui_operation(pilot, binding=contract.verify)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("modelo.work.verify did not reach a succeeded terminal")
    await wait_for_tui_refresh(pilot, binding=contract.verify)
    completed.append(contract.verify.operation_id)
    await open_withholding_work(pilot, target)
    await open_workbench_export(pilot, output_path=str(export_path))
    terminal = await activate_tui_operation(pilot, binding=contract.export)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("modelo.export did not reach a succeeded terminal")
    await acknowledge_export_result(pilot)
    completed.append(contract.export.operation_id)
    await open_withholding_work(pilot, target)
    terminal = await activate_tui_operation(pilot, binding=contract.local_file)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("modelo.work.file did not reach a succeeded terminal")
    await wait_for_tui_refresh(pilot, binding=contract.local_file)
    completed.append(contract.local_file.operation_id)
    return tuple(completed)


async def assert_recorded_reopen(pilot: Any, target: WithholdingWork) -> None:
    """Observe the recorded-state sentence after a fresh launcher admission."""
    from textual.widgets import Static

    from cadrumo.core.i18n.render import tr

    await open_withholding_work(pilot, target)
    await wait_for_public_selector(pilot, "#wb-next")
    rendered = str(pilot.app.screen.query_one("#wb-next", Static).render()).strip()
    pattern = re.escape(tr("tui.modelo.workbench.next.recorded", date="<DATE>"))
    if re.fullmatch(pattern.replace(re.escape("<DATE>"), r".+"), rendered) is None:
        raise InstalledTuiChildError("installed withholding fresh reopen did not show the recorded filing state")
