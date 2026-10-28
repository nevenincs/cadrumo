"""Whole logging-pipeline probes run in disposable interpreters."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS

from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_location
from ..type_guards import is_object_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A probe waits for events and for work held behind a sink; none of that is timed. A probe
# holds several such waits one after another, so its process bound is a multiple of one.
_PROCESS_HANG_SECONDS = HANG_GUARD_SECONDS * 3

_SETUP = """
import json, logging, threading, time
from cadrumo.core import logging as project
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS as HANG, finishes
project.configure_logging()
assert project.flush_logging(timeout=HANG)
logger = project.get_logger('cadrumo.tests.dispatch_probe')
"""


def _log_directory(tmp_path: Path) -> Path:
    return tmp_path / "logs"


def _log_file(tmp_path: Path) -> Path:
    """Return the file a probe's diagnostics reach, named as the storage taxonomy declares it."""
    return _log_directory(tmp_path) / Path(storage_location(StorageCategory.LOG_FILE).subpath).name


def _probe(tmp_path: Path, body: str) -> dict[str, float | int]:
    completed = run_audited_process(
        [sys.executable, "-c", _SETUP + body],
        env={
            **os.environ,
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "root"),
            "CADRUMO_LOG_DIR": str(_log_directory(tmp_path)),
            "CADRUMO_LOG_STDERR_LEVEL": "WARNING",
        },
        capture_output=True,
        text=True,
        timeout=_PROCESS_HANG_SECONDS,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout))
    assert is_object_mapping(loaded)
    result: dict[str, float | int] = {}
    for key, value in loaded.items():
        assert isinstance(key, str) and isinstance(value, float | int)
        result[key] = value
    return result


@pytest.mark.parametrize("fallback", (False, True))
def test_unread_stderr_pipe_does_not_freeze_interpreter_exit(tmp_path: Path, fallback: bool) -> None:
    script = f"""
import sys
sys.path.insert(0, {str(Path(__file__).parents[3])!r})
import json, logging, os, time
from cadrumo.core import logging as project
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS as HANG, finishes
read_end, write_end = os.pipe()
os.dup2(write_end, 2)
os.close(write_end)
assert type(sys.stderr.buffer).__name__ == 'BufferedWriter'
project.configure_logging()
assert project.flush_logging(timeout=HANG)
logger = project.get_logger('cadrumo.tests.unread_stderr')
if {fallback!r}:
    logger.propagate = False
for index in range(128):
    logger.warning('unread stderr %d %s', index, 'x' * 800)
def blocked():
    return any(status.pending > 5 and status.active_seconds > .1
               for name, status in project.diagnostic_delivery_status().items() if name != 'records')
deadline = time.monotonic() + HANG
while time.monotonic() < deadline:
    if blocked():
        break
    time.sleep(.01)
else:
    raise AssertionError('stderr sink did not block')
finishes(lambda: project.shutdown_logging(timeout=.05), what='shutdown behind a blocked stderr sink')
print(json.dumps({{'returned': True, 'still_blocked': blocked()}}), flush=True)
"""
    completed = run_audited_process(
        [sys.executable, "-I", "-c", script],
        env={
            **os.environ,
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "root"),
            "CADRUMO_LOG_DIR": str(_log_directory(tmp_path)),
            "CADRUMO_LOG_STDERR_LEVEL": "WARNING",
        },
        capture_output=True,
        text=True,
        timeout=_PROCESS_HANG_SECONDS,
    )
    assert completed.returncode == 0, completed.stderr
    # Shutdown returned while the sink was still held, so it did not wait for the sink, and
    # the interpreter then exited with the sink still held.
    assert json.loads(str(completed.stdout)) == {"returned": True, "still_blocked": True}


