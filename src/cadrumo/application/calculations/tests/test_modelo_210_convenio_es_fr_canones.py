"""Modelo 210 IRNR España-Francia convenio cánones ceiling resolution.

Grounds the Spain-France double-taxation treaty (CDI firmado 10-10-1995, en vigor
01-07-1997, BOE-A-1997-12729) cánones source-state ceiling against the real
registry engine (no mocks). The treaty caps source-state taxation of royalties:

* Art 12.2.a cánones — "el impuesto así establecido no puede exceder del 5 por
  100 del importe bruto de los cánones" → ceiling 0.05.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
FR-resident cánones item resolves to min(0.24, 0.05) = 0.05 (domestic cánones is
the Art 25.1.a general 24% rate — cánones has no specific letter in the
consolidated Art 25.1). This is a grounded treaty figure (read verbatim from the
bundled BOE corpus), so the assertion is non-tautological — a regression that
dropped the treaty row, or mis-typed the ceiling as flat, would change the
resolved rate and fail the test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.tests.published_authority import published_legal_reference
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_fr_canones_resolves_treaty_ceiling_of_5_percent() -> None:
    """FR-resident cánones: min(domestic 0.24, treaty 0.05) = 0.05 (art 12.2.a)."""
    tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="FR", base="1000.00")

    assert tipo == Decimal("0.05")
    assert cuota == Decimal("50.00")  # 1000 × 0.05


def test_fr_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The FR cánones treaty row and its BOE-grounded legal entry are registered."""
    assert published_legal_reference("convenio-es-fr-1995:art-12").id == "convenio-es-fr-1995:art-12"
    art12 = published_legal_reference("convenio-es-fr-1995:art-12")
    assert art12.document_id == "BOE-A-1997-12729"
    assert "no puede exceder del 5 por 100" in art12.required_text
