"""``aeat config check`` and ``aeat config repair`` show the setup rows the components role reports.

The workstation report comes from the profile worker, which does not read
component state, so ``config check`` reads the role's quick check itself.
``config repair`` reads the same rows with no profile session. The report is a
recorded worker reply and the role's side is a conversation the real role
recorded, replayed on a real pipe; what is checked is each command's own
composition: one row per row the role reported, graded, and one typed notice,
with no rows, when the role cannot answer.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import typer
import typer.main

from cadrumo.tests.components_role_replay import ReplayLauncher
from cadrumo.tests.english_locale_fixture import english_locale_fixture

from .....adapters.outbound.components import client as components_client
from .....adapters.outbound.components.client import ComponentsLaunch
from .....application.workstation_check import WorkstationCheckReport
from .....application.workstation_check_operation import WorkstationCheckProjection
from .....core.json_contract import ResolvedNoticeAction
from .....core.storage_environment import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from ...tests.cli_runner import invoke_cached_cli
from .. import check_cli, repair_commands

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")


def _context(output_format: str) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": output_format})


def _unavailable(
    image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path
) -> ComponentsLaunch:
    del image, arguments, environment, directory
    raise FileNotFoundError("the binary went away")


@pytest.fixture
def role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Answer the role's start with a recorded conversation, or with a start that fails."""
    image = tmp_path / "cadrumo.exe"
    image.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, str(image))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))
    report = WorkstationCheckReport(profile_id=_PROFILE, capabilities=(), dependencies=(), preflight=(), issues=())
    monkeypatch.setattr(
        check_cli, "read_workstation_check_for_cli", lambda ctx: WorkstationCheckProjection.from_report(report)
    )

    def choose(name: str | None) -> ReplayLauncher | None:
        launcher = None if name is None else ReplayLauncher(name)
        monkeypatch.setattr(components_client, "launch_components_role", _unavailable if launcher is None else launcher)
        return launcher

    return choose


def test_config_check_renders_one_setup_row_per_row_the_role_reports(
    role: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    launcher = role("status_quick_browser_ready")

    check_cli.config_check(_context("json"))
    envelope = json.loads(capsys.readouterr().out)

    assert launcher.launch.arguments == ("--role", "components", "status")
    rows = {row["check"]: row for row in envelope["result"]["preflight"]}
    assert list(rows) == ["setup:browser", "setup:local_ai"]
    assert rows["setup:browser"]["healthy"] is True
    assert rows["setup:local_ai"]["healthy"] is False
    assert rows["setup:local_ai"]["precondition_action"]["action"]["action_id"] == "operator.provision.local_ai"
    assert [notice["code"] for notice in envelope["notices"]] == []


def test_a_role_that_cannot_answer_shows_a_typed_notice_and_no_setup_rows(
    role: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    role(None)

    check_cli.config_check(_context("text"))
    output = capsys.readouterr().out

    assert "setup:" not in output
    assert "notice\tconfig.check.setup_unavailable\tSetup could not be checked right now." in output


def test_repair_reports_each_setup_row_with_no_session(role: Any) -> None:
    role("status_quick_browser_ready")

    result = invoke_cached_cli(["--format", "json", "config", "repair"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.stdout)
    checks = {check["name"]: check for check in envelope["result"]["checks"] if check["name"].startswith("setup.")}
    assert list(checks) == ["setup.browser", "setup.local_ai"]
    assert (checks["setup.browser"]["status"], checks["setup.browser"]["precondition_action"]) == ("ok", None)
    local_ai = checks["setup.local_ai"]
    assert local_ai["status"] == "warn"
    assert local_ai["summary"] == "Local AI: Not set up yet. Set it up in the Cadrumo desktop app."
    assert local_ai["precondition_action"]["action"]["action_id"] == "operator.provision.local_ai"
    assert envelope["notices"] == []


def test_repair_points_at_the_status_command_when_the_role_cannot_answer(role: Any) -> None:
    role(None)

    result = invoke_cached_cli(["--format", "json", "config", "repair"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.stdout)
    assert not [check for check in envelope["result"]["checks"] if check["name"].startswith("setup.")]
    assert [notice["code"] for notice in envelope["notices"]] == ["config.repair.setup_status"]
    notice = repair_commands._setup_status_notice()
    assert notice.message == "Setup could not be checked right now. The status command below checks it again."
    action = notice.action
    assert isinstance(action, ResolvedNoticeAction)
    assert action.action.target_command_key == "config.provision.status"
