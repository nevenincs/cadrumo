"""Unit tests for the Profile model."""

from pathlib import Path

import pytest

from .profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_profile_ensure_storage_dir(tmp_path: Path) -> None:
    """Test that ensure_storage_dir creates the parent directory only."""
    storage_path = tmp_path / "test_state.json"
    profile = Profile(name="test_profile", storage_state_path=storage_path)

    assert not storage_path.exists()
    profile.ensure_storage_dir()

    assert storage_path.parent.exists()
    assert not storage_path.exists()
