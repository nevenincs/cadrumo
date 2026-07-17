"""Single application authority for portable profile-bundle publication."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SecretStr

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import fsync_parent_dir
from ...core.atomic_write import atomic_write_hardened_bytes, atomic_write_hardened_text
from ...core.locks import exclusive_file_lock
from ...core.time import now
from ...domain.user_profile import ProfileExportError, ProfileNotFoundError

if TYPE_CHECKING:
    from ...domain.buckets import BucketEventHistoryRepositoryProtocol
    from ...domain.user_profile import UserProfilePortableExport
    from ..workflow import ProfileBucketPointer


class ProfileBundleExportPurpose(StrEnum):
    """Operator intent for one portable bundle publication."""

    PORTABLE_TRANSFER = "portable_transfer"
    SUBJECT_ACCESS = "subject_access"


class ProfileBundleExportTransport(StrEnum):
    """Wire protection applied to the published portable bundle."""

    CLEARTEXT_LOCAL = "cleartext_local"
    PASSPHRASE_ENCRYPTED = "passphrase_encrypted"  # noqa: S105 - transport taxonomy, not a secret


class ProfileBundleExportRequest(BaseModel):
    """Typed request for the sole portable profile export operation."""

    model_config = _STRICT_FROZEN

    profile_name: str | None = Field(default=None, min_length=1, max_length=160)
    destination: Path
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    passphrase: SecretStr | None = None


class ProfileBundleExportResult(BaseModel):
    """Published profile-bundle identity and presentation metadata."""

    model_config = _STRICT_FROZEN

    profile_id: str
    display_name: str
    destination: Path
    bundle_schema_version: int
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    data_categories: tuple[str, ...]


_CATEGORY_BY_BUNDLE_FIELD = {
    "profile": "profile_identity_and_facts",
    "work_units": "modelo_work_units",
    "ledger_transactions": "ledger_transactions",
    "calculation_revisions": "calculation_revisions",
    "filing_records": "filing_records",
}


def export_profile_bundle(request: ProfileBundleExportRequest) -> ProfileBundleExportResult:
    """Resolve, serialize, atomically publish, and record one profile export."""
    from ._orchestration import _profile_export_runtime

    pointer = _resolve_export_profile(request.profile_name)
    with _profile_export_runtime(pointer.bucket_id) as event_repository:
        bundle = _serialize_export_bundle(pointer.bucket_id)
        payload = _render_export_payload(bundle, request=request)
        try:
            with exclusive_file_lock(request.destination):
                previous_target = _capture_export_target(request.destination)
                atomic_write_hardened_text(request.destination, payload)
                try:
                    _record_profile_export(
                        pointer=pointer,
                        bundle=bundle,
                        request=request,
                        repository=event_repository,
                    )
                except Exception as exc:
                    try:
                        _restore_export_target(request.destination, previous_target)
                    except Exception as compensation_exc:
                        raise ProfileExportError(
                            "profile export audit failed and its destination could not be restored",
                            context={
                                "destination": str(request.destination),
                                "audit_error": type(exc).__name__,
                                "compensation_error": type(compensation_exc).__name__,
                            },
                        ) from compensation_exc
                    raise ProfileExportError(
                        "profile export audit failed; its destination was restored",
                        context={
                            "destination": str(request.destination),
                            "audit_error": type(exc).__name__,
                        },
                    ) from exc
        except ProfileExportError:
            raise
        except OSError as exc:
            raise ProfileExportError(
                "portable profile export could not publish its destination",
                context={"destination": str(request.destination)},
            ) from exc

    return ProfileBundleExportResult(
        profile_id=pointer.bucket_id,
        display_name=pointer.label,
        destination=request.destination,
        bundle_schema_version=bundle.bundle_schema_version,
        purpose=request.purpose,
        transport=request.transport,
        data_categories=_bundle_data_categories(bundle),
    )


def _resolve_export_profile(profile_name: str | None) -> ProfileBucketPointer:
    from ...core import resolve_active_bucket_id
    from ..workflow import read_profile_bucket, read_profile_bucket_by_id

    if profile_name is not None:
        pointer = read_profile_bucket(profile_name)
        missing_identity = profile_name
    else:
        active = resolve_active_bucket_id()
        pointer = read_profile_bucket_by_id(active) if active is not None else None
        missing_identity = active or "active"
    if pointer is None:
        raise ProfileNotFoundError(
            "profile export target does not exist",
            context={"profile": missing_identity},
        )
    return pointer


def _serialize_export_bundle(bucket_id: str) -> UserProfilePortableExport:
    from ._bundle import serialize_profile_bundle

    return serialize_profile_bundle(bucket_id=bucket_id)


def _render_export_payload(
    bundle: UserProfilePortableExport,
    *,
    request: ProfileBundleExportRequest,
) -> str:
    if request.transport is ProfileBundleExportTransport.CLEARTEXT_LOCAL:
        if request.passphrase is not None:
            raise ProfileExportError("cleartext profile export cannot carry a passphrase")
        return bundle.model_dump_json(indent=2)
    if request.passphrase is None:
        raise ProfileExportError("passphrase-encrypted profile export requires a passphrase")
    from ._bundle_encryption import encrypt_profile_bundle_for_passphrase

    encrypted = encrypt_profile_bundle_for_passphrase(
        bundle,
        passphrase=request.passphrase.get_secret_value(),
    )
    return encrypted.model_dump_json(indent=2)


def _capture_export_target(path: Path) -> tuple[bool, bytes, int]:
    """Capture an existing regular target so a failed audit can restore it."""
    if path.is_symlink():
        raise ProfileExportError(
            "portable profile export refuses a symbolic-link destination",
            context={"destination": str(path)},
        )
    if not path.exists():
        return False, b"", 0o600
    if not path.is_file():
        raise ProfileExportError(
            "portable profile export destination must be a regular file",
            context={"destination": str(path)},
        )
    return True, path.read_bytes(), path.stat().st_mode & 0o777


def _restore_export_target(path: Path, snapshot: tuple[bool, bytes, int]) -> None:
    """Compensate a published target after its audit event fails."""
    existed, contents, mode = snapshot
    if existed:
        atomic_write_hardened_bytes(path, contents, mode=mode)
        return
    path.unlink(missing_ok=True)
    fsync_parent_dir(path)


def _bundle_data_categories(bundle: UserProfilePortableExport) -> tuple[str, ...]:
    categories = tuple(
        category
        for field_name in type(bundle).model_fields
        if (category := _CATEGORY_BY_BUNDLE_FIELD.get(field_name)) is not None
    )
    carried = tuple(f"secure_object_namespace:{namespace}" for namespace in bundle.coverage_manifest.carried_namespaces)
    return (*categories, *carried)


def _record_profile_export(
    *,
    pointer: ProfileBucketPointer,
    bundle: UserProfilePortableExport,
    request: ProfileBundleExportRequest,
    repository: BucketEventHistoryRepositoryProtocol,
) -> None:
    from ...domain.buckets import (
        BucketEvent,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = now().replace(microsecond=0)
    payload = {
        "display_name": pointer.label,
        "out": str(request.destination),
        "purpose": request.purpose.value,
        "schema_version": str(bundle.bundle_schema_version),
        "transport": request.transport.value,
    }
    event_id = derive_bucket_event_id(
        bucket_id=pointer.bucket_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=pointer.bucket_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=pointer.bucket_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=pointer.bucket_id,
        payload_version=1,
        payload=payload,
    )
    repository.save(append_bucket_event(repository.load(), event))


__all__ = [
    "ProfileBundleExportPurpose",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTransport",
    "export_profile_bundle",
]
