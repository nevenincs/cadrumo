"""CLI surface tests for `aeat app live justificante {list, view}`.

The ``capture`` verb is a live read (covered by the application-layer
orchestrator and the opt-in live test); these tests exercise the local
read verbs and the registration wiring without contacting AEAT.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from .._app_live import justificante_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(aeat_audit_dir=tmp_path / "audit"),
        profile_create_storage_span("default"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield


def test_justificante_list_is_empty_on_fresh_bucket(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(justificante_app, ["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_justificante_view_refuses_unknown_snapshot(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(justificante_app, ["view", "no-such-snapshot"])
    assert result.exit_code != 0
