"""The runtime executable's text envelope shows the sandbox banner as the CLI's does."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from cadrumo.adapters.persistence.storage.tests.committed_profile import create_committed_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import override_settings
from cadrumo.core.json_contract import Notice, NoticeSeverity

from ..presentation import emit_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "8f2c1a9e-4b3d-4c5e-9f6a-7b8c9d0e1f2a"


def _emit_text() -> list[str]:
    app = typer.Typer()
    notice = Notice(severity=NoticeSeverity.INFO, code="probe.code", message="probe message")

    @app.command()
    def probe(ctx: typer.Context) -> None:
        emit_envelope(ctx, command="probe", result=None, lines=["body"], notices=[notice])

    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0, result.output
    return result.output.splitlines()


def test_text_mode_prints_the_sandbox_banner_first_for_a_sandbox(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        create_committed_profile(storage_root, bucket_id=_BUCKET_ID, label="sandbox:runtime")
        with override_settings(cadrumo_active_profile=_BUCKET_ID):
            out = _emit_text()

    assert out[0].startswith("SANDBOX\t")
    assert out[1:] == ["body", "notice\tprobe.code\tprobe message"]


def test_text_mode_has_no_banner_for_a_real_profile(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        create_committed_profile(storage_root, bucket_id=_BUCKET_ID, label="real-profile")
        with override_settings(cadrumo_active_profile=_BUCKET_ID):
            out = _emit_text()

    assert out == ["body", "notice\tprobe.code\tprobe message"]
