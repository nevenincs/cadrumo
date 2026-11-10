"""A sign-in attempt names why it failed, against a real contained helper process."""

from __future__ import annotations

import logging
import os
import sys
import textwrap
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import JsonValue

from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS
from cadrumo.tests.log_records import delivered_records

from ..auth_attempt import AuthAttempt
from ..launch_environment import system_environment

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_application,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job containment"),
]

_LOGGER = "cadrumo_agent_service.host.auth_attempt"
_HELPER = textwrap.dedent(
    """
    import json, sys
    mode = sys.argv[1]
    attempt = "00000000-0000-4000-8000-000000000001"

    def emit(event, **fields):
        frame = {"version": 1, "attempt_id": attempt, "provider": "example", "event": event, **fields}
        sys.stdout.write(json.dumps(frame) + "\\n")
        sys.stdout.flush()

    sys.stderr.write("STDERR-SECRET https://example.invalid/?code=PIPE-SECRET\\n")
    sys.stderr.flush()
    if mode == "garbage":
        sys.stdout.write("PIPE-SECRET not json\\n")
        sys.stdout.flush()
        sys.stdin.readline()
        sys.exit(0)
    emit("ready")
    sys.stdin.readline()
    if mode == "eof":
        sys.exit(0)
    emit("started")
    if mode == "failed":
        emit("failed", reason="provider_error", cause="cli_reported_error")
    elif mode == "cancelled_disconnected":
        emit("cancelled", reason="host_disconnected", cause="host_disconnected")
    else:
        emit("succeeded")
        if mode == "succeeded_nonzero":
            sys.exit(3)
    sys.exit(0)
    """
)


def _attempt(tmp_path: Path, mode: str, *, confirm: Callable[[], tuple[bool, str | None]] | None = None) -> AuthAttempt:
    script = tmp_path / "helper.py"
    script.write_text(_HELPER, encoding="utf-8", newline="\n")
    return AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=Path(sys.executable),
        arguments=(str(script), mode),
        directory=tmp_path,
        environment=system_environment(os.environ),
        valid=lambda: True,
        confirm=confirm,
    )


def _settled(attempt: AuthAttempt) -> dict[str, JsonValue]:
    deadline = time.monotonic() + HANG_GUARD_SECONDS
    while attempt.active and time.monotonic() < deadline:
        time.sleep(0.05)
    attempt.close()
    return attempt.observe()


def _messages(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(record.levelno, record.getMessage()) for record in delivered_records(caplog, _LOGGER)]


