"""One fresh installed-TUI child operation for PROFILE-01.

This module is intentionally launched by an interpreter whose ``cadrumo``
package is installed from a wheel.  It uses public Textual controls only:
registration, login, the Profile Manager route, visible repeatable-row buttons,
and visible field dialogs.  No application service or encrypted repository is
imported as a write shortcut.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    open_profile_manager_field,
    query_public_selector,
    register_profile_through_installed_tui,
    wait_for_public_selector,
)

from .scenario import ProfileRowLifecycleScenario, build_profile_row_lifecycle_scenario

_SCHEMA_VERSION = "profile-01-installed-tui-row-child-v1"
_OPERATION_CHOICES = ("create-add", "add", "edit", "no-op", "clear", "remove", "assert-clear", "assert-absent")
ProfileTuiOperation = Literal["create-add", "add", "edit", "no-op", "clear", "remove", "assert-clear", "assert-absent"]


class ProfileTuiChildAcceptanceError(RuntimeError):
    """Stable child failure with no profile values or credentials in its text."""

    def __init__(self, code: str) -> None:
        """Retain only a stable code that is safe to write into a receipt."""
        self.code = code
        super().__init__(f"PROFILE-01 installed TUI operation refused: {code}")


@dataclass(frozen=True, slots=True)
class ProfileTuiChildEvidence:
    """Value-free evidence written by exactly one installed TUI child process."""

    schema_version: str
    status: Literal["proven"]
    operation: ProfileTuiOperation
    product_origin: str
    product_init_sha256: str
    row_key: str | None
    row_visible: bool
    clear_visible_absent: bool
    selector_fact_visible: bool
    no_op_observed: bool

    def to_dict(self) -> dict[str, object]:
        """Return only durable status/identity observations for the outer driver."""
        return cast("dict[str, object]", asdict(self))


def run_profile_tui_operation(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    operation: ProfileTuiOperation,
    row_key: str | None,
    scenario: ProfileRowLifecycleScenario | None = None,
) -> ProfileTuiChildEvidence:
    """Run exactly one visible operation against an installed profile manager."""
    if operation not in _OPERATION_CHOICES:
        raise ProfileTuiChildAcceptanceError("unknown_operation")
    if operation in {"edit", "no-op", "clear", "remove", "assert-clear", "assert-absent"} and not _valid_row_key(
        row_key
    ):
        raise ProfileTuiChildAcceptanceError("numeric_row_required")
    scenario = scenario or build_profile_row_lifecycle_scenario()
    product = installed_product_evidence(workspace_root=workspace_root)
    if operation == "create-add":
        _register_profile_through_visible_tui(profile_label=profile_label, passphrase=passphrase)
    else:
        from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
        from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

        with live_exchange_rate_composition(), profile_adapter_composition():
            asyncio.run(_admit_existing_profile_session(passphrase=passphrase))

    observed_row: list[str | None] = [row_key]
    clear_absent: list[bool] = [False]
    row_visible: list[bool] = [False]
    selector_visible: list[bool] = [False]
    no_op_observed: list[bool] = [False]

    async def drive_after_home(pilot: Any) -> None:
        await pilot.press("f4")
        await wait_for_public_selector(pilot, "#manager-status", polls=180)
        if operation in {"create-add", "add"}:
            observed_row[0] = await _add_activity_row(pilot=pilot, scenario=scenario)
            added_row = _required_row_key(observed_row[0])
            row_visible[0] = True
            selector_visible[0] = _field_is_present(
                pilot=pilot,
                path=scenario.path(added_row, scenario.selector_field),
            )
            if not selector_visible[0]:
                raise ProfileTuiChildAcceptanceError("added_selector_fact_not_visible")
        elif operation == "edit":
            target_row = _required_row_key(row_key)
            await _edit_clearable_field(pilot=pilot, row_key=target_row, scenario=scenario)
            row_visible[0] = _row_is_visible(pilot=pilot, row_key=target_row, scenario=scenario)
            selector_visible[0] = _field_is_present(
                pilot=pilot,
                path=scenario.path(target_row, scenario.selector_field),
            )
        elif operation == "no-op":
            target_row = _required_row_key(row_key)
            no_op_observed[0] = await _submit_visible_no_op(pilot=pilot, row_key=target_row, scenario=scenario)
            row_visible[0] = _row_is_visible(pilot=pilot, row_key=target_row, scenario=scenario)
            selector_visible[0] = _field_is_present(
                pilot=pilot,
                path=scenario.path(target_row, scenario.selector_field),
            )
            if not no_op_observed[0] or not row_visible[0] or not selector_visible[0]:
                raise ProfileTuiChildAcceptanceError("visible_no_op_outcome_mismatch")
        elif operation == "clear":
            target_row = _required_row_key(row_key)
            await _clear_clearable_field(pilot=pilot, row_key=target_row, scenario=scenario)
            row_visible[0] = _row_is_visible(pilot=pilot, row_key=target_row, scenario=scenario)
            clear_absent[0] = not _field_is_present(
                pilot=pilot,
                path=scenario.path(target_row, scenario.clearable_field),
            )
            selector_visible[0] = _field_is_present(
                pilot=pilot,
                path=scenario.path(target_row, scenario.selector_field),
            )
            if not clear_absent[0]:
                raise ProfileTuiChildAcceptanceError("cleared_field_still_visible")
            if not selector_visible[0]:
                raise ProfileTuiChildAcceptanceError("clear_lost_selector_fact")
        elif operation == "remove":
            target_row = _required_row_key(row_key)
            await _remove_activity_row(pilot=pilot, row_key=target_row, scenario=scenario)
            row_visible[0] = _row_is_visible(pilot=pilot, row_key=target_row, scenario=scenario)
            if row_visible[0]:
                raise ProfileTuiChildAcceptanceError("removed_row_still_visible")
        elif operation == "assert-clear":
            target_row = _required_row_key(row_key)
            row_visible[0] = _row_is_visible(pilot=pilot, row_key=target_row, scenario=scenario)
            clear_absent[0] = not _field_is_present(
                pilot=pilot,
                path=scenario.path(target_row, scenario.clearable_field),
            )
            selector_visible[0] = _field_is_present(
                pilot=pilot,
                path=scenario.path(target_row, scenario.selector_field),
            )
            if not row_visible[0] or not clear_absent[0] or not selector_visible[0]:
                raise ProfileTuiChildAcceptanceError("fresh_reopen_clear_state_mismatch")
        else:
            target_row = _required_row_key(row_key)
            row_visible[0] = _row_is_visible(pilot=pilot, row_key=target_row, scenario=scenario)
            if row_visible[0]:
                raise ProfileTuiChildAcceptanceError("fresh_reopen_removed_row_visible")
        pilot.app.exit()

    from cadrumo.entrypoints.tui.launcher import main

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive_after_home),
    )
    if exit_code != 0:
        raise ProfileTuiChildAcceptanceError("launcher_nonzero_exit")
    return ProfileTuiChildEvidence(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        operation=operation,
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        row_key=observed_row[0],
        row_visible=row_visible[0],
        clear_visible_absent=clear_absent[0],
        selector_fact_visible=selector_visible[0],
        no_op_observed=no_op_observed[0],
    )


def _register_profile_through_visible_tui(*, profile_label: str, passphrase: str) -> None:
    """Create one fresh profile through the ordinary installed registration screen."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))


