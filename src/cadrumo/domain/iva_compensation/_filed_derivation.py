"""Canonical Modelo 303 filed-casilla carry-forward derivation policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ...core import CasillaId, validated_casilla_id
from ._carry_forward import derive_303_compensation_available


def _casilla_id(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="Modelo 303 compensation derivation casilla constant")


M303_COMPENSATION_AVAILABLE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")
M303_COMPENSATION_POSTERIOR_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
M303_COMPENSATION_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
M303_COMPENSATION_GENERADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")


@dataclass(frozen=True, slots=True)
class M303CompensationAvailableDerivation:
    """One policy-authoritative available-compensation result from filed casillas."""

    available: Decimal
    basis: Literal["generated", "resultado"]
    operand_refs: tuple[CasillaId, ...]
    operand_values: tuple[Decimal, ...]


def derive_m303_compensation_available_from_casillas(
    casilla_values: Mapping[CasillaId, Decimal],
) -> M303CompensationAvailableDerivation | None:
    """Derive Modelo 303 available compensation from canonical filed casillas.

    A directly filed generated-credit casilla takes precedence. When it is
    unavailable, the statutory result casilla is converted through the pure
    carry-forward policy. Absence of both inputs leaves the observation unchanged.
    """
    posterior = casilla_values.get(M303_COMPENSATION_POSTERIOR_CASILLA)
    if posterior is None:
        return None
    generated = casilla_values.get(M303_COMPENSATION_GENERADA_CASILLA)
    if generated is not None:
        return M303CompensationAvailableDerivation(
            available=posterior + generated,
            basis="generated",
            operand_refs=(M303_COMPENSATION_POSTERIOR_CASILLA, M303_COMPENSATION_GENERADA_CASILLA),
            operand_values=(posterior, generated),
        )
    resultado = casilla_values.get(M303_COMPENSATION_RESULTADO_CASILLA)
    if resultado is None:
        return None
    return M303CompensationAvailableDerivation(
        available=derive_303_compensation_available(posterior=posterior, resultado=resultado),
        basis="resultado",
        operand_refs=(),
        operand_values=(),
    )


__all__ = [
    "M303_COMPENSATION_AVAILABLE_CASILLA",
    "M303_COMPENSATION_GENERADA_CASILLA",
    "M303_COMPENSATION_POSTERIOR_CASILLA",
    "M303_COMPENSATION_RESULTADO_CASILLA",
    "M303CompensationAvailableDerivation",
    "derive_m303_compensation_available_from_casillas",
]
