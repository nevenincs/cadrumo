"""Obtaining a logger is side-effect free; the first record still reaches cadrumo.log.

Each probe runs in a fresh interpreter because the in-process test session has
already configured logging, and the behaviour under test is what happens before
any host did.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ..type_guards import is_object_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE = """
import json, logging, sys
from pathlib import Path

from cadrumo.core import logging as project_logging

if sys.argv[2] == "deferred":
    project_logging.defer_logging_configuration()
logger = project_logging.get_logger("cadrumo.tests.first_record")
log_file = Path(sys.argv[1]) / "cadrumo.log"
before = {"exists": log_file.exists(), "configured": project_logging._configured}
logger.info("info record %s", "before-warning")
after_info = {"exists": log_file.exists(), "configured": project_logging._configured}
logger.warning("first record %s", "probe")
logging.shutdown()
print(json.dumps({"before": before, "after_info": after_info, "configured": project_logging._configured}))
"""

_RECORD_LINE = re.compile(
    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[WARNING\] cadrumo\.tests\.first_record: first record probe\n",
)


def _run_probe(tmp_path: Path, mode: str) -> tuple[dict[str, object], str, Path]:
    log_dir = tmp_path / "logs"
    env = {
        **os.environ,
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "root"),
        "CADRUMO_LOG_DIR": str(log_dir),
    }
    completed = run_audited_process(
        [sys.executable, "-c", _PROBE, str(log_dir), mode],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout))
    assert is_object_mapping(loaded)
    report = {str(key): value for key, value in loaded.items()}
    return report, str(completed.stderr), log_dir / "cadrumo.log"


def test_a_logger_obtained_before_configuration_writes_its_first_warning_to_the_log_file(tmp_path: Path) -> None:
    report, _, log_file = _run_probe(tmp_path, "normal")

    assert report["before"] == {"exists": False, "configured": False}
    assert report["after_info"] == {"exists": False, "configured": False}
    assert report["configured"] is True
    assert _RECORD_LINE.fullmatch(log_file.read_text(encoding="utf-8"))


def test_a_deferred_process_keeps_the_log_file_closed_and_reports_on_stderr(tmp_path: Path) -> None:
    report, stderr, log_file = _run_probe(tmp_path, "deferred")

    assert report["configured"] is False
    assert not log_file.exists()
    assert "first record probe" in stderr
