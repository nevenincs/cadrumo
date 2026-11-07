"""The period whose law the transitional food rates of RD-ley 4/2024 change.

The statute prints the date its second clause takes effect; the quarter that
date opens and the quarter before it are read from that printed date, so a test
that needs a prompt compiled under the older and the newer tiers asks this
module rather than naming a year.
"""

from __future__ import annotations

from typing import Final

from .....core.period import Period
from .....domain.calculations.registry.tests.legal_text import legal_text_match, spanish_date

_STEP = spanish_date(
    *legal_text_match(
        "real-decreto-ley-4-2024:art-1", r"dos\. con efectos desde el (\d{1,2}) de (\w+) de (\d{4})"
    ).groups()
)
_STEP_QUARTER = (_STEP.month - 1) // 3 + 1

TRANSITIONAL_RATE_QUARTER: Final = Period.from_year_and_code(_STEP.year, f"{_STEP_QUARTER}T")
"""The quarter the statute's stepped tiers first apply in."""

QUARTER_BEFORE_TRANSITIONAL_RATE: Final = Period.from_year_and_code(_STEP.year, f"{_STEP_QUARTER - 1}T")
"""The quarter immediately before the stepped tiers apply, in the same year."""

TRANSITIONAL_RATE_ANNUAL: Final = Period.from_year_and_code(_STEP.year, "0A")
"""The annual span of the year the stepped tiers are introduced in."""
