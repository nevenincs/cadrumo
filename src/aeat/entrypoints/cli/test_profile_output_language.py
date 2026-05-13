"""CLI behavior tests for profile-owned output language."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _invoke(args: list[str]):
    return _RUNNER.invoke(app, args)


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
    from aeat.application.profile._actions import set_active_profile, set_profile_values
    from aeat.application.workflow._persistence import workflow_state_repository

    repository = workflow_state_repository()
    repository.update(lambda state: set_active_profile(state, "default"))
    repository.update(
        lambda state: set_profile_values(
            state,
            "default",
            {"tax.id": "00000000T", "activity": "Servicios"},
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
            "--output-language",
            "en",
        ]
    )
    get_result = _invoke(["--format", "json", "config", "profile", "get", "output.language"])

    assert init_result.exit_code == 0, init_result.output
    assert get_result.exit_code == 0, get_result.output
    assert json.loads(_json_output(get_result))["value"] == "en"
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    assert record.values["output.language"] == "en"
    assert ("profile.created", "default", "default") in [
        (event.action, event.bucket_id, event.object_id) for event in state.bucket_events
    ]
    assert any(
        event.action == "profile.values.updated"
        and event.bucket_id == "default"
        and event.object_id is not None
        and "output.language" in event.object_id
        for event in state.bucket_events
    )
    assert output_language() == "en"


def test_config_profile_set_validates_profile_output_language(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.core.i18n import output_language

    _isolate(monkeypatch, tmp_path)
    _seed_profile()

    set_result = _invoke(["config", "profile", "set", "output.language", "ca"])
    get_result = _invoke(["--format", "json", "config", "profile", "get", "output.language"])
    invalid_result = _invoke(["config", "profile", "set", "output.language", "zz"])

    assert set_result.exit_code == 0, set_result.output
    assert get_result.exit_code == 0, get_result.output
    assert json.loads(_json_output(get_result))["value"] == "ca"
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    assert record.values["output.language"] == "ca"
    assert output_language() == "ca"
    assert invalid_result.exit_code != 0
    assert "zz" in invalid_result.output
    assert "Traceback" not in invalid_result.output
    reloaded = workflow_state_repository().load().active_profile_record()
    assert reloaded is not None
    assert reloaded.values["output.language"] == "ca"
