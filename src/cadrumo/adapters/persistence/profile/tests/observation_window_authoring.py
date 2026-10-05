"""Atomic set replacement for finite observation fixtures."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Protocol, cast

from pydantic import BaseModel

from .....core.period import Period
from .....core.time.clock import now
from ...storage.envelope.secure_bound_repository import SecureBoundRepository
from ...storage.envelope.tests.record_set_authoring import replace_records
from ...storage.path_safety import safe_repository_id
from ..percepciones_observations import (
    PercepcionObservationRepositoryAdapter,
)
from ..percepciones_observations import (
    _translate_storage_failure as translate_percepcion_failure,
)
from ..retencion_observations import (
    RetencionObservationRepositoryAdapter,
)
from ..retencion_observations import (
    _translate_storage_failure as translate_retencion_failure,
)


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

    The clear and the write commit as ONE transaction through the repository
    port's ``replace_records`` operation.
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
    if isinstance(repository, RetencionObservationRepositoryAdapter):
        translate_retencion_failure(
            "retencion_validate_observation_window_modelo", lambda: safe_repository_id(modelo, context="modelo")
        )
    elif isinstance(repository, PercepcionObservationRepositoryAdapter):
        translate_percepcion_failure(
            "percepcion_validate_observation_window_modelo", lambda: safe_repository_id(modelo, context="modelo")
        )
    else:
        raise TypeError("observation fixture requires its concrete persistence adapter")
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
    replace_records(repository, replacements, stale_identifiers)


def _in_window(payload: BaseModel, *, modelo: str, filing_year: int, period: Period) -> bool:
    """Return whether ``payload`` belongs to the (modelo, filing_year, period) window."""
    window_payload = cast(_WindowKeyedPayload, payload)
    return (
        window_payload.modelo == modelo
        and window_payload.filing_year == filing_year
        and (window_payload.period.registry_token == period.registry_token)
    )
