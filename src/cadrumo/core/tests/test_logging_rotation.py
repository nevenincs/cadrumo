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
from pathlib import Path

import pytest

from .. import logging as _logging_mod
from ..config import override_settings
from ..directory_scan import scan_directory
from ..logging import configure_logging

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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
            backups = scan_directory(log_dir, pattern="cadrumo.log.*")
            assert backups, "writing past the cap must produce at least one rotated backup"
            assert len(backups) <= 2, "retained backups must not exceed cadrumo_log_file_backup_count"
    finally:
        _logging_mod._configured = False
        configure_logging()
        _logging_mod._configured = original_configured or True
