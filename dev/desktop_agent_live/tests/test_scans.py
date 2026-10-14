"""The lane's key scan and survivor check, on real files and real processes."""

from __future__ import annotations

import io
import os
import secrets
import sys
import zipfile
from pathlib import Path

import pytest

from ..scans import (
    KEY_PREFIX,
    READ_CHUNK_BYTES,
    ProcessRecord,
    descendants,
    process_table,
    scan_command_lines,
    scan_tree,
    survivors,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _planted() -> str:
    """A fake key: the real prefix and a random tail no finding may repeat."""
    return f"{KEY_PREFIX}test-{secrets.token_hex(12)}"


def test_a_clean_tree_passes(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "cadrumo.log").write_text("signed in; agent ready\n", encoding="utf-8")
    (tmp_path / "empty.bin").write_bytes(b"")
    result = scan_tree([tmp_path])
    assert result.clean


def test_a_planted_key_in_a_log_fails_and_is_not_repeated(tmp_path: Path) -> None:
    key = _planted()
    log = tmp_path / "logs" / "agent.log"
    log.parent.mkdir()
    log.write_text(f"request header x-api-key: {key}\n", encoding="utf-8")
    result = scan_tree([tmp_path])
    assert not result.clean
    assert [finding.encoding for finding in result.findings] == ["utf-8"]
    location = result.findings[0].location
    assert str(log) in location
    assert location.endswith("at byte 26")
    tail = key.removeprefix(KEY_PREFIX)
    assert all(tail not in finding.location for finding in result.findings)


def test_a_key_stored_as_utf16_is_found(tmp_path: Path) -> None:
    # Chromium keeps web storage values as UTF-16 text.
    (tmp_path / "000003.log").write_bytes(b"\x00\x01" + _planted().encode("utf-16-le"))
    result = scan_tree([tmp_path])
    assert [finding.encoding for finding in result.findings] == ["utf-16-le"]
    assert result.findings[0].location.endswith("at byte 2")


def test_a_key_across_a_read_boundary_is_found_once(tmp_path: Path) -> None:
    start = READ_CHUNK_BYTES - 3
    path = tmp_path / "large.bin"
    path.write_bytes(b"x" * start + _planted().encode("ascii") + b"y" * 64)
    result = scan_tree([tmp_path])
    assert [finding.location for finding in result.findings] == [f"file {path} at byte {start}"]


def test_a_key_compressed_inside_a_trace_archive_is_found(tmp_path: Path) -> None:
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as nested:
        nested.writestr("resources/page.html", f"<input value='{_planted()}'>")
    trace = tmp_path / "test-results" / "trace.zip"
    trace.parent.mkdir()
    with zipfile.ZipFile(trace, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trace.trace", f'{{"type":"action","value":"{_planted()}"}}')
        archive.writestr("nested.zip", inner.getvalue())
    result = scan_tree([tmp_path])
    locations = [finding.location for finding in result.findings]
    assert len(locations) == 2
    assert any(location.startswith(f"file {trace} member trace.trace at byte ") for location in locations)
    assert any(" member nested.zip member resources/page.html at byte " in location for location in locations)


@pytest.mark.windows_only
def test_a_file_that_cannot_be_read_is_not_clean(tmp_path: Path) -> None:
    import win32con
    import win32file

    locked = tmp_path / "locked.log"
    locked.write_text("held open without sharing\n", encoding="utf-8")
    handle = win32file.CreateFile(str(locked), win32con.GENERIC_READ, 0, None, win32con.OPEN_EXISTING, 0, None)
    try:
        result = scan_tree([tmp_path])
    finally:
        handle.Close()
    assert not result.findings
    assert result.unreadable == (f"file {locked}",)
    assert not result.clean


def _sleepers(scope: object, *arguments: str) -> list[int]:
    """Start one waiting interpreter per argument in ``scope``; return their PIDs."""
    from cadrumo_runtime.adapters.windows_process import WindowsProcessScope

    assert isinstance(scope, WindowsProcessScope)
    environment = {name: value for name, value in os.environ.items() if name.upper() in {"SYSTEMROOT", "PATH"}}
    return [
        scope.launch(
            executable=Path(sys.executable).resolve(),
            arguments=("-c", "import time; time.sleep(120)", argument),
            directory=Path.cwd(),
            environment=environment,
        ).pid
        for argument in arguments
    ]


def _record(table: dict[int, ProcessRecord], pid: int) -> ProcessRecord:
    record = table.get(pid)
    assert record is not None, f"WMI does not list process {pid}"
    return record


@pytest.mark.windows_only
def test_a_planted_key_on_a_command_line_names_only_the_process() -> None:
    from cadrumo_runtime.adapters.windows_process import WindowsProcessScope

    key = _planted()
    scope = WindowsProcessScope()
    try:
        planted, clean = _sleepers(scope, f"--token={key}", "--quiet")
        table = process_table()
        result = scan_command_lines([_record(table, planted), _record(table, clean)])
    finally:
        scope.terminate(timeout=15)
    assert [finding.location for finding in result.findings] == [
        f"command line of process {planted} ({_record(table, planted).name})"
    ]
    assert key.removeprefix(KEY_PREFIX) not in result.findings[0].location


@pytest.mark.windows_only
def test_a_started_process_left_running_is_a_survivor_until_it_ends() -> None:
    from cadrumo_runtime.adapters.windows_process import WindowsProcessScope

    scope = WindowsProcessScope()
    try:
        (owned,) = _sleepers(scope, "--left-running")
        table = process_table()
        started = {_record(table, pid) for pid in scope.active_process_ids()} | descendants(table, [os.getpid()])
        assert owned in {process.pid for process in started}
        assert owned in {process.pid for process in survivors(started, process_table())}
    finally:
        scope.terminate(timeout=15)
    assert owned not in {process.pid for process in survivors(started, process_table())}


def test_a_reused_pid_is_not_a_survivor() -> None:
    started = [ProcessRecord(pid=40, parent=4, name="cadrumo.exe", created="20261013100000.000000+120")]
    reused = {40: ProcessRecord(pid=40, parent=9, name="notepad.exe", created="20261013110000.000000+120")}
    assert survivors(started, reused) == []
    assert survivors(started, {40: started[0]}) == started


def test_a_parent_pid_reused_by_an_older_process_is_not_followed() -> None:
    table = {
        1: ProcessRecord(pid=1, parent=0, name="lane", created="20261013100000.000000+120"),
        2: ProcessRecord(pid=2, parent=1, name="cadrumo.exe", created="20261013100001.000000+120"),
        3: ProcessRecord(pid=3, parent=2, name="msedgewebview2.exe", created="20261013100002.000000+120"),
        4: ProcessRecord(pid=4, parent=1, name="older", created="20261013090000.000000+120"),
    }
    assert {process.pid for process in descendants(table, [1])} == {2, 3}
