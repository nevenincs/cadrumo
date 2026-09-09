"""Cross-owner error typing contracts."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_censo_sync_error_typing() -> None:
    from ..application.user_profile.censo_errors import CensoSyncError
    from ..core.errors.hierarchy import CadrumoError

    assert issubclass(CensoSyncError, CadrumoError)
    assert not issubclass(CensoSyncError, ValueError)
