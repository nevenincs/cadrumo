"""Rental register subpackage.

Per-finca and per-contract register backing LIRPF rental aggregates
(arts. 22-24 and 85), the LIRPF art. 23.2 four-tier auto-resolver
introduced by Ley 12/2023, and the LIRPF art. 23.1.f amortización
multi-year ledger with a per-finca cost-basis cap.

Callers outside :mod:`aeat.domain.fincas` import only from this module.
Internal modules (``_models``, ``_enums``, ``_errors``,
``_repository``, ``_tier_resolver``, ``_amortization_ledger``,
``_expense_rollup``, and ``_aggregates``) are implementation details.
"""

from __future__ import annotations

from ._aggregates import (
    ContractTierAttribution,
    FincaAggregates,
    FincaAttribution,
    compute_finca_aggregates,
)
from ._amortization_ledger import (
    ART_23_1_F_RATE,
    AmortizationComputation,
    computation_to_ledger_entry,
    compute_amortization_for_year,
)
from ._enums import ExpenseCategory, ReduccionTier, UseType
from ._errors import (
    AmortizationLedgerCapExceededError,
    ContractNotFoundError,
    FincaAggregationError,
    FincaNotFoundError,
    FincaRegisterError,
    TierResolutionError,
)
from ._expense_rollup import (
    CAPPED_CATEGORIES,
    CARRY_FORWARD_MAX_YEARS,
    CarryForwardEntry,
    GastosForYear,
    compute_gastos_for_year,
)
from ._models import (
    Arrendamiento,
    Finca,
    FincaAmortizacionLedgerEntry,
    FincaGasto,
    FincaRendimientoRecord,
)
from ._repository import (
    ArrendamientoRepository,
    FincaAmortizacionLedgerRepository,
    FincaGastoRepository,
    FincaRendimientoRepository,
    FincaRepository,
)
from ._tier_resolver import (
    DEFAULT_EJERCICIO_AMENDMENT_YEAR,
    LEY_12_2023_IN_FORCE_DATE,
    TierResolution,
    resolve_reduccion,
)

__all__ = [
    "ART_23_1_F_RATE",
    "CAPPED_CATEGORIES",
    "CARRY_FORWARD_MAX_YEARS",
    "DEFAULT_EJERCICIO_AMENDMENT_YEAR",
    "LEY_12_2023_IN_FORCE_DATE",
    "AmortizationComputation",
    "AmortizationLedgerCapExceededError",
    "Arrendamiento",
    "ArrendamientoRepository",
    "CarryForwardEntry",
    "ContractNotFoundError",
    "ContractTierAttribution",
    "ExpenseCategory",
    "Finca",
    "FincaAggregates",
    "FincaAggregationError",
    "FincaAmortizacionLedgerEntry",
    "FincaAmortizacionLedgerRepository",
    "FincaAttribution",
    "FincaGasto",
    "FincaGastoRepository",
    "FincaNotFoundError",
    "FincaRegisterError",
    "FincaRendimientoRecord",
    "FincaRendimientoRepository",
    "FincaRepository",
    "GastosForYear",
    "ReduccionTier",
    "TierResolution",
    "TierResolutionError",
    "UseType",
    "computation_to_ledger_entry",
    "compute_amortization_for_year",
    "compute_finca_aggregates",
    "compute_gastos_for_year",
    "resolve_reduccion",
]
