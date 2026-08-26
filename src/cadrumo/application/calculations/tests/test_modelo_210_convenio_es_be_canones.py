"""Modelo 210 IRNR España-Bélgica convenio cánones ceiling resolution.

Grounds the Spain-Belgium double-taxation treaty (CDI hecho en Bruselas el
14-06-1995, en vigor 25-06-2003, BOE-A-2003-13375) cánones source-state ceiling
against the real registry engine (no mocks):

* Art 12.2 cánones — "el impuesto así exigido no podrá exceder del 5 por 100 del
  importe bruto de los cánones" → ceiling 0.05.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
BE-resident cánones item resolves to min(0.24, 0.05) = 0.05 (domestic cánones is
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


def test_be_canones_resolves_treaty_ceiling_of_5_percent(tmp_path: Path) -> None:
    """BE-resident cánones: min(domestic 0.24, treaty 0.05) = 0.05 (art 12.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="BE", base="1000.00")

    assert tipo == Decimal("0.05")
    assert cuota == Decimal("50.00")  # 1000 × 0.05


def test_be_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The BE cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-be-1995:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-be-1995:art-12"]
    assert art12.document_id == "BOE-A-2003-13375"
    assert "no podrá exceder del 5 por 100" in art12.required_text
