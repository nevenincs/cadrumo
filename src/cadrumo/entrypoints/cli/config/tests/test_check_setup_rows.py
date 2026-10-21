"""``aeat config check`` shows the setup rows it reads through the runtime, or says it could not read them.

The workstation report comes from the profile worker, which has no runtime
connection, so the command reads ``dependencies.status`` itself. The report
and the status read are answered here by recorded runtime replies built from
real registry rows; what is checked is the command's own composition: one
``setup:<item>`` preflight row per registry row, and a typed notice, with no
rows, when the runtime refuses. ``config repair`` points at the status
command instead, because it runs without a session.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
import typer
import typer.main
from pydantic import BaseModel

from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....application.dependency_contracts import DependencyCheckMode, DependencyProbeOutcome, DependencyProbeReading
from .....application.dependency_registry import dependency_item_declarations, derive_dependency_row
from .....application.dependency_setup_operation import (
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
    DependencyStatusRequest,
    DependencyStatusResultV1,
)
from .....application.workstation_check import WorkstationCheckReport
from .....application.workstation_check_operation import WorkstationCheckProjection
from .....core.config import override_settings
from .....core.json_contract import ResolvedNoticeAction
from .....core.operations import OperationEffect, OperationTerminalCondition
from .. import check_cli, repair_commands

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")


def _context(output_format: str) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": output_format})


def _status() -> DependencyStatusResultV1:
    rows = tuple(
        derive_dependency_row(
            declaration,
            DependencyProbeReading(
                item_id=declaration.item_id,
                mode=DependencyCheckMode.QUICK,
                outcome=DependencyProbeOutcome.ABSENT
                if declaration.item_id == "browser"
                else DependencyProbeOutcome.PRESENT,
            ),
        )
        for declaration in dependency_item_declarations()
    )
    return DependencyStatusResultV1(mode=DependencyCheckMode.QUICK, rows=rows, complete=False, hardware_limited=False)


def _install(monkeypatch: pytest.MonkeyPatch, *, refused: bool) -> list[tuple[str, BaseModel]]:
    submitted: list[tuple[str, BaseModel]] = []
    report = WorkstationCheckReport(profile_id=_PROFILE, capabilities=(), dependencies=(), preflight=(), issues=())

    def run(client: object, payload: BaseModel, **options: Any) -> RegisteredOperationCompletion[Any]:
        del client
        submitted.append((options["definition_id"], payload))
        if refused:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        return RegisteredOperationCompletion(
            operation_id="a" * 64,
            projection=_status(),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(
        check_cli, "read_workstation_check_for_cli", lambda ctx: WorkstationCheckProjection.from_report(report)
    )
    monkeypatch.setattr(check_cli, "run_registered_operation", run)
    monkeypatch.setattr(check_cli, "bound_profile_client", lambda ctx: object())
    return submitted


def test_config_check_renders_one_setup_row_per_registry_item(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    submitted = _install(monkeypatch, refused=False)

    with override_settings(cadrumo_output_language="en"):
        check_cli.config_check(_context("json"))
    envelope = json.loads(capsys.readouterr().out)

    assert submitted == [(DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID, DependencyStatusRequest())]
    rows = {row["check"]: row for row in envelope["result"]["preflight"]}
    assert list(rows) == [f"setup:{declaration.item_id}" for declaration in dependency_item_declarations()]
    assert rows["setup:browser"]["healthy"] is False
    assert rows["setup:browser"]["precondition_action"]["action"]["action_id"] == "operator.provision.browser"
    assert all(row["healthy"] for name, row in rows.items() if name != "setup:browser")
    assert [notice["code"] for notice in envelope["notices"]] == []


def test_an_unreachable_runtime_shows_a_typed_notice_and_no_setup_rows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, refused=True)

    with override_settings(cadrumo_output_language="en"):
        check_cli.config_check(_context("text"))
    output = capsys.readouterr().out

    assert "setup:" not in output
    assert "notice\tconfig.check.setup_unavailable\tSetup could not be checked" in output


def test_repair_points_at_the_status_command_instead_of_reading_setup() -> None:
    with override_settings(cadrumo_output_language="en"):
        notice = repair_commands._setup_status_notice()

    assert notice.code == "config.repair.setup_status"
    assert notice.message == "Setup is shown by the status command below once you're signed in."
    action = notice.action
    assert isinstance(action, ResolvedNoticeAction)
    assert action.action.target_command_key == "config.provision.status"
