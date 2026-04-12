"""Deadline helpers for the AEAT notifications inbox.

Pure, deterministic functions over a loaded :class:`aeat.inbox.Inbox`.
See [[2026-04-12-notifications-inbox-adr]] decisions D5 and D8.
"""

from __future__ import annotations

from datetime import date

from aeat.inbox._models import Inbox, Notificacion, NotificacionPriority


def next_appeal_deadline(
    inbox: Inbox,
    *,
    today: date | None = None,
    lead_days: int | None = None,
) -> Notificacion | None:
    """Return the soonest CRITICAL/HIGH notification with an open deadline.

    Considers only notifications that:

    - have a non-``None`` :attr:`Notificacion.appeal_deadline`,
    - have :attr:`Notificacion.priority` of ``CRITICAL`` or ``HIGH``,
    - have not been acknowledged, and
    - have ``appeal_deadline >= today``.

    If ``lead_days`` is provided, only notifications whose deadline
    falls within ``[today, today + lead_days]`` are considered — this
    is what ``aeat inbox next-deadline`` reads from
    ``AEAT_INBOX_ALERT_LEAD_DAYS``.

    Args:
        inbox: The loaded :class:`Inbox`.
        today: The reference calendar date; defaults to
            :meth:`datetime.date.today`.
        lead_days: Optional alert-window lead in days. ``None`` means
            "any future deadline".

    Returns:
        The :class:`Notificacion` with the earliest matching deadline,
        or ``None`` if nothing qualifies.
    """
    reference = today if today is not None else date.today()
    candidates: list[Notificacion] = []
    for record in inbox.values():
        if record.acknowledged_at is not None:
            continue
        if record.priority not in (NotificacionPriority.CRITICAL, NotificacionPriority.HIGH):
            continue
        deadline = record.appeal_deadline
        if deadline is None or deadline < reference:
            continue
        if lead_days is not None and (deadline - reference).days > lead_days:
            continue
        candidates.append(record)
    if not candidates:
        return None

    def _deadline_key(record: Notificacion) -> date:
        # Safe: candidates are pre-filtered to non-None deadlines above.
        assert record.appeal_deadline is not None
        return record.appeal_deadline

    return min(candidates, key=_deadline_key)
