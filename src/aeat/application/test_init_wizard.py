"""Root ``aeat init`` wizard round-trip tests (UX-003)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'init.db').as_posix()}")


def test_aeat_init_quiet_mode_writes_profile_engine_can_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`aeat init --quiet ...` must write a profile the deadline engine reads.

    UX-003 closure check. The wizard sets tax.id + activity + iva.regime
    via the same backend setup init uses, then :func:`autonomo_profile_from_mapping`
    resolves iva.regime to ``IVARegime.GENERAL`` on the next read.
    """
    _isolate(monkeypatch, tmp_path)
    from aeat.application.workflow._persistence import workflow_state_repository
    from aeat.domain.deadlines import IVARegime, autonomo_profile_from_mapping
    from aeat.entrypoints.cli import app

    result = _RUNNER.invoke(
        app,
        [
            "init",
            "--quiet",
            "--name",
            "kent",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios profesionales",
            "--iva-regime",
            "general",
        ],
    )
    assert result.exit_code == 0, result.output

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    profile = autonomo_profile_from_mapping(record.values, tax_id_default="00000000T")
    assert profile.iva_regime is IVARegime.GENERAL


def test_aeat_init_quiet_mode_refuses_without_required_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`aeat init --quiet` without --name / --tax-id / --activity must exit 2."""
    _isolate(monkeypatch, tmp_path)
    from aeat.entrypoints.cli import app

    result = _RUNNER.invoke(app, ["init", "--quiet", "--name", "kent"])
    assert result.exit_code != 0
    assert "--quiet" in result.output or "name" in result.output
