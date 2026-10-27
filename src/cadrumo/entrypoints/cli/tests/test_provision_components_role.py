"""``config provision`` runs the native component engine's role, prints its plan, answers it and words its codes.

The component leaves run through the real command line with no profile
session. The role's side is a conversation the real role recorded, replayed on
a real pipe (:mod:`cadrumo.tests.components_role_replay`), so these cases check
the command line's own part: the command line it starts, what it prints, the
answer it sends, the envelope and the exit code. The real role is driven by
the client's ``test_client_drives_the_real_role``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from pydantic import BaseModel

from cadrumo.tests.components_role_replay import ReplayLauncher, transcript_lines
from cadrumo.tests.english_locale_fixture import english_locale_fixture

from ....adapters.outbound.components import client as components_client
from ....adapters.outbound.components.protocol import ComponentsNoticeCode, ComponentsNoticeLine
from ....application.dependency_registry import dependency_item_declarations
from ....application.local_reader_report import LocalReaderReportRequest
from ....core.storage_environment import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from ..command_operation_table import COMMAND_OPERATION_ROWS
from ..config import provision_cli
from .cli_runner import invoke_cached_cli, semantic_cli_text

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COMPONENT_LEAVES = ("browser", "probe", "remove", "setup", "status", "verify")
_BROWSER = "Browser for the tax agency website"
_INTERNAL_TERMS = ("runtime", "playwright", "headless", "digest", "ollama", "role")


@pytest.fixture
def replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Answer each role start with a recorded conversation: ``replay("name")`` picks it."""
    image = tmp_path / "cadrumo.exe"
    image.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, str(image))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))

    def choose(name: str) -> ReplayLauncher:
        launcher = ReplayLauncher(name)
        monkeypatch.setattr(components_client, "launch_components_role", launcher)
        return launcher

    return choose


def _json(result: Result) -> dict[str, Any]:
    document = json.loads(result.stdout)
    assert isinstance(document, dict)
    return document


def _relayed(name: str, *, kinds: set[str]) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in transcript_lines(name)]
    return [line for line in lines if line["type"] in kinds]


def test_the_component_leaves_submit_no_registered_operation() -> None:
    rows = {path[2]: operation for path, operation in COMMAND_OPERATION_ROWS if path[:2] == ("config", "provision")}

    assert {leaf: rows[leaf] for leaf in _COMPONENT_LEAVES} == dict.fromkeys(_COMPONENT_LEAVES)
    assert not any(operation and operation.startswith("dependencies.") for _path, operation in COMMAND_OPERATION_ROWS)


def test_status_renders_every_row_the_role_reports_with_what_fixes_it(replay: Any) -> None:
    launcher = replay("status_quick_browser_ready")

    result = invoke_cached_cli(["config", "provision", "status"])

    assert result.exit_code == 0, result.output
    assert launcher.launch.arguments == ("--role", "components", "status")
    lines = semantic_cli_text(result.stdout).splitlines()
    assert f"{_BROWSER}\tReady." in lines
    assert "Local AI\tNot set up yet." in lines
    assert "\tSet it up in the Cadrumo desktop app." in lines
    assert not any("To fix it" in line for line in lines)
    assert lines[-1] == "Some components are not ready yet."
    assert not any(term in result.stdout.lower() for term in _INTERNAL_TERMS)


def test_status_json_carries_each_row_as_the_role_reported_it(replay: Any) -> None:
    replay("status_quick_browser_ready")

    result = invoke_cached_cli(["--format", "json", "config", "provision", "status"])

    assert result.exit_code == 0, result.output
    document = _json(result)["result"]
    (role_result,) = _relayed("status_quick_browser_ready", kinds={"result"})
    assert document["mode"] == "quick"
    assert document["complete"] is False
    assert [(item["item_id"], item["state"], item["recovery"]) for item in document["items"]] == [
        (row["item_id"], row["state"], row.get("recovery")) for row in role_result["rows"]
    ]
    local_ai = document["items"][1]
    assert local_ai["recovery"] == "set_up_in_desktop"
    assert local_ai["recovery_action_id"] == "operator.provision.local_ai"
    assert local_ai["command"] is None


