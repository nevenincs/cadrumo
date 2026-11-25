"""Slow child launches are paid from the calibration launch budget, never scored as a derivation's cost."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from ......core.config import Settings, override_settings
from ......tests.log_records import delivered_records
from .. import kdf_process, kdf_supervision
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from ..kdf_supervision import calibrate_profile_kdf, fixed_profile_kdf_fallback
from ..kdf_worker_supervision import SupervisedKdfWorker

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_MEBIBYTE = 1024 * 1024
_SALT = b"b" * 16
_STRONGEST_ELIGIBLE = (64, 10, 1)
"""Memory MiB, iterations and lanes of the strongest point the fixture's resources admit."""


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Settings]:
    """Measure a small real grid: one lane at the floor's memory, with a band every point there meets."""
    monkeypatch.setattr(
        kdf_supervision,
        "profile_kdf_resources",
        lambda: kdf_supervision.ProfileCustodyKdfResources(available_memory_bytes=150 * _MEBIBYTE, cpu_count=1),
    )
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS", 0.001)
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS", 1.5)
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_SAMPLE_COUNT", 2)
    # A loaded test host must not end the search on derivation time; launch time is what is under test.
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS", 120.0)
    with override_settings(cadrumo_storage_root=tmp_path, cadrumo_profile_kdf_measure_calibration=True) as settings:
        yield settings


def _point(calibration: kdf_supervision.ProfileCustodyKdfCalibration) -> tuple[int, int, int]:
    parameters = calibration.parameters
    return (parameters.memory_mib, parameters.iterations, parameters.parallelism)


def _slow_launches(monkeypatch: pytest.MonkeyPatch, delay_seconds: float) -> list[subprocess.Popen[bytes]]:
    """Delay each real child's process creation at the launch boundary, then launch it unchanged."""
    launched: list[subprocess.Popen[bytes]] = []
    lock = threading.Lock()
    launch_process = kdf_process.launch_worker_process

    def slow(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        time.sleep(delay_seconds)
        process = launch_process(command, launch_kwargs)
        with lock:
            launched.append(process)
        return process

    monkeypatch.setattr(kdf_process, "launch_worker_process", slow)
    return launched


def _fallbacks(caplog: pytest.LogCaptureFixture) -> list[tuple[int, object]]:
    return [
        (record.levelno, record.__dict__.get("reason"))
        for record in delivered_records(caplog, kdf_supervision.__name__)
        if record.msg == "profile_kdf_calibration_fallback"
    ]


def test_launches_slower_than_a_sample_still_calibrate_to_the_strongest_measured_point(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=kdf_supervision.__name__)
    # Every launch alone outlasts the 2 s sample bound; within the budget, none may cost a sample.
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_LAUNCH_BUDGET_SECONDS", 120.0)
    launched = _slow_launches(monkeypatch, delay_seconds=2.2)

    calibration = calibrate_profile_kdf(salt=_SALT, settings=settings)

    assert calibration.source == "measured"
    assert _point(calibration) == _STRONGEST_ELIGIBLE
    assert len(launched) >= 3, "the search measured several samples, each in its own child"
    assert all(process.poll() is not None for process in launched), "calibration leaves no child running"
    assert _fallbacks(caplog) == []


def test_an_exhausted_launch_budget_falls_back_to_the_floor_with_a_warning(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=kdf_supervision.__name__)
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_LAUNCH_BUDGET_SECONDS", 1.0)
    launched = _slow_launches(monkeypatch, delay_seconds=1.5)

    calibration = calibrate_profile_kdf(salt=_SALT, settings=settings)

    assert calibration.source == "fallback"
    assert calibration.parameters == fixed_profile_kdf_fallback(salt=_SALT)
    assert _fallbacks(caplog) == [(logging.WARNING, "launch_budget_exhausted")]
    assert all(process.poll() is not None for process in launched), "the abandoned spare was contained"


def test_a_child_that_fails_to_launch_is_retried_and_never_scored_over_the_band(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=kdf_supervision.__name__)
    verify = SupervisedKdfWorker.verify_ready_attestation
    attested: list[SupervisedKdfWorker] = []

    def refuse_the_first(worker: SupervisedKdfWorker, ready: tuple[int, bytes]) -> None:
        attested.append(worker)
        if len(attested) == 1:
            raise ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE)
        verify(worker, ready)

    monkeypatch.setattr(SupervisedKdfWorker, "verify_ready_attestation", refuse_the_first)
    # No derivation may overrun a sample here, so only a mis-scored launch could read as over the band.
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS", 10.0)
    monkeypatch.setattr(kdf_supervision, "PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS", 9.0)

    calibration = calibrate_profile_kdf(salt=_SALT, settings=settings)

    # Scoring the failed launch as over the band would have steered the first probe to fewer iterations.
    assert calibration.source == "measured"
    assert _point(calibration) == _STRONGEST_ELIGIBLE
    assert len(attested) >= 2
    assert _fallbacks(caplog) == []
