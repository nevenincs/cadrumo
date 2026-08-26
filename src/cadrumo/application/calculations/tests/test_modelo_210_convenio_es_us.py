"""Modelo 210 IRNR España-Estados Unidos convenio resolution (tranche).

Grounds the Spain-US double-taxation treaty (CDI 22-02-1990, redacción vigente
tras el Protocolo de 2013 en vigor 27-11-2019, BOE-A-1990-30940) against the real
registry engine (no mocks). The two-regime split is resolved by grounding the
CURRENTLY-in-force (post-protocol) rates:

* Art 10.2.b dividendos — "15 por ciento del importe bruto de los dividendos en
  los demás casos" → dividend ceiling 0.15 (min(0.19, 0.15) = 0.15).
* Art 11.1 intereses — "sólo pueden someterse a imposición en ese otro Estado" →
  interest exempt at source (0), mirroring the DE art-11 exemption.

Grounded verbatim from the bundled BOE consolidated corpus (non-tautological).
The 5%/0% dividend tiers and the art 11.2 interest exceptions are not modelled.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_us_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """US-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.b)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="dividend", country_code="US", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")


def test_us_interest_is_source_state_exempt(tmp_path: Path) -> None:
    """US-resident interest: source-state exemption (art 11.1) → 0."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="interest", country_code="US", base="1000.00")

    assert tipo == Decimal("0")
    assert cuota == Decimal("0.00")


def test_us_treaty_legal_entries_are_grounded() -> None:
    """The US treaty rows and their BOE-grounded legal entries are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-us-1990:art-10" in catalogues.legal
    assert "convenio-es-us-1990:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-us-1990:art-10"]
    art11 = catalogues.legal["convenio-es-us-1990:art-11"]
    assert art10.document_id == "BOE-A-1990-30940"
    assert art11.document_id == "BOE-A-1990-30940"
    assert "15 por ciento del importe bruto de los dividendos" in art10.required_text
    assert "sólo pueden someterse a imposición en ese otro Estado" in art11.required_text