def test_a_helper_failure_reaches_the_snapshot_and_the_log_with_its_cause(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        answer = _settled(_attempt(tmp_path, "failed"))
        records = _messages(caplog)
    assert answer["event"] == "failed"
    assert answer["reason"] == "provider_error"
    assert answer["cause"] == "cli_reported_error"
    assert answer["next_step"] == "console_sign_in"
    ((level, message),) = records
    assert level == logging.WARNING
    assert "cause=cli_reported_error" in message
    assert "SECRET" not in message


@pytest.mark.parametrize(
    ("mode", "cause", "next_step"),
    [
        ("eof", "helper_ended_without_result", "console_sign_in"),
        ("garbage", "helper_output_invalid", "update_app"),
    ],
)
def test_a_helper_stream_that_ends_or_breaks_is_named(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, mode: str, cause: str, next_step: str
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        answer = _settled(_attempt(tmp_path, mode))
        records = _messages(caplog)
    assert (answer["event"], answer["reason"], answer["cause"], answer["next_step"]) == (
        "failed",
        "provider_error",
        cause,
        next_step,
    )
    assert records
    assert all(level == logging.WARNING and f"cause={cause}" in message for level, message in records)
    assert "SECRET" not in " ".join(message for _level, message in records)


def test_a_helper_that_cannot_start_is_named(tmp_path: Path) -> None:
    attempt = AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=tmp_path / "absent.exe",
        arguments=(),
        directory=tmp_path,
        environment=system_environment(os.environ),
        valid=lambda: True,
    )
    answer = _settled(attempt)
    assert (answer["event"], answer["reason"], answer["cause"]) == ("failed", "provider_error", "helper_start_failed")


def test_a_disconnected_helper_cancellation_keeps_its_cause_and_a_retry(tmp_path: Path) -> None:
    answer = _settled(_attempt(tmp_path, "cancelled_disconnected"))
    assert (answer["event"], answer["cause"], answer["next_step"]) == ("cancelled", "host_disconnected", "retry")


def test_success_with_a_nonzero_exit_is_named(tmp_path: Path) -> None:
    answer = _settled(_attempt(tmp_path, "succeeded_nonzero"))
    assert (answer["event"], answer["reason"], answer["cause"]) == ("failed", "provider_error", "helper_exit_nonzero")
    assert answer["next_step"] == "console_sign_in"


def test_success_is_confirmed_by_a_fresh_status_read(tmp_path: Path) -> None:
    reads: list[str] = []

    def confirm() -> tuple[bool, str | None]:
        reads.append("read")
        return True, None

    answer = _settled(_attempt(tmp_path, "succeeded", confirm=confirm))
    assert answer["event"] == "succeeded"
    assert "cause" not in answer
    assert reads == ["read"]


def test_success_the_status_read_does_not_confirm_fails_with_both_causes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        answer = _settled(_attempt(tmp_path, "succeeded", confirm=lambda: (False, "probe_timed_out")))
        records = _messages(caplog)
    assert answer["event"] == "failed"
    assert answer["reason"] == "provider_error"
    assert answer["cause"] == "status_not_confirmed"
    assert answer["status_cause"] == "probe_timed_out"
    assert answer["next_step"] == "console_sign_in"
    ((level, message),) = records
    assert level == logging.WARNING
    assert "cause=status_not_confirmed" in message
    assert "status_cause=probe_timed_out" in message


def test_success_with_a_signed_out_status_and_no_probe_cause_still_fails(tmp_path: Path) -> None:
    answer = _settled(_attempt(tmp_path, "succeeded", confirm=lambda: (False, None)))
    assert (answer["event"], answer["cause"]) == ("failed", "status_not_confirmed")
    assert "status_cause" not in answer


def test_a_confirmation_that_raises_is_a_status_read_failure_never_a_success(tmp_path: Path) -> None:
    def confirm() -> tuple[bool, str | None]:
        raise RuntimeError("PRIVATE-DETAIL")

    answer = _settled(_attempt(tmp_path, "succeeded", confirm=confirm))
    assert (answer["event"], answer["cause"], answer["status_cause"]) == (
        "failed",
        "status_not_confirmed",
        "status_read_failed",
    )
    assert "PRIVATE-DETAIL" not in str(answer)


def test_a_helper_that_failed_is_never_confirmed(tmp_path: Path) -> None:
    reads: list[str] = []

    def confirm() -> tuple[bool, str | None]:
        reads.append("read")
        return True, None

    answer = _settled(_attempt(tmp_path, "failed", confirm=confirm))
    assert answer["event"] == "failed"
    assert reads == []


_WITHDRAWING_HELPER = textwrap.dedent(
    """
    import json, pathlib, sys, time
    mode, sentinel = sys.argv[1], pathlib.Path(sys.argv[2])
    attempt = "00000000-0000-4000-8000-000000000001"

    def emit(event, **fields):
        frame = {"version": 1, "attempt_id": attempt, "provider": "example", "event": event, **fields}
        sys.stdout.write(json.dumps(frame) + "\\n")
        sys.stdout.flush()

    emit("ready")
    sys.stdin.readline()
    if mode == "withdrawn_before_started":
        sentinel.write_text("withdrawn", encoding="utf-8")
        emit("started")
        sys.stdin.readline()
        sys.exit(0)
    emit("started")
    emit("succeeded")
    if mode == "withdrawn_after_success":
        time.sleep(0.5)
        sentinel.write_text("withdrawn", encoding="utf-8")
    sys.exit(0)
    """
)


def _withdrawing_attempt(
    tmp_path: Path,
    mode: str,
    *,
    confirm: Callable[[], tuple[bool, str | None]] | None = None,
    prepare: Callable[[], None] | None = None,
) -> tuple[AuthAttempt, Path]:
    """An attempt whose authority holds until the sentinel file exists."""
    script = tmp_path / "withdrawing_helper.py"
    script.write_text(_WITHDRAWING_HELPER, encoding="utf-8", newline="\n")
    sentinel = tmp_path / "withdrawn"
    attempt = AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=Path(sys.executable),
        arguments=(str(script), mode, str(sentinel)),
        directory=tmp_path,
        environment=system_environment(os.environ),
        valid=lambda: not sentinel.exists(),
        confirm=confirm,
        prepare=prepare,
    )
    return attempt, sentinel


