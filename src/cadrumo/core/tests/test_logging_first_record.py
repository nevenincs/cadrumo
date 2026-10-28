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
from cadrumo.tests.hang_guard import PROCESS_HANG_GUARD_SECONDS

from ..type_guards import is_object_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE = """
import json, sys
from contextlib import nullcontext
from pathlib import Path

from cadrumo.core import logging as project_logging
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS as HANG

def drain():
    if not project_logging.flush_logging(timeout=HANG):
        import faulthandler
        faulthandler.dump_traceback()
        print(project_logging.diagnostic_delivery_status(), file=sys.stderr)
        raise AssertionError('bounded diagnostic drain did not complete')

mode = sys.argv[2]
if mode in {"deferred", "late", "document-deferred"}:
    project_logging.defer_logging_configuration()
logger = project_logging.get_logger("cadrumo.tests.first_record")
log_file = Path(sys.argv[1]) / "cadrumo.log"
before = {"exists": log_file.exists(), "configured": project_logging._configured}
if mode == "overflow":
    for index in range(project_logging._PENDING_RECORD_LIMIT + 5):
        logger.info("held record %d", index)
    project_logging.configure_logging()
else:
    with project_logging.operator_document_output() if mode == "document-deferred" else nullcontext():
        logger.info("info record %s", "before-warning")
        if mode == "document-deferred":
            logger.warning("first record %s", "probe")
drain()
after_info = {"exists": log_file.exists(), "configured": project_logging._configured}
if mode in {"late", "document-deferred"}:
    project_logging.resume_logging_configuration()
    project_logging.configure_logging()
    if mode == "document-deferred":
        logger.warning("outside document scope")
elif mode != "overflow":
    logger.warning("first record %s", "probe")
drain()
project_logging.shutdown_logging()
print(json.dumps({"before": before, "after_info": after_info, "configured": project_logging._configured,
                  "dropped": project_logging.diagnostic_delivery_status()['records'].dropped}))
"""

# A foreign root handler stands for caplog or any handler a library attaches: it is
# not one of the sinks the first record installs, and must see each record once.
_DELIVERY_PROBE = """
import json, logging, sys
from cadrumo.core import logging as project_logging
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS as HANG

class Recorder(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())

mode, kind = sys.argv[2], sys.argv[3]
recorder = Recorder()
logging.getLogger().addHandler(recorder)
logger = (
    logging.getLogger("probe.delivery") if kind == "stdlib" else project_logging.get_logger("cadrumo.tests.delivery")
)
if mode == "orphan":
    logger.propagate = False
if mode == "deferred":
    project_logging.defer_logging_configuration()
if mode == "held":
    logger.info("held record")
logger.warning("first record")
assert project_logging.flush_logging(timeout=HANG), project_logging.diagnostic_delivery_status()
project_logging.shutdown_logging()
print(json.dumps({"delivered": recorder.messages, "configured": project_logging._configured}))
"""

_STAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
_CONTEXT = r' \| \{"process_id":\d+,"process_role":"python","thread_id":\d+,"thread_name":"MainThread"\}'
_INFO_LINE = rf"{_STAMP} \[INFO\] cadrumo\.tests\.first_record: info record before-warning{_CONTEXT}\n"
_WARNING_LINE = rf"{_STAMP} \[WARNING\] cadrumo\.tests\.first_record: first record probe{_CONTEXT}\n"


def _run_probe(
    tmp_path: Path, mode: str, *, probe: str = _PROBE, kind: str = "project"
) -> tuple[dict[str, object], str, Path]:
    log_dir = tmp_path / "logs"
    env = {
        **os.environ,
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "root"),
        "CADRUMO_LOG_DIR": str(log_dir),
    }
    if mode == "document-deferred":
        env["CADRUMO_LOG_STDERR_LEVEL"] = "WARNING"
    completed = run_audited_process(
        [sys.executable, "-c", probe, str(log_dir), mode, kind],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=PROCESS_HANG_GUARD_SECONDS,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout))
    assert is_object_mapping(loaded)
    report = {str(key): value for key, value in loaded.items()}
    return report, str(completed.stderr), log_dir / "cadrumo.log"


