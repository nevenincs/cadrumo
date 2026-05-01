"""Unit tests for :mod:`aeat.portals._categories`."""

from __future__ import annotations

import pytest

from ._categories import AuthMethod, PortalCategory, Subdomain, UrlStability

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_portal_category_has_exactly_7_members() -> None:
    """ADR §3: 7 members."""
    expected = {
        PortalCategory.AUTH,
        PortalCategory.FILING,
        PortalCategory.CENSUS,
        PortalCategory.CONSULTATION,
        PortalCategory.BORRADOR,
        PortalCategory.PAYMENT,
        PortalCategory.CALENDAR_REFERENCE,
    }
    assert set(PortalCategory) == expected
    assert len(list(PortalCategory)) == 7


def test_auth_method_has_exactly_7_members() -> None:
    """ADR §3: 7 members including ANONYMOUS and REFERENCE_NUMBER."""
    expected = {
        AuthMethod.ANONYMOUS,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
        AuthMethod.REFERENCE_NUMBER,
    }
    assert set(AuthMethod) == expected
    assert len(list(AuthMethod)) == 7


def test_url_stability_has_exactly_4_members() -> None:
    """ADR §3: 4 tiers."""
    expected = {
        UrlStability.STABLE_PROTOCOL_GRADE,
        UrlStability.STABLE_WITHIN_CAMPAIGN,
        UrlStability.VOLATILE_APP_PATH,
        UrlStability.RETIRED,
    }
    assert set(UrlStability) == expected
    assert len(list(UrlStability)) == 4


def test_subdomain_has_exactly_7_members() -> None:
    """ADR §3: 7 hosts."""
    expected_values = {
        "sede.agenciatributaria.gob.es",
        "www1.agenciatributaria.gob.es",
        "www2.agenciatributaria.gob.es",
        "www3.agenciatributaria.gob.es",
        "agenciatributaria.gob.es",
        "www.agenciatributaria.es",
        "clave.gob.es",
    }
    assert {s.value for s in Subdomain} == expected_values
    assert len(list(Subdomain)) == 7


@pytest.mark.parametrize(
    "enum_cls",
    [PortalCategory, AuthMethod, UrlStability],
)
def test_enum_values_are_lowercase(enum_cls: type[PortalCategory | AuthMethod | UrlStability]) -> None:
    """Category-family enums use lowercase snake_case values."""
    for member in enum_cls:
        assert member.value == member.value.lower()