def _settlement(attempt: AuthAttempt, caplog: pytest.LogCaptureFixture) -> dict[str, str]:
    """Read the settled outcome from its log line; a withdrawn attempt's observe() answers only a cancellation."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        deadline = time.monotonic() + HANG_GUARD_SECONDS
        while attempt.active and time.monotonic() < deadline:
            time.sleep(0.05)
        attempt.close()
        ((_level, message),) = _messages(caplog)
    return dict(field.split("=", 1) for field in message.split(" ") if "=" in field)


def test_success_without_a_confirmation_reader_is_served_as_success(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    attempt, _sentinel = _withdrawing_attempt(tmp_path, "succeeded")
    settled = _settlement(attempt, caplog)
    assert (settled["event"], settled["reason"], settled["cause"]) == ("succeeded", "none", "none")
    assert attempt.observe()["event"] == "succeeded"


def test_success_after_authority_was_withdrawn_is_cancelled_and_never_confirmed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    reads: list[str] = []

    def confirm() -> tuple[bool, str | None]:
        reads.append("read")
        return True, None

    attempt, sentinel = _withdrawing_attempt(tmp_path, "withdrawn_after_success", confirm=confirm)
    settled = _settlement(attempt, caplog)
    assert sentinel.exists()
    assert (settled["event"], settled["reason"], settled["cause"], settled["status_cause"]) == (
        "cancelled",
        "none",
        "none",
        "none",
    )
    assert reads == []


def test_authority_withdrawn_during_the_confirmation_cancels_and_keeps_the_status_cause(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    sentinel = tmp_path / "withdrawn"

    def confirm() -> tuple[bool, str | None]:
        sentinel.write_text("withdrawn", encoding="utf-8")
        return True, "probe_timed_out"

    attempt, _sentinel = _withdrawing_attempt(tmp_path, "succeeded", confirm=confirm)
    settled = _settlement(attempt, caplog)
    assert (settled["event"], settled["reason"], settled["cause"], settled["status_cause"]) == (
        "cancelled",
        "none",
        "none",
        "probe_timed_out",
    )


def test_authority_withdrawn_by_the_preparation_cancels_before_the_helper_starts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    sentinel = tmp_path / "withdrawn"

    def prepare() -> None:
        sentinel.write_text("withdrawn", encoding="utf-8")

    attempt, _sentinel = _withdrawing_attempt(tmp_path, "succeeded", prepare=prepare)
    settled = _settlement(attempt, caplog)
    assert (settled["event"], settled["reason"], settled["cause"]) == ("cancelled", "none", "none")
    assert settled["cleanup_confirmed"] == "True"


def test_a_failing_preparation_is_a_failed_cleanup_before_the_helper_starts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def prepare() -> None:
        raise RuntimeError("PRIVATE-DETAIL")

    attempt, _sentinel = _withdrawing_attempt(tmp_path, "succeeded", prepare=prepare)
    settled = _settlement(attempt, caplog)
    assert (settled["event"], settled["reason"], settled["cause"]) == ("failed", "cleanup_failed", "agent_stop_failed")
    answer = attempt.observe()
    assert (answer["event"], answer["reason"], answer["cause"]) == ("failed", "cleanup_failed", "agent_stop_failed")
    assert "PRIVATE-DETAIL" not in str(answer)


def test_an_event_published_after_authority_was_withdrawn_cancels_without_a_cause(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    attempt, sentinel = _withdrawing_attempt(tmp_path, "withdrawn_before_started")
    settled = _settlement(attempt, caplog)
    assert sentinel.exists()
    assert (settled["event"], settled["reason"], settled["cause"]) == ("cancelled", "none", "none")
    assert settled["cleanup_confirmed"] == "True"
