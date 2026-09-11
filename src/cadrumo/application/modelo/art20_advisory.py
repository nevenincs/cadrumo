"""Generic verification mechanics for registry-selected Art.20 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ...domain.modelos.verification_report import ModeloVerificationFinding

__all__ = ["art20_reduccion_advisory_finding"]


# TODO(fact-relocation): resolve Art.20 RNT/reduction ceiling predicate, applicability, and advisory message from selected registry revision
def _registry_art20_declaration(
    revision: object,
    *,
    context: ModeloFactResolutionContext,
) -> object:
    """Leave revision-specific Art.20 declarations at the registry boundary."""
    del revision, context
    raise NotImplementedError("registry-selected Art.20 verification declarations are unresolved")


def art20_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    context: ModeloFactResolutionContext,
) -> ModeloVerificationFinding | None:
    """Delegate Art.20 reduction verification declarations to the registry."""
    del casilla_values
    _registry_art20_declaration(revision, context=context)
    return None
