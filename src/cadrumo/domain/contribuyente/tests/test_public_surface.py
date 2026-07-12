"""Public surface regressions for ``cadrumo.domain.contribuyente``."""

from __future__ import annotations

from datetime import date

import pytest

from ... import contribuyente
from .. import DescendantInfo, descendant_list_from_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_descendant_list_from_facts_is_public_package_surface() -> None:
    """Application/modelo imports descendant fact reconstruction from this package boundary."""

    assert "descendant_list_from_facts" in contribuyente.__all__

    descendants = descendant_list_from_facts(
        {
            "renta_family.descendiente.0.birth_date": "2022-03-14",
            "renta_family.descendiente.0.convivencia": "true",
            "renta_family.descendiente.0.custodia_compartida": "true",
        },
    )

    assert descendants == (
        DescendantInfo(
            birth_date=date(2022, 3, 14),
            convive_con_contribuyente=True,
            custodia_compartida=True,
        ),
    )
