"""Modelo 210 IRNR España-Estados Unidos convenio cánones exemption resolution.

Grounds the Spain-US double-taxation treaty (CDI 22-02-1990, BOE-A-1990-30940)
cánones source-state exemption in its redacción VIGENTE tras el Protocolo de 2013
(Artículo VI, BOE-A-2019-15166, en vigor 27-11-2019), which replaced the original
tiered 5/8/10% article 12 in full:

* Art 12 cánones — "sólo pueden someterse a imposición en ese otro Estado" →
  source-state exempt (0), mirroring the US art-11 interest exemption.

The override kind is EXEMPT, so the resolver drives the source-state rate to zero
regardless of the domestic 24% cánones rate. Grounded verbatim from the bundled
BOE consolidated (post-Protocol) corpus (non-tautological).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_us_canones_is_source_state_exempt(tmp_path: Path) -> None:
    """US-resident cánones: source-state exemption (art 12, Protocolo 2019) → 0."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="US", base="1000.00")

    assert tipo == Decimal("0")
    assert cuota == Decimal("0.00")


def test_us_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The US cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-us-1990:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-us-1990:art-12"]
    assert art12.document_id == "BOE-A-1990-30940"
    assert "sólo pueden someterse a imposición en ese otro Estado" in art12.required_text
