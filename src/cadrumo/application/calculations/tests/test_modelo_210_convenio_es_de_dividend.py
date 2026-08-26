"""Modelo 210 IRNR España-Alemania dividend ceiling resolution.

Grounds the Spain-Germany double-taxation treaty (CDI firmado 03-02-2011, en
vigor 18-10-2012, BOE-A-2012-10212) dividend source-state ceiling against the
real registry engine (no mocks). Art 10.2.b caps the general source-state rate:
"el impuesto así exigido no podrá exceder del: ... b) 15 por ciento del importe
bruto de los dividendos en todos los demás casos" → ceiling 0.15.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
DE-resident dividend resolves to min(0.19, 0.15) = 0.15. This is a grounded
treaty figure (read verbatim from the bundled BOE corpus), so the assertion is
non-tautological — a regression that dropped the dividend row, or mis-typed the
ceiling as flat, would change the resolved rate and fail the test. The pre-existing
DE interest override (exempt, art 11) is left intact and re-asserted here.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_de_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """DE-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.b)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="dividend", country_code="DE", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")  # 1000 × 0.15


def test_de_dividend_legal_entry_is_grounded() -> None:
    """The DE dividend treaty row and its BOE-grounded art-10 legal entry exist."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-de-2011:art-10" in catalogues.legal
    art10 = catalogues.legal["convenio-es-de-2011:art-10"]
    assert art10.document_id == "BOE-A-2012-10212"
    assert "15 por ciento del importe bruto de los dividendos" in art10.required_text


def test_de_interest_exempt_override_is_preserved(tmp_path: Path) -> None:
    """The pre-existing DE interest exemption (art 11) is untouched by #216."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, _cuota = resolve_convenio_rate(tipo_renta="interest", country_code="DE", base="1000.00")

    assert tipo == Decimal("0")  # art 11 source-state exemption
