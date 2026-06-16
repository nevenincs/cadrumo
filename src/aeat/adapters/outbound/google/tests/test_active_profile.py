"""Tests for the Google OAuth active-profile resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.i18n import tr
from .._active_profile import resolve_active_profile
from .._errors import GoogleAuthProfileUnboundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_unbound_profile_uses_localised_suggestion(tmp_path: Path) -> None:
    """The resolver raises the adapter error with translated operator guidance."""

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None),
        pytest.raises(GoogleAuthProfileUnboundError) as exc_info,
    ):
        resolve_active_profile()

    expected = tr("adapters.google.profile_binding.suggestions.create_profile")
    assert exc_info.value.suggestion == expected
    assert expected != "adapters.google.profile_binding.suggestions.create_profile"
    assert exc_info.value.translated_message == "adapters.google.profile_binding.errors.no_active_profile"
