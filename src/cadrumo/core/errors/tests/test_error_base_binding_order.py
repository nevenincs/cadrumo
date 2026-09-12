"""Regression proof for the core error hierarchy."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_hierarchy_owns_the_base_classes() -> None:
    """The relocation that made the guard possible must not be undone."""
    from ..hierarchy import CadrumoError, CoreError
    from ..not_found import CoreNotFoundError

    assert issubclass(CoreError, CadrumoError)
    assert issubclass(CoreNotFoundError, CoreError)
    assert CoreError.__module__ == "cadrumo.core.errors.hierarchy"
