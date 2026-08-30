"""Unit tests for the closed IVA enumerations exposed by :mod:`cadrumo.domain.iva`.

Pins membership and round-trip semantics for :class:`IvaCategory`,
:class:`EUMemberState` and :class:`IvaRateKind` so accidental additions or
removals surface as test failures.
"""

from __future__ import annotations

import pytest

from ..schema import EUMemberState, IvaCategory, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_iva_category_has_every_named_member() -> None:
    """:class:`IvaCategory` must carry exactly the 18 declared members.

    ``DOMESTIC_REVERSE_CHARGE`` exists to disambiguate
    *inversión del sujeto pasivo* on domestic transactions
    (Art. 84.Uno.2º) from intra-community acquisitions, which already use
    ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE``.
    """
    expected = {
        "DOMESTIC_GENERAL",
        "DOMESTIC_REDUCED",
        "DOMESTIC_SUPER_REDUCED",
        "DOMESTIC_ZERO",
        "DOMESTIC_EXEMPT",
        "DOMESTIC_NOT_SUBJECT",
        "DOMESTIC_REVERSE_CHARGE",
        "INTRA_COMMUNITY_SUPPLY",
        "INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE",
        "INTRA_COMMUNITY_TRIANGULATION",
        "INTRA_COMMUNITY_SERVICE_SUPPLY",
        "INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE",
        "EXPORT_THIRD_COUNTRY_ZERO_RATED",
        "EXPORT_ASSIMILATED_ZERO_RATED",
        "IMPORT_THIRD_COUNTRY",
        "RECARGO_EQUIVALENCIA",
        "REGIMEN_SIMPLIFICADO",
        "REAGP_COMPENSATION",
        "OPERACION_NO_SUJETA",
        "ERRONEOUS_INVOICE",
        "UNKNOWN",
    }
    assert {member.name for member in IvaCategory} == expected


def test_iva_category_values_roundtrip_through_strenum() -> None:
    """Every IvaCategory value re-parses to the same member."""
    for member in IvaCategory:
        assert IvaCategory(member.value) is member


def test_eu_member_state_has_27_strict_member_states_plus_xi_prefix() -> None:
    """EUMemberState covers the 27 EU states plus the post-Brexit XI IVA prefix."""
    assert len([member for member in EUMemberState if member is not EUMemberState.XI]) == 27
    assert EUMemberState.XI.value == "xi"


def test_iva_rate_kind_has_five_tiers() -> None:
    """IvaRateKind covers the five tiers used by the substrate."""
    assert {m.name for m in IvaRateKind} == {
        "GENERAL",
        "REDUCED",
        "SUPER_REDUCED",
        "ZERO",
        "EXEMPT",
    }
