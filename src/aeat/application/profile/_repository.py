"""Secure bucket repository for operator profile values."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.errors import AeatError
from ...core.logging import get_logger
from ..workflow._utils import utc_now
from ._models import ProfileRecord

_LOGGER = get_logger(__name__)

PROFILE_BUCKET_NAMESPACE = "aeat.application.profile.bucket"
PROFILE_BUCKET_VERSION = 1


def _clear_output_language_cache() -> None:
    try:
        from ...core.i18n._render import clear_output_language_cache
    except Exception:  # pragma: no cover - cache invalidation must never block persistence
        _LOGGER.debug("profile bucket persistence could not import i18n cache invalidator", exc_info=True)
        return
    clear_output_language_cache()


class ProfileBucketPersistenceError(AeatError):
    """Raised when a profile bucket cannot be persisted or loaded."""


class ProfileBucket(BaseModel):
    """Profile-owned secure bucket payload."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: str = Field(min_length=1, max_length=128)
    profile: ProfileRecord
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


def profile_bucket_id(profile_name: str) -> str:
    """Return the canonical bucket id for a profile name."""

    trimmed = profile_name.strip()
    if not trimmed:
        raise ValueError("profile name must not be blank")
    return trimmed


def profile_bucket_object_key(profile_name: str) -> str:
    """Return the secure object key for one profile bucket payload."""

    return f"profile-bucket:{profile_bucket_id(profile_name)}"


class ProfileBucketRepository:
    """Read and write profile values in profile-associated secure buckets."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        self._objects = objects or SecureObjectRepository()

    def load_bucket(self, profile_name: str) -> ProfileBucket | None:
        """Load the complete profile bucket payload."""

        bucket_id = profile_bucket_id(profile_name)
        try:
            record = self._objects.load(
                PROFILE_BUCKET_NAMESPACE,
                profile_bucket_object_key(bucket_id),
                expected_class=SensitivityClass.IDENTITY,
                max_supported_version=PROFILE_BUCKET_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("profile bucket integrity error bucket_id=%s", bucket_id, exc_info=True)
            raise ProfileBucketPersistenceError(
                f"profile bucket {bucket_id!r} integrity error: {type(exc).__name__}: {exc}"
            ) from exc
        if record is None:
            return None
        envelope = Envelope[ProfileBucket].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.IDENTITY:
            raise ProfileBucketPersistenceError(
                f"profile bucket {bucket_id!r} has classification {envelope.classification}; IDENTITY expected"
            )
        if envelope.schema_version > PROFILE_BUCKET_VERSION:
            raise ProfileBucketPersistenceError(
                f"profile bucket {bucket_id!r} is at version {envelope.schema_version}; "
                f"consumer supports {PROFILE_BUCKET_VERSION}"
            )
        if envelope.payload.bucket_id != bucket_id:
            raise ProfileBucketPersistenceError(
                f"profile bucket object {bucket_id!r} contains bucket {envelope.payload.bucket_id!r}"
            )
        return envelope.payload

    def load(self, profile_name: str) -> ProfileRecord | None:
        bucket = self.load_bucket(profile_name)
        return None if bucket is None else bucket.profile

    def save(self, profile: ProfileRecord) -> ProfileRecord:
        bucket_id = profile_bucket_id(profile.name)
        existing = self.load_bucket(bucket_id)
        now = utc_now()
        stored = profile.model_copy(update={"updated_at": now})
        payload = ProfileBucket(
            bucket_id=bucket_id,
            profile=stored,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        envelope = Envelope[ProfileBucket](
            schema_version=PROFILE_BUCKET_VERSION,
            written_at=now,
            classification=SensitivityClass.IDENTITY,
            payload=payload,
        )
        self._objects.save(
            namespace=PROFILE_BUCKET_NAMESPACE,
            object_key=profile_bucket_object_key(bucket_id),
            classification=SensitivityClass.IDENTITY,
            schema_version=PROFILE_BUCKET_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _clear_output_language_cache()
        return stored

    def delete(self, profile_name: str) -> bool:
        bucket_id = profile_bucket_id(profile_name)
        deleted = self._objects.delete(PROFILE_BUCKET_NAMESPACE, profile_bucket_object_key(bucket_id))
        if deleted:
            _clear_output_language_cache()
        return deleted

    def list_profiles(self) -> tuple[ProfileRecord, ...]:
        profiles: list[ProfileRecord] = []
        for record in self._objects.list_records(
            PROFILE_BUCKET_NAMESPACE,
            expected_class=SensitivityClass.IDENTITY,
            max_supported_version=PROFILE_BUCKET_VERSION,
        ):
            envelope = Envelope[ProfileBucket].model_validate_json(record.payload.decode("utf-8"))
            profiles.append(envelope.payload.profile)
        return tuple(sorted(profiles, key=lambda item: item.name))


def profile_bucket_repository() -> ProfileBucketRepository:
    """Return the canonical profile bucket repository."""

    return ProfileBucketRepository()


__all__ = [
    "PROFILE_BUCKET_NAMESPACE",
    "PROFILE_BUCKET_VERSION",
    "ProfileBucket",
    "ProfileBucketPersistenceError",
    "ProfileBucketRepository",
    "profile_bucket_id",
    "profile_bucket_object_key",
    "profile_bucket_repository",
]
