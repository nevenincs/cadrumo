"""Independent optional recovery envelopes and portable recovery artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ._errors import ProfileCustodyPasswordError, ProfileCustodyRecordError
from ._kdf_supervision import (
    ProfileCustodySentinelRecord,
    unlock_profile_custody,
    unlock_profile_custody_material,
    verify_profile_custody_sentinel,
    wrap_profile_custody_material,
)
from ._records import (
    PROFILE_CUSTODY_PASSWORD_GENERATION_MAX,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION: Final = 1
PROFILE_CUSTODY_RECOVERY_MAX_BYTES: Final = 1024
PROFILE_CUSTODY_RECOVERY_ARTIFACT_SCHEMA: Final = "profile-recovery-artifact/v1"
PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES: Final = 1024
PROFILE_CUSTODY_RECOVERY_FILENAME: Final = "recovery.v1.json"
_SHA256_DIGEST_PREFIX: Final = "sha256:"
_SHA256_DIGEST_LENGTH: Final = len(_SHA256_DIGEST_PREFIX) + 64


def _canonical_json_bytes(payload: Mapping[str, object], *, maximum_bytes: int, subject: str) -> bytes:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8_ENCODING)
    if len(encoded) > maximum_bytes:
        raise ValueError(f"{subject} exceeds its canonical byte limit")
    return encoded


def _canonical_digest(payload: Mapping[str, object], *, maximum_bytes: int, subject: str) -> str:
    canonical = _canonical_json_bytes(payload, maximum_bytes=maximum_bytes, subject=subject)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _reject_duplicate_members(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, member in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member {key!r}")
        result[key] = member
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r} is forbidden")


# These narrow helpers are shared by the two current-format record modules;
# their callers still supply each record's independent byte ceiling and subject.
canonical_custody_json_bytes = _canonical_json_bytes
canonical_custody_digest = _canonical_digest
reject_duplicate_custody_members = _reject_duplicate_members
reject_custody_json_constant = _reject_json_constant


def _validate_digest(value: str, *, field_name: str) -> str:
    if (
        len(value) != _SHA256_DIGEST_LENGTH
        or not value.startswith(_SHA256_DIGEST_PREFIX)
        or any(character not in "0123456789abcdef" for character in value[len(_SHA256_DIGEST_PREFIX) :])
    ):
        raise ValueError(f"{field_name} must be a lowercase sha256 digest")
    return value


def validate_profile_custody_dek_epoch(value: str) -> str:
    """Validate the immutable random 128-bit epoch's canonical representation."""
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("dek_epoch must be canonical base64") from exc
    if len(decoded) != 16 or base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("dek_epoch must encode exactly 16 canonical bytes")
    return value


