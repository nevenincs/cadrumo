"""Public taxpayer-model types used by registry rule evaluators.

Re-exports :class:`TaxpayerProfile` and the associated enums from the
private implementation module so callers can import from this stable surface.
This is a canonical non-``__init__`` public re-export module, safe to
import as a leaf without triggering :mod:`cadrumo.domain.deadlines`'s
``._profiles`` -> :mod:`cadrumo.core.setup_answers` circular-import edge that a
top-level package import would risk. :func:`cadrumo.core.setup_answers._m`
resolves this module lazily for exactly that reason.
"""

from __future__ import annotations

from ._models import (
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    TaxpayerProfile,
)

__all__ = [
    "EntityType",
    "FiscalResidency",
    "IVARegime",
    "IrpfEstimationRegime",
    "IrpfIncomeCategory",
    "IrpfSpecialRegime",
    "LegalEntityForm",
    "TaxpayerProfile",
]
