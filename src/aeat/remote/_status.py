"""Closed enumeration of AEAT remote filing statuses.

This module exposes :class:`RemoteFilingStatus`, the typed domain enum
that wraps the free-form Spanish status strings printed by AEAT. The
``UNKNOWN`` fallback keeps the surface forward-compatible with statuses
that AEAT introduces without notice; callers must preserve the raw
Spanish prose elsewhere on the record (see
:class:`aeat.remote.RemoteFiling.raw_status`).

Status string mapping (authoritative — update with every enum extension):

===============================  =====================================
AEAT status string               ``RemoteFilingStatus`` member
===============================  =====================================
``"Presentada"``                 :attr:`RemoteFilingStatus.PRESENTADA`
``"En tramitacion"``             :attr:`RemoteFilingStatus.EN_TRAMITACION`
``"En tramitación"``             :attr:`RemoteFilingStatus.EN_TRAMITACION`
``"Rechazada"``                  :attr:`RemoteFilingStatus.RECHAZADA`
``"Subsanada"``                  :attr:`RemoteFilingStatus.SUBSANADA`
``"Complementaria"``             :attr:`RemoteFilingStatus.COMPLEMENTARIA`
``"Anulada"``                    :attr:`RemoteFilingStatus.ANULADA`
Anything else                    :attr:`RemoteFilingStatus.UNKNOWN`
===============================  =====================================

Any resolution that lands on :attr:`RemoteFilingStatus.UNKNOWN` emits a
``logging.warning`` through :func:`aeat.logging.get_logger` with the
offending raw string plus the modelo/period context so maintainers can
extend the enum in a follow-up PR.
"""

from __future__ import annotations

from enum import StrEnum

from ..logging import get_logger

_logger = get_logger(__name__)


class RemoteFilingStatus(StrEnum):
    """Closed status vocabulary for :class:`aeat.remote.RemoteFiling`.

    Members mirror the Spanish status strings AEAT prints on the
    expediente detail page. Unknown strings fold into :attr:`UNKNOWN`
    and the caller preserves the raw prose in ``raw_status`` so no
    information is lost in the translation.
    """

    PRESENTADA = "presentada"
    """AEAT has received and accepted the filing."""
    EN_TRAMITACION = "en_tramitacion"
    """AEAT is processing the filing; no terminal decision yet."""
    RECHAZADA = "rechazada"
    """AEAT rejected the filing; Kent must remediate."""
    SUBSANADA = "subsanada"
    """A previously rejected filing has been amended and re-accepted."""
    COMPLEMENTARIA = "complementaria"
    """The filing is a rectifying complement to a prior expediente."""
    ANULADA = "anulada"
    """The filing was cancelled after acceptance."""
    UNKNOWN = "unknown"
    """Fallback for statuses the enum does not yet model."""


_KNOWN_STATUS_MAP: dict[str, RemoteFilingStatus] = {
    "presentada": RemoteFilingStatus.PRESENTADA,
    "en tramitacion": RemoteFilingStatus.EN_TRAMITACION,
    "en tramitación": RemoteFilingStatus.EN_TRAMITACION,
    "rechazada": RemoteFilingStatus.RECHAZADA,
    "subsanada": RemoteFilingStatus.SUBSANADA,
    "complementaria": RemoteFilingStatus.COMPLEMENTARIA,
    "anulada": RemoteFilingStatus.ANULADA,
}


def classify_status(
    raw_status: str,
    *,
    modelo: str | None = None,
    period: str | None = None,
) -> RemoteFilingStatus:
    """Map a raw AEAT status string to a :class:`RemoteFilingStatus` member.

    Args:
        raw_status: The Spanish status string as AEAT prints it. The
            lookup is case-insensitive and tolerant of leading/trailing
            whitespace.
        modelo: Optional modelo identifier used to annotate the warning
            log when the string resolves to :attr:`RemoteFilingStatus.UNKNOWN`.
        period: Optional period identifier used similarly for diagnostics.

    Returns:
        The matching :class:`RemoteFilingStatus` member. Unknown input
        returns :attr:`RemoteFilingStatus.UNKNOWN` and emits a warning
        log record so the enum can be extended in a follow-up PR.
    """
    key = raw_status.strip().casefold()
    resolved = _KNOWN_STATUS_MAP.get(key)
    if resolved is not None:
        return resolved
    _logger.warning(
        "remote filing status %r does not map to a known RemoteFilingStatus member "
        "(modelo=%s, period=%s); falling back to UNKNOWN",
        raw_status,
        modelo,
        period,
    )
    return RemoteFilingStatus.UNKNOWN


__all__ = ["RemoteFilingStatus", "classify_status"]
