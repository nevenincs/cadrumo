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
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core.config import Settings, load_settings
from ...core.errors import AeatError
from ...core.time import _now
from .._storage_paths import storage_path

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


def _derive_observation_id(
    *,
    surface: VerifySurface,
    nif: str,
    verdict: VerifyVerdict,
    checked_at: datetime,
) -> str:
    canonical = f"{surface.value}|{nif}|{verdict}|{checked_at.isoformat()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load(settings: Settings, bucket_id: str) -> list[VerifyObservation]:
    path = storage_path(settings.aeat_audit_dir / "live" / "verify", bucket_id)
    if not path.exists():
        return []
    return [
        VerifyObservation.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _save(settings: Settings, bucket_id: str, observations: list[VerifyObservation]) -> None:
    path = storage_path(settings.aeat_audit_dir / "live" / "verify", bucket_id)
    payload = "\n".join(o.model_dump_json() for o in observations)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


class VerifyService:
    """Bucket-scoped audit log of NIF verify checks.

    Structurally read-only. The service has no submit,
    no mutate, and no method that would alter AEAT-side state. Verify
    surfaces themselves are read-only by construction; this layer only
    records observations the drivers produce.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()

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
        observations = _load(self._settings, bucket_id)
        existing = next(
            (o for o in observations if o.observation_id == observation_id),
            None,
        )
        if existing is not None:
            return existing
        observations.append(observation)
        _save(self._settings, bucket_id, observations)
        return observation

    def list_observations(
        self,
        *,
        bucket_id: str,
        surface: VerifySurface | None = None,
        nif: str | None = None,
    ) -> tuple[VerifyObservation, ...]:
        """Return all observations in capture order. Optional filters."""
        observations = _load(self._settings, bucket_id)
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
            for o in _load(self._settings, bucket_id)
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
        matches = [o for o in _load(self._settings, bucket_id) if o.surface is surface and o.nif == nif]
        if not matches:
            return None
        return max(matches, key=lambda o: o.checked_at)


__all__ = [
    "VerifyObservation",
    "VerifyObservationNotFoundError",
    "VerifyService",
    "VerifySurface",
    "VerifyVerdict",
]
