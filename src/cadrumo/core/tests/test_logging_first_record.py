"""Obtaining a logger is side-effect free; early records still reach cadrumo.log.

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

removal = sys.argv[3]
if removal != "native":
    def remove_in_place(self, hdlr):
        with logging._lock:
            if hdlr in self.handlers:
                self.handlers.remove(hdlr)

    def remove_by_replacing(self, hdlr):
        with logging._lock:
            if hdlr in self.handlers:
                self.handlers = [handler for handler in self.handlers if handler is not hdlr]

    logging.Logger.removeHandler = remove_in_place if removal == "in-place" else remove_by_replacing

from cadrumo.core import logging as project_logging

mode = sys.argv[2]
if mode in {"deferred", "late"}:
    project_logging.defer_logging_configuration()
logger = project_logging.get_logger("cadrumo.tests.first_record")
log_file = Path(sys.argv[1]) / "cadrumo.log"
before = {"exists": log_file.exists(), "configured": project_logging._configured}
if mode == "overflow":
    for index in range(project_logging._PENDING_RECORD_LIMIT + 5):
        logger.info("held record %d", index)
    project_logging.configure_logging()
else:
    logger.info("info record %s", "before-warning")
after_info = {"exists": log_file.exists(), "configured": project_logging._configured}
if mode == "late":
    project_logging.resume_logging_configuration()
    project_logging.configure_logging()
elif mode != "overflow":
    logger.warning("first record %s", "probe")
logging.shutdown()
print(json.dumps({"before": before, "after_info": after_info, "configured": project_logging._configured}))
"""

_STAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}"
_INFO_LINE = rf"{_STAMP} \[INFO\] cadrumo\.tests\.first_record: info record before-warning\n"
_WARNING_LINE = rf"{_STAMP} \[WARNING\] cadrumo\.tests\.first_record: first record probe\n"


def _run_probe(tmp_path: Path, mode: str, *, removal: str = "native") -> tuple[dict[str, object], str, Path]:
    log_dir = tmp_path / "logs"
    env = {
        **os.environ,
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "root"),
        "CADRUMO_LOG_DIR": str(log_dir),
    }
    completed = run_audited_process(
        [sys.executable, "-c", _PROBE, str(log_dir), mode, removal],
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


def test_a_warning_configures_logging_and_replays_the_records_held_before_it(tmp_path: Path) -> None:
    report, _, log_file = _run_probe(tmp_path, "normal")

    assert report["before"] == {"exists": False, "configured": False}
    assert report["after_info"] == {"exists": False, "configured": False}
    assert report["configured"] is True
    assert re.fullmatch(_INFO_LINE + _WARNING_LINE, log_file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("removal", ["in-place", "replacing"])
def test_the_record_that_configures_logging_is_written_once_under_either_handler_removal(
    tmp_path: Path, removal: str
) -> None:
    """The configuring record reaches the file exactly once, however the handlers are removed.

    ``Logger.removeHandler`` mutated the handler list in place until CPython
    3.13.15 and 3.14.7, which replace the list instead (gh-79366); the
    interpreter under test has only one of the two, so the probe installs each
    in turn. Under replacement the record was lost from the file, which is how
    a crash's traceback went missing; handing it to every handler under
    in-place removal would write it twice.
    """
    _, _, log_file = _run_probe(tmp_path, "normal", removal=removal)

    assert re.fullmatch(_INFO_LINE + _WARNING_LINE, log_file.read_text(encoding="utf-8"))


def test_a_host_that_configures_late_still_writes_its_earlier_info_record(tmp_path: Path) -> None:
    report, _, log_file = _run_probe(tmp_path, "late")

    assert report["after_info"] == {"exists": False, "configured": False}
    assert report["configured"] is True
    assert re.fullmatch(_INFO_LINE, log_file.read_text(encoding="utf-8"))


def test_held_records_keep_only_the_newest_when_the_buffer_overflows(tmp_path: Path) -> None:
    _, _, log_file = _run_probe(tmp_path, "overflow")

    held = re.findall(r"held record (\d+)", log_file.read_text(encoding="utf-8"))
    assert [int(index) for index in held] == list(range(5, 205))


def test_a_deferred_process_keeps_the_log_file_closed_and_reports_on_stderr(tmp_path: Path) -> None:
    report, stderr, log_file = _run_probe(tmp_path, "deferred")

    assert report["configured"] is False
    assert not log_file.exists()
    assert "first record probe" in stderr