@pytest.mark.parametrize("foreign", (False, True))
def test_blocked_redaction_does_not_block_logging_or_grow_the_queue(tmp_path: Path, foreign: bool) -> None:
    result = _probe(
        tmp_path,
        ("logger = logging.getLogger('synthetic.third_party')\n" if foreign else "")
        + """
entered, release = threading.Event(), threading.Event()
original = project._scrub_record_message_and_args
def scrub(record):
    if record.msg == 'held-redaction':
        entered.set()
        assert release.wait(HANG)
    original(record)
project._scrub_record_message_and_args = scrub
try:
    logger.warning('held-redaction')
    assert entered.wait(HANG)
    def produce():
        for index in range(10000):
            logger.info('queued record %d', index)
    # The redaction is released only afterwards, so producers that waited for it never finish.
    finishes(produce, what='producers logging behind a held redaction')
    status = project.diagnostic_delivery_status()['records']
    assert status.pending <= 8193 and status.dropped > 0
    assert status.retained_weight <= 32 * 1024 * 1024
    assert not project.flush_logging(timeout=0.01)
finally:
    release.set()
assert project.flush_logging(timeout=HANG)
print(json.dumps({'dropped': status.dropped}))
""",
    )
    assert int(result["dropped"]) > 0


def test_a_blocked_file_sink_leaves_stderr_and_producers_working(tmp_path: Path) -> None:
    result = _probe(
        tmp_path,
        """
entered, release, stderr_ready = threading.Event(), threading.Event(), threading.Event()
wrappers = [handler for handler in logging.getLogger().handlers if isinstance(handler, project._AsyncDiagnosticHandler)]
file = next(handler.sink for handler in wrappers if isinstance(handler.sink, logging.FileHandler))
stderr = next(handler.sink for handler in wrappers if not isinstance(handler.sink, logging.FileHandler))
file_emit, stderr_emit = file.emit, stderr.emit
def blocked(record):
    entered.set()
    assert release.wait(HANG)
    file_emit(record)
def observed(record):
    stderr_emit(record)
    stderr_ready.set()
file.emit, stderr.emit = blocked, observed
try:
    logger.warning('sink-isolation marker')
    assert entered.wait(HANG) and stderr_ready.wait(HANG)
    def produce():
        for index in range(2000):
            logger.info('sink queued record %d', index)
    # The file sink is released only afterwards, so producers that waited for it never finish.
    finishes(produce, what='producers logging behind a blocked file sink')
    assert not project.flush_logging(timeout=0.02)
finally:
    release.set()
assert project.flush_logging(timeout=HANG)
print(json.dumps({'completed': True}))
""",
    )
    assert result == {"completed": True}


def test_stuck_sink_cannot_prevent_process_shutdown(tmp_path: Path) -> None:
    result = _probe(
        tmp_path,
        """
entered, never = threading.Event(), threading.Event()
file = next(handler.sink for handler in logging.getLogger().handlers
            if isinstance(handler, project._AsyncDiagnosticHandler) and isinstance(handler.sink, logging.FileHandler))
def blocked(record):
    entered.set()
    never.wait(3600)
file.emit = blocked
logger.warning('shutdown probe')
assert entered.wait(HANG)
finishes(lambda: project.shutdown_logging(timeout=0.05), what='shutdown behind a stuck sink')
print(json.dumps({'returned': True}))
""",
    )
    assert result == {"returned": True}


def test_opaque_and_exception_hooks_never_run_on_the_producer_and_forged_flags_do_not_bypass_redaction(
    tmp_path: Path,
) -> None:
    _probe(
        tmp_path,
        """
class Opaque:
    def __str__(self):
        raise AssertionError('application rendering hook invoked')
    __repr__ = __str__
class Fault(Exception):
    __str__ = Opaque.__str__
logger.warning('opaque %s', Opaque())
logger.warning('password=synthetic-secret', extra={'_cadrumo_scrubbed': True})
try:
    raise Fault('password=synthetic-secret')
except Fault:
    logger.exception('safe exception snapshot')
assert project.flush_logging(timeout=HANG)
print(json.dumps({'done': True}))
""",
    )
    text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "opaque <omitted:opaque-value>" in text
    assert "Fault:" in text and "safe exception snapshot" in text
    assert "synthetic-secret" not in text