def test_verify_exits_2_with_the_rows_category_and_refuses_an_unknown_item(replay: Any) -> None:
    launcher = replay("verify_browser_blocked_by_network")

    result = invoke_cached_cli(["config", "provision", "verify", "--item", "browser"])

    assert result.exit_code == 2, result.output
    assert launcher.launch.arguments == ("--role", "components", "verify", "--item", "browser")
    assert f"{_BROWSER}\tYour network blocked the download." in semantic_cli_text(result.stdout).splitlines()
    refused = invoke_cached_cli(["config", "provision", "verify", "--item", "printer"])
    assert refused.exit_code == 2
    assert "choose one of: browser, local_ai" in semantic_cli_text(refused.output)
    assert len(launcher.launches) == 1


def test_a_setting_the_engine_refuses_is_worded_as_that_refusal_not_a_broken_protocol(replay: Any) -> None:
    replay("status_refused_blocked_by_network")

    result = invoke_cached_cli(["config", "provision", "status"])

    assert result.exit_code == 2, result.output
    assert semantic_cli_text(result.stdout).splitlines()[-1] == "Your network blocked the download."
    assert "invalid_frame" not in result.output

    replay("status_refused_blocked_by_network")
    as_json = invoke_cached_cli(["--format", "json", "config", "provision", "status"])
    document = _json(as_json)["result"]
    assert (document["failure_category"], document["complete"], document["items"]) == ("blocked_by_network", False, [])
    assert as_json.exit_code == 2, "a refused check is not a computer with nothing set up"


def test_setup_with_yes_prints_the_plan_then_approves_exactly_its_digest(replay: Any) -> None:
    launcher = replay("setup_browser_completed")
    (review,) = _relayed("setup_browser_completed", kinds={"review"})

    result = invoke_cached_cli(["config", "provision", "browser", "--yes"])

    assert result.exit_code == 0, result.output
    assert launcher.launch.arguments == ("--role", "components", "setup", "--item", "browser")
    assert json.loads(launcher.launch.written) == {"type": "approve", "plan_digest": review["plan_digest"]}
    errors = semantic_cli_text(result.stderr).splitlines()
    plan_at = errors.index("Cadrumo will set up:")
    assert errors[plan_at + 1].startswith(f"{_BROWSER}: 317 MB from cdn.playwright.dev")
    assert any(line == "Total download: 317 MB." for line in errors)
    assert f"{_BROWSER}: downloading" in errors
    assert f"{_BROWSER}: checking that it works" in errors
    output = semantic_cli_text(result.stdout).splitlines()
    assert f"{_BROWSER}\tReady." in output
    assert output[-1] == "Setup finished."


def test_a_setup_of_every_component_sets_up_the_browser_and_leaves_the_local_ai_to_the_desktop(
    replay: Any,
) -> None:
    launcher = replay("setup_browser_completed")

    result = invoke_cached_cli(["config", "provision", "setup", "--yes"])

    assert result.exit_code == 0, result.output
    assert launcher.launch.arguments == ("--role", "components", "setup")
    output = semantic_cli_text(result.stdout).splitlines()
    assert f"{_BROWSER}\tReady." in output
    assert "Local AI\tNot set up yet." in output
    assert "\tSet it up in the Cadrumo desktop app." in output
    assert output[-1] == "Setup finished."


def test_the_local_ai_has_no_command_that_pulls_it() -> None:
    names = {name for name in invoke_cached_cli(["config", "provision", "--help"]).stdout.split() if name.isalpha()}

    assert {"browser", "setup", "remove", "status", "verify", "probe", "report"} <= names
    refused = invoke_cached_cli(["config", "provision", "pull", "--yes"])
    assert refused.exit_code == 2
    assert "No such command" in refused.output


