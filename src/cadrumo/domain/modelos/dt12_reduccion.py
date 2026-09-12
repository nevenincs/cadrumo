"""Deferred DT12 reduction boundary.

The versioned registry owns the DT12 formula specification, scalar operands,
eligibility windows, ordering, and rounding declarations. This module retains
typed input and result shells while the registry-backed evaluator is wired into
its consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.queries import RegistryQueryService
from ..calculations.registry.schema_base import DateAxis
from .errors import PensionReduccionError

if TYPE_CHECKING:
    from .modelo_fact_context import ModeloFactResolutionContext


# fact-relocation: selected Modelo 100 DT12 declarations are consumed through RegistryQueryService and the dated mapping fact
def _registry_dt12_formula_declaration(context: ModeloFactResolutionContext) -> ResolvedMappingFact:
    """Resolve the selected Modelo 100 surface and dated DT12 formula."""
    model_report = RegistryQueryService(context.authority).describe_modelo("100")
    resolved = context.authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-dt12-reduction-formula-spec",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=context.filing_period,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected DT12 declaration must resolve as a mapping fact")
    del model_report
    return resolved


def compute_dt12_reduccion_plan_pensiones(
    *,
    gross_rescate: Decimal,
    aportaciones_pre_2007: Decimal,
    aportaciones_totales: Decimal,
    context: ModeloFactResolutionContext,
) -> Decimal:
    """Evaluate the DT12 reduction from the canonical registry specification."""
    _registry_dt12_formula_declaration(context)
    del gross_rescate, aportaciones_pre_2007, aportaciones_totales, context
    raise NotImplementedError("registry-selected DT12 formula evaluation remains outside this boundary")


class Dt12WindowBranch(StrEnum):
    """Typed branch label retained for registry-produced eligibility results."""

    GENERAL = "general"
    TRANSITIONAL = "transitional"
    CLIFF = "cliff"


@dataclass(frozen=True, slots=True)
class Dt12WindowEligibility:
    """Typed eligibility result shell for registry-produced window decisions."""

    contingencia_year: int
    rescate_year: int
    branch: Dt12WindowBranch
    eligible: bool
    eligible_through_year: int


def dt12_regime_window_eligibility(
    *,
    contingencia_year: int,
    rescate_year: int,
    context: ModeloFactResolutionContext,
) -> Dt12WindowEligibility:
    """Evaluate the DT12 eligibility window from registry declarations."""
    _registry_dt12_formula_declaration(context)
    del contingencia_year, rescate_year, context
    raise NotImplementedError("registry-selected DT12 eligibility evaluation remains outside this boundary")


__all__ = [
    "Dt12WindowBranch",
    "Dt12WindowEligibility",
    "PensionReduccionError",
    "compute_dt12_reduccion_plan_pensiones",
    "dt12_regime_window_eligibility",
]
