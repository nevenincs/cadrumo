"""Tests for the Google OAuth active-profile resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from ..active_profile import resolve_active_profile
from ..errors import GoogleAuthProfileUnboundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_unbound_profile_carries_only_the_failed_resolution_fact(tmp_path: Path) -> None:
    """The adapter surfaces the unresolved profile without a recovery transport."""

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None),
        pytest.raises(GoogleAuthProfileUnboundError) as exc_info,
    ):
        resolve_active_profile()

    assert exc_info.value.context == {"active_profile": ""}
    assert not hasattr(exc_info.value, "suggestion")
    assert exc_info.value.translated_message == "adapters.google.profile_binding.errors.no_active_profile"
