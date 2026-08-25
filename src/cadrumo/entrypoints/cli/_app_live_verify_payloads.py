"""Typed JSON transport schemas for the live verify service."""

from __future__ import annotations

from ...core.identity import BucketId
from ...core.json_contract import OutputSchema


class VerifyObservationPayload(OutputSchema):
    """Shared JSON projection of one persisted verify observation.

    Mirrors :class:`VerifyObservation` while keeping ``bucket_id`` on detail
    and capture responses. ``surface`` is the :class:`VerifySurface` value, and
    ``matched_expectation`` records whether the optional operator expectation
    matched the live verdict.
    """

    bucket_id: BucketId
    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


class VerifyObservationSummaryPayload(OutputSchema):
    """Compact verify-observation row for list output.

    Used by :class:`VerifyListResult` for compact :class:`VerifyObservation`
    projections. The list command already carries ``bucket_id`` at the envelope
    result level, so each row keeps only the observation identity,
    :class:`VerifySurface` value, NIF, verdict, and expectation-match status.
    """

    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


class VerifyListResult(OutputSchema):
    """Typed listing of persisted NIF verification observations.

    ``rows`` contains :class:`VerifyObservationSummaryPayload` projections read
    through :class:`VerifyService`; the command does not contact AEAT.
    """

    bucket_id: BucketId
    count: int
    rows: list[VerifyObservationSummaryPayload]


class VerifyViewResult(VerifyObservationPayload):
    """Typed detail view for one persisted :class:`VerifyObservation`.

    The inherited :class:`VerifyObservationPayload` fields are resolved through
    :class:`VerifyService` storage, not by performing a fresh live check.
    """


class VerifyLatestResult(OutputSchema):
    """Typed newest-observation response for one surface/NIF pair.

    ``observation_id`` is ``None`` when :class:`VerifyService` finds no
    :class:`VerifyObservation` matching the requested (:class:`VerifySurface`,
    NIF) pair; ``surface`` and ``nif`` are still populated to identify the
    lookup, and every observation-derived field is ``None``.
    """

    bucket_id: BucketId
    observation_id: str | None
    surface: str
    nif: str
    verdict: str | None = None
    expected: str | None = None
    matched_expectation: bool | None = None
    checked_at: str | None = None


class VerifyNifIvaResult(VerifyObservationPayload):
    """Typed result for an IXVI NIF-IVA live-read observation.

    The command persists the read-only AEAT verdict through
    :class:`VerifyService` before emitting the inherited
    :class:`VerifyObservationPayload` fields.
    """


class VerifyTgviResult(VerifyObservationPayload):
    """Typed result for a TGVI/GROI live-read observation.

    The command persists the read-only AEAT verdict through
    :class:`VerifyService` before emitting the inherited
    :class:`VerifyObservationPayload` fields.
    """


__all__ = [
    "VerifyLatestResult",
    "VerifyListResult",
    "VerifyNifIvaResult",
    "VerifyObservationPayload",
    "VerifyObservationSummaryPayload",
    "VerifyTgviResult",
    "VerifyViewResult",
]
