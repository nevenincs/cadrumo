"""The lane's own decisions: its synthetic files, the provider lane, the conversations and desktops it may touch."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..desktop_processes import classify_desktops, person_environment
from ..lane import (
    LANE_ATTACHMENTS,
    created_during,
    write_lane_attachments,
)
from ..lane_diagnostics import lane_problems, ready_lanes, sign_in_failures

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_attach_buttons_files_are_synthetic_and_cover_every_outcome(tmp_path: Path) -> None:
    directory = write_lane_attachments(tmp_path / "attach")
    names = sorted(entry.name for entry in directory.iterdir())
    assert names == sorted(LANE_ATTACHMENTS)
    for name, content in LANE_ATTACHMENTS.items():
        assert (directory / name).read_bytes() == content
    # Stored, refused by format, refused by name and refused by content.
    assert {".txt", ".csv", ".zip", ".pdf"} <= {Path(name).suffix for name in names}
    assert any(name.startswith(".") for name in names)
    assert not (directory / "lane-mismatch.pdf").read_bytes().startswith(b"%PDF")


def _lane(provider: str, transport: str, **health: object) -> dict[str, object]:
    ready = {
        "configured": "available",
        "transport": "available",
        "catalog": "available",
        "authentication": "authenticated",
        "selectable": True,
    }
    return {
        "provider_id": provider,
        "transport": transport,
        "executable": True,
        "model_source": "catalog",
        "health": {**ready, **health},
        "catalog": {"models": [{"id": "m1"}]},
    }


def test_the_ready_lane_is_the_one_the_agent_column_starts_on() -> None:
    catalog = {
        "providers": [
            _lane("codex", "cli"),
            _lane("claude", "cli"),
            _lane("claude", "api", authentication="unauthenticated", selectable=False),
            _lane("codex", "api"),
        ]
    }
    ready, missing = ready_lanes(catalog)
    # Providers in the order served, each one's API lane before its app.
    assert ready == ["codex/api", "codex/cli", "claude/cli"]
    assert missing == {"claude/api": ["authentication unauthenticated", "not selectable"]}


def test_no_ready_lane_names_what_each_lacks() -> None:
    lacking = _lane("claude", "api", configured="unavailable", authentication="unknown", selectable=False)
    lacking["executable"] = False
    lacking["catalog"] = {"models": []}
    ready, missing = ready_lanes({"providers": [lacking]})
    assert ready == []
    assert missing["claude/api"] == [
        "configured unavailable",
        "authentication unknown",
        "not selectable",
        "not executable",
        "no models",
    ]
    declared = _lane("local", "api")
    declared |= {"model_source": "declared", "catalog": {}}
    assert lane_problems(declared) == []
    assert ready_lanes({}) == ([], {})


def test_only_the_runs_own_conversations_are_deleted() -> None:
    before = {"r-person-1", "r-person-2"}
    assert created_during(before, {"r-person-1", "r-person-2", "r-lane-1"}) == {"r-lane-1"}
    # One the person had and the run did not list is not the run's to delete.
    assert created_during(before, {"r-person-2"}) == set()


def _desktop(pid: int, exe: str | None, *arguments: str, parent_alive: bool = True) -> dict[str, object]:
    return {
        "pid": pid,
        "name": "cadrumo.exe",
        "exe": exe,
        "cmdline": [exe or "", *arguments],
        "parent_alive": parent_alive,
    }


def test_only_a_test_desktop_whose_lane_is_gone_may_be_stopped(tmp_path: Path) -> None:
    testing = tmp_path / "build" / "desktop" / "testing"
    installed = str(tmp_path / "Programs" / "Cadrumo" / "cadrumo.exe")
    leftover = str(testing / "agent-live-package" / "Debug" / "app" / "cadrumo.exe")
    desktops = classify_desktops(
        [
            _desktop(1, installed),
            _desktop(2, leftover, "--gui", parent_alive=False),
            _desktop(3, leftover, "--gui"),
            _desktop(4, installed, "--role", "runtime", "session", "hold"),
            _desktop(5, None),
            {"pid": 6, "name": "python.exe", "exe": leftover, "cmdline": []},
        ],
        testing,
    )
    by_pid = {desktop.pid: desktop for desktop in desktops}
    assert sorted(by_pid) == [1, 2, 3, 5]
    assert (by_pid[1].test_build, by_pid[1].orphaned) == (False, False)
    assert (by_pid[2].test_build, by_pid[2].orphaned) == (True, True)
    assert (by_pid[3].test_build, by_pid[3].orphaned) == (True, False)
    # An image that cannot be read is the person's.
    assert by_pid[5].test_build is False
    # A directory that only shares the name's start is not the testing tree.
    beside = classify_desktops(
        [_desktop(7, str(tmp_path / "build" / "desktop" / "testing-other" / "cadrumo.exe"))], testing
    )
    assert beside[0].test_build is False


def test_the_desktop_runs_on_the_persons_root_with_the_accounts_credential_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_OUTPUT_LANGUAGE", "ca")
    monkeypatch.setenv("CADRUMO_LLM_ANTHROPIC_API_KEY", "not-for-the-desktop")
    monkeypatch.setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--remote-debugging-port=1")
    environment = person_environment(tmp_path / "root", tmp_path / "package")
    assert environment["CADRUMO_STORAGE_ROOT"] == str(tmp_path / "root")
    assert environment["CADRUMO_DESKTOP_PACKAGE_ROOT"] == str(tmp_path / "package")
    assert not {
        "CADRUMO_OUTPUT_LANGUAGE",
        "CADRUMO_LLM_ANTHROPIC_API_KEY",
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    } & set(environment)


def test_a_failed_sign_in_the_desktop_recorded_is_named_by_its_code() -> None:
    # The events as the desktop's diagnostics recorded a sign-in that ran out of time.
    timed_out = {
        "sequence": 36,
        "kind": "helper_result",
        "role": "sign_in",
        "failure": {"code": "timed_out", "operation": "cli", "message": "The child process exceeded its deadline"},
        "helperResult": {"command": "config.login", "executable": "cli", "code": None, "reason": None},
    }
    refused = {
        "sequence": 41,
        "kind": "helper_result",
        "role": "sign_in",
        "failure": {"code": "child_failed", "operation": "cli"},
        "helperResult": {"command": "config.login", "code": "wrong_password", "reason": None},
    }
    unrelated = [
        {"sequence": 35, "kind": "failure", "failure": {"code": "timed_out"}, "role": "sign_in"},
        {"sequence": 37, "kind": "helper_result", "failure": None, "helperResult": {"command": "config.login"}},
        {
            "sequence": 38,
            "kind": "helper_result",
            "failure": {"code": "x"},
            "helperResult": {"command": "profile.list"},
        },
    ]
    assert sign_in_failures([refused, *unrelated, timed_out]) == [
        (36, "timed_out"),
        (41, "child_failed (wrong_password)"),
    ]
    assert sign_in_failures(unrelated) == []
