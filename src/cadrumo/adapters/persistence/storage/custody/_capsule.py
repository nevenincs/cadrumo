"""Immutable current-format capsule marker and one-rename publication seam."""

from __future__ import annotations

import os
import re
import stat
import sys
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import StorageCategory
from ._errors import ProfileCustodyRecordError
from ._kdf_supervision import ProfileCustodySentinelRecord
from ._paths import profile_custody_path
from ._records import ProfileCustodyEnvelope
from ._recovery import (
    PROFILE_CUSTODY_RECOVERY_FILENAME,
    ProfileCustodyRecoveryEnvelope,
    canonical_custody_digest,
    canonical_custody_json_bytes,
    reject_custody_json_constant,
    reject_duplicate_custody_members,
)
from ._sentinel import PROFILE_CUSTODY_SENTINEL_FILENAME, write_profile_custody_sentinel

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION: Final = 1
PROFILE_CUSTODY_LAYOUT_VERSION: Final = 1
PROFILE_CUSTODY_COMMIT_MAX_BYTES: Final = 512
PROFILE_CUSTODY_COMMIT_FILENAME: Final = "profile.commit.v1.json"
PROFILE_CUSTODY_DATA_MAX_ENTRIES: Final = 1024
PROFILE_CUSTODY_DATA_FILE_MAX_BYTES: Final = 64 * 1024 * 1024
_COMMIT_TIME_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z\Z")


class _ProfileCustodyCommitPayload(BaseModel):
    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    layout_version: Literal[1]
    profile_id: UUID
    transaction_id: UUID
    publication_kind: Literal["enroll", "restore"]
    published_at: str

    @field_validator("published_at")
    @classmethod
    def _validate_published_at(cls, value: str) -> str:
        if _COMMIT_TIME_RE.fullmatch(value) is None:
            raise ValueError("profile capsule publication time must be canonical UTC microseconds")
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError as exc:
            raise ValueError("profile capsule publication time is invalid") from exc
        return value


