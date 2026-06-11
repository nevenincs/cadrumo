"""Integration tests for profile-owned output-language resolution.

Tests exercise the full application stack: language preference is stored
in the active profile via the workflow state repository and read back
through core.i18n._render.output_language. Requires an isolated storage
runtime for each test (no shared global state).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..application.user_profile._orchestration import profile_create_storage_span
from ..core.config import override_settings
from ..core.i18n._render import output_language
from .secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def isolated_language_state(tmp_path: Path) -> Iterator[None]:
    """Pin the unset-language state via ContextVar and bootstrap a
    real profile storage span.

    Empty-string ``aeat_output_language`` shadows any ambient env
    value; the storage-isolation + profile-create span gives the
    locale resolver a real backing store to read from.
    """

    with (
        override_settings(aeat_output_language=""),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        yield


def _seed_profile_language(language: str) -> None:
    from ..application.user_profile._orchestration import set_active_field
    from ..application.user_profile._testing import register_minimal_profile
    from ..application.workflow._persistence import workflow_state_repository
    from ..domain.user_profile import UserProfileFact

    repository = workflow_state_repository()
    repository.update(lambda state: register_minimal_profile(state, profile_id="default"))
    repository.update(
        lambda state: set_active_field(state, UserProfileFact(path="preferences.output_language", value=language)),
    )


def test_output_language_reads_active_profile_without_emitting_bucket_events(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    from ..application.workflow._persistence import workflow_state_repository

    _seed_profile_language("ca")
    repository = workflow_state_repository()
    before = len(repository.load().bucket_events)

    assert output_language() == "ca"

    assert len(repository.load().bucket_events) == before


def test_environment_output_language_override_wins_over_profile(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    _seed_profile_language("ca")

    with override_settings(aeat_output_language="en"):
        assert output_language() == "en"


def test_environment_output_language_override_is_canonical(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    _seed_profile_language("ca")

    with override_settings(aeat_output_language="es"):
        assert output_language() == "es"


def test_clean_install_defaults_to_spanish(isolated_language_state: None) -> None:
    del isolated_language_state
    assert output_language() == "es"


def test_unsupported_profile_output_language_falls_back_to_settings_default(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    _seed_profile_language("zz")

    assert output_language() == "es"
