"""Modelo 210 IRNR España-Bélgica convenio ceiling resolution (tranche).

Grounds the Spain-Belgium double-taxation treaty (CDI hecho en Bruselas el
14-06-1995, en vigor 25-06-2003, BOE-A-2003-13375) dividend and interest
source-state ceilings against the real registry engine (no mocks):

* Art 10.2.a dividendos — "no podrá exceder del 15 por 100 del importe bruto de
  los dividendos" → ceiling 0.15.
* Art 11.2 intereses — "no podrá exceder del 10 por 100 del importe bruto de los
  intereses" → ceiling 0.10.

Both CEILING overrides resolve to min(domestic 0.19, treaty): dividend 0.15,
interest 0.10. Grounded verbatim from the bundled BOE corpus (non-tautological).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_be_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """BE-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.a)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="dividend", country_code="BE", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")


def test_be_interest_resolves_treaty_ceiling_of_10_percent(tmp_path: Path) -> None:
    """BE-resident interest: min(domestic 0.19, treaty 0.10) = 0.10 (art 11.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="interest", country_code="BE", base="1000.00")

    assert tipo == Decimal("0.10")
    assert cuota == Decimal("100.00")


def test_be_treaty_legal_entries_are_grounded() -> None:
    """The BE treaty rows and their BOE-grounded legal entries are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-be-1995:art-10" in catalogues.legal
    assert "convenio-es-be-1995:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-be-1995:art-10"]
    art11 = catalogues.legal["convenio-es-be-1995:art-11"]
    assert art10.document_id == "BOE-A-2003-13375"
    assert art11.document_id == "BOE-A-2003-13375"
    assert "no podrá exceder del 15 por 100" in art10.required_text
    assert "no podrá exceder del 10 por 100" in art11.required_text
