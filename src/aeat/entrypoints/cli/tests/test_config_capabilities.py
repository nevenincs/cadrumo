"""Real-behaviour CLI tests for ``aeat config profile capabilities`` show/set.

Exercises the operator surface end to end against the real Typer app and real
persistence in an isolated storage root: setting a capability writes a profile
fact, and ``show`` resolves it back with its source. No mocks.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield


def _show() -> dict[str, dict]:
    result = _RUNNER.invoke(app, ["--format", "json", "config", "profile", "capabilities", "show"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["result"]["capabilities"]
    return {row["capability"]: row for row in rows}


def test_show_reports_every_capability_with_default_posture() -> None:
    rows = _show()
    assert set(rows) == {"cloud_evidence_upload", "llm_vision", "google_export"}
    # Defaults: cloud off (global), vision/google on (default).
    assert rows["cloud_evidence_upload"]["enabled"] is False
    assert rows["llm_vision"]["enabled"] is True
    assert rows["google_export"]["enabled"] is True


def test_set_disables_a_capability_and_show_reflects_it() -> None:
    setres = _RUNNER.invoke(
        app,
        ["--format", "json", "config", "profile", "capabilities", "set", "llm_vision", "off"],
    )
    assert setres.exit_code == 0, setres.output
    payload = json.loads(setres.output)["result"]
    assert payload["capability"] == "llm_vision" and payload["enabled"] is False

    rows = _show()
    assert rows["llm_vision"]["enabled"] is False
    assert rows["llm_vision"]["source"] == "profile"


def test_set_enables_cloud_upload_via_profile_opt_in() -> None:
    setres = _RUNNER.invoke(
        app,
        ["config", "profile", "capabilities", "set", "cloud_evidence_upload", "on"],
    )
    assert setres.exit_code == 0, setres.output
    rows = _show()
    assert rows["cloud_evidence_upload"]["enabled"] is True
    assert rows["cloud_evidence_upload"]["source"] == "profile"