async def _admit_existing_profile_session(*, passphrase: str) -> None:
    """Unlock an existing profile through the shipped visible Login screen."""
    from textual.widgets import Input

    from cadrumo.application.user_profile.login_interaction import (
        ProfileLoginInventoryState,
        attempt_profile_login,
        observe_profile_login_inventory,
    )
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.login import LoginScreen

    inventory = observe_profile_login_inventory()
    if inventory.state is not ProfileLoginInventoryState.RECOGNIZED:
        raise ProfileTuiChildAcceptanceError("existing_profile_not_recognized")
    with bundled_indexed_authority().operation() as operation:
        screen = LoginScreen(
            choices=inventory.choices,
            authenticate=lambda candidate_profile_id, candidate_passphrase: attempt_profile_login(
                candidate_profile_id,
                candidate_passphrase,
                profile_decode_context=operation.profile_decode_context(),
            ),
            preselected=inventory.preselected_profile_id,
        )
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await wait_for_public_selector(pilot, "#field-passphrase")
            field = query_public_selector(pilot, "#field-passphrase", Input)
            if not isinstance(field, Input):
                raise ProfileTuiChildAcceptanceError("login_passphrase_control_invalid")
            field.value = passphrase
            await pilot.click("#btn-unlock")
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
    if screen.outcome is None:
        raise ProfileTuiChildAcceptanceError("login_not_admitted")


