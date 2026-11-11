"""Background KDF measurement gives the permit way to a waiting unlock and never adopts the fallback."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from ......core.config import Settings
from ..kdf_lease_waiters import announced_kdf_waiter, kdf_waiter_present
from ..kdf_supervision import (
    ProfileKdfYieldedError,
    calibrate_profile_kdf_in_background,
    profile_kdf_lease,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SALT = b"y" * 16


def _settings(tmp_path: Path) -> Settings:
    return Settings(cadrumo_storage_root=tmp_path, cadrumo_profile_kdf_measure_calibration=True)


def _lease_root(tmp_path: Path) -> Path:
    """The directory the lease resolves for these settings; taking a lease creates it."""
    with profile_kdf_lease(settings=_settings(tmp_path), deadline=time.monotonic() + 5):
        pass
    (root,) = {path.parent for path in tmp_path.rglob("profile-kdf.v1.lock")}
    return root


def test_a_waiting_unlock_is_announced_only_while_it_waits(tmp_path: Path) -> None:
    root = _lease_root(tmp_path)
    assert not kdf_waiter_present(root)
    with announced_kdf_waiter(root):
        assert kdf_waiter_present(root)
    assert not kdf_waiter_present(root)


def test_a_dead_waiters_marker_is_stale_and_removed(tmp_path: Path) -> None:
    root = _lease_root(tmp_path)
    exited = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, check=True)
    marker = root / "profile-kdf-waiters" / f"{int(exited.stdout)}-deadbeefdeadbeef"
    marker.parent.mkdir(exist_ok=True)
    marker.touch()

    assert not kdf_waiter_present(root)
    assert not marker.exists()


def test_background_work_yields_to_an_announced_waiter_without_taking_the_permit(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = _lease_root(tmp_path)
    with (
        announced_kdf_waiter(root),
        pytest.raises(ProfileKdfYieldedError),
        profile_kdf_lease(settings=settings, deadline=time.monotonic() + 5, background=True),
    ):
        pytest.fail("background work took the permit from a waiting unlock")
    # The yield released nothing it did not hold: a foreground unlock still gets the permit at once.
    with profile_kdf_lease(settings=settings, deadline=time.monotonic() + 1):
        pass


def test_background_work_yields_while_an_unlock_holds_the_permit(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    held = threading.Event()
    release = threading.Event()

    def unlock() -> None:
        with profile_kdf_lease(settings=settings, deadline=time.monotonic() + 5):
            held.set()
            release.wait(10)

    owner = threading.Thread(target=unlock)
    owner.start()
    try:
        assert held.wait(10)
        started = time.monotonic()
        with (
            pytest.raises(ProfileKdfYieldedError),
            profile_kdf_lease(settings=settings, deadline=time.monotonic() + 5, background=True),
        ):
            pytest.fail("background work shared the permit with a running unlock")
        assert time.monotonic() - started < 1.0, "background work waited for the permit instead of yielding"
    finally:
        release.set()
        owner.join(10)


def test_a_foreground_unlock_waiting_on_another_process_is_announced(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = _lease_root(tmp_path)
    holder = subprocess.Popen(  # noqa: S603 - the test's own interpreter holds the real OS lease
        [
            sys.executable,
            "-c",
            "import sys, time\n"
            "from cadrumo.core.config import Settings\n"
            "from cadrumo.adapters.persistence.storage.custody.kdf_supervision import profile_kdf_lease\n"
            "with profile_kdf_lease(settings=Settings(cadrumo_storage_root=sys.argv[1]),"
            " deadline=time.monotonic() + 30):\n"
            "    print('held', flush=True)\n"
            "    sys.stdin.readline()\n",
            str(tmp_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        seen: list[bool] = []

        def wait_for_permit() -> None:
            with profile_kdf_lease(settings=settings, deadline=time.monotonic() + 20):
                pass

        waiter = threading.Thread(target=wait_for_permit)
        waiter.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not seen:
            if kdf_waiter_present(root):
                seen.append(True)
            time.sleep(0.05)
        assert seen, "a foreground unlock waiting on another process was never announced"
        assert holder.stdin is not None
        holder.stdin.write("\n")
        holder.stdin.flush()
        waiter.join(20)
        assert not waiter.is_alive()
        assert not kdf_waiter_present(root), "the waiter's announcement outlived its wait"
    finally:
        holder.kill()
        holder.wait(10)


def test_background_calibration_abandons_rather_than_adopting_the_fallback(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    root = _lease_root(tmp_path)
    with announced_kdf_waiter(root):
        assert calibrate_profile_kdf_in_background(salt=_SALT, settings=settings) is None