def test_a_warning_configures_logging_and_replays_the_records_held_before_it(tmp_path: Path) -> None:
    """The held info record and the configuring warning each reach the file exactly once."""
    report, _, log_file = _run_probe(tmp_path, "normal")

    assert report["before"] == {"exists": False, "configured": False}
    assert report["after_info"] == {"exists": False, "configured": False}
    assert report["configured"] is True
    assert re.fullmatch(_INFO_LINE + _WARNING_LINE, log_file.read_text(encoding="utf-8"))


def test_a_host_that_configures_late_still_writes_its_earlier_info_record(tmp_path: Path) -> None:
    report, _, log_file = _run_probe(tmp_path, "late")

    assert report["after_info"] == {"exists": False, "configured": False}
    assert report["configured"] is True
    assert re.fullmatch(_INFO_LINE, log_file.read_text(encoding="utf-8"))


def test_held_records_keep_only_the_newest_when_the_buffer_overflows(tmp_path: Path) -> None:
    report, _, log_file = _run_probe(tmp_path, "overflow")

    held = re.findall(r"held record (\d+)", log_file.read_text(encoding="utf-8"))
    assert [int(index) for index in held] == list(range(5, 205))
    assert report["dropped"] == 5


def test_a_deferred_process_keeps_the_log_file_closed_and_reports_on_stderr(tmp_path: Path) -> None:
    report, stderr, log_file = _run_probe(tmp_path, "deferred")

    assert report["configured"] is False
    assert not log_file.exists()
    assert "first record probe" in stderr


def test_document_diagnostics_defer_without_stderr_and_replay_after_scope_exit(tmp_path: Path) -> None:
    """A fresh JSON process preserves early diagnostics without falling back to stderr."""
    report, stderr, log_file = _run_probe(tmp_path, "document-deferred")

    assert report["after_info"] == {"exists": False, "configured": False}
    assert report["configured"] is True
    assert "first record probe" not in stderr
    assert "info record before-warning" not in stderr
    assert "outside document scope" in stderr
    assert re.fullmatch(
        _INFO_LINE
        + _WARNING_LINE
        + rf"{_STAMP} \[WARNING\] cadrumo\.tests\.first_record: outside document scope{_CONTEXT}\n",
        log_file.read_text(encoding="utf-8"),
    )


def _logged_messages(log_file: Path) -> list[str]:
    return [str(message) for message in re.findall(r"\] [\w.]+: (.+?) \| \{", log_file.read_text(encoding="utf-8"))]


@pytest.mark.parametrize("kind", ["stdlib", "project"])
def test_the_record_that_configures_logging_reaches_a_foreign_handler_and_the_file_once(
    tmp_path: Path, kind: str
) -> None:
    report, _, log_file = _run_probe(tmp_path, "first", probe=_DELIVERY_PROBE, kind=kind)

    assert report["configured"] is True
    assert report["delivered"] == ["first record"]
    assert _logged_messages(log_file) == ["first record"]


@pytest.mark.parametrize("kind", ["stdlib", "project"])
def test_a_held_record_is_replayed_to_the_sinks_without_reaching_a_foreign_handler_again(
    tmp_path: Path, kind: str
) -> None:
    report, _, log_file = _run_probe(tmp_path, "held", probe=_DELIVERY_PROBE, kind=kind)

    assert report["delivered"] == ["held record", "first record"]
    assert _logged_messages(log_file) == ["held record", "first record"]


@pytest.mark.parametrize("kind", ["stdlib", "project"])
def test_a_deferred_process_gives_a_warning_to_a_foreign_handler_and_stderr_once(tmp_path: Path, kind: str) -> None:
    report, stderr, log_file = _run_probe(tmp_path, "deferred", probe=_DELIVERY_PROBE, kind=kind)

    assert report["configured"] is False
    assert report["delivered"] == ["first record"]
    assert stderr.count("first record") == 1
    assert not log_file.exists()


@pytest.mark.parametrize("kind", ["stdlib", "project"])
def test_a_logger_without_any_handler_reaches_the_fallback_sink_once(tmp_path: Path, kind: str) -> None:
    report, stderr, _ = _run_probe(tmp_path, "orphan", probe=_DELIVERY_PROBE, kind=kind)

    assert report["delivered"] == []
    assert stderr.count("first record") == 1
