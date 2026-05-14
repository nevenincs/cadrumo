"""CLI behavior tests for profile-owned output language."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _json_output(result: Any) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    return match.group(0) if match else result.output


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'profile-language.db').as_posix()}")
    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)
    dispose_engine()


def _seed_profile() -> None:
    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    repository.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides={"identity.tax_id": "00000000T", "activities.description": "Servicios"},
        )
    )


def test_config_init_writes_profile_output_language(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.core.i18n import output_language

    _isolate(monkeypatch, tmp_path)

    init_result = _invoke(
        [
            "config",
            "init",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
            "--tax-residence-ccaa",
            "madrid",
            "--output-language",
            "en",
        ]
    )
    get_result = _invoke(["--format", "json", "config", "profile", "get", "preferences.output_language"])

    assert init_result.exit_code == 0, init_result.output
    assert get_result.exit_code == 0, get_result.output
    assert json.loads(_json_output(get_result))["value"] == "en"
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    from aeat.application.user_profile._orchestration import fact_value

    assert fact_value(record, "preferences.output_language") == "en"
    assert ("profile.created", "default", "default") in [
        (event.action, event.bucket_id, event.object_id) for event in state.bucket_events
    ]
    assert ("profile.selected", "default", "default") in [
        (event.action, event.bucket_id, event.object_id) for event in state.bucket_events
    ]
    assert output_language() == "en"


def test_config_profile_set_validates_profile_output_language(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.core.i18n import output_language

    _isolate(monkeypatch, tmp_path)
    _seed_profile()

    set_result = _invoke(["config", "profile", "set", "preferences.output_language", "ca"])
    get_result = _invoke(["--format", "json", "config", "profile", "get", "preferences.output_language"])
    invalid_result = _invoke(["config", "profile", "set", "preferences.output_language", "zz"])

    assert set_result.exit_code == 0, set_result.output
    assert get_result.exit_code == 0, get_result.output
    assert json.loads(_json_output(get_result))["value"] == "ca"
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    from aeat.application.user_profile._orchestration import fact_value

    assert fact_value(record, "preferences.output_language") == "ca"
    assert output_language() == "ca"
    assert invalid_result.exit_code != 0
    assert "zz" in invalid_result.output
    assert "Traceback" not in invalid_result.output
    reloaded = workflow_state_repository().load().active_profile_record()
    assert reloaded is not None
    assert fact_value(reloaded, "preferences.output_language") == "ca"


def test_global_language_flag_overrides_profile_for_invocation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.application.user_profile._orchestration import set_active_field
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.core.i18n import output_language
    from aeat.domain.user_profile import UserProfileFact

    _isolate(monkeypatch, tmp_path)
    _seed_profile()
    workflow_state_repository().update(
        lambda state: set_active_field(state, UserProfileFact(path="preferences.output_language", value="ca"))
    )

    result = _invoke(["--language", "en", "--format", "json"])

    # The --language flag's effect is scoped to the CLI invocation via
    # override_settings(...) on the Click context. Once the invocation
    # completes, the override unwinds — the test cannot observe the
    # in-process override after _invoke returns. Exit code is the
    # contract we can verify here; the in-block effect is verified
    # directly by test_render_override.py in core/i18n.
    assert result.exit_code == 0, result.output
    # The profile language survives the invocation untouched.
    assert output_language() == "ca"
