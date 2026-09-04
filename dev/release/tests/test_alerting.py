"""Tests for the release-alert transport.

`dev.quality.module_test_reach` listed `dev/release/alerting.py` as unreached
and writing to the tree, and this module is the one that pays for a removal: the
release path no longer stops at a human approval click, so a silently failed
orchestration is indistinguishable from a release nobody started. An untested
alerting channel is that same silence by a slower route.

The module's own docstrings record that this has already happened once. The live
repository carried no ``release-alert`` label, so every default-path alert was
refused by the forge and degraded to a run-log warning - the deliverable that
paid for the removed click was delivering nothing at all. That is the failure
these tests exist to catch a second time.

The gh boundary is driven through a REAL executable rather than a patched
``subprocess``. ``gh_executable`` is a production parameter, so a script on disk
that records its argv is an injected collaborator rather than a mock of the code
under test - and it exercises the argument list, the exit codes, and the
``--body-file`` handoff as the forge itself would see them.
"""

from __future__ import annotations

import json
import os
import pathlib
import stat
import sys
from collections.abc import Iterator

import pytest

from ..alerting import (
    ALERT_LABEL,
    AlertError,
    ReleaseAlert,
    alert_payload,
    emit_alert,
    ensure_alert_label,
    find_open_alert,
    main,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOG_VARIABLE = "CADRUMO_FAKE_GH_LOG"
_BODY_VARIABLE = "CADRUMO_FAKE_GH_BODY"
_ISSUES_VARIABLE = "CADRUMO_FAKE_GH_ISSUES"
_LABEL_QUERY_FAILS = "CADRUMO_FAKE_GH_LABEL_QUERY_FAILS"
_LABELLED_CREATE_FAILS = "CADRUMO_FAKE_GH_LABELLED_CREATE_FAILS"
_LABEL_CREATE_RC = "CADRUMO_FAKE_GH_LABEL_CREATE_RC"

_FAKE_GH_LINES = (
    "import json, os, sys",
    "arguments = sys.argv[1:]",
    "with open(os.environ['CADRUMO_FAKE_GH_LOG'], 'a', encoding='utf-8') as handle:",
    "    handle.write(json.dumps(arguments) + chr(10))",
    "if '--body-file' in arguments:",
    "    source = arguments[arguments.index('--body-file') + 1]",
    "    with open(source, encoding='utf-8') as reader:",
    "        body = reader.read()",
    "    with open(os.environ['CADRUMO_FAKE_GH_BODY'], 'w', encoding='utf-8') as handle:",
    "        handle.write(body)",
    "command = tuple(arguments[:2])",
    "if command == ('issue', 'list'):",
    "    if '--label' in arguments and os.environ.get('CADRUMO_FAKE_GH_LABEL_QUERY_FAILS'):",
    "        sys.stderr.write('unknown label')",
    "        raise SystemExit(1)",
    "    sys.stdout.write(os.environ.get('CADRUMO_FAKE_GH_ISSUES', '[]'))",
    "    raise SystemExit(0)",
    "if command == ('label', 'create'):",
    "    raise SystemExit(int(os.environ.get('CADRUMO_FAKE_GH_LABEL_CREATE_RC', '0')))",
    "if command == ('issue', 'create'):",
    "    if '--label' in arguments and os.environ.get('CADRUMO_FAKE_GH_LABELLED_CREATE_FAILS'):",
    "        sys.stderr.write('label not found')",
    "        raise SystemExit(1)",
    "    sys.stdout.write('https://example.invalid/issues/7')",
    "    raise SystemExit(0)",
    "if command == ('issue', 'comment'):",
    "    raise SystemExit(0)",
    "sys.stderr.write('unexpected invocation')",
    "raise SystemExit(2)",
)


class FakeForge:
    """A gh executable on disk, plus the argv log it appends to."""

    def __init__(self, executable: pathlib.Path, log: pathlib.Path, body: pathlib.Path) -> None:
        self.executable = executable
        self._log = log
        self._body = body

    @property
    def invocations(self) -> list[list[str]]:
        if not self._log.is_file():
            return []
        return [json.loads(line) for line in self._log.read_text(encoding="utf-8").splitlines() if line]

    def subcommands(self) -> list[tuple[str, ...]]:
        return [tuple(arguments[:2]) for arguments in self.invocations]

    @property
    def delivered_body(self) -> str:
        return self._body.read_text(encoding="utf-8") if self._body.is_file() else ""


@pytest.fixture
def forge(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeForge]:
    """Materialise a gh stand-in that records what the module asked the forge to do."""
    implementation = tmp_path / "gh_impl.py"
    implementation.write_text(chr(10).join(_FAKE_GH_LINES) + chr(10), encoding="utf-8")

    if os.name == "nt":
        executable = tmp_path / "gh.cmd"
        launcher = (
            "@echo off",
            chr(34) + sys.executable + chr(34) + " " + chr(34) + str(implementation) + chr(34) + " %*",
        )
    else:
        executable = tmp_path / "gh"
        launcher = (
            "#!/bin/sh",
            "exec "
            + chr(34)
            + sys.executable
            + chr(34)
            + " "
            + chr(34)
            + str(implementation)
            + chr(34)
            + " "
            + chr(34)
            + "$@"
            + chr(34),
        )
    executable.write_text(chr(10).join(launcher) + chr(10), encoding="utf-8")
    if os.name != "nt":
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv(_LOG_VARIABLE, str(tmp_path / "gh.log"))
    monkeypatch.setenv(_BODY_VARIABLE, str(tmp_path / "gh-body.md"))
    yield FakeForge(executable, tmp_path / "gh.log", tmp_path / "gh-body.md")


def _alert(run_id: str = "12345", detail: str = "pytest exited 1") -> ReleaseAlert:
    return ReleaseAlert(
        workflow="release",
        run_id=run_id,
        run_url="https://example.invalid/actions/runs/" + run_id,
        stage="publish",
        detail=detail,
    )


def _open_issue(number: int, fingerprint: str) -> str:
    return json.dumps([{"number": number, "title": "Release alert: release failed (" + fingerprint + ")"}])


def test_the_fingerprint_identifies_the_run_and_not_the_workflow() -> None:
    """Two failed releases deserve two alerts; one release failing twice deserves one."""
    assert _alert("1").fingerprint != _alert("2").fingerprint
    assert _alert("1").fingerprint == "release#1"


def test_the_title_carries_the_fingerprint_so_the_alert_can_be_found_again() -> None:
    """Deduplication searches titles, so a title without it can never be matched."""
    assert _alert("77").fingerprint in _alert("77").title


def test_the_payload_leads_with_the_run_url() -> None:
    """The operator's next action is to open the run, not to search for it."""
    body = alert_payload(_alert())

    assert body.index("https://example.invalid/actions/runs/12345") < body.index("pytest exited 1")


def test_an_empty_detail_says_so_rather_than_rendering_a_blank_block() -> None:
    """A blank fenced block reads as a delivered alert with nothing wrong in it."""
    assert "(no detail captured)" in alert_payload(_alert(detail="   "))


def test_a_webhook_replaces_the_issue_rather_than_supplementing_it(forge: FakeForge) -> None:
    """Two channels for one event train the operator to read whichever is quieter."""
    delivered: list[tuple[str, ReleaseAlert]] = []

    result = emit_alert(
        _alert(),
        repository="owner/repo",
        webhook_url="  https://hooks.example.invalid/abc  ",
        gh_executable=str(forge.executable),
        webhook_sender=lambda url, alert: delivered.append((url, alert)),
    )

    assert [url for url, _ in delivered] == ["https://hooks.example.invalid/abc"]
    assert forge.invocations == [], "the forge was contacted despite a nominated channel"
    assert "webhook" in result


def test_a_first_failure_opens_a_labelled_issue(forge: FakeForge) -> None:
    """The default path needs no configuration, which is why it is the default."""
    result = emit_alert(_alert(), repository="owner/repo", gh_executable=str(forge.executable))

    created = [arguments for arguments in forge.invocations if tuple(arguments[:2]) == ("issue", "create")]
    assert len(created) == 1
    assert ALERT_LABEL in created[0]
    assert "opened alert" in result


def test_the_body_rides_a_file_rather_than_the_command_line(forge: FakeForge) -> None:
    """An unbounded multi-line body is not something a command line can carry.

    Windows caps one at about eight thousand characters and every shell in the
    chain quotes embedded newlines differently, so a regression to ``--body``
    would truncate or mangle exactly the detail the operator needs.
    """
    emit_alert(_alert(), repository="owner/repo", gh_executable=str(forge.executable))

    created = next(arguments for arguments in forge.invocations if tuple(arguments[:2]) == ("issue", "create"))
    assert "--body-file" in created
    assert "--body" not in created
    assert "pytest exited 1" in forge.delivered_body


def test_a_re_run_updates_the_open_alert_instead_of_minting_another(
    forge: FakeForge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An alerting channel that floods is one the operator learns to filter."""
    monkeypatch.setenv(_ISSUES_VARIABLE, _open_issue(41, _alert().fingerprint))

    result = emit_alert(_alert(), repository="owner/repo", gh_executable=str(forge.executable))

    assert ("issue", "comment") in forge.subcommands()
    assert ("issue", "create") not in forge.subcommands()
    assert "updated open alert #41" in result


def test_another_runs_open_alert_does_not_swallow_this_one(
    forge: FakeForge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Matching on the label alone would file every release failure into one thread."""
    monkeypatch.setenv(_ISSUES_VARIABLE, _open_issue(41, "release#99999"))

    emit_alert(_alert(), repository="owner/repo", gh_executable=str(forge.executable))

    assert ("issue", "create") in forge.subcommands()


def test_deduplication_survives_a_repository_with_no_label(
    forge: FakeForge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The label is a filing convenience; losing it must not also cost the dedup.

    This is the state the live repository was actually in, and the reason the
    unlabelled fallback query exists at all.
    """
    monkeypatch.setenv(_LABEL_QUERY_FAILS, "1")
    monkeypatch.setenv(_ISSUES_VARIABLE, _open_issue(41, _alert().fingerprint))

    result = emit_alert(_alert(), repository="owner/repo", gh_executable=str(forge.executable))

    assert "updated open alert #41" in result


def test_an_unlabellable_repository_still_receives_the_alert(
    forge: FakeForge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delivery outranks filing, and this is the assertion that says so.

    Raising here is what the live repository did for every alert it was asked
    to send: the label was absent, the forge refused, and the alert degraded to
    a run-log warning nobody reads.
    """
    monkeypatch.setenv(_LABELLED_CREATE_FAILS, "1")

    result = emit_alert(_alert(), repository="owner/repo", gh_executable=str(forge.executable))

    creates = [arguments for arguments in forge.invocations if tuple(arguments[:2]) == ("issue", "create")]
    assert len(creates) == 2, "the labelled attempt was not retried without the label"
    assert ALERT_LABEL not in creates[1]
    assert "unlabelled" in result


def test_creating_the_label_reports_whether_it_was_created(
    forge: FakeForge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token that cannot create one must return, not raise on its caller."""
    assert ensure_alert_label(repository="owner/repo", gh_executable=str(forge.executable)) is True

    monkeypatch.setenv(_LABEL_CREATE_RC, "1")
    assert ensure_alert_label(repository="owner/repo", gh_executable=str(forge.executable)) is False


def test_an_absent_gh_raises_the_modules_own_error_type(tmp_path: pathlib.Path) -> None:
    """A foreign exception type would escape the caller's ``except AlertError``.

    The alert path lives inside a failure handler, so an unconverted OSError
    would replace the release failure with the alerter's own.
    """
    with pytest.raises(AlertError):
        emit_alert(_alert(), repository="owner/repo", gh_executable=str(tmp_path / "not-installed"))


def test_an_unreachable_forge_leaves_deduplication_undecided_rather_than_raising(
    tmp_path: pathlib.Path,
) -> None:
    """A duplicate alert is a far better outcome than no alert at all."""
    undecided = find_open_alert(
        _alert(),
        repository="owner/repo",
        gh_executable=str(tmp_path / "not-installed"),
    )

    assert undecided is None


def test_the_entry_point_never_replaces_the_failure_it_is_reporting(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The run is already red and the operator needs the first error, not the second."""
    exit_code = main(
        [
            "--repository",
            "owner/repo",
            "--workflow",
            "release",
            "--run-id",
            "5",
            "--gh",
            str(tmp_path / "not-installed"),
        ],
    )

    assert exit_code == 0
    assert "::warning::" in capsys.readouterr().out