class ProfileCustodyCommit(_ProfileCustodyCommitPayload):
    """Minimal immutable marker that is the sole current-format discovery proof."""

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        if (
            len(value) != 71
            or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])
        ):
            raise ValueError("profile capsule self_digest must be a lowercase sha256 digest")
        return value

    @model_validator(mode="after")
    def _verify_self_digest(self) -> ProfileCustodyCommit:
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile capsule commit self_digest does not match")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["self_digest"]
        return payload

    @property
    def computed_self_digest(self) -> str:
        return canonical_custody_digest(
            self.canonical_payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )

    def canonical_json_bytes(self) -> bytes:
        return canonical_custody_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        publication_kind: Literal["enroll", "restore"],
        published_at: datetime | None = None,
    ) -> ProfileCustodyCommit:
        instant = (published_at or datetime.now(UTC)).astimezone(UTC)
        serialized_time = instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        payload = _ProfileCustodyCommitPayload(
            schema_version=PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION,
            layout_version=PROFILE_CUSTODY_LAYOUT_VERSION,
            profile_id=profile_id,
            transaction_id=transaction_id,
            publication_kind=publication_kind,
            published_at=serialized_time,
        ).model_dump(mode="json")
        payload["self_digest"] = canonical_custody_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
            subject="profile capsule commit",
        )
        try:
            return cls.model_validate_json(
                canonical_custody_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                    subject="profile capsule commit",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile capsule commit") from exc


def parse_profile_custody_commit(value: bytes) -> ProfileCustodyCommit:
    """Parse only one bounded canonical commit marker."""
    if len(value) > PROFILE_CUSTODY_COMMIT_MAX_BYTES:
        raise ProfileCustodyRecordError("profile capsule commit exceeds its canonical byte limit")
    try:
        import json

        parsed = json.loads(
            value.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_custody_members,
            parse_constant=reject_custody_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile capsule commit must be a JSON object")
        commit = ProfileCustodyCommit.model_validate_json(
            canonical_custody_json_bytes(
                cast(dict[str, object], parsed),
                maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                subject="profile capsule commit",
            ),
        )
        if commit.canonical_json_bytes() != value:
            raise ValueError("profile capsule commit is not canonical")
        return commit
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile capsule commit is not a valid current-format record") from exc


@dataclass(frozen=True, slots=True)
class ProfileCustodyPasswordMaterial:
    """The exact normal-password read set, intentionally excluding optional recovery."""

    capsule_path: Path
    commit: ProfileCustodyCommit
    envelope: ProfileCustodyEnvelope
    sentinel: ProfileCustodySentinelRecord
    access_trace: tuple[ProfileCustodyPasswordReadOperation, ...]


@dataclass(frozen=True, slots=True)
class ProfileCustodyPasswordReadOperation:
    """One actual filesystem operation in the normal-password read set."""

    operation: Literal["stat", "open", "read"]
    path: Path


def publish_profile_custody_capsule(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    publication_kind: Literal["enroll", "restore"],
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    data_files: Mapping[str, bytes],
    recovery_envelope: ProfileCustodyRecoveryEnvelope | None = None,
    settings: Settings | None = None,
    published_at: datetime | None = None,
) -> Path:
    """Build a complete sibling staging capsule and publish it with one rename."""
    _validate_publication_identity(
        profile_id=profile_id,
        password_envelope=password_envelope,
        sentinel=sentinel,
        recovery_envelope=recovery_envelope,
    )
    _validate_data_file_inventory(data_files)
    destination = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings).parent
    capsules_root = destination.parent
    _ensure_real_directory(capsules_root)
    if os.name != "nt":
        return _publish_profile_custody_capsule_posix(
            capsules_root=capsules_root,
            destination_name=destination.name,
            profile_id=profile_id,
            transaction_id=transaction_id,
            publication_kind=publication_kind,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files=data_files,
            recovery_envelope=recovery_envelope,
            published_at=published_at,
        )
    staging = profile_custody_staging_path(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
    )
    published = False
    stage_snapshot: dict[str, tuple[int, int, bool]] | None = None
    staging_handle: int | None = None
    with ExitStack() as root_anchors:
        root_handle = _anchor_directory(root_anchors, capsules_root, final_access=0x80000000)
        staging_anchors = ExitStack()
        content_anchors = ExitStack()
        try:
            staging.mkdir(mode=0o700, exist_ok=False)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule staging directory cannot be created") from exc
        try:
            staging_handle = _anchor_directory(staging_anchors, staging, final_access=0x80010000)
            custody_root = staging / "custody"
            data_root = staging / "data"
            custody_root.mkdir(mode=0o700)
            data_root.mkdir(mode=0o700)
            _anchor_directory(content_anchors, custody_root)
            _anchor_directory(content_anchors, data_root)
            _write_exclusive_fsynced(custody_root / "envelope.v1.json", password_envelope.canonical_json_bytes())
            if recovery_envelope is not None:
                _write_exclusive_fsynced(
                    custody_root / PROFILE_CUSTODY_RECOVERY_FILENAME, recovery_envelope.canonical_json_bytes()
                )
            write_profile_custody_sentinel(data_root / PROFILE_CUSTODY_SENTINEL_FILENAME, sentinel)
            _write_data_files(data_root, data_files)
            _fsync_directory(custody_root)
            _fsync_directory(data_root)
            commit = ProfileCustodyCommit.create(
                profile_id=profile_id,
                transaction_id=transaction_id,
                publication_kind=publication_kind,
                published_at=published_at,
            )
            _write_exclusive_fsynced(staging / PROFILE_CUSTODY_COMMIT_FILENAME, commit.canonical_json_bytes())
            _fsync_directory(staging)
            stage_snapshot = _windows_stage_snapshot(staging)
            # Child handles intentionally deny delete while staged.  They must
            # be released before Windows grants DELETE for the exact stage
            # handle's atomic rename, while the stage/root identities remain
            # anchored throughout.
            content_anchors.close()
            _rename_directory_noreplace(
                staging,
                destination,
                root_handle=root_handle,
                staging_handle=staging_handle,
            )
            staging_anchors.close()
            _write_through_windows_publication_fence(destination, root_handle=root_handle)
            published = True
            return destination
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule could not be atomically published") from exc
        finally:
            content_anchors.close()
            if not published and stage_snapshot is not None:
                _remove_windows_unpublished_staging(
                    staging,
                    staging_handle=staging_handle,
                    snapshot=stage_snapshot,
                )
            staging_anchors.close()


def _publish_profile_custody_capsule_posix(
    *,
    capsules_root: Path,
    destination_name: str,
    profile_id: UUID,
    transaction_id: UUID,
    publication_kind: Literal["enroll", "restore"],
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    data_files: Mapping[str, bytes],
    recovery_envelope: ProfileCustodyRecoveryEnvelope | None,
    published_at: datetime | None,
) -> Path:
    """Publish through descriptor-relative POSIX operations only."""
    staging_name = f".{profile_id}.staging-{transaction_id}"
    with _posix_directory_fd(capsules_root) as root_fd:
        try:
            os.mkdir(staging_name, mode=0o700, dir_fd=root_fd)
        except FileExistsError as exc:
            raise ProfileCustodyRecordError("profile capsule staging directory already exists") from exc
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule staging directory cannot be created") from exc
        stage_fd = _posix_open_child_directory(root_fd, staging_name)
        stage_identity = os.fstat(stage_fd)
        published = False
        try:
            custody_fd = _posix_mkdir_child_directory(stage_fd, "custody")
            data_fd = _posix_mkdir_child_directory(stage_fd, "data")
            try:
                _write_exclusive_fsynced_fd(custody_fd, "envelope.v1.json", password_envelope.canonical_json_bytes())
                if recovery_envelope is not None:
                    _write_exclusive_fsynced_fd(
                        custody_fd,
                        PROFILE_CUSTODY_RECOVERY_FILENAME,
                        recovery_envelope.canonical_json_bytes(),
                    )
                _write_exclusive_fsynced_fd(data_fd, PROFILE_CUSTODY_SENTINEL_FILENAME, sentinel.canonical_json_bytes())
                _write_posix_data_files(data_fd, data_files)
                os.fsync(custody_fd)
                os.fsync(data_fd)
            finally:
                os.close(custody_fd)
                os.close(data_fd)
            commit = ProfileCustodyCommit.create(
                profile_id=profile_id,
                transaction_id=transaction_id,
                publication_kind=publication_kind,
                published_at=published_at,
            )
            _write_exclusive_fsynced_fd(stage_fd, PROFILE_CUSTODY_COMMIT_FILENAME, commit.canonical_json_bytes())
            os.fsync(stage_fd)
            _renameat2_noreplace(
                source_fd=root_fd,
                source_name=staging_name,
                destination_fd=root_fd,
                destination_name=destination_name,
            )
            os.fsync(root_fd)
            published = True
            return capsules_root / destination_name
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule could not be atomically published") from exc
        finally:
            os.close(stage_fd)
            if not published:
                _remove_posix_staging_if_same(root_fd, staging_name, stage_identity)


def recognize_current_profile_capsule(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
    _trace: list[ProfileCustodyPasswordReadOperation] | None = None,
) -> Path | None:
    """Recognize an exact UUID capsule through its marker and nothing else."""
    marker_path = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings)
    capsule_path = marker_path.parent
    if not _lexists(capsule_path, trace=_trace):
        return None
    if os.name != "nt":
        with _posix_directory_fd(capsule_path) as capsule_fd:
            if not _posix_child_exists(capsule_fd, marker_path.name, trace=_trace, display_path=marker_path):
                return None
            commit = parse_profile_custody_commit(
                _read_regular_file_fd(
                    capsule_fd,
                    marker_path.name,
                    display_path=marker_path,
                    maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                    trace=_trace,
                )
            )
        if commit.profile_id != profile_id:
            raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
        return capsule_path
    with ExitStack() as anchors:
        _anchor_directory(anchors, capsule_path)
        if not _lexists(marker_path, trace=_trace):
            return None
        commit = parse_profile_custody_commit(
            _read_regular_file(marker_path, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES, trace=_trace)
        )
    if commit.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
    return capsule_path