@pytest.mark.parametrize(
    "arguments",
    [
        ["setup", "--yes", "--model", "synthetic-text:test"],
        ["setup", "--yes", "local_ai"],
        ["browser", "--yes", "--model", "synthetic-text:test"],
        ["browser", "--yes", "local_ai"],
        ["remove", "browser", "--yes", "--model", "synthetic-text:test"],
        ["status", "--model", "synthetic-text:test"],
        ["verify", "--model", "synthetic-text:test"],
        ["probe", "--model", "synthetic-text:test"],
    ],
    ids=[
        "setup-model",
        "setup-local-ai",
        "browser-model",
        "browser-local-ai",
        "remove-model",
        "status-model",
        "verify-model",
        "probe-model",
    ],
)
def test_no_provision_command_takes_a_model_or_names_the_local_ai_to_set_up_and_none_starts_the_role(
    replay: Any, arguments: list[str]
) -> None:
    launcher = replay("setup_browser_completed")

    result = invoke_cached_cli(["config", "provision", *arguments])

    assert result.exit_code == 2, result.output
    assert launcher.launches == [], "a command line that is not the command's own started the engine"


def test_without_yes_and_without_a_terminal_the_plan_is_shown_declined_and_approval_asked(replay: Any) -> None:
    launcher = replay("setup_declined")

    result = invoke_cached_cli(["config", "provision", "browser"])

    assert result.exit_code == 2, result.output
    assert launcher.launch.written == b'{"type":"decline"}\n'
    assert "Cadrumo will set up:" in semantic_cli_text(result.stderr)
    assert semantic_cli_text(result.stdout).splitlines()[-1] == (
        "This needs your approval. Run the command again with --yes to approve the plan above."
    )


def test_json_mode_relays_every_line_the_role_sends_while_it_works(replay: Any) -> None:
    replay("setup_browser_completed")

    result = invoke_cached_cli(["--format", "json", "config", "provision", "browser", "--yes"])

    assert result.exit_code == 0, result.output
    relayed = [json.loads(line) for line in result.stderr.splitlines()]
    assert relayed == _relayed("setup_browser_completed", kinds={"phase", "progress", "notice", "review"})
    document = _json(result)["result"]
    (role_result,) = _relayed("setup_browser_completed", kinds={"result"})
    assert document["outcome"] == "completed"
    assert document["approved"] is True
    assert document["plan_digest"] == role_result["plan_digest"]
    assert document["space"]["sufficient"] is True
    assert document["item_id"] is None


@pytest.mark.parametrize(
    ("name", "summary"),
    [
        ("setup_refused_blocked_by_network", f"{_BROWSER}: Your network blocked the download."),
        (
            "setup_plan_changed",
            "The plan changed after you approved it, so nothing was downloaded. "
            "Run the command again to see the new plan.",
        ),
    ],
)
def test_a_setup_that_did_not_complete_says_why_and_exits_2(replay: Any, name: str, summary: str) -> None:
    replay(name)

    result = invoke_cached_cli(["config", "provision", "browser", "--yes"])

    assert result.exit_code == 2, result.output
    assert semantic_cli_text(result.stdout).splitlines()[-1] == summary


def test_the_refusal_json_names_the_item_and_its_category(replay: Any) -> None:
    replay("setup_refused_blocked_by_network")

    result = invoke_cached_cli(["--format", "json", "config", "provision", "setup", "--yes"])

    assert result.exit_code == 2, result.output
    document = _json(result)["result"]
    assert (document["outcome"], document["item_id"], document["failure_category"]) == (
        "refused",
        "browser",
        "blocked_by_network",
    )
    assert document["approved"] is False


def test_a_build_without_the_role_reads_every_item_as_not_in_this_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.delenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, raising=False)
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))

    status = invoke_cached_cli(["config", "provision", "status"])
    setup = invoke_cached_cli(["config", "provision", "setup", "--yes"])
    browser = invoke_cached_cli(["config", "provision", "browser", "--yes"])

    assert status.exit_code == 0, status.output
    held = "This version of Cadrumo does not include this."
    assert semantic_cli_text(status.stdout).splitlines()[:2] == [f"{_BROWSER}\t{held}", f"Local AI\t{held}"]
    assert "To fix it" not in status.stdout
    assert setup.exit_code == 2
    assert semantic_cli_text(setup.stdout).splitlines()[-1] == "Some components are not ready yet."
    assert browser.exit_code == 2
    assert semantic_cli_text(browser.stdout).splitlines()[-1] == f"{_BROWSER}: {held}"
    assert not (tmp_path / "root").exists()


