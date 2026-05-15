"""Application-layer calculation utilities — observation repository and
the multi-year resolver that lets relation / binding pre-resolution
consult prior years' filings.

The runtime calc engine (`aeat.domain.calculations.registry._formula_runtime`)
takes pre-resolved `relation_values` and `binding_values` mappings.
This package provides the application-side helpers that produce
those mappings from the operator's local filing history, so annual
modelos (e.g. modelo 200, IS) and multi-year regimes (e.g. IVA
prorrata four-year average, IVA regularización inversiones five-year
straight-line, IS BIN unlimited carryforward) can resolve their
inputs from authoritative prior filings instead of operator
hand-entry.
"""

from ._binding_prefill import (
    BindingPrefillReport,
    PrefilledBinding,
    resolve_bindings_from_local_store,
)
from ._multi_year import MultiYearResolver, resolve_prior_year_observations
from ._observations_repository import (
    CalculationObservationRepository,
    observation_key,
)
from ._relation_prefill import resolve_relations_from_local_store
from ._row_set_assembly import (
    assemble_atribucion_observations,
    assemble_foreign_asset_observations,
    assemble_refund_observations,
    assemble_related_party_observations,
    assemble_withholding_observations,
)

__all__ = [
    "BindingPrefillReport",
    "CalculationObservationRepository",
    "MultiYearResolver",
    "PrefilledBinding",
    "assemble_atribucion_observations",
    "assemble_foreign_asset_observations",
    "assemble_refund_observations",
    "assemble_related_party_observations",
    "assemble_withholding_observations",
    "observation_key",
    "resolve_bindings_from_local_store",
    "resolve_prior_year_observations",
    "resolve_relations_from_local_store",
]
