"""The supported terminal sizes every TUI suite proves its surfaces at.

One declaration, because three once disagreed. `test_visual_verification`,
`components/tests/test_widgets` and `modelo/view/tests/test_work_review`
each carried a private triple sharing only the 80x24 floor, so a layout
regression at 120x40 was caught by one suite and invisible to the other
two, and one at 160x48 was caught by two and missed by the third. The
union was never the answer: it is five sizes nobody chose, and it
multiplies every parametrised TUI test's runtime for no stated reason.

Each entry carries the reason it is here. A size without a recorded
rationale cannot be defended when someone later asks whether it is worth
its runtime, which is how the three sets drifted apart in the first
place.
"""

from __future__ import annotations

from typing import Final

TERMINAL_FLOOR: Final = (80, 24)
"""The smallest a real terminal can be.

The size at which an overflowing layout stops being cosmetic and starts
hiding controls, so it is the one every suite already agreed on.
"""

TERMINAL_ABOVE_WRAP_TRANSITION: Final = (100, 30)
"""Immediately above the width at which summary content begins to wrap.

Measured 2026-08-30: the modelo review summary is unwrapped at 98 columns
and wraps at 97, so 100 sits one column into the safe side -- which is
where a wrapping regression surfaces FIRST. Nothing sampled this band
deliberately before: of the seven distinct widths the three private sets
declared, none fell above the transition and below 120.

INVALIDATION CONDITION, stated structurally rather than as a version:
100 is correct while it samples immediately above the wrap transition.
Shortening summary content moves the transition DOWN and 100 stays valid;
only content GROWING past it invalidates this size. Re-derive if summary
content grows.
"""

TERMINAL_ORDINARY: Final = (120, 40)
"""An ordinary working terminal, comfortably clear of the transition."""

TERMINAL_WIDE: Final = (200, 50)
"""A wide terminal, where nothing should wrap and layout has room to spare."""

SUPPORTED_TERMINAL_SIZES: Final = (
    TERMINAL_FLOOR,
    TERMINAL_ABOVE_WRAP_TRANSITION,
    TERMINAL_ORDINARY,
    TERMINAL_WIDE,
)
"""Every size a TUI surface is proven at, smallest first.

Four rather than three: the transition band is where the wrapping defect
class is born, and adding one sample there is the cost accepted for
covering it. A suite that genuinely needs a size outside this set
declares that size beside this import WITH its reason, so the exception
reads as an exception rather than as a fourth private triple.
"""

SUPPORTED_TERMINAL_SIZE_IDS: Final = ("floor", "above-wrap", "ordinary", "wide")
"""Stable parametrisation ids, so a failure names the size's ROLE."""
