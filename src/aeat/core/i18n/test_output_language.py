"""Profile-owned output-language resolution tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_language_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)
    # Per-bucket storage: the seeded profile writes a bucket manifest,
    # an encrypted record, and the active-profile pointer under the
    # storage root — redirect it into tmp so the test stays isolated.
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'language.db').as_posix()}")
    # The column-encrypt path requires an active bucket session even
    # for seeding; an ephemeral provider supplies one for the test.
    with EphemeralMasterKeyProvider():
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_language_state
    _seed_profile_language("ca")

    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")

    assert output_language() == "en"


def test_environment_output_language_override_is_canonical(
    isolated_language_state: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_language_state
    _seed_profile_language("ca")

    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "es")

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
