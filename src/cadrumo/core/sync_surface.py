"""The closed set of surfaces a synchronisation run can cover.

A sync run reads or writes exactly one external surface, and "which surface"
decides what a run record means: the two members below differ in direction, in
counterparty and in what a divergence signifies, so a record that did not name
its surface would leave every count it carries ambiguous.

The set is deliberately two. A third member may only be added when a third
surface actually ships -- an enum that anticipates a surface produces run
records for something nothing writes, and a value that has never been written
cannot be distinguished later from one that was written and then retired.

English rather than a Spanish stem, per the domain naming rule: neither member
names an AEAT concept. ``FILED_DECLARATIONS`` is a sweep over the operator's own
filing history and ``CALC_SHEETS_EXPORT`` is a spreadsheet mirror with no AEAT
counterpart at all -- the AEAT nouns live inside what the sweep reads, not in
the act of sweeping.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "SyncSurface",
]


class SyncSurface(StrEnum):
    """Which external surface one synchronisation run covered.

    Attributes:
        FILED_DECLARATIONS: The AEAT filed-declaration sweep. Reads from AEAT
            and writes into the local store, so a divergence here means the
            local record disagreed with what AEAT holds, and the operator's own
            filing is the authority.
        CALC_SHEETS_EXPORT: The calculation-workbook export to Sheets. Writes
            outward from the local store to a one-way mirror, so a divergence
            means the remote copy had drifted from local -- the reverse
            direction, and never a statement about what AEAT holds.
    """

    FILED_DECLARATIONS = "filed_declarations"
    CALC_SHEETS_EXPORT = "calc_sheets_export"
