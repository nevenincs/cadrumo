"""Public taxpayer-model types used by registry rule evaluators.

Re-exports :class:`TaxpayerProfile` and the associated enums from the
private implementation module so callers can import from this stable surface.
"""

from __future__ import annotations

from ._models import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    TaxpayerProfile,
)

__all__ = [
    "EntityType",
    "IrpfEstimationRegime",
    "IrpfIncomeCategory",
    "IrpfSpecialRegime",
    "TaxpayerProfile",
]
