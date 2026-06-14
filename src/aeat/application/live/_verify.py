"""Bucket-scoped verify service.

Wraps the two read-only AEAT verify oracles into a bucket-scoped
audit log. Verify observations are persisted through a
:class:`SecureObjectRepository` scoped to the active profile bucket.

  * NIF-IVA (VIES) — intracomunitario counterparty validation
  * TGVI / GROI    — intra-community operator (registered Spanish NIF)

Both surfaces are on-demand single-shot checks. The service records
each check as a typed observation tied to the active bucket so the
operator can audit which NIFs were verified, when, and against what
verdict. Subsequent invocations against the same NIF produce a new
observation row; history is never overwritten. Each observation is
wrapped in an :class:`Envelope` before being written to the secure store.

Structurally read-only:
  * the service has no submit / mutate verb;
  * the underlying drivers call ``AeatAccessGate.require_live_read()``
    before remote contact; this layer consumes their results only;
  * the operator's ``--expected valid|invalid|unknown`` hint is
    recorded alongside the verdict so a mistaken expectation is
    auditable.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import LIVE_VERIFY_OBSERVATION_NAMESPACE, Envelope
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ...core.config import Settings, load_settings
from ...core.errors import AeatError
from ...core.hashing import sha256_hex
from ...core.identity import BucketId
from ...core.time import now
from ._errors import LiveApplicationInputError

VerifyVerdict = Literal["valid", "invalid", "unknown"]


class VerifySurface(StrEnum):
    """Closed catalogue of supported verify surfaces."""

    NIF_IVA = "nif_iva"
    TGVI = "tgvi"


class VerifyObservationNotFoundError(AeatError):
    """Raised when a verify-observation lookup misses by id."""


class VerifyObservation(BaseModel):
    """One persisted verify check.

    The ``observation_id`` is content-addressed (SHA-256 of canonical
    fields) so two identical checks against the same NIF on the same
    timestamp deduplicate without separate id management.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observation_id: str = Field(min_length=64, max_length=64)
    bucket_id: BucketId
    surface: VerifySurface
    nif: str = Field(min_length=1, max_length=32)
    verdict: VerifyVerdict
    expected: VerifyVerdict | None = Field(default=None)
    matched_expectation: bool | None = Field(default=None)
    checked_at: datetime
    raw_evidence_locator: str | None = Field(default=None, max_length=512)
    persisted_at: datetime


def verify_observation_object_key(bucket_id: str, observation_id: str) -> str:
    """Return the canonical secure-object key for a :class:`VerifyObservation`.

    The key encodes both the bucket and the observation so the store
    remains globally unique across buckets even when two buckets check
    the same NIF at the same instant.

    Args:
        bucket_id: The profile bucket's UUIDv4 identifier.
        observation_id: The SHA-256 hex content-address of the observation.

    Raises:
        LiveApplicationInputError: When either argument is blank after
            stripping whitespace.
    """
    trimmed_bucket = bucket_id.strip()
    trimmed_observation = observation_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            "bucket_id must not be blank",
            translated_message="application.live.verify.errors.bucket_id_blank",
        )
    if not trimmed_observation:
        raise LiveApplicationInputError(
            "observation_id must not be blank",
            translated_message="application.live.verify.errors.observation_id_blank",
        )
    return f"verify-observation:{trimmed_bucket}:{trimmed_observation}"


def _derive_observation_id(
    *,
    surface: VerifySurface,
    nif: str,
    verdict: VerifyVerdict,
    checked_at: datetime,
) -> str:
    canonical = f"{surface.value}|{nif}|{verdict}|{checked_at.isoformat()}"
    return sha256_hex(canonical.encode("utf-8"))


