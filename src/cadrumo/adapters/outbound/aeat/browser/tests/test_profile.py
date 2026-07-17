"""Unit tests for the Profile model."""

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from ..profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_profile_rejects_plaintext_storage_state_paths(tmp_path: Path) -> None:
    """Browser profiles cannot carry a Playwright storage-state file path."""
    constructor = cast("Callable[..., Profile]", Profile)
    with pytest.raises(TypeError, match="storage_state_path"):
        constructor(name="test-profile", storage_state_path=tmp_path / "state.json")


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


def test_profile_resolves_browser_defaults_on_construction() -> None:
    """An unsupplied locale/timezone is filled from Settings at construction."""

    from ......core.config import Settings

    settings = Settings()
    profile = Profile(name="defaults")

    assert profile.locale == settings.cadrumo_browser_locale
    assert profile.timezone_id == settings.cadrumo_browser_timezone


def test_profile_honours_explicit_locale_without_touching_settings() -> None:
    """An explicitly supplied locale bypasses the lazy default factory."""

    profile = Profile(
        name="explicit",
        locale="ca-ES",
        timezone_id="Atlantic/Canary",
    )

    assert profile.locale == "ca-ES"
    assert profile.timezone_id == "Atlantic/Canary"
