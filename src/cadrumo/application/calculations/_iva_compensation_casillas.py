"""Canonical IVA-compensation casilla identifiers for the calculations layer.

The Modelo 303 compensation chain and the Modelo 390 annual carry are read by
two separate consumers -- the filed-history projection and the binding-prefill
resolver -- which each declared their own private copy of the same seven
Modelo 303 constants behind their own copy of the same validating wrapper.
Two hand-maintained copies of one registry vocabulary drift silently: a casilla
renamed on one side keeps resolving on the other, and the two surfaces then
disagree about which value the operator's compensation actually came from.

This module is the one declaration both import. Each constant is validated
through :func:`~core.validated_casilla_id` at import time, so a token that is
not a well-formed casilla id fails at module load rather than at the first
compensation calculation that touches it.
"""

from __future__ import annotations

from typing import Final

from ...core import CasillaId, validated_casilla_id

__all__ = [
    "M303_COMPENSACION_APLICADA_CASILLA",
    "M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA",
    "M303_DISPONIBLE_CASILLA",
    "M303_GENERADA_CASILLA",
    "M303_POSTERIOR_CASILLA",
    "M303_RESULTADO_CASILLA",
    "M303_RESULTADO_FINAL_CASILLA",
    "M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA",
    "M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA",
    "iva_compensation_casilla_id",
]


def iva_compensation_casilla_id(value: object) -> CasillaId:
    """Return ``value`` as a validated IVA-compensation casilla id.

    Args:
        value: The registry casilla token declared by this module.

    Returns:
        The validated :obj:`CasillaId`.

    Raises:
        RuntimeError: The token is not a well-formed casilla id. Raised at
            import time, so a malformed constant can never reach a
            compensation calculation.
    """
    try:
        return validated_casilla_id(value, surface="IVA compensation casilla constant")
    except ValueError as exc:
        raise RuntimeError(f"IVA compensation casilla constant {value!r} is not a CasillaId") from exc


M303_RESULTADO_CASILLA: Final[CasillaId] = iva_compensation_casilla_id("iva.resultado")
"""Modelo 303 periodic resultado, before the compensation chain is applied."""

M303_GENERADA_CASILLA: Final[CasillaId] = iva_compensation_casilla_id("iva.compensacion-generada-periodo")
"""Compensation the period itself generated."""

M303_POSTERIOR_CASILLA: Final[CasillaId] = iva_compensation_casilla_id(
    "iva.compensacion-pendiente-periodos-posteriores",
)
"""Compensation carried forward to later periods."""

M303_DISPONIBLE_CASILLA: Final[CasillaId] = iva_compensation_casilla_id("iva.compensacion-disponible-fin-periodo")
"""Compensation available at the close of the period."""

M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: Final[CasillaId] = iva_compensation_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)
"""Compensation carried in from earlier periods."""

M303_COMPENSACION_APLICADA_CASILLA: Final[CasillaId] = iva_compensation_casilla_id("iva.compensacion-aplicada-periodo")
"""Compensation actually applied in the period."""

M303_RESULTADO_FINAL_CASILLA: Final[CasillaId] = iva_compensation_casilla_id("71")
"""Modelo 303 resultado after the compensation chain (official casilla 71)."""

M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA: Final[CasillaId] = iva_compensation_casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
)
"""Modelo 390 annual compensation declared for the last period."""

M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: Final[CasillaId] = iva_compensation_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
)
"""Modelo 390 annual compensation generated outside the last period."""
