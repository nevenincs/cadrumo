"""Modelo 210 IRNR España-Países Bajos convenio cánones ceiling resolution.

Grounds the Spain-Netherlands double-taxation treaty (CDI 16-06-1971, en vigor
20-09-1972, BOE-A-1972-1469) cánones source-state ceiling against the real
registry engine (no mocks):

* Art 12.2 cánones — "el impuesto así exigido no puede exceder del 6 por 100 del
  importe bruto de los cánones" → ceiling 0.06 (the PERMANENT rate; Protocol
  clause XIV's 5% was a transitional 1972-1977 rate, long expired).

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
NL-resident cánones item resolves to min(0.24, 0.06) = 0.06 (domestic cánones is
the Art 25.1.a general 24% rate). Grounded verbatim from the bundled BOE corpus
(non-tautological).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_nl_canones_resolves_treaty_ceiling_of_6_percent(tmp_path: Path) -> None:
    """NL-resident cánones: min(domestic 0.24, treaty 0.06) = 0.06 (art 12.2, permanent)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="NL", base="1000.00")

    assert tipo == Decimal("0.06")
    assert cuota == Decimal("60.00")  # 1000 × 0.06


def test_nl_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The NL cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-nl-1971:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-nl-1971:art-12"]
    assert art12.document_id == "BOE-A-1972-1469"
    assert "no puede exceder del 6 por 100" in art12.required_text
