"""Rotating diagnostic-log handler for cadrumo.log.

The diagnostic log formerly used a plain ``FileHandler`` and grew without
bound. It is now a size-capped ``RotatingFileHandler`` whose cap and backup
count are settings. These tests reconfigure logging against a temp log
directory and exercise the real handler, then restore the healthy default
configuration so sibling tests see an intact logger.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import subprocess
import sys
from pathlib import Path

import pytest

from .. import logging as _logging_mod
from ..config import override_settings
from ..diagnostic_log import DiagnosticFormatter
from ..directory_scan import scan_directory
from ..log_file_handler import AnnouncingRotatingFileHandler
from ..logging import LOG_FILE_FORMAT, configure_logging

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
            stdout, stderr = child.communicate(timeout=30)
            assert child.returncode == 0, (stdout, stderr)
            assert not stderr, stderr
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=10)
    records = [
        line
        for path in tmp_path.glob("shared.log*")
        if path.suffix != ".lock"
        for line in path.read_text().splitlines()
    ]
    expected = {f"writer-{writer}-record-{index:03d}" for writer in range(3) for index in range(40)}
    assert len(records) == len(expected)
    assert set(records) == expected


def _rotating_file_handlers(log_dir: Path) -> list[logging.handlers.RotatingFileHandler]:
    root = logging.getLogger()
    return [
        handler
        for handler in root.handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler) and Path(handler.baseFilename).parent == log_dir
    ]


def test_file_handler_is_rotating_with_settings_cap_and_backups(tmp_path: Path) -> None:
    log_dir = tmp_path / "probe-logs"
    original_configured = _logging_mod._configured
    try:
        _logging_mod._configured = False
        with override_settings(
            cadrumo_log_dir=log_dir,
            cadrumo_log_file_max_bytes=1024,
            cadrumo_log_file_backup_count=3,
        ):
            configure_logging()
            handlers = _rotating_file_handlers(log_dir)
            assert len(handlers) == 1, "exactly one rotating file handler must target the log dir"
            handler = handlers[0]
            assert handler.maxBytes == 1024
            assert handler.backupCount == 3
    finally:
        _logging_mod._configured = False
        configure_logging()
        _logging_mod._configured = original_configured or True


def test_log_rolls_over_and_bounds_backups(tmp_path: Path) -> None:
    log_dir = tmp_path / "probe-logs"
    original_configured = _logging_mod._configured
    try:
        _logging_mod._configured = False
        with override_settings(
            cadrumo_log_dir=log_dir,
            cadrumo_log_file_max_bytes=512,
            cadrumo_log_file_backup_count=2,
        ):
            configure_logging()
            emitter = logging.getLogger("cadrumo.tests.rotation")
            for index in range(400):
                emitter.warning("rotation probe record %d with padding %s", index, "x" * 40)
            for handler in _rotating_file_handlers(log_dir):
                handler.flush()

            base = log_dir / "cadrumo.log"
            assert base.exists(), "the active log file must exist"
            # Rollover produced at least one backup, and the backup count is
            # bounded by the configured ceiling (no unbounded growth).
            backups = [path for path in scan_directory(log_dir, pattern="cadrumo.log.*") if path.suffix[1:].isdigit()]
            assert backups, "writing past the cap must produce at least one rotated backup"
            assert len(backups) <= 2, "retained backups must not exceed cadrumo_log_file_backup_count"
    finally:
        _logging_mod._configured = False
        configure_logging()
        _logging_mod._configured = original_configured or True


def test_file_records_use_the_published_line_format(tmp_path: Path) -> None:
    log_dir = tmp_path / "format-logs"
    original_configured = _logging_mod._configured
    try:
        _logging_mod._configured = False
        with override_settings(cadrumo_log_dir=log_dir):
            configure_logging()
            handlers = _rotating_file_handlers(log_dir)
            assert len(handlers) == 1
            formatter = handlers[0].formatter
            assert formatter is not None
            probe = logging.LogRecord(
                "cadrumo.tests.format", logging.ERROR, __file__, 1, "rendered %s", ("probe",), None
            )
            assert formatter.format(probe) == DiagnosticFormatter(LOG_FILE_FORMAT).format(probe)
            logging.getLogger("cadrumo.tests.format").warning("format probe")
            handlers[0].flush()
            lines = (log_dir / "cadrumo.log").read_text(encoding="utf-8").splitlines()
    finally:
        _logging_mod._configured = False
        configure_logging()
        _logging_mod._configured = original_configured or True
    line = re.compile(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z \[WARNING\] cadrumo\.tests\.format: format probe"
        r' \| \{"process_id":\d+,"process_role":"python","thread_id":\d+,"thread_name":"MainThread"\}'
    )
    assert any(line.fullmatch(entry) for entry in lines), lines