def profile_custody_staging_path(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
) -> Path:
    """Return the one journal-addressable, permanently undiscoverable stage path."""
    destination = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings).parent
    return destination.parent / f".{profile_id}.staging-{transaction_id}"


def load_committed_profile_password_material(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
) -> ProfileCustodyPasswordMaterial:
    """Read normal-password authority without even resolving optional recovery paths."""
    trace: list[ProfileCustodyPasswordReadOperation] = []
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, _trace=trace)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    marker_path = capsule_path / PROFILE_CUSTODY_COMMIT_FILENAME
    if os.name != "nt":
        with _posix_directory_fd(capsule_path) as capsule_fd:
            custody_fd = _posix_open_child_directory(capsule_fd, "custody")
            data_fd = _posix_open_child_directory(capsule_fd, "data")
            try:
                commit = parse_profile_custody_commit(
                    _read_regular_file_fd(
                        capsule_fd,
                        marker_path.name,
                        display_path=marker_path,
                        maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                        trace=trace,
                    )
                )
                envelope = _read_password_envelope_fd(
                    custody_fd,
                    display_path=capsule_path / "custody" / "envelope.v1.json",
                    trace=trace,
                )
                sentinel = _read_sentinel_fd(
                    data_fd,
                    display_path=capsule_path / "data" / PROFILE_CUSTODY_SENTINEL_FILENAME,
                    trace=trace,
                )
            finally:
                os.close(custody_fd)
                os.close(data_fd)
    else:
        with ExitStack() as anchors:
            _anchor_directory(anchors, capsule_path)
            _anchor_directory(anchors, capsule_path / "custody")
            _anchor_directory(anchors, capsule_path / "data")
            commit = parse_profile_custody_commit(
                _read_regular_file(marker_path, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES, trace=trace)
            )
            envelope = _read_password_envelope(capsule_path / "custody" / "envelope.v1.json", trace=trace)
            sentinel = _read_sentinel(capsule_path / "data" / PROFILE_CUSTODY_SENTINEL_FILENAME, trace=trace)
    if envelope.profile_id != profile_id or sentinel.profile_id != profile_id:
        raise ProfileCustodyRecordError("normal password custody identity does not match its committed capsule")
    if sentinel.dek_epoch != envelope.dek_epoch:
        raise ProfileCustodyRecordError("normal password custody DEK epoch does not match its sentinel")
    return ProfileCustodyPasswordMaterial(
        capsule_path=capsule_path,
        commit=commit,
        envelope=envelope,
        sentinel=sentinel,
        access_trace=tuple(trace),
    )


