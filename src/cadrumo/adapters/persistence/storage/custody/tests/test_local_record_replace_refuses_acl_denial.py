"""A real staging ACL refusal does not enter the publication retry loop.

The test applies a deny-by-omission DACL to the destination's parent and
observes/delegates the actual exclusive stage-open and replacement calls. It
records the native stage-open error, then proves that no replacement was
attempted, the old record remains intact, and the stage was cleaned up.
"""

from __future__ import annotations

import getpass
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo.core import atomic_write

from ..errors import ProfileCustodyRecordError
from ..filesystem import (
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.windows_only, pytest.mark.hex_persistence_adapter]

_LIMIT = 4096
_FIRST = b'{"phase":"prepared"}'
_SECOND = b'{"phase":"published"}'
_THIRD = b'{"phase":"settled"}'


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


def _set_operator_access(directory: Path, rights: int) -> None:
    """Replace the directory's DACL with one allow entry for the operator."""
    import win32security

    operator = win32security.LookupAccountName(None, getpass.getuser())[0]
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION,
        win32security.OBJECT_INHERIT_ACE | win32security.CONTAINER_INHERIT_ACE,
        rights,
        operator,
    )
    win32security.SetNamedSecurityInfo(
        str(directory),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        dacl,
        None,
    )


@contextmanager
def _directory_refusing_new_files(directory: Path) -> Generator[None]:
    """Grant the operator read, delete and DACL rights only, so creating a file is denied."""
    import ntsecuritycon

    read_only = (
        ntsecuritycon.FILE_GENERIC_READ
        | ntsecuritycon.FILE_GENERIC_EXECUTE
        | ntsecuritycon.DELETE
        | ntsecuritycon.WRITE_DAC
    )
    _set_operator_access(directory, read_only)
    try:
        yield
    finally:
        _set_operator_access(directory, ntsecuritycon.FILE_ALL_ACCESS)


def test_an_acl_denied_stage_open_is_refused_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)
    write_profile_custody_local_record(path, _SECOND, publish_once=False)

    real_open = os.open
    real_replace = os.replace
    stage_attempts: list[Path] = []
    stage_errors: list[OSError] = []
    replace_attempts: list[str] = []

    def is_stage(raw_path: str | bytes | os.PathLike[str]) -> bool:
        candidate = Path(os.fsdecode(raw_path))
        return (
            candidate.parent == tmp_path
            and candidate.name.startswith(f"{path.name}.")
            and candidate.name.endswith(".tmp")
        )

    def observe_open(
        raw_path: str | bytes | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        stage = is_stage(raw_path) and bool(flags & os.O_EXCL)
        if stage:
            stage_attempts.append(Path(os.fsdecode(raw_path)))
        try:
            if dir_fd is None:
                return real_open(raw_path, flags, mode)
            return real_open(raw_path, flags, mode, dir_fd=dir_fd)
        except OSError as exc:
            if stage:
                stage_errors.append(exc)
                _record_native_error(record_property, phase="stage-open", error=exc)
            raise

    def observe_replace(source: str | bytes | os.PathLike[str], destination: str | bytes | os.PathLike[str]) -> None:
        if Path(os.fsdecode(destination)) == path:
            replace_attempts.append("attempted")
        real_replace(source, destination)

    monkeypatch.setattr(atomic_write.os, "open", observe_open)
    monkeypatch.setattr(atomic_write.os, "replace", observe_replace)

    with (
        _directory_refusing_new_files(tmp_path),
        pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written") as refused,
    ):
        write_profile_custody_local_record(path, _THIRD, publish_once=False)

    assert len(stage_attempts) == 1
    assert len(stage_errors) == 1
    assert isinstance(stage_errors[0], PermissionError)
    assert replace_attempts == []
    assert refused.value.__cause__ is stage_errors[0]
    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _SECOND
    residue = [child for child in tmp_path.iterdir() if child != path]
    assert residue == [], f"a refused stage-open left temporary files: {residue}"
    record_property("s16.stage_attempts", str(len(stage_attempts)))
    record_property("s16.replace_attempts", str(len(replace_attempts)))
    record_property("s16.typed_cause_object_id", hex(id(refused.value.__cause__)))
    record_property("s16.typed_cause_is_observed_native", str(refused.value.__cause__ is stage_errors[0]))
    record_property("s16.target_unchanged", "true")
    record_property("s16.stage_residue_count", str(len(residue)))


def test_synthetic_stage_winerror_five_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    path = tmp_path / "handover-journal"
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    stage_attempts: list[Path] = []
    replace_attempts: list[str] = []
    synthetic_errors: list[PermissionError] = []
    real_open = os.open
    real_replace = os.replace

    def observe_open(
        raw_path: str | bytes | os.PathLike[str],
        flags: int,
        _mode: int = 0o777,
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
            error = PermissionError(13, "synthetic stage denial", str(candidate), 5)
            synthetic_errors.append(error)
            _record_native_error(record_property, phase="stage-open-synthetic", error=error)
            raise error
        if dir_fd is None:
            return real_open(raw_path, flags, _mode)
        return real_open(raw_path, flags, _mode, dir_fd=dir_fd)

    def observe_replace(source: str | bytes | os.PathLike[str], destination: str | bytes | os.PathLike[str]) -> None:
        if Path(os.fsdecode(destination)) == path:
            replace_attempts.append("attempted")
        real_replace(source, destination)

    monkeypatch.setattr(atomic_write.os, "open", observe_open)
    monkeypatch.setattr(atomic_write.os, "replace", observe_replace)

    with pytest.raises(ProfileCustodyRecordError, match="cannot be atomically written") as refused:
        write_profile_custody_local_record(path, _SECOND, publish_once=False)

    assert len(stage_attempts) == 1
    assert len(synthetic_errors) == 1
    assert getattr(synthetic_errors[0], "winerror", None) == 5
    assert replace_attempts == []
    assert refused.value.__cause__ is synthetic_errors[0]
    assert read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT) == _FIRST
    residue = [child for child in tmp_path.iterdir() if child != path]
    assert residue == []
    record_property("s16.native.origin", "synthetic structural control; not OS evidence")
    record_property("s16.stage_attempts", str(len(stage_attempts)))
    record_property("s16.replace_attempts", str(len(replace_attempts)))
    record_property("s16.typed_cause_object_id", hex(id(refused.value.__cause__)))
    record_property("s16.typed_cause_is_synthetic_error", str(refused.value.__cause__ is synthetic_errors[0]))
    record_property("s16.target_unchanged", "true")
    record_property("s16.stage_residue_count", str(len(residue)))
