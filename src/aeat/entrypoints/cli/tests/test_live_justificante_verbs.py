"""CLI surface tests for `aeat app live justificante {list, view}`.

The ``capture`` verb is a live read (covered by the application-layer
orchestrator and the opt-in live test); these tests exercise the local
read verbs and the registration wiring without contacting AEAT.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.live import JustificanteCaptureSnapshotService
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
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


def test_justificante_capture_command_is_not_registered(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(justificante_app, ["capture", "--help"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_justificante_view_refuses_unknown_snapshot(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(justificante_app, ["view", "no-such-snapshot"])
    assert result.exit_code != 0


def test_justificante_list_and_view_emit_registry_period_tokens(cli_runner: CliRunner) -> None:
    pdf_bytes = b"%PDF-1.4\njustificante period cli smoke\n%%EOF"
    snapshot = JustificanteCaptureSnapshotService(bucket_id="default").capture(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=datetime(2026, 4, 20, 10, 30, tzinfo=UTC),
    )

    listed = cli_runner.invoke(justificante_app, ["list"])
    assert listed.exit_code == 0, listed.output
    assert f"{snapshot.snapshot_id}\t130\t2026\t1T\t" in listed.output
    assert "2026 1T" not in listed.output

    viewed = cli_runner.invoke(justificante_app, ["view", snapshot.snapshot_id[:12]])
    assert viewed.exit_code == 0, viewed.output
    assert "period\t1T" in viewed.output
    assert "period\t2026 1T" not in viewed.output