def _validate_publication_identity(
    *,
    profile_id: UUID,
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    recovery_envelope: ProfileCustodyRecoveryEnvelope | None,
) -> None:
    if password_envelope.profile_id != profile_id or sentinel.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule custody identity does not match its immutable UUID")
    if sentinel.dek_epoch != password_envelope.dek_epoch:
        raise ProfileCustodyRecordError("profile capsule sentinel DEK epoch does not match password custody")
    if recovery_envelope is not None and (
        recovery_envelope.profile_id != profile_id or recovery_envelope.dek_epoch != password_envelope.dek_epoch
    ):
        raise ProfileCustodyRecordError("optional recovery identity does not match password custody")


def _write_data_files(data_root: Path, data_files: Mapping[str, bytes]) -> None:
    _validate_data_file_inventory(data_files)
    reserved = {PROFILE_CUSTODY_SENTINEL_FILENAME}
    for relative_name, payload in sorted(data_files.items()):
        relative_path = _validated_data_path(relative_name)
        if relative_path.as_posix() in reserved:
            raise ProfileCustodyRecordError("profile capsule data inventory tries to replace the DEK sentinel")
        target = data_root.joinpath(*relative_path.parts)
        # `mkdir(parents=True)` follows an existing intermediate link.  Build
        # every component deliberately and retain no-delete anchors until the
        # leaf is durably created instead.
        with ExitStack() as anchors:
            current = data_root
            for component in relative_path.parts[:-1]:
                candidate = current / component
                with suppress(FileExistsError):
                    candidate.mkdir(mode=0o700)
                _anchor_directory(anchors, candidate)
                current = candidate
            _write_exclusive_fsynced(target, payload)
            _fsync_directory(target.parent)


