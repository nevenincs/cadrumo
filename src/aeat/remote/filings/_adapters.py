"""Adapters that project :mod:`aeat.history` records into :mod:`aeat.remote`.

The adapter layer keeps the :mod:`aeat.remote` boundary clean of the
history reader's looser string-typed surface. :class:`aeat.history.FiledModelo`
carries a free-form Spanish status string and a ``dict[str, str]``
casillas mapping; :mod:`aeat.remote` requires a typed
:class:`aeat.remote.RemoteFilingStatus` plus a tuple of strictly-typed
:class:`aeat.remote.RemoteCasilla` records. The conversion happens
once, here, so every downstream consumer (reconciler, sync-run stage,
live tests) sees a uniform shape.

The adapter is intentionally private. Callers from outside this
subpackage cannot import it; they interact only with the public
``fetch`` entry points on :mod:`aeat.remote.filings`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from ...history import FiledModelo
from ...schema import CasillaDataType
from .._errors import RemoteParseError
from .._schema import RemoteCasilla, RemoteFiling
from .._status import classify_status


def _coerce_currency(raw_value: str) -> Decimal | None:
    """Return ``raw_value`` coerced to :class:`Decimal`, or ``None`` on blank input.

    AEAT prints monetary values in the Spanish convention — dot as
    thousand separator, comma as decimal separator. The helper applies
    the minimal normalisation needed to pass the value through
    :class:`decimal.Decimal` without losing precision.

    Args:
        raw_value: The raw Spanish-formatted string exactly as AEAT
            printed it. Leading/trailing whitespace is tolerated.

    Returns:
        The parsed :class:`Decimal`, or ``None`` when ``raw_value`` is
        an empty string after stripping.

    Raises:
        RemoteParseError: If ``raw_value`` is non-empty but fails
            :class:`Decimal` coercion.
    """
    stripped = raw_value.strip()
    if not stripped:
        return None
    # Spanish locale: dot = thousand separator, comma = decimal point.
    normalised = stripped.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalised)
    except InvalidOperation as exc:
        raise RemoteParseError(f"could not coerce casilla value {raw_value!r} to Decimal: {exc}") from exc


def remote_casilla_from_raw(casilla_id: str, raw_value: str) -> RemoteCasilla:
    """Build a :class:`RemoteCasilla` from a ``(casilla_id, raw_value)`` pair.

    The adapter classifies every casilla as :attr:`CasillaDataType.CURRENCY_EUR`
    because the Tier-1 modelos (130, 303, 390) expose only monetary
    casillas in the filing-detail surface. Richer data-type resolution
    — mapping casilla identifiers against
    :class:`aeat.casillas.CasillaRecord` — is deferred to a follow-on
    PR that wires the casilla catalogue through.

    Args:
        casilla_id: Canonical casilla identifier as AEAT prints it.
        raw_value: Uncoerced Spanish-formatted string.

    Returns:
        A strict, frozen :class:`RemoteCasilla` with the coerced
        value populated when the raw value parses cleanly and left
        ``None`` otherwise.

    Raises:
        RemoteParseError: If the raw value is non-empty but fails
            :class:`Decimal` coercion.
    """
    coerced = _coerce_currency(raw_value)
    return RemoteCasilla(
        casilla_id=casilla_id,
        raw_value=raw_value,
        data_type=CasillaDataType.CURRENCY_EUR,
        coerced_value=coerced,
    )


def remote_filing_from_history(filed: FiledModelo) -> RemoteFiling:
    """Project a :class:`aeat.history.FiledModelo` into a :class:`RemoteFiling`.

    The projection preserves every byte of AEAT-surfaced information
    the Tier-1 fetchers need downstream:

    * ``filed.metadata.status`` is carried verbatim on
      :attr:`RemoteFiling.raw_status` and folded through
      :func:`classify_status` onto :attr:`RemoteFiling.status`.
    * ``filed.metadata.presented_at`` becomes
      :attr:`RemoteFiling.submitted_at` (AEAT labels the value
      ``"Fecha de presentación"``; the rename aligns it with the rest
      of the typed domain where ``submitted_at`` is the canonical
      timestamp for a successfully-received filing).
    * Every entry in ``filed.calculations.casillas`` becomes one
      :class:`RemoteCasilla`, ordered by casilla identifier for
      reproducibility across repeat fetches.

    Receipt metadata is deliberately left empty at this tier: the
    history reader already publishes the justificante URL on
    :attr:`aeat.history.FiledModeloMetadata.justificante_url`, but
    content-hash materialisation belongs in the Tier-1 fetchers that
    know which receipts are worth caching. Phase 3 receipts-over-time
    work will populate :attr:`RemoteFiling.receipts` separately.

    Args:
        filed: The upstream :class:`aeat.history.FiledModelo` record.

    Returns:
        A strict, frozen :class:`RemoteFiling` carrying the typed
        projection.

    Raises:
        RemoteParseError: If any casilla's raw value cannot be
            coerced to :class:`Decimal`.
    """
    # Normalise the submission timestamp to UTC so downstream
    # comparisons never have to reason about naive vs. aware datetimes.
    submitted_at = filed.metadata.presented_at
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=UTC)

    casillas = tuple(
        remote_casilla_from_raw(casilla_id, raw_value)
        for casilla_id, raw_value in sorted(filed.calculations.casillas.items())
    )

    status = classify_status(
        filed.metadata.status,
        modelo=filed.metadata.modelo,
        period=filed.metadata.period,
    )

    return RemoteFiling(
        modelo=filed.metadata.modelo,
        period=filed.metadata.period,
        expediente_id=filed.metadata.expediente_id,
        status=status,
        raw_status=filed.metadata.status,
        submitted_at=submitted_at,
        casillas=casillas,
        complementaria_of=filed.metadata.complementaria_of,
    )


def _utcnow() -> datetime:
    """Return the current UTC wall-clock time.

    Factored out so unit tests that need a deterministic
    ``captured_at`` marker can pass their own ``now`` callable through
    the fetcher entry points.
    """
    return datetime.now(UTC)


__all__ = [
    "remote_casilla_from_raw",
    "remote_filing_from_history",
]
