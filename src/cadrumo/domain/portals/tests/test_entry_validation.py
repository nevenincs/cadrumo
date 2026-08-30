from __future__ import annotations

from typing import TypedDict, cast

import pytest

from .._entries.common import build_entry
from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..errors import PortalValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _PortalEntryOverrides(TypedDict, total=False):
    url: str
    path: str


@pytest.mark.parametrize(
    "kwargs",
    (
        {"url": "https://example.com", "path": "/also-present"},
        {"path": "no-leading-slash"},
    ),
)
def test_portal_validation_error_for_invalid_entry_shapes(kwargs: _PortalEntryOverrides) -> None:
    with pytest.raises(PortalValidationError) as raised:
        build_entry(
            portal=cast(Portal, None),
            subdomain=cast(PortalHost, None),
            category=cast(PortalCategory, None),
            auth_methods=cast(list[AuthMethod], []),
            url_stability=cast(UrlStability, None),
            label="test",
            purpose="test",
            **kwargs,
        )

    assert raised.type is PortalValidationError
