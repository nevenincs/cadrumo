"""Unit tests for the closed IVA enumerations exposed by :mod:`cadrumo.domain.iva`.

Pins membership and round-trip semantics for :class:`IvaCategory`,
:class:`EUMemberState` and :class:`IvaRateKind` so accidental additions or
removals surface as test failures.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ...calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...calculations.registry.iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON_DATE = date(2025, 1, 1)


def test_iva_category_has_every_named_member(operation: PinnedAuthorityOperation) -> None:
    """:class:`IvaCategory` must carry exactly the 18 declared members.

    ``DOMESTIC_REVERSE_CHARGE`` exists to disambiguate
    *inversión del sujeto pasivo* on domestic transactions
    (Art. 84.Uno.2º) from intra-community acquisitions, which already use
    ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE``.
    """
    expected = {
        "domestic_general",
        "domestic_reduced",
        "domestic_super_reduced",
        "domestic_zero",
        "domestic_exempt",
        "domestic_not_subject",
        "operacion_no_sujeta",
        "intra_community_supply",
        "export_third_country_zero_rated",
        "export_assimilated_zero_rated",
        "intra_community_triangulation",
        "domestic_reverse_charge",
        "intra_community_service_supply",
        "intra_community_service_acquisition_reverse_charge",
        "intra_community_acquisition_reverse_charge",
        "import_third_country",
        "recargo_equivalencia",
        "regimen_simplificado",
        "reagp_compensation",
        "erroneous_invoice",
        "unknown",
    }
    catalogue = resolve_iva_category_catalogue(effective_date=_ON_DATE, authority=operation)
    assert {member.value for member in catalogue.all_categories} == expected


def test_iva_category_values_roundtrip_through_strenum(operation: PinnedAuthorityOperation) -> None:
    """Every IvaCategory value re-parses to the same member."""
    catalogue = resolve_iva_category_catalogue(effective_date=_ON_DATE, authority=operation)
    for member in catalogue.all_categories:
        assert catalogue.require(member.value) == member


def test_iva_category_catalogue_reuses_the_scoped_projection(operation: PinnedAuthorityOperation) -> None:
    """Repeated reads in one pinned operation do not rebuild immutable metadata."""
    first = resolve_iva_category_catalogue(effective_date=_ON_DATE, authority=operation)
    second = resolve_iva_category_catalogue(effective_date=_ON_DATE, authority=operation)

    assert second is first


def test_eu_member_state_has_27_strict_member_states_plus_xi_prefix(
    operation: PinnedAuthorityOperation,
) -> None:
    """EUMemberState covers the 27 EU states plus the post-Brexit XI IVA prefix."""
    catalogue = resolve_eu_member_state_catalogue(effective_date=_ON_DATE, authority=operation)
    xi = catalogue.require("xi")
    assert len([member for member in catalogue.choices if member != xi]) == 27
    assert xi.value == "xi"


def test_iva_rate_kind_has_five_tiers(operation: PinnedAuthorityOperation) -> None:
    """IvaRateKind covers the five tiers used by the substrate."""
    catalogue = resolve_iva_rate_kind_catalogue(effective_date=_ON_DATE, authority=operation)
    assert {kind.value for kind in catalogue.all_kinds} == {
        "general",
        "reduced",
        "super_reduced",
        "zero",
        "exempt",
    }
