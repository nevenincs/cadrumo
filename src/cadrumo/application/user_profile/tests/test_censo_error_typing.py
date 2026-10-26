"""Cross-owner error typing contracts."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_censo_sync_error_typing() -> None:
    from ....core.errors.hierarchy import CadrumoError
    from ..censo_errors import CensoSyncError

    assert issubclass(CensoSyncError, CadrumoError)
    assert not issubclass(CensoSyncError, ValueError)
