"""KDF lifecycle diagnostics disclose phases without altering custody failures."""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import time
from itertools import count
from pathlib import Path
from typing import cast

import pytest

from ......core.config import Settings
from ......core.diagnostic_log import DiagnosticFormatter, diagnostic_scope
from ......core.logging import LOG_FILE_FORMAT
from .. import _kdf_worker_supervision as supervision
from .._kdf_codec import KDF_FAILED_FRAME, KDF_FRAME_CONTROL, calibration_frame_bytes
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..errors import ProfileCustodyRefusedError
from ..records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PRIVATE = "synthetic-private-kdf-canary"
_PHASE_NAMES = ("start", "ready_wait", "ready_attestation", "request_write", "result_wait", "clean_exit", "cleanup")


def _kdf() -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
        output_bytes=32,
    )


@pytest.fixture
def simulated_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _SupervisedKdfWorker:
    """Inject transport boundaries; real child/crypto coverage stays in supervision tests."""
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + 30, settings=Settings(cadrumo_local_storage_root=tmp_path)
    )
    frames = iter(
        ((KDF_FRAME_CONTROL, _PRIVATE.encode()), (KDF_FRAME_CONTROL, calibration_frame_bytes(derivation_ns=125)))
    )
    monkeypatch.setattr(_SupervisedKdfWorker, "_start", lambda _self: None)
    monkeypatch.setattr(_SupervisedKdfWorker, "_read_response_frame", lambda _self: next(frames))
    monkeypatch.setattr(_SupervisedKdfWorker, "_verify_ready_attestation", lambda _self, _frame: None)
    monkeypatch.setattr(_SupervisedKdfWorker, "_write_request", lambda _self, _payload: None)
    monkeypatch.setattr(_SupervisedKdfWorker, "_require_clean_worker_exit", lambda _self: None)
    return worker


def _summary(caplog: pytest.LogCaptureFixture) -> tuple[logging.LogRecord, dict[str, object]]:
    records = [
        record
        for record in caplog.records
        if record.name == supervision.__name__ and record.msg == "kdf_worker_lifecycle"
    ]
    assert len(records) == 1
    record = records[0]
    rendered = DiagnosticFormatter(LOG_FILE_FORMAT).format(record)
    _, suffix = rendered.split(" | ", 1)
    context: object = json.loads(suffix)
    assert isinstance(context, dict)
    assert len(context) <= 32
    assert _PRIVATE not in rendered
    assert record.exc_info is None and record.args == ()
    return record, cast("dict[str, object]", context)


