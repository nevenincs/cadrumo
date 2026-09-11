"""Deferred filed-compensation derivation boundary.

The versioned registry owns the M303/M390 casilla, relation, partition, and
formula declarations. This module retains the typed history/evidence result
shape while the registry-backed resolver is wired into its consumers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.constants import ZERO
from .carry_forward import derive_303_compensation_available

# These identifiers are registry vocabulary used by the filed-compensation
# derivation and its consumers.  They live with the domain policy that reads
# the filed chain; application consumers must not maintain a second copy.
M303_COMPENSATION_AVAILABLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="M303_COMPENSATION_AVAILABLE_CASILLA",
)
M303_COMPENSATION_POSTERIOR_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-posteriores",
    surface="M303_COMPENSATION_POSTERIOR_CASILLA",
)
M303_COMPENSATION_RESULTADO_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado",
    surface="M303_COMPENSATION_RESULTADO_CASILLA",
)
M303_COMPENSATION_GENERADA_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-generada-periodo",
    surface="M303_COMPENSATION_GENERADA_CASILLA",
)
M303_COMPENSATION_APLICADA_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-aplicada-periodo",
    surface="M303_COMPENSATION_APLICADA_CASILLA",
)
M303_COMPENSATION_PENDING_PRIOR_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="M303_COMPENSATION_PENDING_PRIOR_CASILLA",
)
M303_COMPENSATION_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id(
    "71",
    surface="M303_COMPENSATION_RESULTADO_FINAL_CASILLA",
)
M390_COMPENSATION_GENERATED_OUTSIDE_LAST_PERIOD_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
    surface="M390_COMPENSATION_GENERATED_OUTSIDE_LAST_PERIOD_CASILLA",
)
M390_COMPENSATION_LAST_PERIOD_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
    surface="M390_COMPENSATION_LAST_PERIOD_CASILLA",
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
    refunded: bool,
) -> M303CompensationAvailableDerivation | None:
    """Derive Modelo 303 available compensation from canonical filed casillas.

    A directly filed generated-credit casilla takes precedence. When it is
    unavailable, the statutory result casilla is converted through the pure
    carry-forward policy. Absence of both inputs leaves the observation
    unchanged.
    """
    posterior = casilla_values.get(M303_COMPENSATION_POSTERIOR_CASILLA)
    if posterior is None:
        return None
    generated = casilla_values.get(M303_COMPENSATION_GENERADA_CASILLA)
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
            operand_refs=(M303_COMPENSATION_POSTERIOR_CASILLA, M303_COMPENSATION_GENERADA_CASILLA),
            operand_values=(posterior, generated),
        )
    resultado = casilla_values.get(M303_COMPENSATION_RESULTADO_CASILLA)
    if resultado is None:
        return None
    available = derive_303_compensation_available(
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
    "M303_COMPENSATION_APLICADA_CASILLA",
    "M303_COMPENSATION_AVAILABLE_CASILLA",
    "M303_COMPENSATION_GENERADA_CASILLA",
    "M303_COMPENSATION_POSTERIOR_CASILLA",
    "M303_COMPENSATION_RESULTADO_CASILLA",
    "M303CompensationAvailableDerivation",
    "M303CompensationBasis",
    "M303CompensationBasisValue",
    "derive_m303_compensation_available_from_casillas",
]
