"""Bucket-scoped verify service.

Wraps the two read-only AEAT verify oracles into a bucket-scoped
audit log:

  * NIF-IVA (VIES) — intracomunitario counterparty validation
  * TGVI / GROI    — intra-community operator (registered Spanish NIF)

Both surfaces are on-demand single-shot checks. The service records
each check as a typed observation tied to the active bucket so the
operator can audit which NIFs were verified, when, and against what
verdict. Subsequent invocations against the same NIF produce a new
observation row; history is never overwritten.

Structurally read-only:
  * the service has no submit / mutate verb;
  * the underlying drivers call ``AeatAccessGate.require_live_read()``
    before remote contact; this layer consumes their results only;
  * the operator's ``--expected valid|invalid|unknown`` hint is
    recorded alongside the verdict so a mistaken expectation is
    auditable.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import LIVE_VERIFY_OBSERVATION_NAMESPACE, Envelope
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ...core.config import Settings, load_settings
from ...core.errors import AeatError
from ...core.time import _now

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
    bucket_id: str = Field(min_length=1)
    surface: VerifySurface
    nif: str = Field(min_length=1, max_length=32)
    verdict: VerifyVerdict
    expected: VerifyVerdict | None = Field(default=None)
    matched_expectation: bool | None = Field(default=None)
    checked_at: datetime
    raw_evidence_locator: str | None = Field(default=None, max_length=512)
    persisted_at: datetime


def verify_observation_object_key(bucket_id: str, observation_id: str) -> str:
    trimmed_bucket = bucket_id.strip()
    trimmed_observation = observation_id.strip()
    if not trimmed_bucket:
        raise AeatError("bucket_id must not be blank")
    if not trimmed_observation:
        raise AeatError("observation_id must not be blank")
    return f"verify-observation:{trimmed_bucket}:{trimmed_observation}"


def _derive_observation_id(
    *,
    surface: VerifySurface,
    nif: str,
    verdict: VerifyVerdict,
    checked_at: datetime,
) -> str:
    canonical = f"{surface.value}|{nif}|{verdict}|{checked_at.isoformat()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class VerifyObservationRepository:
    """Secure-object repository for bucket-scoped verify observations."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise AeatError("bucket_id must not be blank")
        self._bucket_id = trimmed
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(trimmed)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def load(self, observation_id: str) -> VerifyObservation | None:
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
            raise AeatError(
                f"verify observation bucket_id={observation.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        if observation.observation_id != observation_id:
            raise AeatError(
                f"verify observation id={observation.observation_id!r} "
                f"does not match requested observation {observation_id!r}"
            )
        return observation

    def list_observations(self) -> tuple[VerifyObservation, ...]:
        observations = [
            observation
            for record in self._objects.list_records(
                LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
                expected_class=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
                max_supported_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            )
            for observation in (self._observation_from_record(record),)
            if observation.bucket_id == self._bucket_id
        ]
        return tuple(sorted(observations, key=lambda item: (item.checked_at, item.observation_id)))

    def save(self, observation: VerifyObservation) -> None:
        if observation.bucket_id != self._bucket_id:
            raise AeatError(
                f"verify observation bucket_id={observation.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        envelope = Envelope[VerifyObservation](
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=datetime.now(UTC),
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
        """Persist one verify observation. Deduplicates identical replays."""
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
            persisted_at=_now(),
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
        """Return all observations in capture order. Optional filters."""
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
        """Look up one observation by full id or unambiguous prefix."""
        matches = [
            o
            for o in self._repository_for(bucket_id).list_observations()
            if o.observation_id == observation_id or o.observation_id.startswith(observation_id)
        ]
        if not matches:
            raise VerifyObservationNotFoundError(
                f"no verify observation matches {observation_id!r} in bucket {bucket_id!r}",
                suggestion="aeat app live verify nif-iva",
            )
        if len(matches) > 1:
            full_ids = sorted(o.observation_id for o in matches)
            raise VerifyObservationNotFoundError(
                f"prefix {observation_id!r} is ambiguous; matches {full_ids!r}",
                suggestion="provide a longer prefix",
            )
        return matches[0]

    def latest_for_nif(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface,
        nif: str,
    ) -> VerifyObservation | None:
        """Return the most recent observation for (surface, nif), or None."""
        matches = [
            o
            for o in self._repository_for(bucket_id).list_observations()
            if o.surface is surface and o.nif == nif
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
