"""Canonical wall-clock helpers for the AEAT domain.

A single, testable entry-point for obtaining the current UTC time.
Call-sites must import :func:`now` from :mod:`cadrumo.core.time` rather
than inlining ``datetime.now(tz=UTC)`` directly, so the production
clock can be traced and call-sites stay uniform.

Deterministic-output seam
-------------------------
:func:`now` consults a context-variable frozen instant so a replay or
golden-capture scope can make every call site that routes through it
deterministic. The seam is DEFAULT-OFF: production never enters
:func:`frozen_clock`, so :func:`now` returns real
``datetime.now(tz=UTC)`` with zero behaviour change. The seam is
context-var scoped — never process-global — so it cannot leak across
tasks the way ``freezegun`` / ``time_machine`` global freezing does, the
pattern banned in live-marked tests by the repo-root shared collection policy.
:func:`frozen_clock`
additionally refuses to activate while the pytest live-read opt-in
(:attr:`cadrumo.core.config.Settings.live_tests_enabled`) is set, keeping
live-marked tests on real wall-clock plus explicit ``clock=`` injection
exactly as today.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from ..errors.hierarchy import CoreValidationError
from ._utc import validate_utc_aware

_FROZEN_INSTANT: ContextVar[datetime | None] = ContextVar(
    "_aeat_frozen_clock_instant",
    default=None,
)
"""Replay/test-scoped frozen instant consulted by :func:`now`; ``None`` in production."""


def now() -> datetime:
    """Return the current UTC-aware datetime, or the frozen instant when the seam is active.

    In production :data:`_FROZEN_INSTANT` is never set, so this returns
    real wall-clock ``datetime.now(tz=UTC)`` with zero behaviour change.
    Under a :func:`frozen_clock` scope it returns the frozen instant,
    making every call site that routes through this function
    deterministic for the duration of the scope.

    Returns:
        A :class:`datetime.datetime` instance with :data:`datetime.UTC` as its
        ``tzinfo``.
    """
    frozen = _FROZEN_INSTANT.get()
    if frozen is not None:
        return frozen
    return datetime.now(tz=UTC)


MADRID_TZ = ZoneInfo("Europe/Madrid")
"""Spain's peninsular civil timezone, the authority for regulated calendar boundaries.

Spanish tax calendar boundaries are governed by Spain's official civil date, not
the UTC date: filing plazos at the AEAT sede electrónica follow peninsular
official time (Ley 39/2015 art. 31), and the IVA rate of an operation is the one
in force at devengo (LIVA art. 90.Dos with art. 75) — a Spanish-calendar fact.
The civil date leads UTC by one to two hours around midnight.
"""


def today_madrid() -> date:
    """Return the current civil date in Europe/Madrid, derived from the clock seam.

    This is the authority a regulated date-boundary comparison defaults to (a
    filing plazo, an IVA rate-change date, a statutory-window year boundary) —
    :func:`now` (UTC) reports yesterday's Spanish date for up to two hours every
    night, selecting the wrong side of such a boundary in that window. Because
    it derives from :func:`now`, :func:`frozen_clock` pins it with zero new seam
    state; determinism is inherited, not re-engineered.

    Convention: a *regulated or civil-date* reference-date default reads
    :func:`today_madrid`; a raw UTC calendar date (e.g. the date component of a
    UTC timestamp) reads ``now().date()``. The two are not interchangeable at the
    nightly boundary, so a reference date that legally binds to the Spanish
    calendar MUST use :func:`today_madrid`.

    Returns:
        The current calendar :class:`datetime.date` in Europe/Madrid civil time.
    """
    return now().astimezone(MADRID_TZ).date()


def clock_is_frozen() -> bool:
    """Return whether a :func:`frozen_clock` scope is active for the current context."""
    return _FROZEN_INSTANT.get() is not None


def _refuse_under_live_opt_in() -> None:
    """Raise :class:`CoreValidationError` when the live-test opt-in is active.

    The seam must stay off in live-marked tests: those run against real
    external services on real wall-clock, and freezing the clock there
    is the exact global-freeze anti-pattern the live-import ban exists to
    prevent. ``load_settings`` is imported lazily to avoid a
    module-load cycle between ``core.config`` and ``core.time``.
    """
    from ..config import load_settings

    if load_settings().live_tests_enabled:
        raise CoreValidationError(
            "frozen_clock is forbidden while the live-test opt-in "
            "is set: live-marked tests must run on "
            "real wall-clock plus explicit clock= injection",
        )


@contextmanager
def frozen_clock(instant: datetime) -> Iterator[datetime]:
    """Freeze :func:`now` to ``instant`` for the duration of the scope.

    This is the replay/golden-capture-only seam behind the
    deterministic-output substrate. It is DEFAULT-OFF (production never
    enters it) and context-var scoped (never process-global), and it
    refuses to activate under the pytest live-read opt-in.

    Args:
        instant: The UTC-aware instant :func:`now` returns while active.

    Yields:
        The frozen ``instant``.

    Raises:
        CoreValidationError: When ``instant`` is naive or not UTC, or when
            the pytest live-read opt-in is enabled.
    """
    validate_utc_aware(instant)
    _refuse_under_live_opt_in()
    token = _FROZEN_INSTANT.set(instant)
    try:
        yield instant
    finally:
        _FROZEN_INSTANT.reset(token)
