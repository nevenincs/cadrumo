"""Public surface for the Renta (IRPF / Modelo 100) substrate.

Re-exports the closed-membership classification enums that downstream
consumers (formula bindings, CCAA-conditional deductions, application-
layer extractors) use to tag a Renta domain value.
"""

from __future__ import annotations

from ._substrate import EstimacionDirectaModalidad, RentaCCAA, RentaIncomeType

__all__ = [
    "EstimacionDirectaModalidad",
    "RentaCCAA",
    "RentaIncomeType",
]
