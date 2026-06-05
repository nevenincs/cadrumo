"""Unit tests for the Profile model."""

from pathlib import Path

import pytest

from ..profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_profile_ensure_storage_dir(tmp_path: Path) -> None:
    """Test that ensure_storage_dir creates the parent directory only."""
    storage_path = tmp_path / "test_state.json"
    profile = Profile(name="test_profile", storage_state_path=storage_path)

    assert not storage_path.exists()
    profile.ensure_storage_dir()

    assert storage_path.parent.exists()
    assert not storage_path.exists()


def test_importing_profile_module_does_not_construct_settings() -> None:
    """Importing the browser-profile module must not build Settings.

    A module-import-time ``Settings()`` validates the external-
    constants payload; a transient data/model disagreement there
    would crash an unrelated command (even ``--help``). The
    construction is deferred to ``Profile`` instantiation, so the
    module exposes lazy default factories rather than a pre-built
    settings instance.
    """

    from .. import profile as profile_module

    # No pre-built settings instance is held at module scope.
    assert not hasattr(profile_module, "_BROWSER_DEFAULTS")
    # The defaults are resolved through callables, not a captured object.
    assert callable(profile_module._browser_locale_default)
    assert callable(profile_module._browser_timezone_default)


def test_profile_resolves_browser_defaults_on_construction(tmp_path: Path) -> None:
    """An unsupplied locale/timezone is filled from Settings at construction."""

    from ......core.config import Settings

    settings = Settings()
    profile = Profile(name="defaults", storage_state_path=tmp_path / "state.json")

    assert profile.locale == settings.aeat_browser_locale
    assert profile.timezone_id == settings.aeat_browser_timezone


def test_profile_honours_explicit_locale_without_touching_settings(tmp_path: Path) -> None:
    """An explicitly supplied locale bypasses the lazy default factory."""

    profile = Profile(
        name="explicit",
        storage_state_path=tmp_path / "state.json",
        locale="ca-ES",
        timezone_id="Atlantic/Canary",
    )

    assert profile.locale == "ca-ES"
    assert profile.timezone_id == "Atlantic/Canary"
