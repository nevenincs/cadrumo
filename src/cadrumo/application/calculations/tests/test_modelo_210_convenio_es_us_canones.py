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

import pytest

from ....domain.calculations.registry.tests.published_authority import published_legal_reference
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_us_canones_is_source_state_exempt() -> None:
    """US-resident cánones: source-state exemption (art 12, Protocolo 2019) → 0."""
    tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="US", base="1000.00")

    assert tipo == Decimal("0")
    assert cuota == Decimal("0.00")


def test_us_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The US cánones treaty row and its BOE-grounded legal entry are registered."""
    assert published_legal_reference("convenio-es-us-1990:art-12").id == "convenio-es-us-1990:art-12"
    art12 = published_legal_reference("convenio-es-us-1990:art-12")
    assert art12.document_id == "BOE-A-1990-30940"
    assert "sólo pueden someterse a imposición en ese otro Estado" in art12.required_text
