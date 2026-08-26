"""Modelo 210 IRNR España-Portugal convenio cánones ceiling resolution.

Grounds the Spain-Portugal double-taxation treaty (CDI firmado 26-10-1993, en
vigor 28-06-1995, BOE-A-1995-24001) cánones source-state ceiling against the real
registry engine (no mocks):

* Art 12.2 cánones — "el impuesto así exigido no podrá exceder del 5 por 100 del
  importe bruto de los cánones" → ceiling 0.05.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
PT-resident cánones item resolves to min(0.24, 0.05) = 0.05 (domestic cánones is
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


def test_pt_canones_resolves_treaty_ceiling_of_5_percent(tmp_path: Path) -> None:
    """PT-resident cánones: min(domestic 0.24, treaty 0.05) = 0.05 (art 12.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="PT", base="1000.00")

    assert tipo == Decimal("0.05")
    assert cuota == Decimal("50.00")  # 1000 × 0.05


def test_pt_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The PT cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-pt-1993:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-pt-1993:art-12"]
    assert art12.document_id == "BOE-A-1995-24001"
    assert "no podrá exceder del 5 por 100" in art12.required_text
