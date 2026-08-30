"""Public surface regressions for ``cadrumo.domain.contribuyente``."""

from __future__ import annotations

from datetime import date

import pytest

from .. import descendant_facts
from ..descendant import DescendantInfo
from ..descendant_facts import descendant_list_from_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_descendant_list_from_facts_is_public_module_surface() -> None:
    """Application and modelo reconstruct descendant facts through this module.

    This asserted the package namespace's ``__all__`` until that namespace was
    made inert. The guarantee is unchanged -- the reconstruction is public and
    callable from outside the package -- only the module a caller reaches it
    through moved to the one that defines it.
    """

    assert hasattr(descendant_facts, "descendant_list_from_facts")

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
