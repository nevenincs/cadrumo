"""Annual-cadence revisions must date their own ejercicio, not their orden's.

Two internally-consistent conventions for ``valid_from`` coexisted in this
registry until tonight: January 1 of the ejercicio a revision computes, and
the date its approving orden happened to take legal effect. Both read as
correct in isolation -- each modelo agreed with itself -- and the two only
diverged when compared against each other or against the field the second
convention was silently duplicating (``LegalReference.effective_from``,
which already carries that fact and needs no second home).

The operator ruled ONE convention canonical: ``valid_from`` describes
COVERAGE, because coverage is the only thing ``select_revision`` uses it
for. A revision whose ``valid_from`` names its orden's effective date, not
its own ejercicio's start, refuses an ``on=``-dated query anywhere between
January 1 and the orden's real effective date -- a live gap for a genuinely
in-force filing year, discovered on Modelo 200 as a self-contradiction
against its own declared deadline window and confirmed on seven further
modelos by cross-checking against ``LegalReference.effective_from``.

SCOPE, deliberately narrow. This check applies ONLY to annual-cadence
revisions declaring exactly the single ``0A`` period -- the shape where "the
ejercicio this revision covers" is a well-defined single year. Event-driven
modelos (censal alta/modificacion/baja, comunicacion/variacion), AD-HOC
filings, and periodic multi-token schemes (OSS quarterly/monthly) have no
single ejercicio for ``valid_from`` to date, and are excluded by that
PROPERTY -- never by a list of modelo ids, which would go stale the moment a
new annual-cadence revision is authored.
"""

from __future__ import annotations

from datetime import date

from .schema import ModeloRevision


def revision_declares_single_annual_period(revision: ModeloRevision) -> bool:
    """Report whether a revision's own period declaration is exactly the annual token.

    The sole property this check gates on. A revision declaring ANY other
    period shape -- event-driven, ad-hoc, or a periodic multi-token scheme --
    has no single ejercicio for ``valid_from`` to name, and is excluded here
    rather than by a hand-maintained modelo-id allowlist.
    """
    return revision.period_selector.periods == ("0A",)


def _ejercicio_start(revision: ModeloRevision) -> date | None:
    """The January 1 an annual-cadence revision's own declared year names.

    ``None`` when the revision's period selector carries no dateable year at
    all -- nothing to compare against, so the caller reports no failure
    rather than inventing a claim the revision never made.
    """
    selector = revision.period_selector
    if selector.years:
        return date(min(selector.years), 1, 1)
    if selector.year_from is not None:
        return date(selector.year_from, 1, 1)
    return None


def validate_valid_from_ejercicio_convention(
    *,
    prefix: str,
    revision: ModeloRevision,
) -> list[str]:
    """Return a failure when an annual-cadence revision's ``valid_from`` misdates its own ejercicio.

    Args:
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        revision: The :class:`ModeloRevision` under validation.
    """
    if not revision_declares_single_annual_period(revision):
        return []
    expected = _ejercicio_start(revision)
    if expected is None:
        return []
    if revision.valid_from == expected:
        return []
    return [
        f"{prefix}: valid_from ({revision.valid_from.isoformat()}) does not equal January 1 of this "
        f"annual revision's own declared ejercicio ({expected.isoformat()}). valid_from describes "
        "COVERAGE -- the only thing select_revision uses it for -- never the date the approving orden "
        "happened to take legal effect; that fact already has its home on the citing LegalReference's "
        "effective_from. FIX: set valid_from to the ejercicio start; do not widen the check to accept "
        "an orden-effective-date reading, and do not duplicate the orden's date here instead of fixing it",
    ]


__all__ = [
    "revision_declares_single_annual_period",
    "validate_valid_from_ejercicio_convention",
]