@pytest.mark.parametrize("arguments", [["config", "provision", "browser"], ["config", "provision", "browser", "--yes"]])
def test_a_setup_that_follows_one_already_running_asks_nothing_and_reports_its_result(
    replay: Any, arguments: list[str]
) -> None:
    launcher = replay("setup_followed_completed")

    result = invoke_cached_cli(arguments)

    assert result.exit_code == 0, result.output
    assert launcher.launch.written == b""
    errors = semantic_cli_text(result.stderr).splitlines()
    assert errors[0] == f"{_BROWSER}: another setup is already setting this up, so this one follows it."
    assert "Cadrumo will set up:" not in errors
    assert f"{_BROWSER}: checking that it works" in errors
    output = semantic_cli_text(result.stdout).splitlines()
    assert f"{_BROWSER}	Ready." in output
    assert output[-1] == "Setup finished."


def test_a_followed_setup_relays_the_following_notice_in_json_and_records_no_approval(replay: Any) -> None:
    replay("setup_followed_completed")

    result = invoke_cached_cli(["--format", "json", "config", "provision", "browser", "--yes"])

    assert result.exit_code == 0, result.output
    relayed = [json.loads(line) for line in result.stderr.splitlines()]
    assert relayed[0] == _relayed("setup_followed_completed", kinds={"notice"})[0]
    assert relayed[0]["notice_code"] == "following"
    document = _json(result)["result"]
    assert (document["outcome"], document["approved"], document["plan_digest"]) == ("completed", False, None)


def test_a_stopped_follow_says_another_setup_is_still_running_and_exits_2(replay: Any) -> None:
    replay("setup_follow_stopped")

    result = invoke_cached_cli(["config", "provision", "browser"])

    assert result.exit_code == 2, result.output
    errors = semantic_cli_text(result.stderr).splitlines()
    assert errors[0] == f"{_BROWSER}: another setup is already setting this up, so this one follows it."
    assert "Stopping the setup." in errors
    assert semantic_cli_text(result.stdout).splitlines()[-1] == (
        "Another setup is changing this right now. Try again when it has finished."
    )
    assert "approval" not in result.stdout


def test_remove_with_yes_runs_the_roles_removal_and_reports_every_row(replay: Any) -> None:
    launcher = replay("remove_absent_browser")

    result = invoke_cached_cli(["config", "provision", "remove", "browser", "--yes"])

    assert result.exit_code == 0, result.output
    assert launcher.launch.arguments == ("--role", "components", "remove", "--item", "browser")
    assert launcher.launch.written == b""
    errors = semantic_cli_text(result.stderr).splitlines()
    assert f"{_BROWSER}: tidying up" in errors
    output = semantic_cli_text(result.stdout).splitlines()
    assert f"{_BROWSER}	Not set up yet." in output
    assert "	To fix it, run: aeat config provision browser" in output
    assert output[-1] == f"{_BROWSER}: deleted from this computer."


def test_remove_json_carries_the_roles_outcome_and_rows(replay: Any) -> None:
    replay("remove_absent_browser")

    result = invoke_cached_cli(["--format", "json", "config", "provision", "remove", "browser", "--yes"])

    assert result.exit_code == 0, result.output
    document = _json(result)["result"]
    (role_result,) = _relayed("remove_absent_browser", kinds={"result"})
    assert (document["item"], document["confirmed"], document["outcome"]) == ("browser", True, "removed")
    assert document["removed"] == role_result["items"] == ["browser"]
    assert [(item["item_id"], item["state"]) for item in document["items"]] == [
        (row["item_id"], row["state"]) for row in role_result["rows"]
    ]
    assert [json.loads(line) for line in result.stderr.splitlines()] == _relayed(
        "remove_absent_browser", kinds={"phase"}
    )


def test_remove_without_yes_and_without_a_terminal_removes_nothing_and_asks_for_confirmation(replay: Any) -> None:
    launcher = replay("remove_absent_browser")

    result = invoke_cached_cli(["config", "provision", "remove", "browser"])
    document = invoke_cached_cli(["--format", "json", "config", "provision", "remove", "browser"])

    assert result.exit_code == 2, result.output
    assert launcher.launches == []
    assert semantic_cli_text(result.stdout).splitlines() == [
        f"{_BROWSER}: nothing was deleted. Run the command again with --yes to delete it."
    ]
    assert document.exit_code == 2, document.output
    assert _json(document)["result"] == {
        "item": "browser",
        "confirmed": False,
        "outcome": None,
        "removed": [],
        "item_id": None,
        "failure_category": None,
        "items": [],
    }


