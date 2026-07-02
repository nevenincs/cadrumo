"""Unit tests for :mod:`aeat.domain.portals._categories`."""

from __future__ import annotations

import pytest

from ....core.external_constants import load_external_constants
from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._hosts import portal_host_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("enum_cls", "expected_members"),
    [
        pytest.param(
            PortalCategory,
            {
                PortalCategory.AUTH,
                PortalCategory.FILING,
                PortalCategory.CENSO,
                PortalCategory.CONSULTATION,
                PortalCategory.BORRADOR,
                PortalCategory.PAYMENT,
                PortalCategory.CALENDAR_REFERENCE,
            },
            id="portal-category",
        ),
        pytest.param(
            AuthMethod,
            {
                AuthMethod.ANONYMOUS,
                AuthMethod.CLAVE_PIN,
                AuthMethod.CLAVE_PERMANENTE,
                AuthMethod.CLAVE_MOVIL,
                AuthMethod.CERTIFICATE,
                AuthMethod.DNIE,
                AuthMethod.REFERENCE_NUMBER,
            },
            id="auth-method",
        ),
        pytest.param(
            UrlStability,
            {
                UrlStability.STABLE_PROTOCOL_GRADE,
                UrlStability.STABLE_WITHIN_CAMPAIGN,
                UrlStability.VOLATILE_APP_PATH,
                UrlStability.RETIRED,
            },
            id="url-stability",
        ),
    ],
)
def test_category_family_enum_members(
    enum_cls: type[PortalCategory | AuthMethod | UrlStability],
    expected_members: set[PortalCategory | AuthMethod | UrlStability],
) -> None:
    """Category-family enums expose exactly the committed members."""
    assert set(enum_cls) == expected_members
    assert len(list(enum_cls)) == len(expected_members)


def test_subdomain_has_exactly_7_members() -> None:
    """The subdomain enum exposes exactly 7 central-registry keys."""
    expected_values = {
        "sede",
        "www1",
        "www2",
        "www3",
        "aeat_gob",
        "legacy_www",
        "clave",
    }
    assert {s.value for s in PortalHost} == expected_values
    assert len(list(PortalHost)) == 7


def test_subdomain_hosts_resolve_from_external_constants() -> None:
    """Portal hostnames come from the external constants registry."""
    domains = load_external_constants().aeat.domains
    expected_hosts = {
        domains.sede.removeprefix("https://"),
        domains.www1.removeprefix("https://"),
        domains.www2.removeprefix("https://"),
        domains.www3.removeprefix("https://"),
        domains.aeat_gob.removeprefix("https://"),
        domains.legacy_www.removeprefix("https://"),
        domains.clave.removeprefix("https://"),
    }
    assert {portal_host_name(subdomain) for subdomain in PortalHost} == expected_hosts


@pytest.mark.parametrize(
    "enum_cls",
    [PortalCategory, AuthMethod, UrlStability],
)
def test_enum_values_are_lowercase(enum_cls: type[PortalCategory | AuthMethod | UrlStability]) -> None:
    """Category-family enums use lowercase snake_case values."""
    for member in enum_cls:
        assert member.value == member.value.lower()
