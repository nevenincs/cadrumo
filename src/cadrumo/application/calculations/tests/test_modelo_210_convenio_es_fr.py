"""Modelo 210 IRNR España-Francia convenio ceiling resolution.

Grounds the Spain-France double-taxation treaty (CDI firmado 10-10-1995, en vigor
01-07-1997, BOE-A-1997-12729) dividend and interest source-state ceilings against
the real registry engine (no mocks). The treaty caps source-state taxation:

* Art 10.2.a dividendos — "el impuesto así exigido no podrá exceder del 15 por
  100 del importe bruto de los dividendos" → ceiling 0.15.
* Art 11.2 intereses — "el impuesto así exigido no puede exceder del 10 por 100
  del importe bruto de los intereses" → ceiling 0.10.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
FR-resident dividend resolves to min(0.19, 0.15) = 0.15 and interest to
min(0.19, 0.10) = 0.10. These are grounded treaty figures (read verbatim from the
bundled BOE corpus), so the assertions are non-tautological — a regression that
dropped either treaty row, or mis-typed the ceiling as flat, would change the
resolved rate and fail the test.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_fr_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """FR-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.a)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="dividend", country_code="FR", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")  # 1000 × 0.15


def test_fr_interest_resolves_treaty_ceiling_of_10_percent(tmp_path: Path) -> None:
    """FR-resident interest: min(domestic 0.19, treaty 0.10) = 0.10 (art 11.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="interest", country_code="FR", base="1000.00")

    assert tipo == Decimal("0.10")
    assert cuota == Decimal("100.00")  # 1000 × 0.10


def test_fr_treaty_and_legal_entries_are_grounded() -> None:
    """The FR treaty rows and their BOE-grounded legal entries are registered."""
    authority = bundled_authority()
    catalogues = authority.catalogues
    assert "convenio-es-fr-1995:art-10" in catalogues.legal
    assert "convenio-es-fr-1995:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-fr-1995:art-10"]
    art11 = catalogues.legal["convenio-es-fr-1995:art-11"]
    assert art10.document_id == "BOE-A-1997-12729"
    assert art11.document_id == "BOE-A-1997-12729"
    assert "no podrá exceder del 15 por 100" in art10.required_text
    assert "no puede exceder del 10 por 100" in art11.required_text