class VerifyObservationRepository:
    """Secure-object repository for bucket-scoped verify observations."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError(
                "bucket_id must not be blank",
                translated_message="application.live.verify.errors.bucket_id_blank",
            )
        self._bucket_id = trimmed
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(trimmed)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def load(self, observation_id: str) -> VerifyObservation | None:
        """Return the :class:`VerifyObservation` for ``observation_id``, or ``None`` if absent.

        Args:
            observation_id: The full 64-character SHA-256 hex observation id.

        Raises:
            LiveApplicationInputError: When the loaded observation's
                ``bucket_id`` or ``observation_id`` does not match the
                repository's own bucket or the requested id.
        """
        record = self._objects.load(
            LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
            verify_observation_object_key(self._bucket_id, observation_id),
            expected_class=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            max_supported_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
        )
        if record is None:
            return None
        observation = self._observation_from_record(record, requested_observation_id=observation_id)
        if observation.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                "verify observation bucket does not match repository bucket",
                translated_message="application.live.verify.errors.observation_bucket_mismatch",
                context={
                    "observation_bucket": observation.bucket_id,
                    "repository_bucket": self._bucket_id,
                },
            )
        if observation.observation_id != observation_id:
            raise LiveApplicationInputError(
                "verify observation id does not match requested observation",
                translated_message="application.live.verify.errors.observation_id_mismatch",
                context={
                    "observation_id": observation.observation_id,
                    "requested_observation_id": observation_id,
                },
            )
        return observation

    def list_observations(self) -> tuple[VerifyObservation, ...]:
        """Return all stored observations as a tuple of :class:`VerifyObservation` sorted by check time."""
        observations: list[VerifyObservation] = []
        for record in self._objects.list_records(
            LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
            expected_class=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            max_supported_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
        ):
            observation = self._observation_from_record(record)
            if observation.bucket_id != self._bucket_id:
                raise LiveApplicationInputError(
                    "verify observation bucket does not match repository bucket",
                    translated_message="application.live.verify.errors.observation_bucket_mismatch",
                    context={
                        "observation_bucket": observation.bucket_id,
                        "repository_bucket": self._bucket_id,
                    },
                )
            observations.append(observation)
        return tuple(sorted(observations, key=lambda item: (item.checked_at, item.observation_id)))

    def save(self, observation: VerifyObservation) -> None:
        """Persist ``observation`` as an encrypted :class:`Envelope` in the object store.

        Args:
            observation: The :class:`VerifyObservation` to persist. Its
                ``bucket_id`` must match the repository's own bucket.

        Raises:
            LiveApplicationInputError: When ``observation.bucket_id`` does
                not match the repository's bucket id.
        """
        if observation.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                "verify observation bucket does not match repository bucket",
                translated_message="application.live.verify.errors.observation_bucket_mismatch",
                context={
                    "observation_bucket": observation.bucket_id,
                    "repository_bucket": self._bucket_id,
                },
            )
        envelope = Envelope[VerifyObservation](
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=now(),
            classification=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            payload=observation,
        )
        self._objects.save(
            namespace=LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
            object_key=verify_observation_object_key(self._bucket_id, observation.observation_id),
            classification=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    @staticmethod
    def _observation_from_record(
        record: SecureObjectRecord,
        requested_observation_id: str | None = None,
    ) -> VerifyObservation:
        envelope = Envelope[VerifyObservation].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity:
            observation_label = requested_observation_id or envelope.payload.observation_id
            raise ClassificationError(
                f"verify observation {observation_label!r} has classification {envelope.classification}; "
                f"consumer expected {LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity}",
            )
        if envelope.schema_version > LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version:
            observation_label = requested_observation_id or envelope.payload.observation_id
            raise EnvelopeVersionError(
                f"verify observation {observation_label!r} is at version {envelope.schema_version}; "
                f"consumer supports up to {LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version}",
            )
        return envelope.payload


class VerifyService:
    """Bucket-scoped audit log of NIF verify checks.

    Structurally read-only. The service has no submit,
    no mutate, and no method that would alter AEAT-side state. Verify
    surfaces themselves are read-only by construction; this layer only
    records observations the drivers produce.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()

    def _repository_for(self, bucket_id: str) -> VerifyObservationRepository:
        return VerifyObservationRepository(
            bucket_id=bucket_id,
            objects=secure_object_repository_for_bucket(bucket_id, self._settings),
        )

    def record(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface,
        nif: str,
        verdict: VerifyVerdict,
        checked_at: datetime,
        expected: VerifyVerdict | None = None,
        raw_evidence_locator: str | None = None,
    ) -> VerifyObservation:
        """Persist one verify observation. Deduplicates identical replays.

        Returns a :class:`VerifyObservation` with the persisted observation id
        and all supplied fields.
        """
        observation_id = _derive_observation_id(
            surface=surface,
            nif=nif,
            verdict=verdict,
            checked_at=checked_at,
        )
        matched = expected == verdict if expected is not None else None
        observation = VerifyObservation(
            observation_id=observation_id,
            bucket_id=bucket_id,
            surface=surface,
            nif=nif,
            verdict=verdict,
            expected=expected,
            matched_expectation=matched,
            checked_at=checked_at,
            raw_evidence_locator=raw_evidence_locator,
            persisted_at=now(),
        )
        repository = self._repository_for(bucket_id)
        existing = repository.load(observation_id)
        if existing is not None:
            return existing
        repository.save(observation)
        return observation

    def list_observations(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface | None = None,
        nif: str | None = None,
    ) -> tuple[VerifyObservation, ...]:
        """Return all :class:`VerifyObservation` records in capture order. Optional filters."""
        observations = list(self._repository_for(bucket_id).list_observations())
        if surface is not None:
            observations = [o for o in observations if o.surface is surface]
        if nif is not None:
            observations = [o for o in observations if o.nif == nif]
        return tuple(observations)

    def show(
        self,
        *,
        bucket_id: str,
        observation_id: str,
    ) -> VerifyObservation:
        """Look up and return the :class:`VerifyObservation` for the given full id or unambiguous prefix."""
        matches = [
            o
            for o in self._repository_for(bucket_id).list_observations()
            if o.observation_id == observation_id or o.observation_id.startswith(observation_id)
        ]
        if not matches:
            raise VerifyObservationNotFoundError(
                "no verify observation matches the requested id",
                suggestion="aeat app live verify nif-iva",
                translated_message="application.live.verify.errors.observation_not_found",
                context={"observation_id": observation_id},
            )
        if len(matches) > 1:
            raise VerifyObservationNotFoundError(
                "verify observation prefix matches multiple observations",
                suggestion="provide a longer prefix",
                translated_message="application.live.verify.errors.observation_prefix_ambiguous",
                context={"observation_id": observation_id, "match_count": len(matches)},
            )
        return matches[0]

    def latest_for_nif(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface,
        nif: str,
    ) -> VerifyObservation | None:
        """Return the most recent :class:`VerifyObservation` for (surface, nif), or None."""
        matches = [
            o for o in self._repository_for(bucket_id).list_observations() if o.surface is surface and o.nif == nif
        ]
        if not matches:
            return None
        return max(matches, key=lambda o: o.checked_at)


__all__ = [
    "VerifyObservation",
    "VerifyObservationNotFoundError",
    "VerifyObservationRepository",
    "VerifyService",
    "VerifySurface",
    "VerifyVerdict",
    "verify_observation_object_key",
]
