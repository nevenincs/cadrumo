"""Unit tests for the closed IVA enumerations exposed by :mod:`aeat.domain.iva`.

Pins membership and round-trip semantics for :class:`IvaCategory`,
:class:`EUMemberState` and :class:`IvaRateKind` so accidental additions or
removals surface as test failures.
"""

from __future__ import annotations

import pytest

from .. import EUMemberState, IvaCategory, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_iva_category_has_every_named_member() -> None:
    """:class:`IvaCategory` must carry exactly the 17 declared members.

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
    assert {member.name for member in IvaCategory} == expected


def test_iva_category_values_roundtrip_through_strenum() -> None:
    """Every IvaCategory value re-parses to the same member."""
    for member in IvaCategory:
        assert IvaCategory(member.value) is member


def test_eu_member_state_has_27_members() -> None:
    """EUMemberState must cover the 27 current EU member states."""
    assert len(list(EUMemberState)) == 27


def test_iva_rate_kind_has_five_tiers() -> None:
    """IvaRateKind covers the five tiers used by the substrate."""
    assert {m.name for m in IvaRateKind} == {
        "GENERAL",
        "REDUCED",
        "SUPER_REDUCED",
        "ZERO",
        "EXEMPT",
    }
