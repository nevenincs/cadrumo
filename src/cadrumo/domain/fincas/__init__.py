"""Public facade for the LIRPF fincas register.

Per-:class:`Finca` and per-:class:`Arrendamiento` register backing factual LIRPF
rental aggregates (arts. 22-24 and 85), the LIRPF art. 23.2 four-tier
auto-resolver introduced by Ley 12/2023, and the LIRPF art. 23.1.f
:class:`FincaAmortizacionLedgerEntry` multi-year ledger with a per-finca
cost-basis cap. The ``fincas`` stem is intentional: this package models the
registral / cadastral unit, while filing targets remain registry-owned.

The main public calculations are :func:`compute_finca_aggregates`,
:func:`compute_amortization_for_year`, :func:`compute_gastos_for_year`, and
:func:`resolve_reduccion`. They return typed audit records such as
:class:`FincaAggregates`, :class:`FincaAttribution`,
:class:`ContractTierAttribution`, :class:`AmortizationComputation`,
:class:`GastosForYear`, and :class:`TierResolution`; no function here encodes a
Modelo 100 casilla id or filing-line authority.

Callers outside :mod:`domain.fincas` import only from this module.
Internal modules (``_models``, ``_enums``, ``_errors``,
``_repository_ports``, ``_tier_resolver``, ``_amortization_ledger``,
``_expense_rollup``, and ``_aggregates``) are implementation details.

The concrete ORM-backed repositories that satisfy the reader ports
declared here live in the persistence adapter
(:mod:`adapters.persistence.profile.fincas`), not in this domain
package — keeping the SQLAlchemy / mapper-row coupling out of the
domain layer.

Art. 85 imputation rates and the catastral-revision window enter through the
registry legal-parameter catalogue before the aggregate functions run. The
aggregate records are factual source material for registry-backed Modelo 100
bindings; :class:`domain.calculations.registry.RegistrySnapshot` and
:class:`domain.calculations.registry.CasillaObservation` remain the filing
line and provenance authorities.

See Also:
    :mod:`adapters.persistence.profile.fincas`
        Concrete SQLAlchemy repositories implementing the reader ports exported
        by this domain facade.
    :mod:`domain.calculations.registry`
        Registry authority that turns finca-derived factual inputs into typed
        modelo casilla observations.
    :mod:`domain.manuals`
        Bundled manual corpus that grounds the same LIRPF rental concepts
        without storing operator finca records.
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
from ._expense_rollup import (
    CAPPED_CATEGORIES,
    CARRY_FORWARD_MAX_YEARS,
    CarryForwardEntry,
    GastosForYear,
    compute_gastos_for_year,
)
from ._imputacion_parameters import LirpfArt85ImputacionParameters, load_imputacion_parameters
from ._models import (
    Arrendamiento,
    Finca,
    FincaAmortizacionLedgerEntry,
    FincaGasto,
    FincaRendimientoRecord,
)
from ._repository_ports import (
    ArrendamientoReader,
    FincaAmortizacionLedgerReader,
    FincaGastoReader,
    FincaReader,
    FincaRendimientoReader,
)
from ._source_readiness import FINCAS_SOURCE_KIND, FincasSourceReadiness, fincas_source_readiness
from ._tier_resolver import (
    DEFAULT_EJERCICIO_AMENDMENT_YEAR,
    LEY_12_2023_IN_FORCE_DATE,
    TierResolution,
    resolve_reduccion,
)
from .errors import (
    AmortizationLedgerCapExceededError,
    ContractNotFoundError,
    FincaAggregationError,
    FincaNotFoundError,
    FincaRegisterError,
    TierResolutionError,
)

__all__ = [
    "ART_23_1_F_RATE",
    "CAPPED_CATEGORIES",
    "CARRY_FORWARD_MAX_YEARS",
    "DEFAULT_EJERCICIO_AMENDMENT_YEAR",
    "FINCAS_SOURCE_KIND",
    "LEY_12_2023_IN_FORCE_DATE",
    "AmortizationComputation",
    "AmortizationLedgerCapExceededError",
    "Arrendamiento",
    "ArrendamientoReader",
    "CarryForwardEntry",
    "ContractNotFoundError",
    "ContractTierAttribution",
    "ExpenseCategory",
    "Finca",
    "FincaAggregates",
    "FincaAggregationError",
    "FincaAmortizacionLedgerEntry",
    "FincaAmortizacionLedgerReader",
    "FincaAttribution",
    "FincaGasto",
    "FincaGastoReader",
    "FincaNotFoundError",
    "FincaReader",
    "FincaRegisterError",
    "FincaRendimientoReader",
    "FincaRendimientoRecord",
    "FincasSourceReadiness",
    "GastosForYear",
    "LirpfArt85ImputacionParameters",
    "ReduccionTier",
    "TierResolution",
    "TierResolutionError",
    "UseType",
    "computation_to_ledger_entry",
    "compute_amortization_for_year",
    "compute_finca_aggregates",
    "compute_gastos_for_year",
    "fincas_source_readiness",
    "load_imputacion_parameters",
    "resolve_reduccion",
]
