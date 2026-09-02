"""Portable recovery-artifact records and guarded external export."""

from __future__ import annotations

import ctypes
import json
import os
import stat
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from .....application.user_profile.recovery_contracts import ProfileCustodyRecoveryArtifactWarning
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import (
    bounded_canonical_json_bytes,
    canonical_json_digest,
    reject_duplicate_json_members,
    reject_json_constant,
    validate_prefixed_digest,
)
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .digest_model import CustodyDigestModel
from .errors import ProfileCustodyRecordError
from .filesystem_primitives import WindowsDirectoryAnchorErrors, windows_directory_anchor, windows_file_information_type
from .kdf_supervision import (
    unlock_profile_custody,
    unlock_profile_custody_recovery_material,
)
from .records import (
    PROFILE_CUSTODY_PASSWORD_GENERATION_MAX,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from .recovery import (
    PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
    ProfileCustodyRecoveryAad,
    ProfileCustodyRecoveryEnvelope,
    ProfileCustodyRecoveryUnlock,
    profile_custody_recovery_aad_for,
    validate_profile_custody_dek_epoch,
)
from .sentinel_contract import ProfileCustodySentinelRecord, verify_profile_custody_sentinel

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_RECOVERY_ARTIFACT_SCHEMA: Final = "profile-recovery-artifact/v1"

_RECOVERY_DIRECTORY_ANCHOR_ERRORS = WindowsDirectoryAnchorErrors(
    cannot_open="recovery artifact target parent is not a safe existing directory",
    cannot_verify="recovery artifact target parent identity cannot be verified",
    invalid_entry="recovery artifact target parent must not be a reparse point or non-directory",
    empty_path="recovery artifact target parent is not a safe existing directory",
)


class _RecoveryArtifactPayload(BaseModel):
    model_config = _STRICT_FROZEN

    artifact_schema: Literal["profile-recovery-artifact/v1"]
    profile_id: UUID
    dek_epoch: str
    recovery_generation: int = Field(ge=1, le=PROFILE_CUSTODY_PASSWORD_GENERATION_MAX)
    kdf: ProfileCustodyKdfParameters
    wrapped_dek: ProfileCustodyWrappedDek
    aad: ProfileCustodyRecoveryAad

    @field_validator("dek_epoch")
    @classmethod
    def _validate_epoch(cls, value: str) -> str:
        return validate_profile_custody_dek_epoch(value)


class ProfileCustodyRecoveryArtifact(_RecoveryArtifactPayload, CustodyDigestModel):
    """Portable current-format recovery material, with no normal-login state."""

    _digest_maximum_bytes: ClassVar[int] = PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES
    _digest_subject: ClassVar[str] = "profile custody recovery artifact"
    _digest_mismatch_message: ClassVar[str] = "profile recovery artifact self_digest does not match"

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="self_digest")

    @classmethod
    def from_recovery_envelope(cls, envelope: ProfileCustodyRecoveryEnvelope) -> ProfileCustodyRecoveryArtifact:
        """Derive a portable artifact from an already-current recovery envelope.

        Unlike :meth:`~...recovery.ProfileCustodyRecoveryEnvelope.create`, this
        does not accept raw KDF/wrap parameters — it projects them out of an
        envelope that has ALREADY passed its own self-digest check, so the
        artifact can only ever carry material the custody substrate itself
        vouched for, never values assembled ad hoc for export.
        """
        payload = _RecoveryArtifactPayload(
            artifact_schema=PROFILE_CUSTODY_RECOVERY_ARTIFACT_SCHEMA,
            profile_id=envelope.profile_id,
            dek_epoch=envelope.dek_epoch,
            recovery_generation=envelope.recovery_generation,
            kdf=envelope.kdf,
            wrapped_dek=envelope.wrapped_dek,
            aad=envelope.aad,
        ).model_dump(mode="json")
        payload["self_digest"] = canonical_json_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
            subject="profile recovery artifact",
        )
        try:
            return cls.model_validate_json(
                bounded_canonical_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
                    subject="profile recovery artifact",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile recovery artifact") from exc


@dataclass(frozen=True, slots=True)
class ProfileCustodyRecoveryArtifactExportReceipt:
    """Non-secret durable-export result with the mandatory recovery warnings."""

    artifact: ProfileCustodyRecoveryArtifact
    target: Path
    warnings: tuple[ProfileCustodyRecoveryArtifactWarning, ...]


def parse_profile_custody_recovery_artifact(value: bytes) -> ProfileCustodyRecoveryArtifact:
    """Parse exactly one bounded canonical portable recovery artifact."""
    if len(value) > PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES:
        raise ProfileCustodyRecordError("profile recovery artifact exceeds its canonical byte limit")
    try:
        parsed = json.loads(
            value.decode(_UTF_8_ENCODING, errors="strict"),
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile recovery artifact must be a JSON object")
        artifact = ProfileCustodyRecoveryArtifact.model_validate_json(
            bounded_canonical_json_bytes(
                cast(dict[str, object], parsed),
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
                subject="profile recovery artifact",
            ),
        )
        if artifact.canonical_json_bytes() != value:
            raise ValueError("profile recovery artifact is not canonical")
        return artifact
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile recovery artifact is not a valid current-format record") from exc


def refuse_hostile_recovery_artifact_destination(target: Path, *, settings: Settings | None = None) -> None:
    """Refuse a destination this export must not resolve, rather than warn about it.

    An artifact is wrapped key material leaving the encrypted store, so the
    destination is part of the exposure decision and not a formatting detail.
    Three shapes are refused outright because no warning makes them safe.

    A RELATIVE destination names a file the operator did not fully choose: it
    resolves against whatever directory the process happened to start in, so
    the operator and the export can disagree about where the second door was
    left, and the answer is unrecoverable afterwards.

    A destination carrying ``..`` or ``.`` is refused for the same reason
    reversed -- the written path and the typed path are not visibly the same
    path, and the parent-identity anchor below verifies the parent the export
    actually opens, not the one the operator believes they named.

    A destination INSIDE the Cadrumo storage root is refused because it
    defeats the export's own store-separately warning by construction: the
    artifact and the ciphertext it can unwrap would share one directory tree,
    one backup, and one theft. Inside a bucket it is worse than pointless --
    the capsule inventory folds every regular file under the bucket into the
    deletion fingerprint, so a stray artifact would silently change a
    fingerprint a later resume compares against.
    """
    if not target.is_absolute():
        raise ProfileCustodyRecordError(
            "recovery artifact destination must be an absolute path, not one resolved against a working directory"
        )
    if any(part in {os.pardir, os.curdir} for part in target.parts):
        raise ProfileCustodyRecordError(
            "recovery artifact destination must be a direct path carrying no parent or current directory segment"
        )
    from .....core.paths import effective_storage_root

    storage_root = effective_storage_root(settings=settings)
    if target == storage_root or storage_root in target.parents:
        raise ProfileCustodyRecordError(
            "recovery artifact destination must be outside the Cadrumo storage root, "
            "so the artifact cannot be stored with the data it unwraps"
        )


def export_profile_custody_recovery_artifact(
    envelope: ProfileCustodyRecoveryEnvelope,
    *,
    current_password: str,
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    target: Path,
    settings: Settings | None = None,
) -> ProfileCustodyRecoveryArtifactExportReceipt:
    """Exclusively create a durable external artifact after password authentication."""
    refuse_hostile_recovery_artifact_destination(target, settings=settings)
    if password_envelope.profile_id != envelope.profile_id or password_envelope.dek_epoch != envelope.dek_epoch:
        raise ProfileCustodyRecordError(
            "current password custody proof does not authorize this recovery artifact export"
        )
    password_unlock = unlock_profile_custody(
        password_envelope,
        current_password,
        sentinel=sentinel,
        settings=settings,
    )
    verify_profile_custody_sentinel(
        dek=password_unlock.dek,
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        sentinel=sentinel,
    )
    artifact = ProfileCustodyRecoveryArtifact.from_recovery_envelope(envelope)
    _write_external_exclusive(target, artifact.canonical_json_bytes())
    return ProfileCustodyRecoveryArtifactExportReceipt(
        artifact=artifact,
        target=target,
        warnings=tuple(ProfileCustodyRecoveryArtifactWarning),
    )


def import_profile_custody_recovery_artifact(
    source: Path,
    *,
    expected_profile_id: UUID,
    expected_dek_epoch: str,
) -> ProfileCustodyRecoveryArtifact:
    """Read an artifact without any implicit recovery enrollment or overwrite."""
    artifact = parse_profile_custody_recovery_artifact(
        _read_external_regular_file(source, maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES),
    )
    if artifact.profile_id != expected_profile_id or artifact.dek_epoch != expected_dek_epoch:
        raise ProfileCustodyRecordError("recovery artifact UUID or DEK epoch does not match its named target")
    return artifact


def unlock_imported_profile_custody_recovery_artifact(
    artifact: ProfileCustodyRecoveryArtifact,
    recovery_secret: str,
    *,
    sentinel: ProfileCustodySentinelRecord,
    expected_profile_id: UUID,
    expected_dek_epoch: str,
    settings: Settings | None = None,
) -> ProfileCustodyRecoveryUnlock:
    """Prove an imported artifact with its named identity and committed sentinel.

    This does not install, overwrite, or re-enroll recovery. Recovery is
    enrolled only while the profile is created; an imported artifact proves
    the existing wrapper without opening a second installation path.
    """
    if artifact.profile_id != expected_profile_id or artifact.dek_epoch != expected_dek_epoch:
        raise ProfileCustodyRecordError("recovery artifact UUID or DEK epoch does not match its named target")
    dek = unlock_profile_custody_recovery_material(
        profile_id=artifact.profile_id,
        dek_epoch=artifact.dek_epoch,
        kdf=artifact.kdf,
        wrapped_dek=artifact.wrapped_dek,
        secret=recovery_secret,
        associated_data=profile_custody_recovery_aad_for(
            profile_id=artifact.profile_id,
            dek_epoch=artifact.dek_epoch,
            recovery_generation=artifact.recovery_generation,
            kdf=artifact.kdf,
            aad=artifact.aad,
        ),
        sentinel=sentinel,
        settings=settings,
    )
    return ProfileCustodyRecoveryUnlock(
        profile_id=artifact.profile_id,
        dek_epoch=artifact.dek_epoch,
        recovery_digest=artifact.self_digest,
        dek=dek,
    )


def _read_external_regular_file(path: Path, *, maximum_bytes: int) -> bytes:
    """Read a bounded regular file OUTSIDE the storage root, anchored externally.

    Named for its constraint shape rather than its action, because the custody
    package holds another reader with the same action and a different
    guarantee: ``_filesystem._read_regular_file`` anchors a directory INSIDE
    the storage root and cannot serve a recovery artifact, which by design
    lives outside it. Two readers named alike is how a caller ends up assuming
    the guarantee it did not get -- a third one, in the sentinel module, lost
    its no-follow protection entirely on Windows while carrying the same name.
    """
    if os.name == "nt":
        with _windows_external_directory_anchor(path.parent):
            return _read_windows_regular_file(path, maximum_bytes=maximum_bytes)
    with _posix_external_directory_fd(path.parent) as parent_descriptor:
        return _read_posix_regular_file(
            parent_descriptor,
            path.name,
            maximum_bytes=maximum_bytes,
        )


def _read_posix_regular_file(parent_descriptor: int, name: str, *, maximum_bytes: int) -> bytes:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile recovery record is unavailable") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1 or metadata.st_size > maximum_bytes:
            raise ProfileCustodyRecordError("profile recovery record is not a bounded regular file")
        payload = os.read(descriptor, maximum_bytes + 1)
        if len(payload) != metadata.st_size or len(payload) > maximum_bytes:
            raise ProfileCustodyRecordError("profile recovery record changed during its bounded read")
        return payload
    except OSError as exc:
        raise ProfileCustodyRecordError("profile recovery record cannot be read") from exc
    finally:
        os.close(descriptor)


def _read_windows_regular_file(path: Path, *, maximum_bytes: int) -> bytes:
    """Read an exact leaf handle after rejecting every reparse ancestor."""
    file_information_type = windows_file_information_type()
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
    handle = create_file(
        str(path),
        0x80000000,
        0x00000001 | 0x00000002,
        None,
        3,
        0x00200000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ProfileCustodyRecordError("profile recovery record is unavailable")
    try:
        info = file_information_type()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ProfileCustodyRecordError("profile recovery record identity cannot be verified")
        if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
            raise ProfileCustodyRecordError("profile recovery record must be a non-reparse regular file")
        size = ctypes.c_longlong()
        if not kernel32.GetFileSizeEx(handle, ctypes.byref(size)):
            raise ProfileCustodyRecordError("profile recovery record size cannot be verified")
        if size.value < 1 or size.value > maximum_bytes:
            raise ProfileCustodyRecordError("profile recovery record is not a bounded regular file")
        buffer = ctypes.create_string_buffer(size.value + 1)
        read = wintypes.DWORD()
        read_file = kernel32.ReadFile
        read_file.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        read_file.restype = wintypes.BOOL
        if not read_file(handle, buffer, size.value + 1, ctypes.byref(read), None):
            raise ProfileCustodyRecordError("profile recovery record cannot be read")
        if read.value != size.value:
            raise ProfileCustodyRecordError("profile recovery record changed during its bounded read")
        return buffer.raw[: read.value]
    finally:
        kernel32.CloseHandle(handle)


def _write_external_exclusive(path: Path, payload: bytes) -> None:
    if not path.name:
        raise ProfileCustodyRecordError("recovery artifact target parent is not a safe existing directory")
    parent_descriptor: int | None = None
    descriptor: int | None = None
    anchor = (
        _windows_external_directory_anchor(path.parent)
        if os.name == "nt"
        else _posix_external_directory_fd(path.parent)
    )
    try:
        with anchor as anchored_parent:
            if os.name == "nt":
                descriptor = os.open(
                    path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                    0o600,
                )
            else:
                parent_descriptor = anchored_parent
                if parent_descriptor is None:
                    raise ProfileCustodyRecordError("recovery artifact target parent cannot be identity-anchored")
                parent_metadata = os.fstat(parent_descriptor)
                if not stat.S_ISDIR(parent_metadata.st_mode):
                    raise OSError("recovery artifact parent is not a directory")
                descriptor = os.open(
                    path.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                    0o600,
                    dir_fd=parent_descriptor,
                )
            try:
                _write_export_descriptor(descriptor, payload, parent_descriptor=parent_descriptor)
            except BaseException:
                # A short or interrupted write leaves a file that exists,
                # holds a fragment of wrapped key material, and parses as
                # nothing. Left in place it is worse than no file at all:
                # the exclusive create then refuses every retry to the same
                # destination, and the operator is holding something that
                # looks like their recovery artifact and will not open their
                # records on the day they need it. It is removed through the
                # same anchored parent that authorised its creation, so the
                # removal cannot reach a substituted directory.
                os.close(descriptor)
                descriptor = None
                _remove_failed_export(path, parent_descriptor=parent_descriptor)
                raise
    except OSError as exc:
        raise ProfileCustodyRecordError("recovery artifact target must be created exclusively") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _remove_failed_export(path: Path, *, parent_descriptor: int | None) -> None:
    """Best-effort removal of a partial export, never masking the real failure."""
    try:
        if parent_descriptor is None:
            os.unlink(path)
        else:
            os.unlink(path.name, dir_fd=parent_descriptor)
    except OSError:
        # The write failure is the operator's actionable fact; a removal that
        # could not complete must not replace it with a second, vaguer one.
        return


@contextmanager
def _posix_external_directory_fd(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.anchor or "/", flags)
    except OSError as exc:
        raise ProfileCustodyRecordError("recovery artifact target parent is not a safe existing directory") from exc
    try:
        components = path.parts[1:] if path.anchor else path.parts
        for component in components:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        yield descriptor
    except OSError as exc:
        raise ProfileCustodyRecordError("recovery artifact target parent is not a safe existing directory") from exc
    finally:
        os.close(descriptor)


def _write_export_descriptor(descriptor: int, payload: bytes, *, parent_descriptor: int | None) -> None:
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("recovery artifact short write")
            offset += written
        os.fsync(descriptor)
        if parent_descriptor is not None:
            os.fsync(parent_descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("recovery artifact could not be durably exported") from exc


@contextmanager
def _windows_external_directory_anchor(path: Path):
    """Lock one verified non-reparse export parent against delete substitution."""
    with windows_directory_anchor(path, errors=_RECOVERY_DIRECTORY_ANCHOR_ERRORS):
        yield


__all__ = [
    "PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES",
    "PROFILE_CUSTODY_RECOVERY_ARTIFACT_SCHEMA",
    "ProfileCustodyRecoveryArtifact",
    "ProfileCustodyRecoveryArtifactExportReceipt",
    "ProfileCustodyRecoveryArtifactWarning",
    "export_profile_custody_recovery_artifact",
    "import_profile_custody_recovery_artifact",
    "parse_profile_custody_recovery_artifact",
    "refuse_hostile_recovery_artifact_destination",
    "unlock_imported_profile_custody_recovery_artifact",
]
