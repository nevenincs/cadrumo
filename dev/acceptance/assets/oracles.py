"""Independent cents oracles for the activity-asset acceptance journeys.

These restate the governing facts directly and import nothing from the
product, so an installed journey can compare the product's charge against an
expectation the product could not have produced.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# LIS art. 12.1.a table, "Maquinaria": 12% maximum linear coefficient.
MACHINERY_LINEAR_MAXIMUM = Decimal("0.12")
# RIS art. 5.1.c: a useful life of eight years or more weights the linear coefficient by 2.5.
CONSTANT_PERCENTAGE_WEIGHTING_EIGHT_YEARS_OR_MORE = Decimal("2.5")


def first_year_constant_percentage_oracle(
    *,
    allocated_basis: Decimal,
    linear_coefficient: Decimal,
    weighting: Decimal,
) -> Decimal:
    """Charge for a full first year under RIS art. 5.1, rounded to cents."""
    return (allocated_basis * linear_coefficient * weighting).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def first_year_machinery_constant_percentage(allocated_basis: Decimal) -> Decimal:
    """Full first-year constant-percentage charge for new machinery (12% x 2.5 = 30%)."""
    return first_year_constant_percentage_oracle(
        allocated_basis=allocated_basis,
        linear_coefficient=MACHINERY_LINEAR_MAXIMUM,
        weighting=CONSTANT_PERCENTAGE_WEIGHTING_EIGHT_YEARS_OR_MORE,
    )


__all__ = [
    "CONSTANT_PERCENTAGE_WEIGHTING_EIGHT_YEARS_OR_MORE",
    "MACHINERY_LINEAR_MAXIMUM",
    "first_year_constant_percentage_oracle",
    "first_year_machinery_constant_percentage",
]
