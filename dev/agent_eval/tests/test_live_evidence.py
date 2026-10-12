"""A failed live run keeps scrubbed evidence, a passing one keeps nothing, and a secret is never kept.

Each case builds a real run directory with a log, control files and a planted
secret and runs the real keep-and-remove path; the stream decoder is checked
against the shapes the packaged command line produces.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..live import isolated_host
from ..live.capture import Scrubber
from ..live.evidence import settle_run_root
from ..live.isolated_host import (
    FailedCall,
    PackageHost,
    RunDirectory,
    command_name,
    decode_envelope,
    new_run_directory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PLANTED = "Live-eval-planted-password-value!"
_REFUSAL = {"status": "error", "error": {"code": "REFUSED", "context": {"reason": "no_session"}}}


def _failed_run(base: Path) -> RunDirectory:
    run = new_run_directory(base)
    (run.root / "logs").mkdir()
    (run.root / "logs" / "cadrumo.log").write_text("runtime started\nconnection closed by peer\n", encoding="utf-8")
    (run.root / "profile.sqlite").write_bytes(b"encrypted-database-bytes")
    (run.root / "secret.key").write_bytes(b"key-material")
    (run.control / "ready.json").write_text('{"event": "ready"}', encoding="utf-8")
    (run.control / "stopped.json").write_text('{"code": 1, "event": "runtime_exited"}', encoding="utf-8")
    (run.control / "runtime.stderr").write_text("fatal: listener closed\n", encoding="utf-8")
    (run.control / "stop.partial").write_text("not kept", encoding="utf-8")
    return run


def _call() -> FailedCall:
    return FailedCall("config login", 1, "stdout", '{"status": "error"}', "boom")


def test_a_harness_error_keeps_the_scrubbed_log_and_the_receipt_names_it(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    run = _failed_run(base)
    (run.root / "logs" / "cadrumo.log").write_text(f"login with {_PLANTED} failed\n", encoding="utf-8")
    evidence = tmp_path / "capture" / "run-0-evidence"
    entry = settle_run_root(
        run,
        base,
        keep_reason="harness_error",
        directory=evidence,
        scrubber=Scrubber([("profile_password", _PLANTED)]),
        failures=[_call()],
    )
    assert entry is not None
    assert entry["kept"] is True
    assert entry["directory"] == "run-0-evidence"
    assert "logs-cadrumo.log" in entry["files"]
    kept = (evidence / "logs-cadrumo.log").read_text(encoding="utf-8")
    assert "[scrubbed:profile_password]" in kept
    assert _PLANTED not in kept
    assert json.loads((evidence / "control-stopped.json").read_text(encoding="utf-8"))["code"] == 1
    assert (evidence / "control-runtime.stderr").read_text(encoding="utf-8").startswith("fatal")
    calls = json.loads((evidence / "failed-cli-calls.json").read_text(encoding="utf-8"))
    assert calls[0]["command"] == "config login"
    assert calls[0]["returncode"] == 1
    assert not run.path.exists()


def test_only_logs_and_named_control_files_are_ever_kept(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    run = _failed_run(base)
    evidence = tmp_path / "capture" / "run-0-evidence"
    settle_run_root(run, base, keep_reason="product_finding", directory=evidence, scrubber=Scrubber(()), failures=[])
    assert sorted(path.name for path in evidence.iterdir()) == [
        "control-ready.json",
        "control-runtime.stderr",
        "control-stopped.json",
        "failed-cli-calls.json",
        "logs-cadrumo.log",
    ]


def test_a_planted_secret_the_scrubber_does_not_know_is_refused_and_nothing_is_kept(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    run = _failed_run(base)
    (run.root / "logs" / "cadrumo.log").write_text('{"password": "hunter2-planted"}\n', encoding="utf-8")
    evidence = tmp_path / "capture" / "run-0-evidence"
    entry = settle_run_root(
        run, base, keep_reason="harness_error", directory=evidence, scrubber=Scrubber(()), failures=[_call()]
    )
    assert entry is not None
    assert entry["kept"] is False
    assert entry["withheld"] == "residual_scan_failed"
    assert entry["refused_files"] == ["logs-cadrumo.log"]
    assert not evidence.exists()
    assert "hunter2-planted" not in json.dumps(entry)
    assert not run.path.exists()


def test_a_secret_in_a_recorded_cli_head_is_refused(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    run = _failed_run(base)
    evidence = tmp_path / "capture" / "run-0-evidence"
    leaking = FailedCall("config login", 1, "stderr", "", "sk-ant-api03-plantedplantedplanted")
    entry = settle_run_root(
        run, base, keep_reason="harness_error", directory=evidence, scrubber=Scrubber(()), failures=[leaking]
    )
    assert entry is not None
    assert entry["kept"] is False
    assert entry["refused_files"] == ["failed-cli-calls.json"]
    assert not evidence.exists()


@pytest.mark.parametrize("keep_reason", [None, "agent_failure"])
def test_a_pass_or_agent_failure_deletes_the_run_root_and_keeps_nothing(
    tmp_path: Path, keep_reason: str | None
) -> None:
    base = tmp_path / "runs"
    run = _failed_run(base)
    evidence = tmp_path / "capture" / "run-0-evidence"
    entry = settle_run_root(
        run, base, keep_reason=keep_reason, directory=evidence, scrubber=Scrubber(()), failures=[_call()]
    )
    assert entry is None
    assert not run.path.exists()
    assert not evidence.exists()


def test_a_refusal_on_stdout_with_exit_one_decodes_and_names_its_stream() -> None:
    document, stream = decode_envelope(json.dumps(_REFUSAL), "", 1)
    assert document == _REFUSAL
    assert stream == "stdout"


def test_a_refusal_on_stderr_still_decodes_and_names_its_stream() -> None:
    document, stream = decode_envelope("", json.dumps(_REFUSAL), 1)
    assert document == _REFUSAL
    assert stream == "stderr"


def test_an_envelope_after_a_notice_line_decodes() -> None:
    document, stream = decode_envelope("starting\n" + json.dumps(_REFUSAL) + "\n", "warning text", 1)
    assert document == _REFUSAL
    assert stream == "stdout"


def test_neither_stream_decoding_is_reported_as_none() -> None:
    document, stream = decode_envelope("plain text", "Traceback (most recent call last)", 1)
    assert document is None
    assert stream == "none"


def test_json_that_is_not_an_envelope_object_does_not_decode() -> None:
    assert decode_envelope("[1, 2]", "42", 1) == (None, "none")


def test_the_command_name_stops_at_the_first_value_or_option() -> None:
    assert command_name(("config", "profile", "create", "Live eval abc123")) == "config profile create"
    assert command_name(("config", "login")) == "config login"
    assert command_name(("config", "--format")) == "config"
    assert command_name(("app", "Secret Value")) == "app"


class _Completed:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, completed: _Completed) -> PackageHost:
    monkeypatch.setattr(isolated_host, "run_command", lambda *_args, **_kwargs: completed)
    return PackageHost(
        tmp_path / "package",
        new_run_directory(tmp_path / "runs"),
        ambient={},
        scrubber=Scrubber([("profile_password", _PLANTED)]),
    )


def test_an_undecodable_call_carries_scrubbed_heads_and_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = _host(tmp_path, monkeypatch, _Completed(1, "", f"Traceback ... {_PLANTED}"))
    result = host.cli("config", "login")
    assert result.error_tokens == ("UNDECODABLE_ENVELOPE", "exit_1")
    assert result.stream == "none"
    assert "[scrubbed:profile_password]" in result.stderr_head
    assert _PLANTED not in json.dumps(result.document)
    assert [(call.command, call.returncode) for call in host.failed_calls] == [("config login", 1)]


def test_a_refusal_on_stdout_with_exit_one_is_not_undecodable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = _host(tmp_path, monkeypatch, _Completed(1, json.dumps(_REFUSAL), ""))
    result = host.cli("config", "login")
    assert result.error_tokens == ("REFUSED", "no_session")
    assert result.stream == "stdout"
