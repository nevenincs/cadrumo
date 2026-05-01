"""Shared Kent-profile test fixtures for golden + E2E tests (wave 111).

These builders cover the canonical "Kent the autónomo" filing scenario
reused across every byte-exactness and cross-track integration test:

- :class:`KentProfile` pins NIF / APELLIDOS / NOMBRE once so a change
  to the profile flows through every test automatically.
- :const:`KENT_130_CASILLAS` carries the nine-casilla Q1 2024 Modelo
  130 fixture (ingresos 20 000, gastos 5 000, resultado 3 000) which
  the wave-84 / wave-105 goldens pin + the wave-108 E2E derives from
  Engine inputs.
- :const:`KENT_303_CASILLAS_HAND` carries the twenty-casilla Q1 2024
  Modelo 303 fixture used by the wave-93 / wave-99 hand-picked
  goldens (régimen general, cuota 3 150 a ingresar).
- :func:`kent_130_headers` / :func:`kent_303_headers` return the
  per-ejercicio header dict (canonical CLI-side or DR303 field IDs
  respectively). ``ejercicio`` is a free parameter so 2024 vs 2025
  tests share the same helper.

Not public API — name prefixed with ``_`` to keep it out of the
package's import surface. Tests import from this module directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

# Satisfies the marker-integrity checker — this module is a shared
# fixture helper, not a test module. Real test files that consume these
# fixtures carry their own ``pytestmark`` independently.
pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


@dataclass(frozen=True, slots=True)
class KentProfile:
    """Immutable canonical Kent filer attributes.

    The NIF is a real-valid NIE per the AEAT check-letter algorithm
    (X=0, 1234567 % 23 = 19 → ``L``).
    """

    nif: str = "X1234567L"
    apellidos: str = "DOE RODRIGUEZ"
    nombre: str = "KENT"
    tipo_declaracion: str = "I"
    periodo: str = "1T"


KENT: KentProfile = KentProfile()


KENT_130_CASILLAS: dict[str, Decimal] = {
    "01": Decimal("20000.00"),
    "02": Decimal("5000.00"),
    "03": Decimal("15000.00"),
    "04": Decimal("3000.00"),
    "07": Decimal("3000.00"),
    "12": Decimal("3000.00"),
    "14": Decimal("3000.00"),
    "17": Decimal("3000.00"),
    "19": Decimal("3000.00"),
}


KENT_303_CASILLAS_HAND: dict[str, Decimal] = {
    "01": Decimal("20000.00"),
    "03": Decimal("4200.00"),
    "04": Decimal("4200.00"),
    "06": Decimal("4200.00"),
    "27": Decimal("4200.00"),
    "28": Decimal("5000.00"),
    "29": Decimal("1050.00"),
    "30": Decimal("0.00"),
    "33": Decimal("0.00"),
    "36": Decimal("0.00"),
    "38": Decimal("0.00"),
    "39": Decimal("0.00"),
    "40": Decimal("1050.00"),
    "41": Decimal("0.00"),
    "42": Decimal("0.00"),
    "64": Decimal("3150.00"),
    "65": Decimal("100.00"),
    "66": Decimal("3150.00"),
    "69": Decimal("3150.00"),
    "71": Decimal("3150.00"),
}


def kent_130_headers(ejercicio: str) -> dict[str, str]:
    """Canonical Modelo 130 CLI-side headers stamped with ``ejercicio``."""
    return {
        "EJERCICIO": ejercicio,
        "PERIODO": KENT.periodo,
        "NIF_DECLARANTE": KENT.nif,
        "APELLIDOS": KENT.apellidos,
        "NOMBRE": KENT.nombre,
        "TIPO_DECLARACION": KENT.tipo_declaracion,
    }


def kent_303_headers(ejercicio: str) -> dict[str, str]:
    """Canonical Modelo 303 DR303-field-id headers stamped with ``ejercicio``."""
    return {
        # Envelope header (DP30300).
        "DP30300_F004_EJERCICIO_DE_DEVENGO": ejercicio,
        "DP30300_F008_RESERVADO_PARA_LA_ADMINISTRA": " ",
        "DP30300_F009_VERSI_N_DEL_PROGRAMA": " ",
        "DP30300_F010_RESERVADO_PARA_LA_ADMINISTRA": " ",
        "DP30300_F011_NIF_EMPRESA_DESARROLLO": " ",
        "DP30300_F012_RESERVADO_PARA_LA_ADMINISTRA": " ",
        # Per-page identification (DP30301).
        "DP30301_F006_TIPO_DECLARACI_N": KENT.tipo_declaracion,
        "DP30301_F007_IDENTIFICACI_N_NIF": KENT.nif,
        "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": f"{KENT.apellidos} {KENT.nombre}",
        "DP30301_F009_DEVENGO_EJERCICIO": ejercicio,
        "DP30301_F010_DEVENGO_PER_ODO": KENT.periodo,
    }


__all__ = [
    "KENT",
    "KENT_130_CASILLAS",
    "KENT_303_CASILLAS_HAND",
    "KentProfile",
    "kent_130_headers",
    "kent_303_headers",
]
