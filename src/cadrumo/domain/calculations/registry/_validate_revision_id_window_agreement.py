"""A revision's id may not claim a window its own declarations close.

A revision declares when it applies twice, on two independent axes that nothing
previously required to agree: the date window (``valid_from``/``valid_to``) and
the period selector (``year_from``/``year_to``/``years``). The revision id is a
third statement of the same fact, and in this tree it is the one a reader meets
first.

The axes were found disagreeing in both directions. Modelo 714's
``2021-y-siguientes`` -- "and following" -- carries ``valid_to = 2025-12-31`` and
``year_to = 2025``, closed on both axes while named open. Four other modelos run
the inverse: an open ``valid_to`` with a single-year ``years`` selector doing the
real exclusion. An audit reading either field alone clears revisions that are not
covered, which is the defect class this registry keeps meeting -- a name or a
field read as authority when the authority is declared somewhere else.

This module refuses the first direction, which is the one a name can lie about.
An id asserting open-endedness must be backed by an open window on BOTH axes; if
either closes, the revision contradicts itself and the registry refuses.

What this is NOT
----------------

It is not a naming-convention linter. The subject is the DISAGREEMENT between two
declarations, never the name in isolation: a revision whose id makes no
open-ended claim is not required to be open, is not required to be closed, and is
not examined here at all. A revision named ``2025`` states nothing about
following years, so it cannot contradict anything -- and it is the coverage gate,
not this one, that decides whether the years it omits are a problem.

Equally, an uninformative name is not a pass. The gate simply has no contradiction
to find, and says nothing about the revision either way.

See Also:
    :class:`cadrumo.domain.calculations.registry.ModeloRevision`
        Declares the id, the date window and the period selector this reconciles.
"""

from __future__ import annotations

import re

from .schema import ModeloRevision

#: Matches a revision id whose trailing token claims the window continues.
#:
#: ``y siguientes`` is AEAT's own phrasing for "and following", and it is the only
#: open-endedness claim this tree's revision ids make -- established by sweeping
#: every revision id rather than assumed, and re-checked by the vocabulary anchor
#: in this module's test, which fails if an id appears carrying a tail this
#: pattern does not recognise. A marker that quietly stopped matching would turn
#: the gate green by finding nothing, which is the failure mode it exists to stop.
#:
#: Deliberately anchored at the END. Modelo 303's ``2024-desde-09-y-3t`` and
#: ``2024-hasta-08-y-2t`` contain ``y`` as a separator inside a mid-year split and
#: assert no open window; a looser pattern would refuse them for a claim they
#: never make.
OPEN_ENDED_REVISION_ID_MARKER = re.compile(r"(?:^|[-_])y[-_]siguientes$")


def revision_id_claims_open_window(revision_id: str) -> bool:
    """Report whether a revision id asserts that its window continues indefinitely."""
    return OPEN_ENDED_REVISION_ID_MARKER.search(revision_id) is not None


def revision_window_closures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every declaration that closes this revision's window, in reading order.

    Both axes are reported rather than the first found, because a revision can be
    closed on one, the other, or both, and a refusal naming only one would send a
    reader to fix half of it.
    """
    selector = revision.period_selector
    closures: list[str] = []
    if revision.valid_to is not None:
        closures.append(f"valid_to = {revision.valid_to.isoformat()}")
    if selector.year_to is not None:
        closures.append(f"period_selector.year_to = {selector.year_to}")
    if selector.years and selector.year_from is None:
        closures.append(f"period_selector.years = {list(selector.years)!r}")
    return tuple(closures)


def validate_revision_id_window_agreement(
    *,
    prefix: str,
    revision: ModeloRevision,
) -> list[str]:
    """Return a failure when a revision's id claims a window its data closes.

    Args:
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        revision: The :class:`ModeloRevision` under validation.
    """
    if not revision_id_claims_open_window(str(revision.id)):
        return []
    closures = revision_window_closures(revision)
    if not closures:
        return []
    return [
        f"{prefix}: the revision id claims an open-ended window ('y siguientes') but its own "
        f"declarations close it ({'; '.join(closures)}). One of the two is wrong and a reader "
        "meets the name first, so the disagreement is not cosmetic. Establish which is wrong "
        "from law and design evidence: if the span genuinely ended, rename the revision to the "
        "years it covers. Do NOT widen the window to silence this refusal -- reopening asserts "
        "coverage over years nobody holds evidence for, which is a larger defect than the "
        "misleading name.",
    ]


__all__ = [
    "OPEN_ENDED_REVISION_ID_MARKER",
    "revision_id_claims_open_window",
    "revision_window_closures",
    "validate_revision_id_window_agreement",
]
