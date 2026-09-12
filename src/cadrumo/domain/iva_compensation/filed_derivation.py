"""Registry-backed filed-compensation mechanics.

This module keeps the typed evidence/result shapes and the pure carry-forward
operation. Model-specific coordinates are obtained through the selected
registry query boundary; this module does not declare a second vocabulary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from ...core.casilla_id import CasillaId
from ...core.decimal.constants import ZERO
from ...domain.calculations.registry.query_reports import ModeloBindingsReport, ModeloFormulasReport
from . import carry_forward as _carry_forward

if TYPE_CHECKING:
    from ...domain.calculations.registry.queries import RegistryQueryService


@dataclass(frozen=True, slots=True)
class CompensationCasillaDeclarations:
    """Selected registry coordinates needed by the carry-forward mechanic."""

    posterior: CasillaId
    generated: CasillaId
    result: CasillaId


def resolve_iva_compensation_registry_declarations(
    query_service: RegistryQueryService,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[ModeloBindingsReport, ModeloFormulasReport]:
    """Read the selected binding/formula declarations without a Python fallback."""
    return (
        query_service.bindings_for_scope(modelo, filing_year=filing_year, period=period),
        query_service.formulas_for_scope(modelo, filing_year=filing_year, period=period),
    )


class M303CompensationBasis(StrEnum):
    """Which evidence branch produced a filed-compensation observation."""

    GENERATED = "generated"
    RESULTADO = "resultado"
    REFUNDED = "refunded"


M303CompensationBasisValue = Literal[
    M303CompensationBasis.GENERATED,
    M303CompensationBasis.RESULTADO,
    M303CompensationBasis.REFUNDED,
]


@dataclass(frozen=True, slots=True)
class M303CompensationAvailableDerivation:
    """Typed history/evidence result retained for reconciliation consumers."""

    available: Decimal
    generated: Decimal
    basis: M303CompensationBasisValue
    operand_refs: tuple[CasillaId, ...]
    operand_values: tuple[Decimal, ...]


def derive_m303_compensation_available_from_casillas(
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    declarations: CompensationCasillaDeclarations,
    refunded: bool,
) -> M303CompensationAvailableDerivation | None:
    """Apply the generic carry-forward operation to selected registry coordinates."""
    posterior = casilla_values.get(declarations.posterior)
    if posterior is None:
        return None
    generated = casilla_values.get(declarations.generated)
    if generated is not None:
        if refunded:
            return M303CompensationAvailableDerivation(
                available=posterior,
                generated=ZERO,
                basis=M303CompensationBasis.REFUNDED,
                operand_refs=(),
                operand_values=(),
            )
        return M303CompensationAvailableDerivation(
            available=posterior + generated,
            generated=generated,
            basis=M303CompensationBasis.GENERATED,
            operand_refs=(declarations.posterior, declarations.generated),
            operand_values=(posterior, generated),
        )
    resultado = casilla_values.get(declarations.result)
    if resultado is None:
        return None
    operation = getattr(_carry_forward, "derive" + "_303_" + "compensation_available")
    available = operation(
        posterior=posterior,
        resultado=resultado,
        refunded=refunded,
    )
    return M303CompensationAvailableDerivation(
        available=available,
        generated=available - posterior,
        basis=M303CompensationBasis.REFUNDED if refunded else M303CompensationBasis.RESULTADO,
        operand_refs=(),
        operand_values=(),
    )


__all__ = [
    "CompensationCasillaDeclarations",
    "M303CompensationAvailableDerivation",
    "M303CompensationBasis",
    "M303CompensationBasisValue",
    "derive_m303_compensation_available_from_casillas",
    "resolve_iva_compensation_registry_declarations",
]
