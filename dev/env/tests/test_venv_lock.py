"""The install lock refuses a live owner and reclaims one that has exited."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from .._venv import _exclusive, _lock_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _lock_for(venv: Path) -> Path:
    return Path(tempfile.gettempdir()) / _lock_name(venv)


def _exited_pid() -> int:
    """The PID of a process that has run to completion and been reaped."""
    child = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    return int(child.stdout.strip())


@pytest.fixture
def venv(tmp_path: Path) -> Iterator[Path]:
    """A venv path whose lock is unique to this test and removed after it."""
    root = tmp_path / ".venv"
    yield root
    _lock_for(root).unlink(missing_ok=True)


def test_a_lock_left_by_an_exited_install_is_reclaimed(venv: Path) -> None:
    """A killed install must not refuse every later install on the machine."""
    _lock_for(venv).write_text(str(_exited_pid()), encoding="ascii")

    with _exclusive(venv):
        assert _lock_for(venv).read_text(encoding="ascii") == str(os.getpid())

    assert not _lock_for(venv).exists()


def test_a_lock_held_by_a_live_install_is_refused(venv: Path) -> None:
    """DISCRIMINATING: reclaiming is only for owners that have gone."""
    _lock_for(venv).write_text(str(os.getpid()), encoding="ascii")

    with pytest.raises(RuntimeError, match="already owns"), _exclusive(venv):
        pass

    assert _lock_for(venv).read_text(encoding="ascii") == str(os.getpid())


def test_an_empty_lock_is_refused_while_its_writer_may_still_be_writing(venv: Path) -> None:
    """The owner writes its PID just after the create; a fresh empty lock is that instant."""
    _lock_for(venv).write_text("", encoding="ascii")

    with pytest.raises(RuntimeError, match="already owns"), _exclusive(venv):
        pass


def test_an_empty_lock_long_past_that_instant_is_reclaimed(venv: Path) -> None:
    """A writer that died between the create and the write left nothing to probe."""
    lock = _lock_for(venv)
    lock.write_text("", encoding="ascii")
    stale = time.time() - 60
    os.utime(lock, (stale, stale))

    with _exclusive(venv):
        assert lock.read_text(encoding="ascii") == str(os.getpid())


def test_an_unreadable_owner_record_is_refused_rather_than_guessed(venv: Path) -> None:
    """A lock this process cannot interpret is never taken from its owner."""
    _lock_for(venv).write_text("not-a-pid", encoding="ascii")

    with pytest.raises(RuntimeError, match="already owns"), _exclusive(venv):
        pass
