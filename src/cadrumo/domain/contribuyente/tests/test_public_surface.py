"""Public surface regressions for ``cadrumo.domain.contribuyente``."""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..descendant import DescendantInfo
from ..descendant_facts import descendant_list_from_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

EXERCISE = filing_year_envelope().horizon


def test_descendant_list_from_facts_is_public_module_surface() -> None:
    """Application and modelo reconstruct descendant facts through this module."""

    descendants = descendant_list_from_facts(
        {
            "renta_family.descendiente.0.birth_date": date(EXERCISE - 2, 3, 14).isoformat(),
            "renta_family.descendiente.0.convivencia": "true",
            "renta_family.descendiente.0.custodia_compartida": "true",
        },
    )

    assert descendants == (
        DescendantInfo(
            birth_date=date(EXERCISE - 2, 3, 14),
            convive_con_contribuyente=True,
            custodia_compartida=True,
        ),
    )
