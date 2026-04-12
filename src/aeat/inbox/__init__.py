"""AEAT notifications inbox — fetch, classify, and track formal AEAT notices.

This subpackage is the local, typed, read-only inbox for formal
communications AEAT issues to a Spanish *autónomo*:
*requerimientos*, *propuestas de liquidación*, *acuerdos de
liquidación*, *notificaciones de embargo*, *acuses de recibo*, and
anything else the Sede Electrónica surfaces through ``Mis
notificaciones``. Missing one of these can cost a missed appeal
window, an undefended liquidación, or an enforced embargo — so the
inbox is deliberately biased toward *over-surfacing*: unclassified
notifications default to HIGH priority (see
[[2026-04-12-notifications-inbox-adr]] decision D3).

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.inbox` (the package root); the underscored
submodules are implementation detail.

Non-goals (see ADR decision D7):

- The inbox does **not** draft appeals or responses.
- It is **read-only** against AEAT — acknowledgement is local state.
- It does not send email or SMS — structured log + CLI only.
- v1 persists to a single JSON file under ``AEAT_INBOX_DIR``; the
  storage layer (#10) is not wired in.
"""

from __future__ import annotations

from aeat.inbox._classifier import (
    appeal_window_for,
    classify,
    compute_appeal_deadline,
)
from aeat.inbox._deadline import next_appeal_deadline
from aeat.inbox._errors import (
    InboxAcknowledgeError,
    InboxError,
    InboxFetchError,
)
from aeat.inbox._fetcher import InboxFetcher
from aeat.inbox._models import (
    Inbox,
    Notificacion,
    NotificacionKind,
    NotificacionPriority,
)
from aeat.inbox._protocols import NotificacionSource, RawNotificacion

__all__ = [
    "Inbox",
    "InboxAcknowledgeError",
    "InboxError",
    "InboxFetchError",
    "InboxFetcher",
    "Notificacion",
    "NotificacionKind",
    "NotificacionPriority",
    "NotificacionSource",
    "RawNotificacion",
    "appeal_window_for",
    "classify",
    "compute_appeal_deadline",
    "next_appeal_deadline",
]
