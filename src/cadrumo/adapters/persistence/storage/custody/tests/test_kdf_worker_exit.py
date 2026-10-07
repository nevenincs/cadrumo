"""Real supervised KDF results require zero exit and an exhausted result pipe."""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Literal, cast

import pytest
from argon2.low_level import Type, hash_secret_raw

from ......core.config import Settings, override_settings
from ......core.diagnostic_log import DiagnosticFormatter
from ......core.logging import LOG_FILE_FORMAT
from ...crypto.aes_gcm import open_sealed, seal
from .. import _kdf_process as process_boundary
from .. import _kdf_worker_supervision as supervision
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from ..records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

type _Operation = Literal["calibrate", "unwrap", "wrap"]

_PASSWORD = b"synthetic-private-exit-password-123"
_ASSOCIATED_DATA = b"synthetic-private-exit-context"
_DEK = bytes(range(32))


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


def _key() -> bytes:
    return hash_secret_raw(
        secret=_PASSWORD,
        salt=b"k" * 16,
        time_cost=2,
        memory_cost=19 * 1024,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
        version=19,
    )


@pytest.fixture(scope="module")
def wrapped_dek() -> ProfileCustodyWrappedDek:
    nonce, sealed = seal(_DEK, key=_key(), associated_data=_ASSOCIATED_DATA)
    return ProfileCustodyWrappedDek(
        nonce_b64=base64.b64encode(nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(sealed[:-16]).decode("ascii"),
        tag_b64=base64.b64encode(sealed[-16:]).decode("ascii"),
    )


@pytest.fixture
def settings(tmp_path: Path) -> Generator[Settings]:
    with override_settings(cadrumo_local_storage_root=tmp_path) as settings:
        yield settings


@pytest.fixture
def configure_child_exit(monkeypatch: pytest.MonkeyPatch) -> Callable[[int, bool], None]:
    """Alter only the final exit of the actual contained, attested, cryptographic child."""
    launch_process = process_boundary._launch_worker_process

    def configure(exit_code: int, trailing_byte: bool = False) -> None:
        source = "from cadrumo.adapters.persistence.storage.custody import _kdf_worker as worker\n"
        if trailing_byte:
            source += (
                "original_write = worker.write_kdf_frame\n"
                "writes = 0\n"
                "def write(fd, value, *, kind):\n"
                "    global writes\n"
                "    original_write(fd, value, kind=kind)\n"
                "    writes += 1\n"
                "    if writes == 2:\n"
                "        worker.os.write(fd, b'x')\n"
                "worker.write_kdf_frame = write\n"
            )
        source += f"worker.main()\nraise SystemExit({exit_code})\n"

        def launch(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
            assert command[1:3] == ["-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker"]
            return launch_process([command[0], "-c", source, *command[3:]], launch_kwargs)

        monkeypatch.setattr(process_boundary, "_launch_worker_process", launch)

    return configure


def _operate(
    worker: _SupervisedKdfWorker, operation: _Operation, wrapped_dek: ProfileCustodyWrappedDek
) -> float | bytes | ProfileCustodyWrappedDek | None:
    if operation == "calibrate":
        return worker.calibrate(_kdf())
    if operation == "unwrap":
        return worker.unwrap(password=_PASSWORD, kdf=_kdf(), wrapped_dek=wrapped_dek, associated_data=_ASSOCIATED_DATA)
    return worker.wrap(secret=_PASSWORD, dek=_DEK, kdf=_kdf(), associated_data=_ASSOCIATED_DATA)


def _summary(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    records = [
        record
        for record in caplog.records
        if record.name == supervision.__name__ and record.msg == "kdf_worker_lifecycle"
    ]
    assert len(records) == 1
    rendered = DiagnosticFormatter(LOG_FILE_FORMAT).format(records[0])
    assert _PASSWORD.decode("ascii") not in rendered and _ASSOCIATED_DATA.decode("ascii") not in rendered
    context: object = json.loads(rendered.split(" | ", 1)[1])
    assert isinstance(context, dict) and len(context) <= 32
    return cast("dict[str, object]", context)


@pytest.mark.parametrize("operation", ["calibrate", "unwrap", "wrap"])
def test_nonzero_exit_refuses_a_valid_real_cryptographic_response(
    operation: _Operation,
    configure_child_exit: Callable[[int, bool], None],
    settings: Settings,
    wrapped_dek: ProfileCustodyWrappedDek,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_child_exit(7, False)
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=settings)
    process: subprocess.Popen[bytes] | None = None
    with pytest.raises(ProfileCustodyRefusedError) as refused, worker:
        process = worker._process
        _operate(worker, operation, wrapped_dek)
    assert refused.value.refusal == ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE
    assert process is not None and process.returncode == 7
    context = _summary(caplog)
    assert context["stage"] == "clean_exit" and context["exit_code"] == 7
    assert context["outcome"] == "failed" and context["cleanup_status"] == "completed"
    assert worker._process is None and worker._request_fd is None and worker._result_fd is None


@pytest.mark.parametrize("operation", ["calibrate", "unwrap", "wrap"])
def test_zero_exit_accepts_the_real_cryptographic_response(
    operation: _Operation,
    configure_child_exit: Callable[[int, bool], None],
    settings: Settings,
    wrapped_dek: ProfileCustodyWrappedDek,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_child_exit(0, False)
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    with _SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=settings) as worker:
        process = worker._process
        result = _operate(worker, operation, wrapped_dek)
    assert process is not None and process.returncode == 0
    if operation == "calibrate":
        assert isinstance(result, float) and result > 0
    elif operation == "unwrap":
        assert result == _DEK
    else:
        assert isinstance(result, ProfileCustodyWrappedDek)
        sealed = base64.b64decode(result.ciphertext_b64) + base64.b64decode(result.tag_b64)
        assert (
            open_sealed(base64.b64decode(result.nonce_b64), sealed, key=_key(), associated_data=_ASSOCIATED_DATA)
            == _DEK
        )
    context = _summary(caplog)
    assert context["exit_code"] == 0 and context["stage"] is None
    assert context["outcome"] == context["cleanup_status"] == "completed"


@pytest.mark.parametrize("operation", ["unwrap", "wrap"])
def test_handled_failure_frame_with_zero_exit_remains_a_normal_refusal(
    operation: Literal["unwrap", "wrap"],
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    wrapped_dek: ProfileCustodyWrappedDek,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Preserve the unchanged -m entrypoint and actual exit status for handled refusals.
    launched: list[tuple[subprocess.Popen[bytes], float]] = []
    launch_process = process_boundary._launch_worker_process

    def observe_launch(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        started = time.monotonic()
        process = launch_process(command, launch_kwargs)
        launched.append((process, time.monotonic() - started))
        return process

    monkeypatch.setattr(process_boundary, "_launch_worker_process", observe_launch)
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=settings)
    try:
        with worker:
            process = worker._process
            if operation == "unwrap":
                result = worker.unwrap(
                    password=b"different-synthetic-password-123",
                    kdf=_kdf(),
                    wrapped_dek=wrapped_dek,
                    associated_data=_ASSOCIATED_DATA,
                )
            else:
                result = worker.wrap(secret=_PASSWORD, dek=b"short", kdf=_kdf(), associated_data=_ASSOCIATED_DATA)
    finally:
        # Retain only process/status/timing facts if the unchanged fixture degrades.
        print(
            json.dumps(
                {
                    "operation": operation,
                    "ready_attested": worker._ready_payload is not None,
                    "children": [
                        {"pid": child.pid, "cached_exit_code": child.returncode, "launch_seconds": elapsed}
                        for child, elapsed in launched
                    ],
                }
            )
        )
    assert result is None and process is not None and process.returncode == 0
    context = _summary(caplog)
    assert context["exit_code"] == 0 and context["stage"] is None
    assert context["outcome"] == "refused" and context["cleanup_status"] == "completed"


def test_zero_exit_still_refuses_trailing_result_pipe_data(
    configure_child_exit: Callable[[int, bool], None], settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    configure_child_exit(0, True)
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    process: subprocess.Popen[bytes] | None = None
    with (
        pytest.raises(ProfileCustodyRefusedError) as refused,
        _SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=settings) as worker,
    ):
        process = worker._process
        worker.calibrate(_kdf())
    assert refused.value.refusal == ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE
    assert process is not None and process.returncode == 0
    context = _summary(caplog)
    assert context["exit_code"] == 0 and context["stage"] == "clean_exit" and context["outcome"] == "failed"


def test_cached_exit_code_remains_observable_when_later_cleanup_fails(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=supervision.__name__)
    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=settings)
    cleanup = worker._cleanup_neutral_directory
    primary = OSError("synthetic cleanup failure")
    process: subprocess.Popen[bytes] | None = None

    def cleanup_then_fail() -> None:
        cleanup()
        raise primary

    monkeypatch.setattr(worker, "_cleanup_neutral_directory", cleanup_then_fail)
    with pytest.raises(OSError) as escaped, worker:
        process = worker._process
        assert worker.calibrate(_kdf()) > 0
    assert escaped.value is primary and process is not None and process.returncode == 0
    context = _summary(caplog)
    assert context["exit_code"] == 0 and context["cleanup_status"] == context["outcome"] == "failed"
    assert context["stage"] == "cleanup" and context["cleanup_error_type"] == "OSError"
