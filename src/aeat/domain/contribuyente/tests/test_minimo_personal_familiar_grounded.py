"""Registry-grounding gate for the IRPF mínimo personal y familiar amounts.

The Ley 35/2006 arts. 57-60 mínimo amounts live as Modelo-100 money parameters
per ejercicio. This gate reads each via the registry (``read_parameter``) and
asserts the AEAT-confirmed euro figure, so a parameter that drifts from the law
fails loudly. It is the durable consumer that keeps the per-year mínimo
parameters honest (the menor-tres 3.000-vs-2.800 defect — a bundled-corpus error
that had propagated to the parameter — is exactly what this gate catches).

Amounts confirmed against the AEAT IRPF manuals for the ejercicios 2020-2025 (all
identical — the figures have been stable since the Ley 26/2014 reform): contribuyente
5.550 / +1.150 (>65) / +1.400 (>75); descendientes 2.400 / 2.700 / 4.000 / 4.500;
menor de 3 años +2.800; ascendientes 1.150 / +1.400; discapacidad 3.000 / 9.000 /
+3.000 (gastos de asistencia).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import Modelo
from ...calculations.registry import read_parameter

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (param-id stem, AEAT-confirmed euro amount). The stem is suffixed with the year.
_MINIMO_AMOUNTS: tuple[tuple[str, str], ...] = (
    ("minimo-contribuyente-base", "5550"),
    ("minimo-contribuyente-edad-65-74", "1150"),
    ("minimo-contribuyente-edad-75", "1400"),
    ("minimo-descendientes-primer-hijo", "2400"),
    ("minimo-descendientes-segundo-hijo", "2700"),
    ("minimo-descendientes-tercer-hijo", "4000"),
    ("minimo-descendientes-cuarto-y-siguientes", "4500"),
    ("minimo-descendientes-menor-tres-anos", "2800"),
    ("minimo-ascendientes-mayor-65", "1150"),
    ("minimo-ascendientes-mayor-75", "1400"),
    # Art. 60 mínimo por discapacidad (contribuyente, descendientes, ascendientes).
    ("minimo-discapacidad-grado-33", "3000"),
    ("minimo-discapacidad-grado-65", "9000"),
    ("minimo-discapacidad-gastos-asistencia", "3000"),
)


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
@pytest.mark.parametrize(("stem", "expected"), _MINIMO_AMOUNTS)
def test_minimo_personal_familiar_amount_matches_aeat(year: int, stem: str, expected: str) -> None:
    value = read_parameter(
        Modelo.M100.value,
        str(year),
        f"renta-{year}-{stem}-{year}",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert value == Decimal(expected), f"renta-{year}-{stem}: {value} != AEAT {expected}"
