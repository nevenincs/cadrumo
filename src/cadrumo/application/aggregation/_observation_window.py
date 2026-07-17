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
    save_observation: Callable[..., None],
    captured_at: datetime | None = None,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Replace the FULL observation set for one (modelo, filing_year, period) window.

    SET-REPLACE, not additive upsert: clears any prior rows for the exact
    key-tuple on ``repository``, then writes the supplied ``observations``
    through ``save_observation`` (each repository's own typed
    ``save_observation`` method, which builds the correctly-typed envelope
    payload). An empty ``observations`` clears the window, matching each
    repository's own no-silent-under-declaration contract on the caller side.
    """
    safe_repository_id(modelo, context="modelo")
    when = captured_at if captured_at is not None else now()
    for payload in tuple(repository.iter_records()):
        # CAST-RATIONALE-OBSERVATION-WINDOW-PAYLOAD: repository records share the required window-key fields.
        window_payload = cast(  # nosemgrep: no-cast-in-domain-application reason: row implements _WindowKeyedPayload.
            _WindowKeyedPayload,
            payload,
        )
        if (
            window_payload.modelo == modelo
            and window_payload.filing_year == filing_year
            and window_payload.period.registry_token == period.registry_token
        ):
            repository.delete(repository.extract_identifier(payload))
    for observation in observations:
        save_observation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            source_kind=source_kind,
            captured_at=when,
            source_metadata=source_metadata,
        )


__all__ = ["replace_observation_window"]
