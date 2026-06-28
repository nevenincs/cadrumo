"""Ley 44/2015 art. 14 SAL/SLL reserva especial dotacion.

Sociedades Laborales must endow a special reserve of 10% of net profit each year
until the accumulated reserve reaches at least more than twice (2x) the share
capital (Ley 44/2015 art. 14.1, BOE-A-2015-11071: "se dotará con el diez por
ciento del beneficio líquido de cada ejercicio, hasta que alcance al menos una
cifra superior al doble del capital social").
"""

from __future__ import annotations

from decimal import Decimal

from ...core.external_constants import SAL_RESERVA_CAPITAL_MULTIPLE, SAL_RESERVA_DOTACION_RATE
from ...core.money import round_to_cents
from ._errors import PensionReduccionError


def compute_sal_reserva_especial_dotacion(
    *,
    beneficio_neto: Decimal,
    reserva_dotada: Decimal,
    capital_social: Decimal,
) -> Decimal:
    """Compute the Ley 44/2015 art. 14 SAL/SLL reserva especial dotacion.

    Formula: ``dotacion = min(beneficio_neto * 10%, cap_headroom)`` where
    ``cap_headroom = max(0, capital_social * 2 - reserva_dotada)``. Once the
    accumulated reserva reaches twice (2x) the capital social the dotacion is
    zero (cap reached, per Ley 44/2015 art. 14.1 "una cifra superior al doble
    del capital social"). The result is rounded to 2 decimal places (money-2).

    Raises:
        PensionReduccionError: When ``capital_social`` is zero or negative, or
            when any input is negative.
    """
    if capital_social <= Decimal(0):
        raise PensionReduccionError(
            f"capital_social must be positive; got {capital_social}",
            context={"field": "capital_social", "value": str(capital_social)},
        )
    if beneficio_neto < Decimal(0):
        raise PensionReduccionError(
            f"beneficio_neto must be non-negative; got {beneficio_neto}",
            context={"field": "beneficio_neto", "value": str(beneficio_neto)},
        )
    if reserva_dotada < Decimal(0):
        raise PensionReduccionError(
            f"reserva_dotada must be non-negative; got {reserva_dotada}",
            context={"field": "reserva_dotada", "value": str(reserva_dotada)},
        )

    cap = round_to_cents(capital_social * SAL_RESERVA_CAPITAL_MULTIPLE)
    headroom = max(Decimal("0.00"), cap - reserva_dotada)
    dotacion_obligatoria = round_to_cents(beneficio_neto * SAL_RESERVA_DOTACION_RATE)
    dotacion = min(dotacion_obligatoria, headroom)
    return round_to_cents(dotacion)
