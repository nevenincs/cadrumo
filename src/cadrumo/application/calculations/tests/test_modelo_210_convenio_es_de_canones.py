"""Modelo 210 IRNR España-Alemania convenio cánones exemption resolution.

Grounds the Spain-Germany double-taxation treaty (CDI 2011, en vigor 2012-10-18,
BOE-A-2012-10212) cánones source-state exemption against the real registry engine
(no mocks):

* Art 12 cánones — "sólo pueden someterse a imposición en ese otro Estado" →
  source-state exempt (0), mirroring the DE art-11 interest exemption.

The override kind is EXEMPT, so the resolver drives the source-state rate to zero
regardless of the domestic 24% cánones rate. Grounded verbatim from the bundled
BOE consolidated corpus (non-tautological) — a regression that dropped the treaty
row, or mis-typed the exemption as a ceiling, would change the resolved rate and
fail the test.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.secure_sql import isolated_runtime_profile
from ._convenio_rate_support import resolve_convenio_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_de_canones_is_source_state_exempt(tmp_path: Path) -> None:
    """DE-resident cánones: source-state exemption (art 12) → 0."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = resolve_convenio_rate(tipo_renta="canones", country_code="DE", base="1000.00")

    assert tipo == Decimal("0")
    assert cuota == Decimal("0.00")


def test_de_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The DE cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = bundled_authority().catalogues
    assert "convenio-es-de-2011:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-de-2011:art-12"]
    assert art12.document_id == "BOE-A-2012-10212"
    assert "sólo pueden someterse a imposición en ese otro Estado" in art12.required_text