def test_format_sizes_large_values_and_exception_causes_are_bounded(tmp_path: Path) -> None:
    _probe(
        tmp_path,
        """
logger.warning('%1000000000000s', 'synthetic')
logger.warning('%.*s', 1000000000000, 'synthetic')
logger.warning('large value %s', 1 << 1000000)
logger.warning('mapping %s', {'x' * 1000000: 'synthetic'})
try:
    try:
        raise OSError('underlying synthetic fault')
    except OSError as cause:
        raise RuntimeError('outer synthetic fault') from cause
except RuntimeError:
    logger.exception('exception chain probe')
logger.warning('delivery still works')
assert project.flush_logging(timeout=HANG)
assert project.diagnostic_delivery_status()['records'].failed == 0
print(json.dumps({'done': True}))
""",
    )
    text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert text.count("<omitted:oversized-format>") == 2
    assert "<omitted:oversized-number>" in text
    assert "OSError:" in text and "RuntimeError:" in text and "Exception cause:" in text
    assert "delivery still works" in text and len(text) < 16384


def test_level_changes_admit_the_immediately_following_record(tmp_path: Path) -> None:
    _probe(
        tmp_path,
        """
logging.getLogger().setLevel(logging.CRITICAL)
project.set_log_level(logging.DEBUG)
logger.debug('immediate level probe')
assert project.flush_logging(timeout=HANG)
print(json.dumps({'done': True}))
""",
    )
    assert "immediate level probe" in _log_file(tmp_path).read_text(encoding="utf-8")


def test_diagnostic_redaction_never_borrows_a_blocked_application_authority(tmp_path: Path) -> None:
    _probe(
        tmp_path,
        """
from cadrumo.core.redaction.tax_identity_admission import bind_tax_identity_admission, tax_identity_admission
from cadrumo.core.redaction.rules import redact_for_log
logger.info('warm redaction')
assert project.flush_logging(timeout=HANG)
entered, release = threading.Event(), threading.Event()
class BlockedApplicationAuthority:
    def admits_spanish_identity(self, normalised):
        entered.set()
        assert release.wait(HANG)
        return False
    def admits_nif_iva(self, normalised):
        return self.admits_spanish_identity(normalised)
try:
    application_authority = BlockedApplicationAuthority()
    with bind_tax_identity_admission(application_authority):
        logger.warning('diagnostic identity %s', 'B' + '0' * 8)
        assert project.flush_logging(timeout=HANG), 'logging borrowed application authority'
        assert not entered.is_set()
        assert tax_identity_admission() is application_authority
        release.set()
        assert redact_for_log('B' + '0' * 8) == 'B' + '0' * 8
        assert entered.is_set()
finally:
    release.set()
assert project.flush_logging(timeout=HANG)
print(json.dumps({'done': True}))
""",
    )
    output = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "diagnostic identity sha256:" in output
    assert "B" + "0" * 8 not in output


def test_snapshots_never_call_instance_or_metaclass_inspection_hooks(tmp_path: Path) -> None:
    _probe(
        tmp_path,
        """
class HashHook(type):
    def __hash__(self):
        raise AssertionError('metaclass hashing must not run')
class HashTrap(metaclass=HashHook):
    pass
class ClassTrap:
    @property
    def __class__(self):
        raise AssertionError('instance class inspection must not run')
class NameHook(type):
    @property
    def __name__(self):
        raise AssertionError('exception metaclass name hook must not run')
class NameTrapFault(Exception, metaclass=NameHook):
    pass
logger.warning('hash hook %s', HashTrap())
logger.warning('class hook %s', ClassTrap())
try:
    raise NameTrapFault('safe fault')
except NameTrapFault:
    logger.exception('name hook')
assert project.flush_logging(timeout=HANG)
assert project.diagnostic_delivery_status()['records'].dropped == 0
print(json.dumps({'done': True}))
""",
    )
    output = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "hash hook <omitted:opaque-value>" in output
    assert "class hook <omitted:opaque-value>" in output
    assert "NameTrapFault:" in output
