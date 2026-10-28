"""Rotating diagnostic-log handler for cadrumo.log.

The diagnostic log formerly used a plain ``FileHandler`` and grew without
bound. It is now a size-capped ``RotatingFileHandler`` whose cap and backup
count are settings. These tests reconfigure logging against a temp log
directory and exercise the real handler, then restore the healthy default
configuration so sibling tests see an intact logger.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process
from cadrumo.tests.hang_guard import PROCESS_HANG_GUARD_SECONDS

from ..directory_scan import scan_directory
from ..log_file_handler import AnnouncingRotatingFileHandler

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_idle_writer_does_not_prevent_another_writer_rotating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "shared.log"
    handlers = [AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=12, encoding="utf-8") for _ in range(2)]
    expected = {f"unique-record-{index:02d}-padding-padding" for index in range(12)}
    try:
        for index, message in enumerate(sorted(expected)):
            handlers[index % 2].emit(logging.makeLogRecord({"msg": message}))
    finally:
        for handler in handlers:
            handler.close()
    records = [
        line
        for path in tmp_path.glob("shared.log*")
        if path.suffix != ".lock"
        for line in path.read_text().splitlines()
    ]
    assert len(records) == len(expected)
    assert set(records) == expected
    assert not capsys.readouterr().err


def test_process_writers_preserve_every_record_across_rollovers(tmp_path: Path) -> None:
    script = """
import logging, sys
from pathlib import Path
from cadrumo.core.log_file_handler import AnnouncingRotatingFileHandler
handler = AnnouncingRotatingFileHandler(Path(sys.argv[1]) / 'shared.log', maxBytes=200, backupCount=64, encoding='utf-8')
try:
    for index in range(40):
        handler.emit(logging.makeLogRecord({'msg': f'writer-{sys.argv[2]}-record-{index:03d}'}))
finally:
    handler.close()
"""
    children = []
    try:
        for writer in range(3):
            children.append(
                subprocess.Popen(  # noqa: S603 -- fixed Python probe and disposable log directory, no shell.
                    [sys.executable, "-c", script, str(tmp_path), str(writer)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        for child in children:
            stdout, stderr = child.communicate(timeout=PROCESS_HANG_GUARD_SECONDS)
            assert child.returncode == 0, (stdout, stderr)
            assert not stderr, stderr
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=PROCESS_HANG_GUARD_SECONDS)
    records = [
        line
        for path in tmp_path.glob("shared.log*")
        if path.suffix != ".lock"
        for line in path.read_text().splitlines()
    ]
    expected = {f"writer-{writer}-record-{index:03d}" for writer in range(3) for index in range(40)}
    assert len(records) == len(expected)
    assert set(records) == expected


def _write_configured_log(log_dir: Path, *, max_bytes: int, backups: int, records: int) -> None:
    """Configure under a context-local override and write after leaving that context."""
    script = """
import sys
from pathlib import Path
from cadrumo.core.config import override_settings
from cadrumo.core.logging import configure_logging, flush_logging, get_logger, shutdown_logging
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS as HANG
with override_settings(cadrumo_log_dir=Path(sys.argv[1]), cadrumo_log_file_max_bytes=int(sys.argv[2]),
                       cadrumo_log_file_backup_count=int(sys.argv[3]), cadrumo_log_stderr_level='CRITICAL'):
    configure_logging()
assert flush_logging(timeout=HANG), 'configuration did not complete'
logger = get_logger('cadrumo.tests.format')
for index in range(int(sys.argv[4])):
    logger.warning('format probe %03d %s', index, 'x' * 40)
assert flush_logging(timeout=HANG), 'log delivery did not complete'
shutdown_logging(timeout=2)
"""
    result = run_audited_process(
        [sys.executable, "-c", script, str(log_dir), str(max_bytes), str(backups), str(records)],
        capture_output=True,
        text=True,
        timeout=PROCESS_HANG_GUARD_SECONDS,
    )
    assert result.returncode == 0, result.stderr


def test_file_handler_is_rotating_with_settings_cap_and_backups(tmp_path: Path) -> None:
    log_dir = tmp_path / "probe-logs"
    _write_configured_log(log_dir, max_bytes=1024, backups=3, records=60)

    base = log_dir / "cadrumo.log"
    backups = [path for path in scan_directory(log_dir, pattern="cadrumo.log.*") if path.suffix[1:].isdigit()]
    assert base.exists(), "the context-local override must direct the file to this directory"
    assert len(backups) == 3, "rollover must retain the configured number of backups"
    assert all(path.stat().st_size <= 1024 for path in (base, *backups))


def test_log_rolls_over_and_bounds_backups(tmp_path: Path) -> None:
    log_dir = tmp_path / "probe-logs"
    _write_configured_log(log_dir, max_bytes=512, backups=2, records=60)

    base = log_dir / "cadrumo.log"
    backups = [path for path in scan_directory(log_dir, pattern="cadrumo.log.*") if path.suffix[1:].isdigit()]
    assert base.exists(), "the active log file must exist"
    assert len(backups) == 2, "rollover must retain the configured number of backups"
    assert all(path.stat().st_size <= 512 for path in (base, *backups))


def test_file_records_use_the_published_line_format(tmp_path: Path) -> None:
    log_dir = tmp_path / "format-logs"
    _write_configured_log(log_dir, max_bytes=1024, backups=3, records=1)
    lines = (log_dir / "cadrumo.log").read_text(encoding="utf-8").splitlines()
    line = re.compile(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z \[WARNING\] cadrumo\.tests\.format: format probe 000 x{40}"
        r' \| \{"process_id":\d+,"process_role":"python","thread_id":\d+,"thread_name":"MainThread"\}'
    )
    assert any(line.fullmatch(entry) for entry in lines), lines


@pytest.mark.parametrize("entry", ("first_record", "set_level"))
def test_context_override_reaches_implicit_configuration_after_scope_exit(tmp_path: Path, entry: str) -> None:
    log_dir = tmp_path / "implicit-logs"
    script = """
import logging, sys
from pathlib import Path
from cadrumo.core.config import override_settings
from cadrumo.core.logging import flush_logging, get_logger, set_log_level, shutdown_logging
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS as HANG
logger = get_logger('cadrumo.tests.context_handoff')
with override_settings(cadrumo_log_dir=Path(sys.argv[1]), cadrumo_log_stderr_level='CRITICAL',
                       cadrumo_log_file_level='CRITICAL'):
    if sys.argv[2] == 'first_record':
        logger.critical('context-first-record')
    else:
        set_log_level(logging.INFO, file_level=logging.DEBUG)
assert flush_logging(timeout=HANG), 'configuration did not complete'
if sys.argv[2] == 'set_level':
    logger.debug('context-level-change')
    assert flush_logging(timeout=HANG), 'level change did not reach the file'
shutdown_logging(timeout=2)
"""
    result = run_audited_process(
        [sys.executable, "-c", script, str(log_dir), entry],
        capture_output=True,
        text=True,
        timeout=PROCESS_HANG_GUARD_SECONDS,
    )
    assert result.returncode == 0, result.stderr
    output = (log_dir / "cadrumo.log").read_text(encoding="utf-8")
    assert ("context-first-record" if entry == "first_record" else "context-level-change") in output
