"""Profile-owned output-language resolution tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.core.config import override_settings
from aeat.tests.secure_sql import isolated_profile_storage_root

from ._render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_language_state(tmp_path: Path) -> Iterator[None]:
    """Use override_settings (live-tests-friendly) instead of
    monkeypatch.delenv per the project no-monkeypatch mandate
    (CLAUDE.md). Empty-string aeat_output_language pins the unset
    state via ContextVar; ambient env values are shadowed.
    """

    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    with (
        override_settings(aeat_output_language=""),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _seed_profile_language(language: str) -> None:
    from aeat.application.user_profile._orchestration import set_active_field
    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.domain.user_profile import UserProfileFact

    repository = workflow_state_repository()
    repository.update(lambda state: register_minimal_profile(state, profile_id="default"))
    repository.update(
        lambda state: set_active_field(state, UserProfileFact(path="preferences.output_language", value=language))
    )


def test_output_language_reads_active_profile_without_emitting_bucket_events(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    from aeat.application.workflow._persistence import workflow_state_repository

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
