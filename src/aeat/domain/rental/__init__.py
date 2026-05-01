"""Rental register subpackage (#454).

Per-finca + per-contract register backing the M100 Anexo C aggregates
(LIRPF arts. 22-24 + 85), the LIRPF art. 23.2 four-tier auto-resolver
introduced by Ley 12/2023, and the LIRPF art. 23.1.f amortización 3 %
multi-year ledger with a per-finca cost-basis cap.

Public API: callers outside :mod:`aeat.domain.rental` import only from this
module. Internal modules (``_models``, ``_enums``, ``_errors``,
``_repository``, ``_tier_resolver``, ``_amortization_ledger``,
``_expense_rollup``, ``_anexo_c_aggregator``, ``anexo_c_provider``)
are implementation details.

See ``.vault/adr/2026-04-29-rental-income-hardening-adr.md`` for the
design record and ``.vault/plan/2026-04-29-rental-income-hardening-plan.md``
for the rollout plan.
"""

from __future__ import annotations

from ._amortization_ledger import (
    ART_23_1_F_RATE,
    AmortizationComputation,
    computation_to_ledger_entry,
    compute_amortization_for_year,
)
from ._anexo_c_aggregator import (
    AnexoCAggregates,
    ContractTierAttribution,
    FincaAttribution,
    compute_anexo_c_aggregates,
)
from ._enums import ExpenseCategory, ReduccionTier, UseType
from ._errors import (
    AmortizationLedgerCapExceededError,
    AnexoCAggregationError,
    ContractNotFoundError,
    FincaNotFoundError,
    RentalRegisterError,
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
    RentalAmortizationLedgerEntry,
    RentalContract,
    RentalExpense,
    RentalFinca,
    RentalIncomeRecord,
)
from ._repository import (
    RentalAmortizationLedgerRepository,
    RentalContractRepository,
    RentalExpenseRepository,
    RentalFincaRepository,
    RentalIncomeRepository,
)
from ._tier_resolver import (
    DEFAULT_EJERCICIO_AMENDMENT_YEAR,
    LEY_12_2023_IN_FORCE_DATE,
    TierResolution,
    resolve_reduccion,
)
from .anexo_c_provider import (
    ANEXO_C_CASILLAS,
    AnexoCMergeReport,
    compute_or_passthrough,
)

__all__ = [
    "ANEXO_C_CASILLAS",
    "ART_23_1_F_RATE",
    "CAPPED_CATEGORIES",
    "CARRY_FORWARD_MAX_YEARS",
    "DEFAULT_EJERCICIO_AMENDMENT_YEAR",
    "LEY_12_2023_IN_FORCE_DATE",
    "AmortizationComputation",
    "AmortizationLedgerCapExceededError",
    "AnexoCAggregates",
    "AnexoCAggregationError",
    "AnexoCMergeReport",
    "CarryForwardEntry",
    "ContractNotFoundError",
    "ContractTierAttribution",
    "ExpenseCategory",
    "FincaAttribution",
    "FincaNotFoundError",
    "GastosForYear",
    "ReduccionTier",
    "RentalAmortizationLedgerEntry",
    "RentalAmortizationLedgerRepository",
    "RentalContract",
    "RentalContractRepository",
    "RentalExpense",
    "RentalExpenseRepository",
    "RentalFinca",
    "RentalFincaRepository",
    "RentalIncomeRecord",
    "RentalIncomeRepository",
    "RentalRegisterError",
    "TierResolution",
    "TierResolutionError",
    "UseType",
    "computation_to_ledger_entry",
    "compute_amortization_for_year",
    "compute_anexo_c_aggregates",
    "compute_gastos_for_year",
    "compute_or_passthrough",
    "resolve_reduccion",
]
