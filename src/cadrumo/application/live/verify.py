"""Bucket-scoped verify service.

Wraps the two read-only AEAT verify oracles into a bucket-scoped
audit log. Verify observations are persisted through an application-owned
observation persistence port supplied by the outer composition.

  * NIF-IVA (VIES) — intracomunitario counterparty validation
  * TGVI / GROI    — intra-community operator (registered Spanish NIF)

Both surfaces are on-demand single-shot checks. The service records
each check as a typed observation tied to the active bucket so the
operator can audit which NIFs were verified, when, and against what
verdict. Subsequent invocations against the same NIF produce a new
observation row; history is never overwritten. The persistence implementation
decides how each observation is protected and addressed at rest; this use case
consumes only its application-level contract.

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

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import sha256_hex
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity_check_verdict import IdentityCheckVerdictValue
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from .errors import LiveApplicationInputError
from .verify_ports import VerifyObservationPersistencePort


class VerifySurface(StrEnum):
    """Closed catalogue of supported verify surfaces."""

    NIF_IVA = "nif_iva"
    TGVI = "tgvi"


class VerifyObservationNotFoundError(CadrumoError):
    """Raised when a verify-observation lookup misses by id."""


class VerifyObservation(BaseModel):
    """One persisted verify check.

    The ``observation_id`` is content-addressed (SHA-256 of canonical
    fields) so two identical checks against the same NIF on the same
    timestamp deduplicate without separate id management. It is typed as
    :data:`~cadrumo.core.identity.ContentDigest` so the persisted identity
    carries the canonical lowercase hex-64 digest shape rather than any
    64-character string: a malformed id would otherwise reach the
    secure-object key, the ``load`` round-trip, and the ``show``
    projection unchallenged.

    Both instants are UTC-aware. ``checked_at`` feeds
    :func:`_derive_observation_id` through ``isoformat()``, so an
    ambiguous offset would silently fork the content address of the same
    check; ``persisted_at`` orders encrypted history.
    """

    model_config = STRICT_FROZEN_CONFIG

    observation_id: ContentDigest
    bucket_id: BucketId
    surface: VerifySurface
    nif: str = Field(min_length=1, max_length=32)
    verdict: IdentityCheckVerdictValue
    expected: IdentityCheckVerdictValue | None = Field(default=None)
    matched_expectation: bool | None = Field(default=None)
    checked_at: datetime
    raw_evidence_locator: str | None = Field(default=None, max_length=512)
    persisted_at: datetime

    @field_validator("checked_at", "persisted_at")
    @classmethod
    def _instant_is_utc(cls, value: datetime) -> datetime:
        """Reject a naive or non-UTC instant; see :func:`~cadrumo.core.time.validate_utc_aware`."""
        return validate_utc_aware(value)


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
            translated_message="application.live.verify.errors.bucket_id_blank",
        )
    if not trimmed_observation:
        raise LiveApplicationInputError(
            translated_message="application.live.verify.errors.observation_id_blank",
        )
    return f"verify-observation:{trimmed_bucket}:{trimmed_observation}"


def _derive_observation_id(
    *,
    surface: VerifySurface,
    nif: str,
    verdict: IdentityCheckVerdictValue,
    checked_at: datetime,
) -> str:
    canonical = f"{surface.value}|{nif}|{verdict}|{checked_at.isoformat()}"
    return sha256_hex(canonical.encode("utf-8"))


class VerifyService:
    """Bucket-scoped audit log of NIF verify checks.

    Structurally read-only. The service has no submit,
    no mutate, and no method that would alter AEAT-side state. Verify
    surfaces themselves are read-only by construction; this layer only
    records observations the drivers produce.
    """

    def __init__(self, *, persistence: VerifyObservationPersistencePort) -> None:
        """Initialize this public contract with composed observation persistence."""
        self._persistence = persistence

    def record(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface,
        nif: str,
        verdict: IdentityCheckVerdictValue,
        checked_at: datetime,
        expected: IdentityCheckVerdictValue | None = None,
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
        existing = self._persistence.load(bucket_id=bucket_id, observation_id=observation_id)
        if existing is not None:
            return existing
        self._persistence.save(observation)
        return observation

    def list_observations(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface | None = None,
        nif: str | None = None,
    ) -> tuple[VerifyObservation, ...]:
        """Return all :class:`VerifyObservation` records in capture order. Optional filters."""
        observations = list(self._persistence.list_observations(bucket_id=bucket_id))
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
            for o in self._persistence.list_observations(bucket_id=bucket_id)
            if o.observation_id == observation_id or o.observation_id.startswith(observation_id)
        ]
        if not matches:
            raise VerifyObservationNotFoundError(
                translated_message="application.live.verify.errors.observation_not_found",
                context={"observation_id": observation_id},
            )
        if len(matches) > 1:
            raise VerifyObservationNotFoundError(
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
            o
            for o in self._persistence.list_observations(bucket_id=bucket_id)
            if o.surface is surface and o.nif == nif
        ]
        if not matches:
            return None
        return max(matches, key=lambda o: o.checked_at)


__all__ = [
    "VerifyObservation",
    "VerifyObservationNotFoundError",
    "VerifyService",
    "VerifySurface",
    "verify_observation_object_key",
]
