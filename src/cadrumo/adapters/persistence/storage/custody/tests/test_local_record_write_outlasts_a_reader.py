"""Local-record replacement retries only the real publication boundary.

The reader test holds a real Windows handle and releases it after the delegated
``os.replace`` reports its native refusal. The permanent-block case keeps its
handle through the bounded retry deadline and checks that the final typed error
retains the last observed native cause.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from cadrumo.core import atomic_write

from ..errors import ProfileCustodyRecordError
from ..filesystem import read_optional_profile_custody_local_record, write_profile_custody_local_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LIMIT = 4096
_FIRST = b'{"phase":"prepared"}'
_SECOND = b'{"phase":"published"}'


def _record_native_error(
    record_property: Callable[[str, object], None],
    *,
    phase: str,
    error: OSError,
) -> None:
    record_property("s16.native.phase", phase)
    record_property("s16.native.type", type(error).__name__)
    record_property("s16.native.winerror", repr(getattr(error, "winerror", None)))
    record_property("s16.native.errno", repr(error.errno))
    record_property("s16.native.filename", repr(error.filename))
    record_property("s16.native.object_id", hex(id(error)))


def test_a_write_outlasts_a_reader_that_releases_its_handle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Retry the real replacement refusal, then release the held reader."""
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    if os.name != "nt":
        with path.open("rb"):
            write_profile_custody_local_record(path, _SECOND, publish_once=False)
        assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _SECOND
        record_property("s16.native.phase", "not-applicable-posix-replace-does-not-block-open-readers")
        return

    real_open = os.open
    real_replace = os.replace
    stage_attempts: list[Path] = []
    replace_attempts: list[str] = []
    replace_errors: list[PermissionError] = []
    handle = path.open("rb")
    reader_released = False

    def observe_open(
        raw_path: str | bytes | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        candidate = Path(os.fsdecode(raw_path))
        if (
            dir_fd is None
            and flags & os.O_EXCL
            and candidate.parent == tmp_path
            and candidate.name.startswith(f"{path.name}.")
            and candidate.name.endswith(".tmp")
        ):
            stage_attempts.append(candidate)
        if dir_fd is None:
            return real_open(raw_path, flags, mode)
        return real_open(raw_path, flags, mode, dir_fd=dir_fd)

    def observe_replace(
        source: str | bytes | os.PathLike[str],
        destination: str | bytes | os.PathLike[str],
    ) -> None:
        nonlocal reader_released
        if Path(os.fsdecode(destination)) != path:
            real_replace(source, destination)
            return
        replace_attempts.append("attempted")
        try:
            real_replace(source, destination)
        except PermissionError as exc:
            replace_errors.append(exc)
            _record_native_error(record_property, phase="replace-reader-held", error=exc)
            if not reader_released:
                handle.close()
                reader_released = True
            replace_attempts[-1] = "permission-error-observed"
            raise
        replace_attempts[-1] = "published"

    monkeypatch.setattr(atomic_write.os, "open", observe_open)
    monkeypatch.setattr(atomic_write.os, "replace", observe_replace)

    try:
        write_profile_custody_local_record(path, _SECOND, publish_once=False)
    finally:
        if not handle.closed:
            handle.close()

    assert reader_released, "release must follow an observed native replace refusal"
    assert replace_errors, "the held reader must cause a real PermissionError"
    assert len(stage_attempts) == 1, "retries must reuse the one completed staging file"
    assert replace_attempts == ["permission-error-observed", "published"]
    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _SECOND
    residue = [child for child in tmp_path.iterdir() if child != path]
    assert residue == []
    record_property("s16.native.origin", "observed delegated Windows os.replace refusal")
    record_property("s16.stage_attempts", str(len(stage_attempts)))
    record_property("s16.replace_attempts", str(len(replace_attempts)))
    record_property("s16.replace_sequence", ",".join(replace_attempts))
    record_property("s16.reader_released_after_observed_refusal", str(reader_released))
    record_property("s16.final_target_matches_payload", "true")
    record_property("s16.stage_residue_count", str(len(residue)))


def test_a_permanent_native_write_block_is_still_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """ANTI-TAUTOLOGY: every platform refuses a durable write barrier.

    Windows holds the destination open, the native permanent blocker that its
    retry budget must eventually refuse. POSIX permits replacement of an open
    reader, so it instead presents a real directory at the destination and
    proves the no-follow atomic replacement refuses rather than overwriting it.
    """
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    if os.name != "nt":
        path.unlink()
        path.mkdir()
        with pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written"):
            write_profile_custody_local_record(path, _SECOND, publish_once=False)
        assert path.is_dir()
        return

    real_open = os.open
    real_replace = os.replace
    stage_attempts: list[Path] = []
    replace_attempts: list[str] = []
    replace_errors: list[PermissionError] = []

    def observe_open(
        raw_path: str | bytes | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        candidate = Path(os.fsdecode(raw_path))
        if (
            dir_fd is None
            and flags & os.O_EXCL
            and candidate.parent == tmp_path
            and candidate.name.startswith(f"{path.name}.")
            and candidate.name.endswith(".tmp")
        ):
            stage_attempts.append(candidate)
        if dir_fd is None:
            return real_open(raw_path, flags, mode)
        return real_open(raw_path, flags, mode, dir_fd=dir_fd)

    def observe_replace(
        source: str | bytes | os.PathLike[str],
        destination: str | bytes | os.PathLike[str],
    ) -> None:
        if Path(os.fsdecode(destination)) != path:
            real_replace(source, destination)
            return
        replace_attempts.append("attempted")
        try:
            real_replace(source, destination)
        except PermissionError as exc:
            replace_errors.append(exc)
            _record_native_error(record_property, phase="replace-permanent-reader", error=exc)
            replace_attempts[-1] = "permission-error"
            raise
        replace_attempts[-1] = "published"

    monkeypatch.setattr(atomic_write.os, "open", observe_open)
    monkeypatch.setattr(atomic_write.os, "replace", observe_replace)

    handle = path.open("rb")
    try:
        with pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written") as refused:
            write_profile_custody_local_record(path, _SECOND, publish_once=False)
    finally:
        handle.close()

    assert replace_errors, "the permanent reader must cause a real PermissionError"
    assert len(replace_attempts) > 1, "a permanent denial must exercise the finite retry budget"
    assert len(stage_attempts) == 1, "bounded retries must reuse one completed staging file"
    assert refused.value.__cause__ is replace_errors[-1]
    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _FIRST
    residue = [child for child in tmp_path.iterdir() if child != path]
    assert residue == []
    record_property("s16.native.origin", "observed delegated Windows os.replace refusal")
    record_property("s16.stage_attempts", str(len(stage_attempts)))
    record_property("s16.replace_attempts", str(len(replace_attempts)))
    record_property("s16.typed_cause_object_id", hex(id(refused.value.__cause__)))
    record_property("s16.last_observed_error_object_id", hex(id(replace_errors[-1])))
    record_property("s16.typed_cause_is_last_observed_error", str(refused.value.__cause__ is replace_errors[-1]))
    record_property("s16.target_unchanged", "true")
    record_property("s16.stage_residue_count", str(len(residue)))
