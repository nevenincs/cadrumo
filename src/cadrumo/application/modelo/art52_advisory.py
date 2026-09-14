"""Generic verification mechanics for registry-selected Art.52 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.verification_report import ModeloVerificationFinding

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["art52_reduccion_advisory_finding"]


# fact-relocation: selected Art.52 declarations are consumed through the pinned operation and dated mapping fact
def _registry_art52_declaration(
    revision: object,
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
    effective_date: date,
) -> ResolvedMappingFact:
    """Resolve selected model context and the dated Art.52 mapping fact."""
    del modelo
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-art-52-reduction-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected Art.52 declaration must resolve as a mapping fact")
    del revision
    return resolved


def art52_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
) -> ModeloVerificationFinding | None:
    """Delegate Art.52 reduction verification declarations to the registry."""
    del casilla_values
    effective_date = getattr(revision, "valid_to", None) or date.today()
    _registry_art52_declaration(
        revision,
        operation=operation,
        modelo=modelo,
        effective_date=effective_date,
    )
    raise NotImplementedError("registry-selected Art.52 verification consumer is not yet implemented")
