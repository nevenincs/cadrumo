"""Unit tests for the registry-owned LIVA art. 104.Tres exclusions.

The expected membership is taken from an external authority — the bundled
consolidated LIVA art. 104.Tres — rather than from a re-run of the code under
test. The auto-derived / operator-declared partition keeps only the two
judgment exclusions operator-declared.
"""

from __future__ import annotations

import pytest

from ..prorrata_exclusions import resolve_art104_tres_exclusion_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_art_104_tres_exclusion_has_exactly_the_six_law_members() -> None:
    """The registry catalogue carries exactly the six art. 104.Tres exclusions."""
    catalogue = resolve_art104_tres_exclusion_catalogue()
    assert {str(member) for member in catalogue.all_exclusions} == {
        "foreign_permanent_establishment",
        "direct_iva_cuotas",
        "investment_goods_disposal",
        "non_habitual_real_estate_or_financial",
        "non_subject_art_7",
        "self_supply_art_9_1_d",
    }


def test_operator_declared_set_is_the_two_judgment_exclusions() -> None:
    """Only the PE and non-habitual judgment exclusions are operator-declared."""
    catalogue = resolve_art104_tres_exclusion_catalogue()
    assert {str(member) for member in catalogue.operator_declared} == {
        "foreign_permanent_establishment",
        "non_habitual_real_estate_or_financial",
    }
