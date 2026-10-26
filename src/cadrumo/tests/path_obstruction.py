"""Real-filesystem fault injection for crash-window tests.

A crash-window test asks what survives a failure BETWEEN two durable
operations. Answering it needs the second operation to fail while the first
has already committed, and the honest way to arrange that is a genuine
operating-system fault rather than a test double standing in for the writer:
a double placed at the boundary under test asserts that the double was called,
which is the test's own scaffolding and passes identically against unfixed
code whose call order is intact but whose compensation is missing.

The mechanism here is a directory standing where a file is expected. Every
write syscall the storage substrate uses refuses it -- ``open`` for writing,
and the :func:`os.replace` that completes every tier of
:mod:`~cadrumo.core.atomic_write` -- as :exc:`PermissionError` on Windows and
:exc:`IsADirectoryError` on Linux, both :exc:`OSError`. Production runs
completely unmodified: no seam is added to the writer, no branch is added for
tests, and the code under test reaches the real filesystem exactly as it does
in a release.

READS are refused by the same obstruction, and it serves an unreadable-file
test as well as an unwritable-file one: ``open`` for reading a directory
raises on both platforms too. The entry self-check probes the write direction
because that is the stricter of the two and the one the storage substrate
depends on -- a path that refuses a write may still be readable, but a
directory refuses both.

The obstruction is deliberately NON-EMPTY. An empty directory is removable,
so a writer that tries to clear an unexpected path could dissolve the fault
and turn the test green for the wrong reason.

Reachability. This instrument discriminates between two operations only when
the second targets a path DISTINCT from the first, and that path exists as a
file (or not at all) before the call. A sequence whose read and write share
one path cannot be split by it: obstructing that path makes the earlier read
fail, so the first operation never commits and the window under test is never
entered.

Two other real faults reach windows this one cannot, and between them they
decide whether a given crash window is testable at all. Neither is a double
either -- each makes production refuse for a reason production already has.

- A secure-object write the caller can stamp takes ``expected_revision_id``,
  the substrate's own optimistic-concurrency guard. A stale value placed on
  the write at position N of a real batch makes that write refuse and the
  transaction roll back. This reaches SQL-backed sequences, which have no
  filesystem artefact to obstruct. It does not reach deletes, which carry no
  such guard.
- A caller-supplied sequence can carry a genuinely invalid element at
  position N -- one the real validator rejects. This reaches anything whose
  failing item comes from the caller rather than from the code under test.
  The worked example ships in the retencion observation-window roundtrip: a
  containment-violating stale identifier appended to a real replacement batch
  trips the production ``PathContainmentError``, and the test then asserts the
  prior declared window survived intact. Caller-supplied data, real refusal,
  no production change.

A window that clears none of the three is not closable by any of them. Say so,
and say which condition it fails; that is a bounded result. Reaching for a
double instead produces a test that asserts its own scaffolding and passes
against the unfixed code.

See Also:
    :mod:`~cadrumo.core.atomic_write`
        The staged-write helpers whose final :func:`os.replace` this
        obstruction refuses.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from ..core.external_constants import UTF_8_ENCODING

_BLOCKER_NAME = "blocker"
_BLOCKER_CONTENTS = "obstruction placed by a crash-window test"


class PathObstructionError(RuntimeError):
    """Raised when an obstruction cannot be established or cannot be trusted.

    A fault injector that silently fails to inject makes every test built on
    it vacuous: the code under test runs to completion, the expected refusal
    never happens, and the assertions that follow measure an ordinary success
    path while claiming to measure a failure. This error is how that failure
    mode surfaces loudly instead.
    """


def _obstruction_is_intact(path: Path) -> bool:
    """Return whether the obstruction this module planted is still standing.

    Args:
        path: The obstructed path.

    Returns:
        ``True`` when ``path`` is still the non-empty directory this module
        placed there.
    """
    return path.is_dir() and (path / _BLOCKER_NAME).is_file()


def _assert_writes_refused(path: Path) -> None:
    """Confirm the obstruction really refuses a write, before the test relies on it.

    Opening a directory for writing fails on every platform this ships to, so
    a success here means the obstruction is not in the state this module
    believes it to be. The opened handle is closed and removed before raising
    so a failed self-check leaves nothing behind.

    Args:
        path: The obstructed path to probe.

    Raises:
        PathObstructionError: When a write to ``path`` unexpectedly succeeds.
    """
    try:
        handle = path.open("wb")
    except OSError:
        return
    handle.close()
    path.unlink(missing_ok=True)
    raise PathObstructionError(
        f"obstruction at {path!s} did not refuse a write; the fault was not injected "
        f"and any assertion made under it would be vacuous",
    )


@contextmanager
def obstructed_path(path: Path) -> Generator[Path]:
    """Make every write to ``path`` fail with a real :exc:`OSError` for the block.

    Replaces ``path`` with a non-empty directory, verifies that a write to it
    is genuinely refused, and restores the original state on exit -- including
    the previous file's exact bytes, so a store whose later assertions read
    that file sees what it wrote. Restoration runs even when the block raises.

    An already-obstructed path is refused rather than silently accepted: the
    caller would otherwise be measuring a condition it did not create, and the
    restore would delete a directory it did not place.

    Args:
        path: The file the code under test will try to write. It may or may
            not exist; a parent directory is created when absent.

    Yields:
        The obstructed ``path``, for convenience in assertions.

    The fault is checked at BOTH ends. Checking only on entry would leave the
    case where the code under test dissolves the obstruction and then writes
    successfully: every assertion in the block would describe an ordinary
    success path while the test claimed to describe a failure, and the block
    would exit green. The exit check turns that into a loud error.

    Raises:
        PathObstructionError: When ``path`` is already a directory, when the
            established obstruction does not refuse a write, or when the
            obstruction did not survive the block intact.
    """
    if path.is_dir():
        raise PathObstructionError(
            f"{path!s} is already a directory; obstructing it would measure a condition this block did not create",
        )

    previous_bytes = path.read_bytes() if path.is_file() else None
    if previous_bytes is not None:
        path.unlink()
    path.mkdir(parents=True)
    (path / _BLOCKER_NAME).write_text(_BLOCKER_CONTENTS, encoding=UTF_8_ENCODING, newline="\n")
    try:
        _assert_writes_refused(path)
        yield path
        survived = _obstruction_is_intact(path)
    finally:
        blocker = path / _BLOCKER_NAME
        if blocker.is_file():
            blocker.unlink()
        if path.is_dir():
            path.rmdir()
        if previous_bytes is not None:
            path.write_bytes(previous_bytes)
    if not survived:
        raise PathObstructionError(
            f"the obstruction at {path!s} did not survive the block; the code under test "
            f"removed or replaced it, so anything asserted inside ran against an unfaulted "
            f"path and is vacuous",
        )


def replace_would_refuse(path: Path, *, staging_dir: Path) -> bool:
    """Return whether :func:`os.replace` onto ``path`` is refused.

    The obstruction's guarantee rests on the final syscall of every
    :mod:`~cadrumo.core.atomic_write` tier, not only on ``open``. This exposes
    that check so the module's own tests can prove the rename half directly
    rather than inferring it from the open half.

    Args:
        path: The obstructed destination.
        staging_dir: A directory to stage the throwaway source file in. Kept
            separate from ``path``'s parent so the probe cannot be mistaken
            for a writer's own tempfile.

    Returns:
        ``True`` when the replacement raises :exc:`OSError`.
    """
    source = staging_dir / "replace-probe"
    source.write_bytes(b"replace probe")
    try:
        os.replace(source, path)
    except OSError:
        return True
    finally:
        source.unlink(missing_ok=True)
    return False


__all__ = ["PathObstructionError", "obstructed_path", "replace_would_refuse"]
