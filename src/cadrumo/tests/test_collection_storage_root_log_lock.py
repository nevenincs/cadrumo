"""The collection-time storage root's own cleanup survives an open log handler.

``register_collection_storage_root_cleanup`` removes its process-private root
at ``atexit``. Measured directly: every such root was leaving a
``logs/cadrumo.log`` file behind at the owning process's own exit, on every
run, because the stdlib ``logging`` module registers its own
``atexit.register(logging.shutdown)`` at import time -- long before this
module's cleanup registers during conftest collection -- so LIFO ``atexit``
ordering runs this cleanup BEFORE ``logging.shutdown()`` closes the
``RotatingFileHandler`` :func:`cadrumo.core.logging.configure_logging`
attaches under the root. Windows refuses to delete an open file, and
``shutil.rmtree(root, ignore_errors=True)`` swallows that failure silently, so
the root only ever cleared later, once a *different* process's stale sweep
found it after the lock had already been released -- the ~24h population of
not-yet-reaped roots a live census measured in the shared OS temp directory.
"""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory
from .collection_storage_root import _release_log_handlers_under

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 60


def _root_logger_file_handler(log_file: Path) -> logging.handlers.RotatingFileHandler:
    """Attach and return a real ``RotatingFileHandler`` pointed at ``log_file``."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(str(log_file), encoding="utf-8")
    logging.getLogger().addHandler(handler)
    return handler


def test_an_open_log_handler_blocks_removal_on_this_platform(tmp_path: Path) -> None:
    """The OS-level cause, demonstrated directly with no mocks.

    The positive control this whole file exists to fix against: without
    releasing the handler first, ``shutil.rmtree`` on the locked file is a
    silent no-op on Windows, which is exactly why the real cleanup measured
    as leaving its root behind on every run. POSIX permits unlinking an open
    file, so the platform split mirrors the guard tests elsewhere in this
    package that condition on the same real OS behaviour.
    """
    root = tmp_path / "cadrumo-pytest-probe-blocked"
    handler = _root_logger_file_handler(root / "probe-logs" / "cadrumo.log")
    logging.getLogger().info("probe line, keeps the handler's file open")
    try:
        shutil.rmtree(root, ignore_errors=True)
        if sys.platform == "win32":
            assert root.exists(), (
                "the open handler should have blocked removal on Windows; if this now "
                "passes, the OS lock this fix exists for no longer applies"
            )
        else:
            assert not root.exists(), "POSIX permits removal of an open file"
    finally:
        logging.getLogger().removeHandler(handler)
        with contextlib.suppress(OSError):
            handler.close()
        shutil.rmtree(root, ignore_errors=True)


def test_releasing_the_handler_unblocks_removal(tmp_path: Path) -> None:
    """Releasing the handler is what turns the blocked removal into a real one.

    Exercises :func:`_release_log_handlers_under` directly: closes and detaches
    only the handler writing under ``root``, leaving the removal itself to a
    second, ordinary ``shutil.rmtree`` call -- the same two-step shape
    ``register_collection_storage_root_cleanup`` now performs at ``atexit``.
    """
    root = tmp_path / "cadrumo-pytest-probe-released"
    other_root = tmp_path / "cadrumo-pytest-probe-other"
    handler = _root_logger_file_handler(root / "probe-logs" / "cadrumo.log")
    other_handler = _root_logger_file_handler(other_root / "probe-logs" / "cadrumo.log")
    logging.getLogger().info("probe line for the root under test")
    logging.getLogger().info("probe line for the sibling root that must be left alone")
    try:
        _release_log_handlers_under(root)
        shutil.rmtree(root, ignore_errors=True)
        assert not root.exists(), "releasing the handler must unblock removal of its own root"

        assert other_handler in logging.getLogger().handlers, (
            "releasing one root's handler must not detach a handler writing under a different root"
        )
        other_handler.close()
        other_handler.flush()
    finally:
        for leftover in (handler, other_handler):
            with contextlib.suppress(ValueError):
                logging.getLogger().removeHandler(leftover)
            with contextlib.suppress(OSError):
                leftover.close()
        shutil.rmtree(other_root, ignore_errors=True)


def test_registered_cleanup_removes_a_root_with_a_real_atexit_ordered_log_handler(tmp_path: Path) -> None:
    """The real registered cleanup removes its root under the real ``atexit`` ordering.

    A genuine subprocess reproduces the exact hazard measured against this
    project's own conftest: the stdlib ``logging`` module's own
    ``atexit.register(logging.shutdown)`` fires from module import, well
    before this module's cleanup registers, so only a real interpreter exit
    exercises the LIFO ordering this fix depends on -- an in-process call
    cannot substitute for it.
    """
    root = tmp_path / "cadrumo-pytest-probe-e2e"
    probe = textwrap.dedent(
        f"""
        import logging
        import logging.handlers
        from pathlib import Path

        from cadrumo.tests.collection_storage_root import register_collection_storage_root_cleanup

        root = Path({str(root)!r})
        log_dir = root / "probe-logs"
        log_dir.mkdir(parents=True)
        handler = logging.handlers.RotatingFileHandler(str(log_dir / "cadrumo.log"), encoding="utf-8")
        logging.getLogger().addHandler(handler)
        logging.getLogger().info("probe line, mirrors configure_logging's own attach")
        register_collection_storage_root_cleanup(root)
        # No explicit close/shutdown call here: the point is the real atexit
        # ordering at normal interpreter exit, not a hand-picked one.
        """,
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv; probe source is a test-local literal.
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, f"probe failed:\n{completed.stdout}\n{completed.stderr}"
    assert not root.exists(), (
        f"the registered atexit cleanup left its root behind: {sorted(p.as_posix() for p in scan_directory(root, pattern='*', recursive=True))}"
    )