def test_success_emits_once_after_cleanup_with_monotonic_spans_and_existing_scope(
    simulated_worker: _SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    ticks = count(step=1_000_000)
    monkeypatch.setattr(supervision.time, "monotonic_ns", lambda: next(ticks))
    cleanup_complete = False
    original_close = _SupervisedKdfWorker._close

    def close(worker: _SupervisedKdfWorker, *, failed: bool) -> None:
        nonlocal cleanup_complete
        assert not caplog.records
        original_close(worker, failed=failed)
        cleanup_complete = True

    monkeypatch.setattr(_SupervisedKdfWorker, "_close", close)
    with diagnostic_scope() as identifier, simulated_worker as worker:
        assert not caplog.records
        assert worker.calibrate(_kdf()) == 0.000000125
        assert not caplog.records
    assert cleanup_complete
    _, context = _summary(caplog)
    assert context["diagnostic_id"] == identifier
    assert context["outcome"] == context["cleanup_status"] == "completed"
    assert context["stage"] is None and context["error_type"] is None
    assert context["cleanup_error_type"] is None and context["cleanup_incomplete"] is False
    assert all(context[f"kdf_{phase}_elapsed_ms"] == 1.0 for phase in _PHASE_NAMES)
    assert cast("float", context["elapsed_seconds"]) >= 0.007


@pytest.mark.parametrize(
    "stage", ["start", "ready_wait", "ready_attestation", "request_write", "result_wait", "clean_exit"]
)
def test_failure_retains_the_exact_phase_type_and_primary_without_private_message(
    stage: str,
    simulated_worker: _SupervisedKdfWorker,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    primary = TimeoutError(_PRIVATE) if stage in {"ready_wait", "result_wait", "clean_exit"} else ValueError(_PRIVATE)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise primary

    if stage in {"ready_wait", "result_wait"}:
        reads = 0

        def read(_worker: _SupervisedKdfWorker) -> tuple[int, bytes]:
            nonlocal reads
            reads += 1
            if reads == (1 if stage == "ready_wait" else 2):
                raise primary
            return KDF_FRAME_CONTROL, _PRIVATE.encode()

        monkeypatch.setattr(_SupervisedKdfWorker, "_read_response_frame", read)
    else:
        method = {
            "start": "_start",
            "ready_attestation": "_verify_ready_attestation",
            "request_write": "_write_request",
            "clean_exit": "_require_clean_worker_exit",
        }[stage]
        monkeypatch.setattr(_SupervisedKdfWorker, method, fail)
    with pytest.raises(type(primary)) as escaped, simulated_worker as worker:
        worker.calibrate(_kdf())
    assert escaped.value is primary
    _, context = _summary(caplog)
    assert context["stage"] == stage and context["error_type"] == type(primary).__name__
    assert context["outcome"] == "failed"
    assert context[f"kdf_{stage}_elapsed_ms"] is not None and context["kdf_cleanup_elapsed_ms"] is not None
    if stage in {"start", "ready_wait", "ready_attestation"}:
        assert context["kdf_request_write_elapsed_ms"] is None
        assert context["kdf_result_wait_elapsed_ms"] is None
    assert context["cleanup_status"] == ("unconfirmed" if stage == "start" else "completed")


def test_invalid_result_has_validation_failure_after_the_existing_clean_exit_sequence(
    simulated_worker: _SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    monkeypatch.setattr(
        _SupervisedKdfWorker, "_read_response_frame", lambda _worker: (KDF_FRAME_CONTROL, _PRIVATE.encode())
    )
    with pytest.raises(ProfileCustodyRefusedError), simulated_worker as worker:
        worker.calibrate(_kdf())
    _, context = _summary(caplog)
    assert context["stage"] == "result_validation"
    assert context["kdf_clean_exit_elapsed_ms"] is not None
    assert context["outcome"] == "failed"


def test_refused_result_does_not_disclose_secret_or_associated_data(
    simulated_worker: _SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    wrapped = ProfileCustodyWrappedDek(
        nonce_b64=base64.b64encode(b"n" * 12).decode(),
        ciphertext_b64=base64.b64encode(b"c" * 32).decode(),
        tag_b64=base64.b64encode(b"t" * 16).decode(),
    )
    monkeypatch.setattr(
        _SupervisedKdfWorker, "_read_response_frame", lambda _worker: (KDF_FRAME_CONTROL, KDF_FAILED_FRAME)
    )
    with simulated_worker as worker:
        assert (
            worker.unwrap(
                password=_PRIVATE.encode(), kdf=_kdf(), wrapped_dek=wrapped, associated_data=_PRIVATE.encode()
            )
            is None
        )
    _, context = _summary(caplog)
    assert context["outcome"] == "refused" and context["stage"] is None
    assert context["cleanup_status"] == "completed"


@pytest.mark.parametrize("has_primary", [False, True])
def test_cleanup_failure_still_escapes_and_records_original_failure_separately(
    has_primary: bool,
    simulated_worker: _SupervisedKdfWorker,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    primary = TimeoutError(_PRIVATE)
    cleanup = OSError(_PRIVATE)

    def close(_worker: _SupervisedKdfWorker, *, failed: bool) -> None:
        assert failed is has_primary
        raise cleanup

    monkeypatch.setattr(_SupervisedKdfWorker, "_close", close)
    with pytest.raises(OSError) as escaped, simulated_worker:
        if has_primary:
            raise primary
    assert escaped.value is cleanup
    _, context = _summary(caplog)
    assert context["stage"] == ("caller" if has_primary else "cleanup")
    assert context["error_type"] == ("TimeoutError" if has_primary else "OSError")
    assert context["cleanup_error_type"] == "OSError" and context["cleanup_status"] == "failed"
    assert context["cleanup_incomplete"] is True and context["outcome"] == "failed"


@pytest.mark.parametrize("sink_error", [RuntimeError(_PRIVATE), KeyboardInterrupt(_PRIVATE)])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_sink_cannot_replace_either_original_or_escaping_cleanup_failure(
    sink_error: BaseException,
    cleanup_fails: bool,
    simulated_worker: _SupervisedKdfWorker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = TimeoutError(_PRIVATE)
    cleanup = OSError(_PRIVATE)
    calls = 0

    def log(*_args: object, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise sink_error

    def close(_worker: _SupervisedKdfWorker, *, failed: bool) -> None:
        assert failed
        raise cleanup

    monkeypatch.setattr(supervision.logger, "log", log)
    if cleanup_fails:
        monkeypatch.setattr(_SupervisedKdfWorker, "_close", close)
    expected = cleanup if cleanup_fails else primary
    with pytest.raises(type(expected)) as escaped, simulated_worker:
        raise primary
    assert escaped.value is expected and calls == 1


def test_normal_sink_exception_is_nonfatal_after_successful_cleanup(
    simulated_worker: _SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def log(*_args: object, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise OSError(_PRIVATE)

    monkeypatch.setattr(supervision.logger, "log", log)
    with simulated_worker as worker:
        assert worker.calibrate(_kdf()) == 0.000000125
    assert calls == 1


def test_returned_cleanup_without_confirmed_child_exit_is_unconfirmed(
    simulated_worker: _SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)

    class UnconfirmedProcess:
        returncode = None

    monkeypatch.setattr(_SupervisedKdfWorker, "_close", lambda _worker, *, failed: None)
    with simulated_worker:
        simulated_worker._process = cast("subprocess.Popen[bytes]", UnconfirmedProcess())
    _, context = _summary(caplog)
    assert context["cleanup_status"] == context["outcome"] == "unconfirmed"
    assert context["cleanup_incomplete"] is True and context["cleanup_error_type"] is None
