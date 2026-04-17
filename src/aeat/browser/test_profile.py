"""Unit tests for the Profile model."""

import json
from pathlib import Path

import pytest

from aeat.browser.profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_profile_ensure_storage_dir(tmp_path: Path) -> None:
    """Test that ensure_storage_dir creates the path and writes valid JSON."""
    storage_path = tmp_path / "test_state.json"
    profile = Profile(name="test_profile", storage_state_path=storage_path)

    assert not storage_path.exists()
    profile.ensure_storage_dir()

    assert storage_path.exists()
    content = storage_path.read_text()
    assert json.loads(content) == {}