async def _add_activity_row(*, pilot: Any, scenario: ProfileRowLifecycleScenario) -> str:
    """Add all scenario facts through the visible generic repeatable-row form."""
    from textual.widgets import Input

    await _click_visible(pilot, f"#manager-add-row-{scenario.section}")
    await wait_for_public_selector(pilot, "#row-input-0")
    for index, (_field, value) in enumerate(scenario.add_values()):
        input_widget = query_public_selector(pilot, f"#row-input-{index}", Input)
        input_widget.value = value
    await pilot.click("#btn-row-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#manager-status")
    row_key = _find_numeric_activity_row(pilot=pilot, scenario=scenario)
    if row_key is None:
        raise ProfileTuiChildAcceptanceError("added_row_not_visible")
    return row_key


async def _edit_clearable_field(*, pilot: Any, row_key: str, scenario: ProfileRowLifecycleScenario) -> None:
    """Edit an identified existing row through the ordinary field modal."""
    from textual.widgets import Input

    path = scenario.path(row_key, scenario.clearable_field)
    await open_profile_manager_field(pilot=pilot, path=path)
    await wait_for_public_selector(pilot, "#edit-input")
    input_widget = query_public_selector(pilot, "#edit-input", Input)
    input_widget.value = scenario.amended_cnae
    await pilot.click("#btn-edit-save")
    await pilot.app.workers.wait_for_complete()
    if not _field_is_present(pilot=pilot, path=path):
        raise ProfileTuiChildAcceptanceError("edited_field_not_visible")


async def _clear_clearable_field(*, pilot: Any, row_key: str, scenario: ProfileRowLifecycleScenario) -> None:
    """Use an empty editable box as the TUI's explicit clear action, then save."""
    from textual.widgets import Input

    path = scenario.path(row_key, scenario.clearable_field)
    await open_profile_manager_field(pilot=pilot, path=path)
    await wait_for_public_selector(pilot, "#edit-input")
    input_widget = query_public_selector(pilot, "#edit-input", Input)
    input_widget.value = ""
    await pilot.click("#btn-edit-save")
    await pilot.app.workers.wait_for_complete()


async def _submit_visible_no_op(*, pilot: Any, row_key: str, scenario: ProfileRowLifecycleScenario) -> bool:
    """Submit the exact visible value through the normal modal and observe a successful landing.

    This is deliberately not a synthetic callback invocation.  The child opens
    the identified row's public editor, verifies that the prior visible edit
    reached the screen, saves that untouched value, and waits for the real
    worker.  The row mutation contract therefore receives an explicit value
    identical to the current fact, which is its typed no-op case.
    """
    from textual.widgets import Input

    from cadrumo.entrypoints.tui.components.status import PinnedStatusBar

    path = scenario.path(row_key, scenario.clearable_field)
    await open_profile_manager_field(pilot=pilot, path=path)
    await wait_for_public_selector(pilot, "#edit-input")
    input_widget = query_public_selector(pilot, "#edit-input", Input)
    if input_widget.value != scenario.amended_cnae:
        raise ProfileTuiChildAcceptanceError("visible_no_op_value_mismatch")
    await pilot.click("#btn-edit-save")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()
    status = query_public_selector(pilot, "#manager-status", PinnedStatusBar)
    if not _is_exact_visible_no_op_outcome(
        status_tone=status.tone,
        status_message=status.message,
        field_visible=_field_is_present(pilot=pilot, path=path),
    ):
        raise ProfileTuiChildAcceptanceError("visible_no_op_not_landed")
    return True


def _is_exact_visible_no_op_outcome(*, status_tone: str, status_message: str, field_visible: bool) -> bool:
    """Accept only the localized outcome the visible manager declares for no change.

    The installed child does not read an overview revision or content digest:
    those are not part of the visible operator surface.  It instead requires
    the exact rendered ``no_change`` status produced by the same localized UI
    path, while retaining only a boolean in its durable receipt.
    """
    from cadrumo.core.i18n.render import tr

    return status_tone == "success" and status_message == tr("flows.manager.edit.no_change") and field_visible


async def _remove_activity_row(*, pilot: Any, row_key: str, scenario: ProfileRowLifecycleScenario) -> None:
    """Focus the stable row path and confirm the manager's explicit remove action."""
    await _focus_visible_profile_field(
        pilot=pilot,
        path=scenario.path(row_key, scenario.required_field),
    )
    await _click_visible(pilot, f"#manager-remove-row-{scenario.section}")
    await wait_for_public_selector(pilot, "#btn-row-remove")
    await pilot.click("#btn-row-remove")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#manager-status")


async def _click_visible(pilot: Any, selector: str) -> None:
    """Focus one public control and activate it through the keyboard surface."""
    from textual.widget import Widget

    widget = query_public_selector(pilot, selector, Widget)
    widget.focus()
    await pilot.pause()
    await pilot.press("enter")


