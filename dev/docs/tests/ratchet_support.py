"""The shared per-page ratchet comparison for the docs-sequence debt gates.

Two gates pin a shrinking per-page debt against a committed baseline — the
payload-less ``@result`` frames in :mod:`test_sequence_contract` and the
``unconverted`` ``@static`` frames in :mod:`test_static_frame_reasons`. Both
compare the same way and differ only in the prose they render, so the
comparison lives here once and each gate formats its own message from the
returned divergences.

The comparison is deliberately two-directional. Both gates previously accepted
a page sitting *below* its entry as mid-sweep progress; that licence outlived
its sweep in both cases (73 of 81 and 27 of 60 allowances unclaimed), and an
unclaimed allowance silently pre-authorises exactly that many new violations.
Requiring equality makes the ratchet shrink-only by structure rather than by
convention: clearing a violation reds the gate until its entry comes down in
the same change.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["RatchetDivergence", "ratchet_divergences"]

type RatchetDivergence = tuple[str, int, int]
"""One disagreeing page as ``(page, observed_count, baselined_count)``."""


def ratchet_divergences(
    current: Mapping[str, int],
    baseline: Mapping[str, int],
) -> tuple[RatchetDivergence, ...]:
    """Return every page whose observed count differs from its baselined count.

    Both mappings are read with an absent key meaning zero, so a page dropped
    from the baseline once fully paid down compares equal to a page that
    produces no violations, and a page that regresses from an absent key is
    still reported.

    Args:
        current: Observed per-page violation counts.
        baseline: Committed per-page allowances.

    Returns:
        ``(page, observed, baselined)`` for each disagreeing page, ordered by
        page. Empty when the baseline tracks the tree exactly.
    """
    divergences: list[RatchetDivergence] = []
    for page in sorted(set(current) | set(baseline)):
        observed = current.get(page, 0)
        baselined = baseline.get(page, 0)
        if observed != baselined:
            divergences.append((page, observed, baselined))
    return tuple(divergences)
