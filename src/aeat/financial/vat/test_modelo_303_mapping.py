"""Unit tests for the Modelo 303 casilla bridge (#183)."""

from __future__ import annotations

import pytest

from . import (
    MODELO_303_CASILLA_MAPPING,
    CasillaRole,
    InvoiceDirection,
    Modelo303Contribution,
    VATCategory,
    VATRateKind,
    lookup_modelo_303_contribution,
)
from ._modelo_303_mapping import _OUT_OF_SCOPE_V1

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def test_every_vat_category_is_either_mapped_or_out_of_scope() -> None:
    """Every :class:`VATCategory` member must be classified.

    Missing the test ⇒ silent classification drift.
    """
    mapped = {category for category, _ in MODELO_303_CASILLA_MAPPING}
    seen = mapped | _OUT_OF_SCOPE_V1
    missing = [member for member in VATCategory if member not in seen]
    assert missing == [], f"unhandled VATCategory members: {missing}"


def test_no_overlap_between_mapping_and_out_of_scope() -> None:
    """A category cannot be both mapped and explicitly out-of-scope."""
    mapped = {category for category, _ in MODELO_303_CASILLA_MAPPING}
    overlap = mapped & _OUT_OF_SCOPE_V1
    assert overlap == set(), f"categories listed in both mapping + out-of-scope: {overlap}"


def test_mapping_is_immutable() -> None:
    """The mapping is a MappingProxyType; runtime mutation must fail."""
    from types import MappingProxyType

    assert isinstance(MODELO_303_CASILLA_MAPPING, MappingProxyType)


def test_lookup_returns_empty_for_out_of_scope_category() -> None:
    """Unmapped + out-of-scope categories return ``()``."""
    contributions = lookup_modelo_303_contribution(
        category=VATCategory.UNKNOWN,
        direction=InvoiceDirection.RECEIVED,
    )
    assert contributions == ()


def test_domestic_general_21_issued_lands_on_07() -> None:
    contributions = lookup_modelo_303_contribution(
        category=VATCategory.DOMESTIC_GENERAL_21,
        direction=InvoiceDirection.ISSUED,
    )
    assert contributions == (
        Modelo303Contribution(
            casilla_id="07",
            role=CasillaRole.BASE,
            sign=1,
            rate_kind=VATRateKind.GENERAL,
        ),
    )


def test_domestic_general_21_received_lands_on_28_29() -> None:
    contributions = lookup_modelo_303_contribution(
        category=VATCategory.DOMESTIC_GENERAL_21,
        direction=InvoiceDirection.RECEIVED,
    )
    assert {(c.casilla_id, c.role) for c in contributions} == {
        ("28", CasillaRole.BASE),
        ("29", CasillaRole.CUOTA),
    }


def test_intra_community_acquisition_lands_on_36_37() -> None:
    contributions = lookup_modelo_303_contribution(
        category=VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        direction=InvoiceDirection.RECEIVED,
    )
    assert {(c.casilla_id, c.role) for c in contributions} == {
        ("36", CasillaRole.BASE),
        ("37", CasillaRole.CUOTA),
    }


def test_import_third_country_lands_on_32_33() -> None:
    contributions = lookup_modelo_303_contribution(
        category=VATCategory.IMPORT_THIRD_COUNTRY,
        direction=InvoiceDirection.RECEIVED,
    )
    assert {(c.casilla_id, c.role) for c in contributions} == {
        ("32", CasillaRole.BASE),
        ("33", CasillaRole.CUOTA),
    }


def test_modelo_303_contribution_rejects_zero_sign() -> None:
    """Sign must be ±1; zero is not modelable."""
    with pytest.raises(ValueError, match="must be -1 or"):
        Modelo303Contribution(casilla_id="07", role=CasillaRole.BASE, sign=0)


def test_every_contribution_has_valid_shape() -> None:
    """Every shipped contribution validates: casilla id length + sign."""
    for contributions in MODELO_303_CASILLA_MAPPING.values():
        for contribution in contributions:
            assert 2 <= len(contribution.casilla_id) <= 4
            assert contribution.sign in {-1, 1}
            assert contribution.role in {CasillaRole.BASE, CasillaRole.CUOTA}
