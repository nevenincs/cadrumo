"""A rate expressed on the zero-to-one-hundred scale.

AEAT states rates as percentages: a prorrata of 87, a retencion of 19, an IVA
rate of 21. The bound was written out at thirteen sites across the prorrata,
bienes de inversion, withholding, orden-projection and asset models, all
spelling the same two numbers.

This is a DIFFERENT quantity from :obj:`~cadrumo.core.unit_proportion.UnitProportion`,
not a loose spelling of it, and the two must never be collapsed: 21 means
twenty-one per cent here and would be a nonsense share there, while 0.21 is a
valid share and rounds to nothing as a percentage. A value crossing between the
two scales is converted deliberately at the boundary that converts it, and the
separate aliases are what make that boundary visible.

The interval is inclusive at both ends: a rate of nought and a rate of a
hundred per cent are both real, and an exempt or fully-deductible case relies
on it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final

from pydantic import Field

#: A rate of nothing.
PERCENTAGE_MIN: Final[Decimal] = Decimal("0")

#: A rate of the whole, stated as a hundred rather than as one.
PERCENTAGE_MAX: Final[Decimal] = Decimal("100")

Percentage = Annotated[Decimal, Field(ge=PERCENTAGE_MIN, le=PERCENTAGE_MAX)]
"""A rate stated on the AEAT scale, where a hundred is the whole."""

__all__ = ["PERCENTAGE_MAX", "PERCENTAGE_MIN", "Percentage"]
