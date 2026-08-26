"""Modelo 210 IRNR España-Portugal convenio ceiling resolution (tranche).

Grounds the Spain-Portugal double-taxation treaty (CDI firmado 26-10-1993, en
vigor 28-06-1995, BOE-A-1995-24001) dividend and interest source-state ceilings
against the real registry engine (no mocks):

* Art 10.2.b dividendos — "no podrá exceder del ... b) 15 por 100 del importe
  bruto de los dividendos en los demás casos" → ceiling 0.15.
* Art 11.2 intereses — "no podrá exceder del 15 por 100 del importe bruto de los
  intereses" → ceiling 0.15.

Both CEILING overrides resolve to min(domestic 0.19, treaty 0.15) = 0.15. These
are grounded treaty figures (read verbatim from the bundled BOE corpus), so the
assertions are non-tautological.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_pt_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """PT-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.b)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="dividend", country_code="PT", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")


def test_pt_interest_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """PT-resident interest: min(domestic 0.19, treaty 0.15) = 0.15 (art 11.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="interest", country_code="PT", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")


def test_pt_treaty_legal_entries_are_grounded() -> None:
    """The PT treaty rows and their BOE-grounded legal entries are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-pt-1993:art-10" in catalogues.legal
    assert "convenio-es-pt-1993:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-pt-1993:art-10"]
    art11 = catalogues.legal["convenio-es-pt-1993:art-11"]
    assert art10.document_id == "BOE-A-1995-24001"
    assert art11.document_id == "BOE-A-1995-24001"
    assert "15 por 100 del importe bruto de los dividendos" in art10.required_text
    assert "no podrá exceder del 15 por 100" in art11.required_text
