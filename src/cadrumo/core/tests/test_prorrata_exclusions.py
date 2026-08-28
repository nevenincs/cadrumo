"""Unit tests for the LIVA art. 104.Tres prorrata-exclusion closed set.

The expected membership is taken from an external authority — the bundled
consolidated LIVA art. 104.Tres (``ley-37-1992-art-104.html#a104``), which
enumerates exactly six operations excluded from both terms of the prorrata
ratio (reglas 1.º-6.º) — not from a re-run of the code under test. The
auto-derived / operator-declared partition keeps only the two
judgment exclusions (foreign PE, non-habitual inmobiliario/financiero) are
operator-declared.
"""

from __future__ import annotations

import pytest

from .. import (
    ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS,
    Art104TresExclusion,
)
from .._prorrata_exclusions import ART_104_TRES_AUTO_DERIVED_EXCLUSIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_art_104_tres_exclusion_has_exactly_the_six_law_members() -> None:
    """The enum carries exactly the six art. 104.Tres exclusions, no subvenciones member."""
    assert {member.value for member in Art104TresExclusion} == {
        "foreign_permanent_establishment",
        "direct_iva_cuotas",
        "investment_goods_disposal",
        "non_habitual_real_estate_or_financial",
        "non_subject_art_7",
        "self_supply_art_9_1_d",
    }


def test_operator_declared_set_is_the_two_judgment_exclusions() -> None:
    """Only the PE and non-habitual judgment exclusions are operator-declared."""
    assert (
        frozenset(
            {
                Art104TresExclusion.FOREIGN_PERMANENT_ESTABLISHMENT,
                Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL,
            }
        )
        == ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS
    )


def test_operator_and_auto_partitions_are_disjoint_and_cover_the_closed_set() -> None:
    """Every member is in exactly one of the two partitions."""
    assert ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS.isdisjoint(ART_104_TRES_AUTO_DERIVED_EXCLUSIONS)
    assert (
        frozenset(Art104TresExclusion)
        == ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS | ART_104_TRES_AUTO_DERIVED_EXCLUSIONS
    )


def test_auto_derived_set_is_the_four_category_register_structural_exclusions() -> None:
    """The four auto-derived exclusions are direct cuotas, bienes de inversión, art. 7, art. 9.1.d."""
    assert (
        frozenset(
            {
                Art104TresExclusion.DIRECT_IVA_CUOTAS,
                Art104TresExclusion.INVESTMENT_GOODS_DISPOSAL,
                Art104TresExclusion.NON_SUBJECT_ART_7,
                Art104TresExclusion.SELF_SUPPLY_ART_9_1_D,
            }
        )
        == ART_104_TRES_AUTO_DERIVED_EXCLUSIONS
    )
