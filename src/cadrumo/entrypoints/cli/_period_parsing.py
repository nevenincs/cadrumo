"""Strict AEAT ``--period`` token normalisation at the CLI boundary.

Resolves the canonical AEAT modelo tokens plus ``--year`` into the
:class:`~cadrumo.core.Period` date span the ledger filters by, and refuses every
calendar shape with an instructive message carrying the accepted token set as
structured data.

See Also:
    :class:`~cadrumo.core.Period`
        The canonical period boundary authority this module resolves into.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import typer

from ...core.i18n._render import tr
from ._common import _bad

if TYPE_CHECKING:
    from ...core.period import Period

__all__ = ["_canonical_period", "_filter_canonical_period", "_optional_canonical_period"]


# The ledger ``--period`` surface speaks ONE strict operator grammar — the
# canonical AEAT modelo tokens (``0A`` annual, ``1T``-``4T`` quarters,
# ``01``-``12`` months) the modelo surfaces already teach (one strict period
# grammar everywhere, AEAT tokens only). Those tokens carry no year of their
# own, so every ledger ``--period`` command also takes ``--year`` to supply
# the year context — exactly the modelo ``--year``/``--period`` composition,
# so ``--period 1T --year 2024`` reads identically across ledger and modelo.
# A filing period is ALWAYS carried as a ``(year, bare-token)`` pair — never a
# combined calendar string. The internal value the ledger filters by is a
# :class:`Period` date span built directly from that pair; there is no calendar
# shape, no year-qualified hybrid, and no conversion layer. A calendar shape
# (``2024Q1`` / ``2024-03`` / ``2024``) is refused with a message naming the
# AEAT tokens and the ``--year`` argument.


def _ledger_aeat_token(token: str) -> str | None:
    """Return the normalised ledger-meaningful registry token, or ``None``.

    Validates ``token`` against the registry period union and accepts it only
    when it is a span-shaped :class:`StandardPeriodCode` member the
    ledger can filter by (quarters, months, annual). Extended-union members the ledger
    does not filter by (``EXT-*``, ``AD-HOC``, ``EVENT-N``) and instalment
    claves (``1P``-``4P``) return ``None``.
    """
    from ...core.period import StandardPeriodCode

    try:
        registry_period = StandardPeriodCode(token.strip().upper()).value
    except ValueError:
        return None
    if registry_period not in frozenset(StandardPeriodCode):
        return None
    return registry_period


#: Year used only to probe whether a token maps to a calendar date span. The
#: span shape depends on the token's cadence, not the year, so any supported
#: year answers identically; it never leaks into an operator-supplied period.
_ACCEPTED_PERIOD_PROBE_YEAR = 2024


def _ledger_period_accepted_tokens() -> tuple[str, ...]:
    """Return the span-shaped registry tokens the ledger ``--period`` accepts.

    Derived from the same rule :func:`_canonical_period` applies: a
    :class:`StandardPeriodCode` member the ledger normalises
    (:func:`_ledger_aeat_token`) AND whose ``(year, token)`` :class:`Period`
    carries a calendar date span. The instalment claves (``1P``-``4P``) and the
    extended-union members resolve to no span and are excluded, so the advertised
    accepted set is computed from the acceptance rule and can never drift from
    what the boundary actually admits — a new span-shaped enum member is
    advertised automatically.
    """
    from ...core.period import Period, PeriodError, StandardPeriodCode

    accepted: list[str] = []
    for member in StandardPeriodCode:
        normalised = _ledger_aeat_token(member.value)
        if normalised is None:
            continue
        try:
            resolved = Period.from_year_and_code(_ACCEPTED_PERIOD_PROBE_YEAR, normalised)
        except PeriodError:
            continue
        if resolved.has_date_span():
            accepted.append(normalised)
    return tuple(accepted)


class _LedgerPeriodRefusal(typer.BadParameter):
    """A ``--period`` refusal that carries the accepted token set as structured data.

    Subclasses :class:`typer.BadParameter` so the boundary behaviour is unchanged
    — an instructive usage refusal with the usage exit code — while exposing the
    machine-readable accepted-token set on :attr:`accepted_period_tokens`. The
    terminal JSON handler threads that set into the error envelope's structured
    ``context``, so automation reads the accepted grammar as data rather than
    scraping the rendered range notation, and a wording pass on the message
    cannot change the advertised set.

    Takes the locale key via the keyword ``translated_message`` (with its
    substitution ``context``) rather than an already-resolved string, matching
    the project-wide structured-error contract: the key and its context ride on
    the exception, resolved once here for the click-parse-time rendering, but
    available unflattened for any later structured consumer.
    """

    def __init__(
        self,
        *,
        translated_message: str,
        context: Mapping[str, object] | None = None,
        accepted_period_tokens: tuple[str, ...],
    ) -> None:
        resolved_context = dict(context) if context is not None else {}
        super().__init__(tr(translated_message, **resolved_context))
        self.translated_message: str = translated_message
        self.context: dict[str, object] = resolved_context
        self.accepted_period_tokens: tuple[str, ...] = accepted_period_tokens


def _canonical_period(period: str, *, year: int) -> Period:
    """Resolve a strict AEAT ``--period`` token plus ``--year`` to a :class:`Period`.

    The ledger ``--period`` surface accepts only the canonical AEAT modelo
    tokens (``0A`` annual, ``1T``-``4T`` quarters, ``01``-``12`` months),
    validated through the registry period union at :mod:`core`,
    and composes them with ``--year`` exactly as the modelo surface does. A
    calendar shape (``2026Q1`` / ``2026-03`` / ``2026``) or any other notation
    is refused with a message naming the AEAT tokens and the ``--year``
    argument. The ``(year, token)`` pair builds the
    :class:`Period` date span the ledger filters by — there is no
    intermediate calendar string.
    """
    from ...core.period import Period, PeriodError

    stripped = period.strip()
    if not stripped:
        raise _bad(tr("cli.common.errors.period_empty"))

    registry_period = _ledger_aeat_token(stripped)
    if registry_period is not None:
        try:
            resolved = Period.from_year_and_code(year, registry_period)
        except PeriodError:
            pass
        else:
            if resolved.has_date_span():
                return resolved
            # A registry-valid token the ledger cannot filter by (an instalment
            # clave such as ``1P``): refuse with the AEAT-token guidance below.

    raise _LedgerPeriodRefusal(
        translated_message="cli.common.errors.period_unrecognised",
        context={"raw": period},
        accepted_period_tokens=_ledger_period_accepted_tokens(),
    )


def _filter_canonical_period(token: str, *, year: int) -> Period:
    """Resolve a ``--filter period=`` bare token plus ``--filter year=`` to :class:`Period`.

    The ledger ``--filter`` grammar carries the filing year as a separate
    ``year=`` clause, so ``period=`` is the same bare AEAT token the
    ``--period`` option accepts (``1T`` / ``0A`` / ``03``). A calendar shape or
    a year-qualified hybrid (``2026Q1`` / ``2026-1T``) is refused with a message
    naming the AEAT tokens. Reuses the same ``(year, token)→Period`` mapping the
    ``--period`` / ``--year`` commands use.
    """
    return _canonical_period(token, year=year)


def _optional_canonical_period(period: str | None, *, year: int | None) -> Period | None:
    """Resolve an optional ``--period`` / ``--year`` pair to :class:`Period` or ``None``.

    Returns ``None`` when no ``--period`` is supplied (the command scopes the
    whole ledger). When ``--period`` is supplied it requires ``--year`` (the
    AEAT token carries no year of its own) and converts the pair through
    :func:`_canonical_period`; a ``--period``
    with no ``--year`` refuses with an instructive message naming the
    ``--year`` argument.
    """
    if period is None:
        return None
    if year is None:
        raise _bad(tr("cli.common.errors.period_missing_year", token=period.strip()))
    return _canonical_period(period, year=year)
