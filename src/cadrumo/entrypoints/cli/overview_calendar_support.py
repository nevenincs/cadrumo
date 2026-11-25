"""Render where an overview calendar range sits against the served filing-year envelope.

The read serves the envelope and the range's state; this surface only prints
them. A range outside the envelope must never read as a calendar with nothing
due, so every state other than ``supported`` carries an explanatory notice.
"""

from __future__ import annotations

from ...application.overview.calendar_envelope import OverviewCalendarSupport, OverviewCalendarSupportState
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity

_SUPPORT_NOTICE_CODE_PREFIX = "overview.calendar.support"
_OPEN_CEILING_TEXT = "-"


def _ceiling_text(support: OverviewCalendarSupport) -> str:
    return _OPEN_CEILING_TEXT if support.hard_ceiling is None else str(support.hard_ceiling)


def calendar_support_line(support: OverviewCalendarSupport) -> str:
    """Return the stable text line stating the envelope and the range's state."""
    return f"support\t{support.state.value}\t{support.floor}\t{support.horizon}\t{_ceiling_text(support)}"


def _support_message(support: OverviewCalendarSupport) -> str:
    """Return the localized explanation for a range that is not plainly supported.

    Each key is a literal :func:`tr` argument so the catalogue-parity gate sees it.
    """
    state = support.state
    if state is OverviewCalendarSupportState.PROJECTED:
        return tr("cli.overview.calendar.support.projected", horizon=support.horizon)
    if state is OverviewCalendarSupportState.PARTIAL:
        return tr("cli.overview.calendar.support.partial")
    if state is OverviewCalendarSupportState.BELOW_FLOOR:
        return tr("cli.overview.calendar.support.below_floor", floor=support.floor)
    return tr("cli.overview.calendar.support.above_ceiling", ceiling=support.hard_ceiling)


def calendar_support_notices(support: OverviewCalendarSupport) -> list[Notice]:
    """Project the range's support state onto the envelope notice channel.

    ``supported`` yields nothing. ``projected`` is informational: the entries
    are real deadlines, answered from the newest edition. ``partial`` and the
    two unsupported states warn, because some or all of the range shows no
    obligations for a reason other than nothing being due.
    """
    if support.state is OverviewCalendarSupportState.SUPPORTED:
        return []
    severity = (
        NoticeSeverity.INFO if support.state is OverviewCalendarSupportState.PROJECTED else NoticeSeverity.WARNING
    )
    return [
        Notice(
            severity=severity,
            code=f"{_SUPPORT_NOTICE_CODE_PREFIX}.{support.state.value}",
            message=_support_message(support),
            context={
                "state": support.state.value,
                "floor": str(support.floor),
                "horizon": str(support.horizon),
                "hard_ceiling": _ceiling_text(support),
            },
        )
    ]


__all__ = ["calendar_support_line", "calendar_support_notices"]
