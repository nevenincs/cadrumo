"""Unit tests for the closed VAT enumerations exposed by :mod:`aeat.domain.vat`.

Pins membership and round-trip semantics for :class:`VATCategory`,
:class:`EUMemberState` and :class:`VATRateKind` so accidental additions or
removals surface as test failures.
"""

from __future__ import annotations

import pytest

from . import EUMemberState, VATCategory, VATRateKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_vat_category_has_every_named_member() -> None:
    """:class:`VATCategory` must carry exactly the 17 declared members.

    ``DOMESTIC_REVERSE_CHARGE`` exists to disambiguate
    *inversión del sujeto pasivo* on domestic transactions
    (Art. 84.Uno.2º) from intra-community acquisitions, which already use
    ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE``.
    """
    expected = {
        "DOMESTIC_GENERAL_21",
        "DOMESTIC_REDUCED_10",
        "DOMESTIC_SUPER_REDUCED_4",
        "DOMESTIC_ZERO",
        "DOMESTIC_EXEMPT",
        "DOMESTIC_NOT_SUBJECT",
        "DOMESTIC_REVERSE_CHARGE",
        "INTRA_COMMUNITY_SUPPLY",
        "INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE",
        "INTRA_COMMUNITY_TRIANGULATION",
        "EXPORT_THIRD_COUNTRY_ZERO_RATED",
        "IMPORT_THIRD_COUNTRY",
        "RECARGO_EQUIVALENCIA",
        "REGIMEN_SIMPLIFICADO",
        "OPERACION_NO_SUJETA",
        "ERRONEOUS_INVOICE",
        "UNKNOWN",
    }
    assert {member.name for member in VATCategory} == expected


def test_vat_category_values_roundtrip_through_strenum() -> None:
    """Every VATCategory value re-parses to the same member."""
    for member in VATCategory:
        assert VATCategory(member.value) is member


def test_eu_member_state_has_27_members() -> None:
    """EUMemberState must cover the 27 current EU member states."""
    assert len(list(EUMemberState)) == 27


def test_vat_rate_kind_has_five_tiers() -> None:
    """VATRateKind covers the five tiers used by the substrate."""
    assert {m.name for m in VATRateKind} == {
        "GENERAL",
        "REDUCED",
        "SUPER_REDUCED",
        "ZERO",
        "EXEMPT",
    }
