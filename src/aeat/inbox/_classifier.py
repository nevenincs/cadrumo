"""Classifier for raw AEAT notifications.

The classifier is a pure-function rule table over the Spanish subject
prefix. See [[2026-04-12-notifications-inbox-adr]] decisions D2 and D3:
the table is deterministic, exhaustive against the known surface, and
any unclassified subject falls through to
``(NotificacionKind.OTRO, NotificacionPriority.HIGH)`` — never
``NORMAL``, never ``INFO``. Over-surfacing is by design.

Appeal-window rules are declared in :data:`_APPEAL_WINDOWS` per
:class:`NotificacionKind`. v1 uses calendar-day arithmetic even for
business-day legal rules; see ADR decision D8.
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict

from ._models import NotificacionKind, NotificacionPriority
from ._protocols import RawNotificacion

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _AppealWindow(BaseModel):
    """Declared appeal window for one :class:`NotificacionKind`.

    Attributes:
        days: The window length; units defined by :attr:`unit`.
        unit: ``"calendar"`` or ``"business"``. v1 always computes the
            deadline as calendar days regardless of this field — see
            ADR decision D8. The field is retained so future work can
            tighten business-day arithmetic without schema churn.
        rule: The legal citation this window derives from.
    """

    model_config = _STRICT_FROZEN

    days: int
    unit: Literal["calendar", "business"]
    rule: str


_APPEAL_WINDOWS: dict[NotificacionKind, _AppealWindow | None] = {
    NotificacionKind.REQUERIMIENTO: _AppealWindow(days=10, unit="business", rule="LGT art. 99"),
    NotificacionKind.PROPUESTA_LIQUIDACION: _AppealWindow(days=15, unit="calendar", rule="LGT art. 34.1.l"),
    NotificacionKind.ACUERDO_LIQUIDACION: _AppealWindow(days=30, unit="calendar", rule="LGT art. 223"),
    NotificacionKind.NOTIFICACION_EMBARGO: _AppealWindow(days=30, unit="calendar", rule="LGT art. 170.3"),
    NotificacionKind.ACUSE_RECIBO: None,
    NotificacionKind.COMUNICACION_GENERAL: None,
    NotificacionKind.OTRO: None,
}


class _Rule(NamedTuple):
    """One row of the classifier rule table."""

    prefix: str
    kind: NotificacionKind
    priority: NotificacionPriority


_RULES: tuple[_Rule, ...] = (
    # Most-specific prefixes first. Order matters for longest-prefix match.
    _Rule("requerimiento de informacion", NotificacionKind.REQUERIMIENTO, NotificacionPriority.CRITICAL),
    _Rule("requerimiento de subsanacion", NotificacionKind.REQUERIMIENTO, NotificacionPriority.CRITICAL),
    _Rule("requerimiento", NotificacionKind.REQUERIMIENTO, NotificacionPriority.CRITICAL),
    _Rule("propuesta de liquidacion", NotificacionKind.PROPUESTA_LIQUIDACION, NotificacionPriority.CRITICAL),
    _Rule("propuesta de regularizacion", NotificacionKind.PROPUESTA_LIQUIDACION, NotificacionPriority.CRITICAL),
    _Rule("acuerdo de liquidacion", NotificacionKind.ACUERDO_LIQUIDACION, NotificacionPriority.CRITICAL),
    _Rule("liquidacion provisional", NotificacionKind.ACUERDO_LIQUIDACION, NotificacionPriority.CRITICAL),
    _Rule("liquidacion definitiva", NotificacionKind.ACUERDO_LIQUIDACION, NotificacionPriority.CRITICAL),
    _Rule("diligencia de embargo", NotificacionKind.NOTIFICACION_EMBARGO, NotificacionPriority.CRITICAL),
    _Rule("notificacion de embargo", NotificacionKind.NOTIFICACION_EMBARGO, NotificacionPriority.CRITICAL),
    _Rule("acuse de recibo", NotificacionKind.ACUSE_RECIBO, NotificacionPriority.INFO),
    _Rule("justificante de recepcion", NotificacionKind.ACUSE_RECIBO, NotificacionPriority.INFO),
    _Rule("comunicacion", NotificacionKind.COMUNICACION_GENERAL, NotificacionPriority.NORMAL),
    _Rule("informacion general", NotificacionKind.COMUNICACION_GENERAL, NotificacionPriority.NORMAL),
)


def _normalise(subject_es: str) -> str:
    """Return ``subject_es`` stripped, lowercased, and accent-folded.

    Applies Unicode NFD decomposition, strips combining marks, and
    lowercases the result so ``"Requerimiento de Información"`` and
    ``"requerimiento de informacion"`` both match the same rule prefix.
    """
    decomposed = unicodedata.normalize("NFD", subject_es)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.strip().lower()


def classify(raw: RawNotificacion) -> tuple[NotificacionKind, NotificacionPriority]:
    """Classify a :class:`RawNotificacion` into a ``(kind, priority)`` pair.

    Args:
        raw: The raw notification as delivered by a
            :class:`aeat.inbox._protocols.NotificacionSource`.

    Returns:
        A ``(NotificacionKind, NotificacionPriority)`` tuple. Any
        subject whose Spanish prefix does not match a rule is
        classified as ``(OTRO, HIGH)`` — see ADR decision D3.
    """
    subject_es = raw.subject.get("es", "")
    normalised = _normalise(subject_es)
    for rule in _RULES:
        if normalised.startswith(rule.prefix):
            return rule.kind, rule.priority
    return NotificacionKind.OTRO, NotificacionPriority.HIGH


def appeal_window_for(kind: NotificacionKind) -> timedelta | None:
    """Return the calendar-day appeal window for ``kind``, or ``None``.

    v1 collapses calendar- and business-day rules to calendar days.
    The result is deliberately conservative: on business-day rules the
    deadline is earlier than strict legal reality, so the user sees
    alerts sooner rather than later. See ADR decision D8.

    Args:
        kind: The classified notification kind.

    Returns:
        A :class:`datetime.timedelta` equal to the number of days in
        the declared appeal window, or ``None`` if the kind has no
        window (informational).
    """
    window = _APPEAL_WINDOWS[kind]
    if window is None:
        return None
    return timedelta(days=window.days)


def compute_appeal_deadline(effective_at: datetime, kind: NotificacionKind) -> date | None:
    """Return the appeal deadline for a notification, or ``None``.

    Args:
        effective_at: The legal *fecha de notificación*.
        kind: The classified :class:`NotificacionKind`.

    Returns:
        The calendar date the appeal is due by, or ``None`` if the
        kind has no window.
    """
    window = appeal_window_for(kind)
    if window is None:
        return None
    return (effective_at + window).date()
