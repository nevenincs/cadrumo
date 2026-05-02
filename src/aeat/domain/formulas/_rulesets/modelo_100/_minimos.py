"""Compute the LIRPF arts. 56-61 mínimo personal y familiar.

The mínimo personal y familiar ("personal and family allowance") is the
portion of base liquidable that, per LIRPF art. 56, "no se somete a
tributación" — it does not pay tax. Modelo 100 Anexo F casillas
``0505`` / ``0510`` / ``0515`` / ``0520`` carry the per-component
amounts; ``0500`` is their sum.

The amounts have been stable since 2015. The breakdown per LIRPF
arts. 57-60 is:

- ``art. 57`` mínimo del contribuyente: 5.550 € base; +1.150 € if > 65
  años; +1.400 € additional if > 75.
- ``art. 58`` mínimo por descendientes: 2.400 € (1º) / 2.700 € (2º) /
  4.000 € (3º) / 4.500 € (4º+); +2.800 € per descendiente < 3 años.
- ``art. 59`` mínimo por ascendientes: 1.150 € per ascendiente >= 65 or
  con discapacidad; +1.400 € per ascendiente > 75.
- ``art. 60`` mínimo por discapacidad: 3.000 € if grado < 65 %; 9.000 €
  if grado >= 65 %; +3.000 € additional if the contribuyente needs
  third-party assistance (ayuda asistencia, mobility limitation, or
  grado >= 65 %).

Requisitos comunes (LIRPF art. 61): convivencia + rentas anuales del
descendiente / ascendiente <= 8.000 € (excluidas exentas). The caller is
responsible for filtering out non-qualifying personas before populating
:class:`MinimosProfile`.

See Also:
    :func:`compute_minimo_personal_familiar`: Public entry point.
    :class:`MinimosProfile`: Validated input model.
    :class:`GradoDiscapacidad`: Disability-grade enum used by the profile.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MINIMO_CONTRIBUYENTE_BASE = Decimal("5550.00")
"""LIRPF art. 57 base mínimo del contribuyente (€)."""

MINIMO_CONTRIBUYENTE_EXTRA_OVER_65 = Decimal("1150.00")
"""LIRPF art. 57 increment when the contribuyente is over 65 (€)."""

MINIMO_CONTRIBUYENTE_EXTRA_OVER_75 = Decimal("1400.00")
"""LIRPF art. 57 increment when the contribuyente is over 75 (€)."""

MINIMO_DESCENDIENTE_1 = Decimal("2400.00")
"""LIRPF art. 58 mínimo for the first descendiente (€)."""

MINIMO_DESCENDIENTE_2 = Decimal("2700.00")
"""LIRPF art. 58 mínimo for the second descendiente (€)."""

MINIMO_DESCENDIENTE_3 = Decimal("4000.00")
"""LIRPF art. 58 mínimo for the third descendiente (€)."""

MINIMO_DESCENDIENTE_4_PLUS = Decimal("4500.00")
"""LIRPF art. 58 mínimo for the fourth and subsequent descendientes (€)."""

MINIMO_DESCENDIENTE_BONUS_UNDER_3 = Decimal("2800.00")
"""LIRPF art. 58 bonus per descendiente under 3 years old (€)."""

MINIMO_ASCENDIENTE_OVER_65 = Decimal("1150.00")
"""LIRPF art. 59 mínimo per ascendiente over 65 or with discapacidad (€)."""

MINIMO_ASCENDIENTE_EXTRA_OVER_75 = Decimal("1400.00")
"""LIRPF art. 59 increment per ascendiente over 75 (€)."""

MINIMO_DISCAPACIDAD_GRADO_BAJO = Decimal("3000.00")
"""LIRPF art. 60 mínimo for grado de discapacidad below 65 % (€)."""

MINIMO_DISCAPACIDAD_GRADO_ALTO = Decimal("9000.00")
"""LIRPF art. 60 mínimo for grado de discapacidad >= 65 % (€)."""

MINIMO_DISCAPACIDAD_BONUS_ASISTENCIA = Decimal("3000.00")
"""LIRPF art. 60 bonus when the contribuyente needs third-party assistance (€)."""


class GradoDiscapacidad(StrEnum):
    """Closed enum for the LIRPF art. 60 grado de discapacidad bands.

    Attributes:
        NONE: Contribuyente without recognised discapacidad.
        GRADO_BAJO: Discapacidad in the band ``33 % <= grado < 65 %``.
        GRADO_ALTO: Discapacidad in the band ``grado >= 65 %``.
    """

    NONE = "none"
    GRADO_BAJO = "grado_bajo"
    GRADO_ALTO = "grado_alto"


class MinimosProfile(BaseModel):
    """Validated inputs to :func:`compute_minimo_personal_familiar`.

    Captures the per-contribuyente / per-familia data needed to derive
    the LIRPF arts. 57-60 mínimos. All counts are non-negative; the
    Pydantic v2 ``strict`` + ``frozen`` + ``extra="forbid"`` discipline
    catches type errors at construction time.

    Attributes:
        contribuyente_over_65: ``True`` when the contribuyente is over 65
            (LIRPF art. 57).
        contribuyente_over_75: ``True`` when the contribuyente is over 75;
            implies :attr:`contribuyente_over_65`.
        n_descendientes: Count of qualifying descendientes (LIRPF art. 58).
        n_descendientes_under_3: Count of qualifying descendientes under
            3 years old; subset of :attr:`n_descendientes`.
        n_ascendientes_over_65: Count of qualifying ascendientes over 65
            or with discapacidad (LIRPF art. 59).
        n_ascendientes_over_75: Count of qualifying ascendientes over 75;
            subset of :attr:`n_ascendientes_over_65`.
        contribuyente_grado_discapacidad: Disability band of the
            contribuyente (:class:`GradoDiscapacidad`).
        contribuyente_needs_ayuda_asistencia: ``True`` when the
            contribuyente qualifies for the LIRPF art. 60 third-party
            assistance bonus.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    contribuyente_over_65: bool = False
    contribuyente_over_75: bool = False

    n_descendientes: int = Field(default=0, ge=0)
    n_descendientes_under_3: int = Field(default=0, ge=0)

    n_ascendientes_over_65: int = Field(default=0, ge=0)
    n_ascendientes_over_75: int = Field(default=0, ge=0)

    contribuyente_grado_discapacidad: GradoDiscapacidad = GradoDiscapacidad.NONE
    contribuyente_needs_ayuda_asistencia: bool = False