def _validated_data_path(value: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise ProfileCustodyRecordError("profile capsule data path must be a nonempty portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(component in {"", ".", ".."} for component in path.parts):
        raise ProfileCustodyRecordError("profile capsule data path escapes its staging root")
    return path


def _validate_data_file_inventory(data_files: Mapping[str, bytes]) -> None:
    if len(data_files) > PROFILE_CUSTODY_DATA_MAX_ENTRIES:
        raise ProfileCustodyRecordError("profile capsule data inventory exceeds its entry limit")
    for relative_name, payload in data_files.items():
        _validated_data_path(relative_name)
        if len(payload) > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES:
            raise ProfileCustodyRecordError("profile capsule data file is outside its bounded write contract")


def _read_password_envelope(
    path: Path,
    *,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodyEnvelope:
    from ._records import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, parse_profile_custody_envelope

    return parse_profile_custody_envelope(
        _read_regular_file(path, maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, trace=trace)
    )


def _read_password_envelope_fd(
    parent_fd: int,
    *,
    display_path: Path,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodyEnvelope:
    from ._records import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, parse_profile_custody_envelope

    return parse_profile_custody_envelope(
        _read_regular_file_fd(
            parent_fd,
            "envelope.v1.json",
            display_path=display_path,
            maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
            trace=trace,
        )
    )


def _read_sentinel(
    path: Path,
    *,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodySentinelRecord:
    from ._kdf_supervision import parse_profile_custody_sentinel_record
    from ._sentinel import PROFILE_CUSTODY_SENTINEL_MAX_BYTES

    return parse_profile_custody_sentinel_record(
        _read_regular_file(path, maximum_bytes=PROFILE_CUSTODY_SENTINEL_MAX_BYTES, trace=trace)
    )


def _read_sentinel_fd(
    parent_fd: int,
    *,
    display_path: Path,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodySentinelRecord:
    from ._kdf_supervision import parse_profile_custody_sentinel_record
    from ._sentinel import PROFILE_CUSTODY_SENTINEL_MAX_BYTES

    return parse_profile_custody_sentinel_record(
        _read_regular_file_fd(
            parent_fd,
            PROFILE_CUSTODY_SENTINEL_FILENAME,
            display_path=display_path,
            maximum_bytes=PROFILE_CUSTODY_SENTINEL_MAX_BYTES,
            trace=trace,
        )
    )


def _ensure_real_directory(path: Path) -> None:
    if os.path.lexists(path) and not _is_real_directory(path):
        raise ProfileCustodyRecordError("profile capsule root must not be a link or non-directory")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule root cannot be created") from exc
    if not _is_real_directory(path):
        raise ProfileCustodyRecordError("profile capsule root was not created as a real directory")


def _is_real_directory(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode) and not bool(attributes & reparse)


def _anchor_directory(stack: ExitStack, path: Path, *, final_access: int = 0) -> int | None:
    """Keep a verified directory identity non-deletable for a path operation."""
    if os.name == "nt":
        return stack.enter_context(_windows_directory_anchor(path, final_access=final_access))
    return stack.enter_context(_posix_directory_fd(path))


@contextmanager
def _windows_directory_anchor(path: Path, *, final_access: int = 0) -> Generator[int]:
    """Lock every real component against reparse and delete substitution."""
    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTimeLow", wintypes.DWORD),
            ("ftCreationTimeHigh", wintypes.DWORD),
            ("ftLastAccessTimeLow", wintypes.DWORD),
            ("ftLastAccessTimeHigh", wintypes.DWORD),
            ("ftLastWriteTimeLow", wintypes.DWORD),
            ("ftLastWriteTimeHigh", wintypes.DWORD),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handles: list[int] = []
    try:
        current = Path(path.anchor)
        components = path.parts[1:] if path.anchor else path.parts
        for index, component in enumerate(components):
            current /= component
            handle = create_file(
                str(current),
                final_access if index == len(components) - 1 else 0,
                0x00000001 | 0x00000002,
                None,
                3,
                0x02000000 | 0x00200000,
                None,
            )
            if handle == wintypes.HANDLE(-1).value:
                raise ProfileCustodyRecordError("profile capsule directory cannot be identity-anchored")
            handles.append(int(handle))
            info = _ByHandleFileInformation()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError("profile capsule directory identity cannot be verified")
            if not info.dwFileAttributes & 0x10 or info.dwFileAttributes & 0x400:
                raise ProfileCustodyRecordError(
                    "profile capsule directory must not be a reparse point or non-directory"
                )
        if not handles:
            raise ProfileCustodyRecordError("profile capsule directory cannot be identity-anchored")
        yield handles[-1]
    finally:
        for handle in reversed(handles):
            kernel32.CloseHandle(handle)


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None = None,
) -> bytes:
    _record_read_operation(trace, "open", path)
    if os.name != "nt":
        with _posix_directory_fd(path.parent) as parent_fd:
            return _read_regular_file_open(
                path,
                maximum_bytes=maximum_bytes,
                trace=trace,
                parent_fd=parent_fd,
            )
    with _windows_regular_file_anchor(path):
        return _read_regular_file_open(path, maximum_bytes=maximum_bytes, trace=trace)


def _read_regular_file_open(
    path: Path,
    *,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None,
    parent_fd: int | None = None,
) -> bytes:
    try:
        if parent_fd is None:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        else:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule record is unavailable") from exc
    try:
        _record_read_operation(trace, "stat", path)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1 or metadata.st_size > maximum_bytes:
            raise ProfileCustodyRecordError("profile capsule record is not a bounded regular file")
        _record_read_operation(trace, "read", path)
        payload = os.read(descriptor, maximum_bytes + 1)
        if len(payload) != metadata.st_size or len(payload) > maximum_bytes:
            raise ProfileCustodyRecordError("profile capsule record changed during its bounded read")
        return payload
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule record cannot be read") from exc
    finally:
        os.close(descriptor)


def _read_regular_file_fd(
    parent_fd: int,
    name: str,
    *,
    display_path: Path,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None,
) -> bytes:
    _record_read_operation(trace, "open", display_path)
    return _read_regular_file_open(
        Path(name),
        maximum_bytes=maximum_bytes,
        trace=trace,
        parent_fd=parent_fd,
    )


@contextmanager
def _windows_regular_file_anchor(path: Path):
    """Reject a final reparse point, then lock the verified leaf against replacement."""
    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTimeLow", wintypes.DWORD),
            ("ftCreationTimeHigh", wintypes.DWORD),
            ("ftLastAccessTimeLow", wintypes.DWORD),
            ("ftLastAccessTimeHigh", wintypes.DWORD),
            ("ftLastWriteTimeLow", wintypes.DWORD),
            ("ftLastWriteTimeHigh", wintypes.DWORD),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.windll.kernel32
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(str(path), 0, 0x00000001 | 0x00000002, None, 3, 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ProfileCustodyRecordError("profile capsule record cannot be no-follow opened")
    try:
        info = _ByHandleFileInformation()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ProfileCustodyRecordError("profile capsule record identity cannot be verified")
        if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
            raise ProfileCustodyRecordError("profile capsule record must not be a reparse point or directory")
        yield
    finally:
        kernel32.CloseHandle(handle)


def _lexists(path: Path, *, trace: list[ProfileCustodyPasswordReadOperation] | None) -> bool:
    _record_read_operation(trace, "stat", path)
    if os.name == "nt":
        return os.path.lexists(path)
    try:
        with _posix_directory_fd(path.parent) as parent_fd:
            os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule path cannot be no-follow inspected") from exc
    return True


def _posix_child_exists(
    parent_fd: int,
    name: str,
    *,
    trace: list[ProfileCustodyPasswordReadOperation] | None,
    display_path: Path,
) -> bool:
    _record_read_operation(trace, "stat", display_path)
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule path cannot be no-follow inspected") from exc
    return True


def _record_read_operation(
    trace: list[ProfileCustodyPasswordReadOperation] | None,
    operation: Literal["stat", "open", "read"],
    path: Path,
) -> None:
    if trace is not None:
        trace.append(ProfileCustodyPasswordReadOperation(operation=operation, path=path))


def _write_exclusive_fsynced(path: Path, payload: bytes) -> None:
    if os.name != "nt" and not _is_real_directory(path.parent):
        raise ProfileCustodyRecordError("profile capsule staging parent must not be a link or reparse directory")
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record cannot be exclusively created") from exc
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("profile capsule staging short write")
            offset += written
        os.fsync(descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record could not be fsynced") from exc
    finally:
        os.close(descriptor)


@contextmanager
def _posix_directory_fd(path: Path) -> Generator[int]:
    """Walk an absolute directory a component at a time without following links."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.anchor or "/", flags)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule root cannot be no-follow opened") from exc
    try:
        components = path.parts[1:] if path.anchor else path.parts
        for component in components:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        yield descriptor
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory component is unsafe") from exc
    finally:
        os.close(descriptor)


def _posix_open_child_directory(parent_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory component is unsafe") from exc


def _posix_mkdir_child_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging directory cannot be created") from exc
    return _posix_open_child_directory(parent_fd, name)


def _write_exclusive_fsynced_fd(parent_fd: int, name: str, payload: bytes) -> None:
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record cannot be exclusively created") from exc
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("profile capsule staging short write")
            offset += written
        os.fsync(descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record could not be fsynced") from exc
    finally:
        os.close(descriptor)


def _write_posix_data_files(data_fd: int, data_files: Mapping[str, bytes]) -> None:
    if len(data_files) > PROFILE_CUSTODY_DATA_MAX_ENTRIES:
        raise ProfileCustodyRecordError("profile capsule data inventory exceeds its entry limit")
    for relative_name, payload in sorted(data_files.items()):
        relative_path = _validated_data_path(relative_name)
        if relative_path.as_posix() == PROFILE_CUSTODY_SENTINEL_FILENAME:
            raise ProfileCustodyRecordError("profile capsule data inventory tries to replace the DEK sentinel")
        if len(payload) > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES:
            raise ProfileCustodyRecordError("profile capsule data file is outside its bounded write contract")
        current_fd = os.dup(data_fd)
        try:
            for component in relative_path.parts[:-1]:
                with suppress(FileExistsError):
                    os.mkdir(component, mode=0o700, dir_fd=current_fd)
                next_fd = _posix_open_child_directory(current_fd, component)
                os.close(current_fd)
                current_fd = next_fd
            _write_exclusive_fsynced_fd(current_fd, relative_path.name, payload)
            os.fsync(current_fd)
        finally:
            os.close(current_fd)


def _remove_posix_staging_if_same(parent_fd: int, name: str, identity: os.stat_result) -> None:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProfileCustodyRecordError("unpublished profile capsule staging cannot be inspected") from exc
    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
        raise ProfileCustodyRecordError("unpublished profile capsule staging identity changed before cleanup")
    _remove_posix_tree(parent_fd, name)


def _remove_posix_tree(parent_fd: int, name: str) -> None:
    target_fd = _posix_open_child_directory(parent_fd, name)
    try:
        with os.scandir(target_fd) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    _remove_posix_tree(target_fd, entry.name)
                else:
                    os.unlink(entry.name, dir_fd=target_fd)
    finally:
        os.close(target_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        # Windows does not expose a directory FlushFileBuffers contract. Every
        # staged file is already fsynced; publication uses MoveFileEx
        # WRITE_THROUGH below as the mandatory metadata durability fence.
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory cannot be opened for durability") from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory could not be fsynced") from exc
    finally:
        os.close(descriptor)


def _rename_directory_noreplace(
    staging: Path,
    destination: Path,
    *,
    root_handle: int | None,
    staging_handle: int | None = None,
) -> None:
    """Publish exactly once; fail closed where the platform has no no-replace rename."""
    if os.name == "nt":
        if root_handle is None:
            raise ProfileCustodyRecordError("profile capsule root is not identity-anchored")
        if staging_handle is None:
            raise ProfileCustodyRecordError("profile capsule staging is not identity-anchored")
        _rename_windows_directory_by_handle(staging_handle, destination, root_handle=root_handle)
        return
    if sys.platform.startswith("linux"):
        if staging.parent != destination.parent:
            raise ProfileCustodyRecordError("profile capsule staging and destination roots must match")
        with _posix_directory_fd(staging.parent) as parent_fd:
            _renameat2_noreplace(
                source_fd=parent_fd,
                source_name=staging.name,
                destination_fd=parent_fd,
                destination_name=destination.name,
            )
        return
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication is unavailable on this platform")


def _renameat2_noreplace(*, source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    import ctypes
    import errno

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise ProfileCustodyRecordError("atomic no-replace profile capsule publication is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(source_fd, os.fsencode(source_name), destination_fd, os.fsencode(destination_name), 1) == 0:
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ProfileCustodyRecordError("profile capsule destination already exists") from None
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication failed") from OSError(
        error, os.strerror(error)
    )


def _rename_windows_directory_by_handle(staging_handle: int, destination: Path, *, root_handle: int) -> None:
    """Rename the exact open stage while the complete destination ancestry is locked."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace_if_exists", wintypes.BOOLEAN),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    # A mapped/network volume may reject a non-null RootDirectory.  The source
    # is still renamed by its already-open handle, while the component-wise
    # root anchor makes this absolute destination immutable for the call.
    destination_name = str(destination)
    encoded_name = destination_name.encode("utf-16-le")
    name_offset = _FileRenameInfo.file_name.offset
    # FILE_RENAME_INFO declares one WCHAR in the flexible tail.  The Win32
    # information length is the declared structure plus the remaining UTF-16
    # code units, not the structure's alignment padding.
    rename_buffer = ctypes.create_string_buffer(
        ctypes.sizeof(_FileRenameInfo) + len(encoded_name) - ctypes.sizeof(wintypes.WCHAR)
    )
    rename = _FileRenameInfo.from_buffer(rename_buffer)
    rename.replace_if_exists = False
    rename.root_directory = wintypes.HANDLE()
    rename.file_name_length = len(encoded_name)
    ctypes.memmove(ctypes.addressof(rename_buffer) + name_offset, encoded_name, len(encoded_name))
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    if set_information(
        wintypes.HANDLE(staging_handle),
        3,  # FileRenameInfo: ReplaceIfExists=False is the no-replace contract.
        ctypes.byref(rename),
        len(rename_buffer),
    ):
        return
    error = ctypes.get_last_error()
    if error in {80, 183}:
        raise ProfileCustodyRecordError("profile capsule destination already exists") from None
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication failed") from OSError(
        error, "SetFileInformationByHandle(FileRenameInfo)"
    )


def _write_through_windows_publication_fence(destination: Path, *, root_handle: int | None) -> None:
    """Commit the prior handle-relative rename through Windows' supported fence."""
    if root_handle is None:
        raise ProfileCustodyRecordError("profile capsule root is not identity-anchored for durability")
    import ctypes
    from ctypes import wintypes

    # FlushFileBuffers rejects directory handles on the supported filesystem
    # stack here.  MoveFileExW with MOVEFILE_WRITE_THROUGH is the documented
    # Windows metadata durability contract and remains safe because the entire
    # absolute ancestry is held by no-delete, no-reparse anchors.
    move_file = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD]
    move_file.restype = wintypes.BOOL
    if not move_file(str(destination), str(destination), 0x00000008):
        error = ctypes.get_last_error()
        if error == 109:  # ERROR_BROKEN_PIPE from a mapped/server volume.
            _fsync_windows_published_commit(destination)
            return
        raise ProfileCustodyRecordError("profile capsule root durability fence failed") from OSError(
            error, "MoveFileExW(MOVEFILE_WRITE_THROUGH)"
        )


def _fsync_windows_published_commit(destination: Path) -> None:
    """Use the server-backed commit record as the remote-volume durability fence."""
    try:
        descriptor = os.open(
            destination / PROFILE_CUSTODY_COMMIT_FILENAME,
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("published profile capsule commit cannot be durability-fenced") from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("published profile capsule commit durability fence failed") from exc
    finally:
        os.close(descriptor)


def _windows_stage_snapshot(staging: Path) -> dict[str, tuple[int, int, bool]]:
    """Capture the exact transaction-owned tree before any cleanup can occur."""
    try:
        snapshot: dict[str, tuple[int, int, bool]] = {}
        for current, directories, files in os.walk(staging, topdown=True, followlinks=False):
            current_path = Path(current)
            relative = current_path.relative_to(staging).as_posix()
            metadata = current_path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or _is_reparse_metadata(metadata):
                raise ProfileCustodyRecordError("unpublished profile capsule staging contains a reparse point")
            snapshot[relative] = (metadata.st_dev, metadata.st_ino, True)
            for name in [*directories, *files]:
                entry = current_path / name
                entry_metadata = entry.lstat()
                if stat.S_ISLNK(entry_metadata.st_mode) or _is_reparse_metadata(entry_metadata):
                    raise ProfileCustodyRecordError("unpublished profile capsule staging contains a reparse point")
                snapshot[entry.relative_to(staging).as_posix()] = (
                    entry_metadata.st_dev,
                    entry_metadata.st_ino,
                    stat.S_ISDIR(entry_metadata.st_mode),
                )
        return snapshot
    except OSError as exc:
        raise ProfileCustodyRecordError("unpublished profile capsule staging cannot be identity-inventoried") from exc


def _remove_windows_unpublished_staging(
    staging: Path,
    *,
    staging_handle: int | None,
    snapshot: Mapping[str, tuple[int, int, bool]],
) -> None:
    """Delete only entries proven unchanged while the exact stage is pinned."""
    if staging_handle is None:
        raise ProfileCustodyRecordError("unpublished profile capsule staging is not identity-anchored")
    current_snapshot = _windows_stage_snapshot(staging)
    if current_snapshot != snapshot:
        raise ProfileCustodyRecordError("unpublished profile capsule staging changed before safe cleanup")
    # A native delete disposition is attached to an exact no-reparse handle;
    # postorder guarantees directory emptiness and refuses any swap before it
    # can be marked for removal.
    entries = sorted(snapshot.items(), key=lambda item: item[0].count("/"), reverse=True)
    for relative_name, expected in entries:
        if relative_name == ".":
            continue
        target = staging if relative_name == "." else staging.joinpath(*relative_name.split("/"))
        _windows_delete_exact_entry(target, expected)
    _windows_mark_handle_for_deletion(staging_handle)


def _windows_delete_exact_entry(target: Path, expected: tuple[int, int, bool]) -> None:
    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTimeLow", wintypes.DWORD),
            ("ftCreationTimeHigh", wintypes.DWORD),
            ("ftLastAccessTimeLow", wintypes.DWORD),
            ("ftLastAccessTimeHigh", wintypes.DWORD),
            ("ftLastWriteTimeLow", wintypes.DWORD),
            ("ftLastWriteTimeHigh", wintypes.DWORD),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(str(target), 0x00010000, 0x00000001 | 0x00000002, None, 3, 0x02000000 | 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ProfileCustodyRecordError("unpublished profile capsule entry cannot be identity-opened")
    try:
        info = _ByHandleFileInformation()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ProfileCustodyRecordError("unpublished profile capsule entry identity cannot be verified")
        # Python's volume/inode identity is the stable comparison surface used
        # for the recorded inventory; lstat immediately follows each native
        # handle operation so a provider with a different mapping still fails
        # closed if the path changed.
        metadata = target.lstat()
        actual = (metadata.st_dev, metadata.st_ino, stat.S_ISDIR(metadata.st_mode))
        if actual != expected or _is_reparse_metadata(metadata) or stat.S_ISLNK(metadata.st_mode):
            raise ProfileCustodyRecordError("unpublished profile capsule entry changed before safe cleanup")
        _windows_mark_handle_for_deletion(int(handle))
    finally:
        kernel32.CloseHandle(handle)


def _windows_mark_handle_for_deletion(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOLEAN)]

    disposition = _FileDispositionInfo(True)
    set_information = ctypes.WinDLL("kernel32", use_last_error=True).SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    if not set_information(wintypes.HANDLE(handle), 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
        raise ProfileCustodyRecordError("unpublished profile capsule entry cannot be safely removed")


def _is_reparse_metadata(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


__all__ = [
    "PROFILE_CUSTODY_COMMIT_FILENAME",
    "PROFILE_CUSTODY_COMMIT_MAX_BYTES",
    "PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION",
    "PROFILE_CUSTODY_LAYOUT_VERSION",
    "ProfileCustodyCommit",
    "ProfileCustodyPasswordMaterial",
    "ProfileCustodyPasswordReadOperation",
    "load_committed_profile_password_material",
    "parse_profile_custody_commit",
    "profile_custody_staging_path",
    "publish_profile_custody_capsule",
    "recognize_current_profile_capsule",
]
