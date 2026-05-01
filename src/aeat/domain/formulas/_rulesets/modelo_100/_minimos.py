"""LIRPF arts. 56-61 mínimo personal y familiar helper.

The mínimo personal y familiar ("personal and family allowance") is
the portion of base liquidable that, per LIRPF art. 56, "no se somete
a tributación" — it does not pay tax. Anexo F casillas 0505 / 0510 /
0515 / 0520 carry the per-component amounts; 0500 is their sum.

The amounts have been **stable since 2015** — no posterior law
modification at BOE consolidated text consult 2026-04-28. Per LIRPF
arts. 57-60:

- **art. 57 mínimo del contribuyente**: 5.550 € base; +1.150 € if >65
  años; +1.400 € additional if >75
- **art. 58 mínimo por descendientes**: 2.400 € (1º) / 2.700 € (2º) /
  4.000 € (3º) / 4.500 € (4º+); +2.800 € per descendiente <3 años
- **art. 59 mínimo por ascendientes**: 1.150 € per ascendiente >=65 ó
  con discapacidad; +1.400 € per ascendiente >75
- **art. 60 mínimo por discapacidad**: 3.000 € if grado <65%; 9.000 €
  if grado >=65%; +3.000 € additional if needs ayuda asistencia (third-
  party assistance, mobility limitation, or grado >=65%)

The `compute_minimo_personal_familiar(profile)` helper consumes a
`MinimosProfile` Pydantic model and returns a dict keyed by casilla id
(0505 / 0510 / 0515 / 0520 / 0500) with the per-component amounts.
Callers use the result to populate Anexo F before supplying the
filing to the engine; the engine then verifies the 0500 = sum chain.

Requisitos comunes (LIRPF art. 61): convivencia + rentas anuales
del descendiente / ascendiente <= 8.000 € (excluidas exentas). Caller
is responsible for filtering out non-qualifying personas before
populating the profile.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# LIRPF art. 57 — mínimo del contribuyente.
MINIMO_CONTRIBUYENTE_BASE = Decimal("5550.00")
MINIMO_CONTRIBUYENTE_EXTRA_OVER_65 = Decimal("1150.00")
MINIMO_CONTRIBUYENTE_EXTRA_OVER_75 = Decimal("1400.00")

# LIRPF art. 58 — mínimo por descendientes (per-orden amounts).
MINIMO_DESCENDIENTE_1 = Decimal("2400.00")
MINIMO_DESCENDIENTE_2 = Decimal("2700.00")
MINIMO_DESCENDIENTE_3 = Decimal("4000.00")
MINIMO_DESCENDIENTE_4_PLUS = Decimal("4500.00")
MINIMO_DESCENDIENTE_BONUS_UNDER_3 = Decimal("2800.00")

# LIRPF art. 59 — mínimo por ascendientes.
MINIMO_ASCENDIENTE_OVER_65 = Decimal("1150.00")
MINIMO_ASCENDIENTE_EXTRA_OVER_75 = Decimal("1400.00")

# LIRPF art. 60 — mínimo por discapacidad.
MINIMO_DISCAPACIDAD_GRADO_BAJO = Decimal("3000.00")  # < 65%
MINIMO_DISCAPACIDAD_GRADO_ALTO = Decimal("9000.00")  # >= 65%
MINIMO_DISCAPACIDAD_BONUS_ASISTENCIA = Decimal("3000.00")


class GradoDiscapacidad(StrEnum):
    """LIRPF art. 60 grado de discapacidad — closed enum."""

    NONE = "none"
    GRADO_BAJO = "grado_bajo"  # 33% <= grado < 65%
    GRADO_ALTO = "grado_alto"  # grado >= 65%


class MinimosProfile(BaseModel):
    """Inputs to `compute_minimo_personal_familiar()`.

    Captures the per-contribuyente / per-familia data needed to derive
    the LIRPF arts. 57-60 mínimos. All counts are non-negative; the
    Pydantic v2 strict + frozen + extra=forbid discipline catches
    type errors at construction time.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    # art. 57 — contribuyente.
    contribuyente_over_65: bool = False
    contribuyente_over_75: bool = False  # implies contribuyente_over_65

    # art. 58 — descendientes.
    n_descendientes: int = Field(default=0, ge=0)
    n_descendientes_under_3: int = Field(default=0, ge=0)

    # art. 59 — ascendientes.
    n_ascendientes_over_65: int = Field(default=0, ge=0)
    n_ascendientes_over_75: int = Field(default=0, ge=0)  # subset of over_65

    # art. 60 — discapacidad.
    contribuyente_grado_discapacidad: GradoDiscapacidad = GradoDiscapacidad.NONE
    contribuyente_needs_ayuda_asistencia: bool = False


def compute_minimo_personal_familiar(profile: MinimosProfile) -> dict[str, Decimal]:
    """Derive the 5 mínimo casillas (0505 / 0510 / 0515 / 0520 / 0500)
    from `profile` per LIRPF arts. 57-60.

    Returns a dict keyed by casilla id. Caller passes the values to
    Anexo F before supplying the filing to the engine; the engine then
    verifies 0500 = sum of components via the existing
    ``modelo_100.<año>.f.minimo_personal_familiar_total`` formula.
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