async def _focus_visible_profile_field(*, pilot: Any, path: str) -> None:
    """Focus one public DataTable row without using display order as identity."""
    from textual.widgets import DataTable

    for table in pilot.app.screen.query(DataTable):
        for candidate in table.rows:
            if str(candidate.value) != path:
                continue
            table.focus()
            table.move_cursor(row=table.get_row_index(candidate))
            await pilot.pause()
            return
    raise ProfileTuiChildAcceptanceError("target_row_not_visible")


def _find_numeric_activity_row(*, pilot: Any, scenario: ProfileRowLifecycleScenario) -> str | None:
    """Discover an added row by its semantic canonical field key, never table position."""
    from textual.widgets import DataTable

    prefix = f"{scenario.section}."
    suffix = f".{scenario.required_field}"
    candidates: list[str] = []
    for table in pilot.app.screen.query(DataTable):
        for candidate in table.rows:
            path = str(candidate.value)
            if not path.startswith(prefix) or not path.endswith(suffix):
                continue
            row_key = path[len(prefix) : -len(suffix)]
            if row_key.isdecimal():
                candidates.append(str(int(row_key)))
    if len(set(candidates)) != 1:
        return None
    return candidates[0]


def _row_is_visible(*, pilot: Any, row_key: str, scenario: ProfileRowLifecycleScenario) -> bool:
    """Report whether the row's required leaf is still a visible public manager row."""
    return _field_is_present(pilot=pilot, path=scenario.path(row_key, scenario.required_field))


def _field_is_present(*, pilot: Any, path: str) -> bool:
    """Read only a rendered presence glyph from the visible Profile Manager table."""
    from textual.widgets import DataTable

    for table in pilot.app.screen.query(DataTable):
        for candidate in table.rows:
            if str(candidate.value) != path:
                continue
            cells = table.get_row(candidate)
            return bool(cells) and str(cells[0]) == "●"
    return False


def _valid_row_key(value: str | None) -> bool:
    """Keep child arguments on the established numeric repeatable-row identity contract."""
    return isinstance(value, str) and value.isdecimal()


def _required_row_key(value: str | None) -> str:
    """Return the preflight-validated stable row key or refuse deterministically."""
    if not isinstance(value, str) or not value.isdecimal():
        raise ProfileTuiChildAcceptanceError("numeric_row_required")
    return value


def _read_passphrase_from_stdin() -> str:
    """Read one synthetic credential object without ever echoing its value."""
    try:
        payload: object = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ProfileTuiChildAcceptanceError("credential_stdin_not_json_object") from exc
    if not isinstance(payload, dict):
        raise ProfileTuiChildAcceptanceError("credential_stdin_not_json_object")
    passphrase = payload.get("profile_passphrase")
    if not isinstance(passphrase, str) or not passphrase:
        raise ProfileTuiChildAcceptanceError("credential_stdin_missing_passphrase")
    return passphrase


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one PROFILE-01 installed-TUI row lifecycle operation.")
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--profile-label", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--operation", required=True, choices=_OPERATION_CHOICES)
    parser.add_argument("--row")
    return parser


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    """Write a caller-owned receipt path only after ensuring its parent exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the child and leave a sanitized status receipt for the outer driver."""
    args = _parser().parse_args(argv)
    try:
        evidence = run_profile_tui_operation(
            workspace_root=args.workspace_root,
            profile_label=args.profile_label,
            passphrase=_read_passphrase_from_stdin(),
            operation=args.operation,
            row_key=args.row,
        )
    except (InstalledTuiChildError, ProfileTuiChildAcceptanceError) as exc:
        code = exc.code if isinstance(exc, ProfileTuiChildAcceptanceError) else f"installed_tui_{type(exc).__name__}"
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA_VERSION,
                "status": "failed",
                "failure_class": type(exc).__name__,
                "failure_code": code,
            },
        )
        return 2
    except Exception as exc:
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA_VERSION,
                "status": "failed",
                "failure_class": type(exc).__name__,
                "failure_code": f"unexpected_{type(exc).__name__}",
            },
        )
        return 2
    _write_receipt(args.receipt, evidence.to_dict())
    return 0


if __name__ == "__main__":  # pragma: no cover - executable module boundary
    raise SystemExit(main())


__all__ = [
    "ProfileTuiChildAcceptanceError",
    "ProfileTuiChildEvidence",
    "ProfileTuiOperation",
    "main",
    "run_profile_tui_operation",
]
