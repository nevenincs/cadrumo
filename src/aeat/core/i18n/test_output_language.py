"""Profile-owned output-language resolution tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_language_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)
    monkeypatch.delenv("AEAT_CLI_LANGUAGE", raising=False)
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'language.db').as_posix()}")
    try:
        yield
    finally:
        dispose_engine()


def _seed_profile_language(language: str) -> None:
    from aeat.application.profile._actions import set_active_profile, set_profile_values
    from aeat.application.workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    repository.update(lambda state: set_active_profile(state, "default"))
    repository.update(lambda state: set_profile_values(state, "default", {"output.language": language}))


def test_output_language_reads_active_profile_without_emitting_bucket_events(
    isolated_language_state: None,
) -> None:
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
    _seed_profile_language("ca")

    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")

    assert output_language() == "en"


def test_cli_language_override_wins_over_environment_and_profile(
    isolated_language_state: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_profile_language("ca")

    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "es")
    monkeypatch.setenv("AEAT_CLI_LANGUAGE", "hu")

    assert output_language() == "hu"


def test_clean_install_defaults_to_english(isolated_language_state: None) -> None:
    assert output_language() == "en"


def test_unsupported_profile_output_language_falls_back_to_settings_default(
    isolated_language_state: None,
) -> None:
    _seed_profile_language("zz")

    assert output_language() == "en"
