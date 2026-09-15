from __future__ import annotations

from operator import methodcaller
from typing import TypedDict

import pytest

from .._entries.common import build_entry
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
        methodcaller(
            "__call__",
            portal=None,
            subdomain=None,
            category=None,
            auth_methods=[],
            url_stability=None,
            label="test",
            purpose="test",
            **kwargs,
        )(build_entry)

    assert raised.type is PortalValidationError
