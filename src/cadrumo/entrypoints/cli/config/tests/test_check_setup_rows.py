"""Config check and repair grade the admitted component status rows and unavailable reads."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
import typer
import typer.main

from cadrumo.tests.english_locale_fixture import english_locale_fixture
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....adapters.outbound.components.tests.recorded_rows import recorded_absent_row, set_up_row
from .....application.workstation_check import WorkstationCheckReport
from .....application.workstation_check_operation import WorkstationCheckProjection
from .....core.json_contract import ResolvedNoticeAction
from ...tests.cli_runner import invoke_cached_cli
from .. import check_cli, provision_cli, repair_commands

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("aa000000-0000-4000-8000-0000000000aa")


def _context(output_format: str) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": output_format})


@pytest.fixture
def role(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Supply registered status rows, or the refusal of an unavailable read."""
    report = WorkstationCheckReport(profile_id=_PROFILE, capabilities=(), dependencies=(), preflight=(), issues=())
    monkeypatch.setattr(
        check_cli, "read_workstation_check_for_cli", lambda ctx: WorkstationCheckProjection.from_report(report)
    )

    def choose(name: str | None) -> None:
        def read(_ctx: typer.Context):
            if name is None:
                raise RefusalError(RefusalCode.UNAVAILABLE)
            return (set_up_row("browser"), recorded_absent_row("local_ai"))

        monkeypatch.setattr(provision_cli, "read_quick_setup_rows", read)

    return choose


def test_config_check_renders_one_setup_row_per_row_the_role_reports(
    role: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    role("status_quick_browser_ready")

    check_cli.config_check(_context("json"))
    envelope = json.loads(capsys.readouterr().out)

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


def test_recorded_status_refusal_is_unavailable_without_hiding_unsettled_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = CliRefusedBoundaryError("status unavailable")

    def fail(_ctx: typer.Context):
        raise error

    monkeypatch.setattr(provision_cli, "read_quick_setup_rows", fail)
    assert check_cli.read_setup_rows(_context("text")) is None
    error.__dict__["async_cleanup_error"] = object()
    with pytest.raises(CliRefusedBoundaryError) as caught:
        check_cli.read_setup_rows(_context("text"))
    assert caught.value is error


def test_repair_reports_each_registered_setup_row_when_available(role: Any) -> None:
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