def compute_minimo_personal_familiar(profile: MinimosProfile) -> dict[str, Decimal]:
    """Derive the five mínimo casillas (``0505`` / ``0510`` / ``0515`` / ``0520`` / ``0500``).

    Applies the LIRPF arts. 57-60 lookup tables to ``profile`` and returns
    the per-component amounts. Callers populate Modelo 100 Anexo F with
    the result before supplying the filing to the engine; the engine then
    verifies ``0500 = 0505 + 0510 + 0515 + 0520`` via the
    ``modelo_100.<año>.f.minimo_personal_familiar_total`` formula.

    Args:
        profile: Validated per-contribuyente data, see
            :class:`MinimosProfile`.

    Returns:
        Dict keyed by casilla id (``"0500"``, ``"0505"``, ``"0510"``,
        ``"0515"``, ``"0520"``). Each value is a :class:`~decimal.Decimal`
        quantised to two decimal places.
    """
    # Casilla 0505 — art. 57 mínimo del contribuyente.
    casilla_0505 = MINIMO_CONTRIBUYENTE_BASE
    if profile.contribuyente_over_65:
        casilla_0505 += MINIMO_CONTRIBUYENTE_EXTRA_OVER_65
    if profile.contribuyente_over_75:
        casilla_0505 += MINIMO_CONTRIBUYENTE_EXTRA_OVER_75

    # Casilla 0510 — art. 58 mínimo por descendientes.
    casilla_0510 = Decimal("0.00")
    per_orden = (
        MINIMO_DESCENDIENTE_1,
        MINIMO_DESCENDIENTE_2,
        MINIMO_DESCENDIENTE_3,
    )
    for orden in range(profile.n_descendientes):
        if orden < 3:
            casilla_0510 += per_orden[orden]
        else:
            casilla_0510 += MINIMO_DESCENDIENTE_4_PLUS
    casilla_0510 += MINIMO_DESCENDIENTE_BONUS_UNDER_3 * Decimal(profile.n_descendientes_under_3)

    # Casilla 0515 — art. 59 mínimo por ascendientes.
    casilla_0515 = MINIMO_ASCENDIENTE_OVER_65 * Decimal(
        profile.n_ascendientes_over_65
    ) + MINIMO_ASCENDIENTE_EXTRA_OVER_75 * Decimal(profile.n_ascendientes_over_75)

    # Casilla 0520 — art. 60 mínimo por discapacidad.
    casilla_0520 = Decimal("0.00")
    if profile.contribuyente_grado_discapacidad is GradoDiscapacidad.GRADO_BAJO:
        casilla_0520 = MINIMO_DISCAPACIDAD_GRADO_BAJO
    elif profile.contribuyente_grado_discapacidad is GradoDiscapacidad.GRADO_ALTO:
        casilla_0520 = MINIMO_DISCAPACIDAD_GRADO_ALTO
    if profile.contribuyente_needs_ayuda_asistencia:
        casilla_0520 += MINIMO_DISCAPACIDAD_BONUS_ASISTENCIA

    casilla_0500 = casilla_0505 + casilla_0510 + casilla_0515 + casilla_0520

    return {
        "0500": casilla_0500.quantize(Decimal("0.01")),
        "0505": casilla_0505.quantize(Decimal("0.01")),
        "0510": casilla_0510.quantize(Decimal("0.01")),
        "0515": casilla_0515.quantize(Decimal("0.01")),
        "0520": casilla_0520.quantize(Decimal("0.01")),
    }


__all__ = [
    "GradoDiscapacidad",
    "MinimosProfile",
    "compute_minimo_personal_familiar",
]
