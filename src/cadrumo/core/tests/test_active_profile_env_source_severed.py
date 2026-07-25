"""No environment source selects the active profile.

Profile selection has exactly two writers: the ``active-profile`` pointer
file, and the in-process override channel the ``--profile`` flag and
:func:`override_settings` write through. ``CADRUMO_ACTIVE_PROFILE`` used to
be a third, highest-precedence writer; it was a development override that
operators adopted as the operating mechanism, which let a shell variable
outrank the on-disk pointer and left ``logout`` unable to clear a selection
the application boundary could not unset.

These tests prove both halves of that severance: the environment no longer
reaches the field, and the channel that replaced it still works. They set
real environment variables and write a real dotenv file, then construct a
real ``Settings``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from ...tests.env_scope import scoped_env_var
from ..config import Settings, override_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ENV_NAME = "CADRUMO_ACTIVE_PROFILE"
_SENTINEL = "env-must-not-select-me"


@pytest.fixture
def _dotenv_settings_class(tmp_path: Path) -> type[Settings]:
    """Return a Settings subclass bound to a temp dotenv this test owns."""

    class DotEnvBoundSettings(Settings):
        """Settings variant reading only the temp dotenv."""

        model_config = SettingsConfigDict(
            env_file=tmp_path / ".env",
            env_file_encoding="utf-8",
            env_ignore_empty=True,
        )

    return DotEnvBoundSettings


@pytest.fixture(autouse=True)
def _no_ambient_selection() -> Iterator[None]:
    """Start every case with no ambient selection in the environment."""
    with scoped_env_var(_ENV_NAME, None):
        yield


class TestEnvironmentSourceIsSevered:
    """No environment channel populates the active-profile field."""

    def test_process_environment_does_not_select_a_profile(self) -> None:
        with scoped_env_var(_ENV_NAME, _SENTINEL):
            assert Settings().cadrumo_active_profile is None

    def test_dotenv_file_does_not_select_a_profile(
        self,
        tmp_path: Path,
        _dotenv_settings_class: type[Settings],
    ) -> None:
        (tmp_path / ".env").write_text(f"{_ENV_NAME}={_SENTINEL}\n", encoding="utf-8")

        assert _dotenv_settings_class().cadrumo_active_profile is None

    def test_the_field_is_absent_from_the_environment_inventory(self) -> None:
        """The documented env-var set must not advertise a dead control."""
        assert _ENV_NAME not in Settings.env_var_names()

    def test_a_neighbouring_field_still_reads_its_environment_variable(self) -> None:
        """Anti-tautology: the severance is field-scoped, not a dead source.

        Without this, a filter that silently dropped EVERY environment
        variable would pass every assertion above.
        """
        with scoped_env_var("CADRUMO_BUCKET_DEFAULT_SESSION_ABSOLUTE_MINUTES", "300"):
            assert Settings().cadrumo_bucket_default_session_absolute_minutes == 300


class TestSurvivingSelectionChannel:
    """The in-process channel that replaced the env var still works."""

    def test_override_settings_still_selects_a_profile(self) -> None:
        with override_settings(cadrumo_active_profile="chosen-in-process") as settings:
            assert settings.cadrumo_active_profile == "chosen-in-process"

    def test_direct_construction_still_selects_a_profile(self) -> None:
        """The init channel underneath the ``--profile`` flag."""
        assert Settings(cadrumo_active_profile="chosen-by-flag").cadrumo_active_profile == "chosen-by-flag"

    def test_the_in_process_channel_wins_over_a_set_environment_variable(self) -> None:
        """A stale exported variable cannot contradict an explicit selection."""
        with (
            scoped_env_var(_ENV_NAME, _SENTINEL),
            override_settings(cadrumo_active_profile="chosen-in-process") as settings,
        ):
            assert settings.cadrumo_active_profile == "chosen-in-process"
