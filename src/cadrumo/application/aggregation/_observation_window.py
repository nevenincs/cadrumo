"""Shared set-replace algorithm for per-(modelo, filing_year, period) observation stores.

The percepciones (Modelo 190) and retención (Modelo 180/193) per-perceptor
observation repositories each persist a distinct row type keyed by
``(modelo, filing_year, period)`` plus a per-record identity, and each needs
the exact same SET-REPLACE discipline on a re-pull: clear every prior row for
the window, then write the supplied set. Leaving the stale window behind (an
additive upsert instead of a set-replace) inflates the next calculate's
distinct count with a record the operator no longer declares — a silent
over-count. This module holds that one algorithm so
:class:`~._percepciones_observations_repository.PercepcionObservationRepository`
and :class:`~._retencion_observations_repository.RetencionObservationRepository`
both call it instead of each carrying their own copy of the loop.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, cast

from pydantic import BaseModel

from ...adapters.persistence.storage import safe_repository_id
from ...core import Period
from ...core.time import now

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureBoundRepository


class _WindowKeyedPayload(Protocol):
    """Structural shape shared by every per-perceptor observation envelope payload."""

    modelo: str
    filing_year: int
    period: Period


def replace_observation_window[ObservationT, PayloadT: BaseModel](
    repository: SecureBoundRepository[PayloadT],
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[ObservationT],
    source_kind: str,
    build_payload: Callable[..., PayloadT],
    captured_at: datetime | None = None,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Replace the FULL observation set for one (modelo, filing_year, period) window.

    SET-REPLACE, not additive upsert: every prior row for the exact key-tuple on
    ``repository`` is cleared and the supplied ``observations`` are written in
    its place. An empty ``observations`` clears the window, matching each
    repository's own no-silent-under-declaration contract on the caller side.

    The clear and the write commit as ONE transaction through
    :meth:`~adapters.persistence.storage.SecureBoundRepository.replace_records`.
    Deleting each stale row and then saving each replacement one at a time made
    every intermediate state observable: a failure part-way through the write
    loop left the window holding neither the old declared set nor the new one,
    and the next calculate read that partial window as the operator's declared
    truth — a silent under-count with the evidence for it already destroyed.

    Args:
        repository: The window's encrypted store.
        modelo: Modelo id owning the window.
        filing_year: Filing year owning the window.
        period: Period owning the window.
        observations: The full replacement set (possibly empty).
        source_kind: Capture provenance recorded on every written row.
        build_payload: Each repository's own typed envelope-payload builder.
            Returns the payload rather than persisting it, so every row is
            constructed and validated before any of them is committed.
        captured_at: Capture instant stamped on every written row; defaults to
            now, resolved once so the whole set shares one instant.
        source_metadata: Capture metadata recorded on every written row.
    """
    safe_repository_id(modelo, context="modelo")
    when = captured_at if captured_at is not None else now()
    replacements = tuple(
        build_payload(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            source_kind=source_kind,
            captured_at=when,
            source_metadata=source_metadata,
        )
        for observation in observations
    )
    stale_identifiers = tuple(
        repository.extract_identifier(payload)
        for payload in repository.iter_records()
        if _in_window(payload, modelo=modelo, filing_year=filing_year, period=period)
    )
    repository.replace_records(replacements, stale_identifiers)


def _in_window(payload: BaseModel, *, modelo: str, filing_year: int, period: Period) -> bool:
    """Return whether ``payload`` belongs to the (modelo, filing_year, period) window."""
    # CAST-RATIONALE-OBSERVATION-WINDOW-PAYLOAD: repository records share the required window-key fields.
    window_payload = cast(  # nosemgrep: no-cast-in-domain-application reason: row implements _WindowKeyedPayload.
        _WindowKeyedPayload,
        payload,
    )
    return (
        window_payload.modelo == modelo
        and window_payload.filing_year == filing_year
        and window_payload.period.registry_token == period.registry_token
    )


__all__ = ["replace_observation_window"]