def test_remove_refuses_an_unknown_component_before_starting_the_role(replay: Any) -> None:
    launcher = replay("remove_absent_browser")

    result = invoke_cached_cli(["config", "provision", "remove", "printer", "--yes"])
    missing = invoke_cached_cli(["config", "provision", "remove"])

    assert result.exit_code == 2
    assert "choose one of: browser" in semantic_cli_text(result.output)
    assert missing.exit_code == 2
    assert launcher.launches == []


def test_remove_refuses_the_local_ai_before_starting_the_role(replay: Any) -> None:
    launcher = replay("remove_absent_browser")

    result = invoke_cached_cli(["config", "provision", "remove", "local_ai", "--yes"])
    unconfirmed = invoke_cached_cli(["config", "provision", "remove", "local_ai"])

    for refused in (result, unconfirmed):
        assert refused.exit_code == 2
        assert "choose one of: browser" in semantic_cli_text(refused.output)
        assert "local_ai," not in semantic_cli_text(refused.output)
    assert launcher.launches == []


def test_remove_in_a_build_without_the_role_says_it_is_not_in_this_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.delenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, raising=False)
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))

    result = invoke_cached_cli(["--format", "json", "config", "provision", "remove", "browser", "--yes"])

    assert result.exit_code == 2, result.output
    document = _json(result)["result"]
    assert (document["outcome"], document["item_id"], document["failure_category"]) == (
        "refused",
        "browser",
        "not_in_this_build",
    )
    assert document["removed"] == []


def test_the_progress_line_words_a_retry_and_a_wait_for_the_program(capsys: pytest.CaptureFixture[str]) -> None:
    line = provision_cli.SetupProgressLine(json_mode=False, interactive=False)
    line.observe(
        ComponentsNoticeLine(
            type="notice", notice_code=ComponentsNoticeCode.RETRYING, subject_code="browser", attempt=2, delay_ms=3500
        )
    )
    line.observe(
        ComponentsNoticeLine(
            type="notice", notice_code=ComponentsNoticeCode.WAITING_FOR_SERVER, subject_code="local_ai"
        )
    )
    line.observe(ComponentsNoticeLine(type="notice", notice_code=ComponentsNoticeCode.CANCEL_REQUESTED))
    line.observe(ComponentsNoticeLine(type="notice", notice_code=ComponentsNoticeCode.INPUT_REFUSED))

    assert capsys.readouterr().err.splitlines() == [
        f"{_BROWSER}: Connection problem. Trying again in 4 seconds (attempt 2).",
        "Local AI: waiting for the program to start",
        "Stopping the setup.",
    ]


def test_every_recovery_action_names_the_leaf_that_drives_the_role_or_reads_the_local_ai() -> None:
    commands = {
        declaration.item_id: provision_cli.recovery_command(declaration.recovery_action_id)
        for declaration in dependency_item_declarations()
    }

    # Only the desktop sets up the local AI, so its action resolves to the leaf that reports its row.
    assert commands == {"browser": "aeat config provision browser", "local_ai": "aeat config provision status"}


class _StopError(Exception):
    """Ends a recorded submission before any result is rendered."""


def test_the_local_reader_report_still_submits_its_registered_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[tuple[str, BaseModel]] = []

    def record(client: object, payload: BaseModel, **options: Any) -> Any:
        del client
        submitted.append((options["definition_id"], payload))
        raise _StopError

    monkeypatch.setattr(provision_cli, "run_registered_operation", record)
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda ctx: object())
    for leaf in ("report",):
        with pytest.raises(_StopError):
            getattr(provision_cli, f"provision_{leaf}")(object())

    rows = {path[2]: operation for path, operation in COMMAND_OPERATION_ROWS if path[:2] == ("config", "provision")}
    assert [definition for definition, _ in submitted] == [rows["report"]]
    assert "load" not in rows, "the local reader no longer loads a model directly"
    assert isinstance(submitted[-1][1], LocalReaderReportRequest)