class ProfileCustodyRecoveryAad(BaseModel):
    """Closed recovery wrapper AAD descriptor carried by durable records."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    product: Literal["cadrumo"]
    purpose: Literal["profile-recovery-dek-wrap/v1"]
    key_schedule: Literal["profile-recovery-dek-wrap/v1"]


_RECOVERY_AAD = ProfileCustodyRecoveryAad(
    schema_version=1,
    product="cadrumo",
    purpose="profile-recovery-dek-wrap/v1",
    key_schedule="profile-recovery-dek-wrap/v1",
)


class _RecoveryPayload(BaseModel):
    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    profile_id: UUID
    recovery_generation: int = Field(ge=1, le=PROFILE_CUSTODY_PASSWORD_GENERATION_MAX)
    dek_epoch: str
    kdf: ProfileCustodyKdfParameters
    wrapped_dek: ProfileCustodyWrappedDek
    aad: ProfileCustodyRecoveryAad
    previous_recovery_digest: str | None

    @field_validator("dek_epoch")
    @classmethod
    def _validate_epoch(cls, value: str) -> str:
        return validate_profile_custody_dek_epoch(value)

    @field_validator("previous_recovery_digest")
    @classmethod
    def _validate_previous_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_digest(value, field_name="previous_recovery_digest")


class ProfileCustodyRecoveryEnvelope(_RecoveryPayload):
    """One optional, independently current-format recovery wrapper."""

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return _validate_digest(value, field_name="self_digest")

    @model_validator(mode="after")
    def _verify_self_digest(self) -> ProfileCustodyRecoveryEnvelope:
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile recovery self_digest does not match its canonical record")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["self_digest"]
        return payload

    @property
    def computed_self_digest(self) -> str:
        return _canonical_digest(
            self.canonical_payload,
            maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
            subject="profile recovery envelope",
        )

    def canonical_json_bytes(self) -> bytes:
        return _canonical_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
            subject="profile recovery envelope",
        )

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        recovery_generation: int,
        dek_epoch: str,
        kdf: ProfileCustodyKdfParameters,
        wrapped_dek: ProfileCustodyWrappedDek,
        previous_recovery_digest: str | None = None,
    ) -> ProfileCustodyRecoveryEnvelope:
        try:
            payload = _RecoveryPayload(
                schema_version=PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION,
                profile_id=profile_id,
                recovery_generation=recovery_generation,
                dek_epoch=dek_epoch,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                aad=_RECOVERY_AAD,
                previous_recovery_digest=previous_recovery_digest,
            ).model_dump(mode="json")
            payload["self_digest"] = _canonical_digest(
                payload,
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                subject="profile recovery envelope",
            )
            return cls.model_validate_json(
                _canonical_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                    subject="profile recovery envelope",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a valid profile recovery envelope") from exc


def parse_profile_custody_recovery_envelope(value: bytes) -> ProfileCustodyRecoveryEnvelope:
    """Parse exactly one bounded canonical optional recovery envelope."""
    if len(value) > PROFILE_CUSTODY_RECOVERY_MAX_BYTES:
        raise ProfileCustodyRecordError("profile recovery envelope exceeds its canonical byte limit")
    try:
        parsed = json.loads(
            value.decode(_UTF_8_ENCODING, errors="strict"),
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile recovery envelope must be a JSON object")
        envelope = ProfileCustodyRecoveryEnvelope.model_validate_json(
            _canonical_json_bytes(
                cast(dict[str, object], parsed),
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                subject="profile recovery envelope",
            ),
        )
        if envelope.canonical_json_bytes() != value:
            raise ValueError("profile recovery envelope is not canonical")
        return envelope
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile recovery envelope is not a valid current-format record") from exc


def profile_custody_recovery_aad(envelope: ProfileCustodyRecoveryEnvelope) -> bytes:
    """Derive the one closed recovery-wrapper AAD domain from its record."""
    return _profile_custody_recovery_aad(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        recovery_generation=envelope.recovery_generation,
        kdf=envelope.kdf,
        aad=envelope.aad,
    )


def create_profile_custody_recovery_envelope(
    *,
    profile_id: UUID,
    recovery_secret: str,
    dek: bytes,
    dek_epoch: str,
    kdf: ProfileCustodyKdfParameters,
    recovery_generation: int = 1,
    previous_recovery_digest: str | None = None,
    settings: Settings | None = None,
) -> ProfileCustodyRecoveryEnvelope:
    """Create optional recovery only through the supervised S03 KDF owner."""
    aad = _profile_custody_recovery_aad(
        profile_id=profile_id,
        dek_epoch=dek_epoch,
        recovery_generation=recovery_generation,
        kdf=kdf,
        aad=_RECOVERY_AAD,
    )
    wrapped_dek = wrap_profile_custody_material(
        secret=recovery_secret,
        dek=dek,
        kdf=kdf,
        associated_data=aad,
        settings=settings,
    )
    return ProfileCustodyRecoveryEnvelope.create(
        profile_id=profile_id,
        recovery_generation=recovery_generation,
        dek_epoch=dek_epoch,
        kdf=kdf,
        wrapped_dek=wrapped_dek,
        previous_recovery_digest=previous_recovery_digest,
    )


def _profile_custody_recovery_aad(
    *,
    profile_id: UUID,
    dek_epoch: str,
    recovery_generation: int,
    kdf: ProfileCustodyKdfParameters,
    aad: ProfileCustodyRecoveryAad,
) -> bytes:
    return _canonical_json_bytes(
        {
            "aad": aad.model_dump(mode="json"),
            "dek_epoch": dek_epoch,
            "kdf_digest": _canonical_digest(
                kdf.model_dump(mode="json"),
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                subject="profile recovery KDF",
            ),
            "profile_id": str(profile_id),
            "recovery_generation": recovery_generation,
            "schema_version": 1,
        },
        maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
        subject="profile recovery AAD",
    )


@dataclass(frozen=True, slots=True)
class ProfileCustodyRecoveryUnlock:
    """A DEK accepted through the explicit recovery-only door."""

    profile_id: UUID
    dek_epoch: str
    recovery_digest: str
    dek: bytes


def unlock_profile_custody_recovery(
    envelope: ProfileCustodyRecoveryEnvelope,
    recovery_secret: str,
    *,
    sentinel: ProfileCustodySentinelRecord,
    settings: Settings | None = None,
) -> ProfileCustodyRecoveryUnlock:
    """Use the S03 supervised unwrap boundary for an explicit recovery secret."""
    try:
        dek = unlock_profile_custody_material(
            profile_id=envelope.profile_id,
            dek_epoch=envelope.dek_epoch,
            kdf=envelope.kdf,
            wrapped_dek=envelope.wrapped_dek,
            secret=recovery_secret,
            associated_data=profile_custody_recovery_aad(envelope),
            sentinel=sentinel,
            settings=settings,
        )
    except ProfileCustodyPasswordError:
        raise
    return ProfileCustodyRecoveryUnlock(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        recovery_digest=envelope.self_digest,
        dek=dek,
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


class ProfileCustodyRecoveryArtifact(_RecoveryArtifactPayload):
    """Portable current-format recovery material, with no normal-login state."""

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return _validate_digest(value, field_name="self_digest")

    @model_validator(mode="after")
    def _verify_self_digest(self) -> ProfileCustodyRecoveryArtifact:
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile recovery artifact self_digest does not match")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["self_digest"]
        return payload

    @property
    def computed_self_digest(self) -> str:
        return _canonical_digest(
            self.canonical_payload,
            maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
            subject="profile recovery artifact",
        )

    def canonical_json_bytes(self) -> bytes:
        return _canonical_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
            subject="profile recovery artifact",
        )

    @classmethod
    def from_recovery_envelope(cls, envelope: ProfileCustodyRecoveryEnvelope) -> ProfileCustodyRecoveryArtifact:
        payload = _RecoveryArtifactPayload(
            artifact_schema=PROFILE_CUSTODY_RECOVERY_ARTIFACT_SCHEMA,
            profile_id=envelope.profile_id,
            dek_epoch=envelope.dek_epoch,
            recovery_generation=envelope.recovery_generation,
            kdf=envelope.kdf,
            wrapped_dek=envelope.wrapped_dek,
            aad=envelope.aad,
        ).model_dump(mode="json")
        payload["self_digest"] = _canonical_digest(
            payload,
            maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
            subject="profile recovery artifact",
        )
        try:
            return cls.model_validate_json(
                _canonical_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES,
                    subject="profile recovery artifact",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a profile recovery artifact") from exc


class ProfileCustodyRecoveryArtifactWarning(StrEnum):
    """Stable operator warnings that accompany every recovery artifact export."""

    OFFLINE_GUESSING_EXPOSURE = "OFFLINE_GUESSING_EXPOSURE"
    STORE_SEPARATELY = "STORE_SEPARATELY"
    RETAINED_EXPORTED_COPY = "RETAINED_EXPORTED_COPY"
    LOSS_DOES_NOT_BLOCK_PASSWORD_LOGIN = "LOSS_DOES_NOT_BLOCK_PASSWORD_LOGIN"  # noqa: S105 - warning code


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
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile recovery artifact must be a JSON object")
        artifact = ProfileCustodyRecoveryArtifact.model_validate_json(
            _canonical_json_bytes(
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
        _read_regular_file(source, maximum_bytes=PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES),
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

    This does not install or overwrite optional recovery.  A later explicit
    recovery owner decides whether a successfully proved artifact may be
    enrolled, preserving the import collision boundary.
    """
    if artifact.profile_id != expected_profile_id or artifact.dek_epoch != expected_dek_epoch:
        raise ProfileCustodyRecordError("recovery artifact UUID or DEK epoch does not match its named target")
    dek = unlock_profile_custody_material(
        profile_id=artifact.profile_id,
        dek_epoch=artifact.dek_epoch,
        kdf=artifact.kdf,
        wrapped_dek=artifact.wrapped_dek,
        secret=recovery_secret,
        associated_data=_profile_custody_recovery_aad(
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


def _read_regular_file(path: Path, *, maximum_bytes: int) -> bytes:
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
        info = _ByHandleFileInformation()
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
            _write_export_descriptor(descriptor, payload, parent_descriptor=parent_descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("recovery artifact target must be created exclusively") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


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
        for component in components:
            current /= component
            handle = create_file(
                str(current),
                0,
                0x00000001 | 0x00000002,
                None,
                3,
                0x02000000 | 0x00200000,
                None,
            )
            if handle == wintypes.HANDLE(-1).value:
                raise ProfileCustodyRecordError("recovery artifact target parent is not a safe existing directory")
            handles.append(int(handle))
            info = _ByHandleFileInformation()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError("recovery artifact target parent identity cannot be verified")
            if not info.dwFileAttributes & 0x10 or info.dwFileAttributes & 0x400:
                raise ProfileCustodyRecordError(
                    "recovery artifact target parent must not be a reparse point or non-directory"
                )
        yield
    finally:
        for handle in reversed(handles):
            kernel32.CloseHandle(handle)


__all__ = [
    "PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES",
    "PROFILE_CUSTODY_RECOVERY_ARTIFACT_SCHEMA",
    "PROFILE_CUSTODY_RECOVERY_FILENAME",
    "PROFILE_CUSTODY_RECOVERY_MAX_BYTES",
    "PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION",
    "ProfileCustodyRecoveryAad",
    "ProfileCustodyRecoveryArtifact",
    "ProfileCustodyRecoveryArtifactExportReceipt",
    "ProfileCustodyRecoveryArtifactWarning",
    "ProfileCustodyRecoveryEnvelope",
    "ProfileCustodyRecoveryUnlock",
    "export_profile_custody_recovery_artifact",
    "import_profile_custody_recovery_artifact",
    "parse_profile_custody_recovery_artifact",
    "parse_profile_custody_recovery_envelope",
    "profile_custody_recovery_aad",
    "unlock_imported_profile_custody_recovery_artifact",
    "unlock_profile_custody_recovery",
]
