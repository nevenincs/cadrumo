"""Parity tests: aeat config profile set/get read the same profile bucket.

Pins the contract that ``aeat config profile set``, ``aeat config
profile get`` and ``aeat config profile status`` share the active
profile bucket selected by ``WorkflowState``. Operator-entered values
written by one verb are visible to every other verb in the group.
"""

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
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'parity.db').as_posix()}")


def _seed_active_profile(tax_id: str = "00000000T", activity: str = "design") -> None:
    """Seed an active profile through the profile application service."""

    from aeat.application.profile._actions import set_active_profile, set_profile_values
    from aeat.application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    repo.update(lambda state: set_active_profile(state, "default"))
    repo.update(
        lambda state: set_profile_values(
            state,
            "default",
            {"tax.id": tax_id, "activity": activity, "name": "kent"},
        )
    )


def test_config_set_then_config_get_round_trips_iva_regime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written via config profile set is readable via config profile get.

    Pins the profile-bucket contract: both verbs read and write the
    same profile-associated secure bucket selected by workflow state.
    """

    _isolate(monkeypatch, tmp_path)
    _seed_active_profile()

    from aeat.entrypoints.cli import app

    set_via_config = _RUNNER.invoke(app, ["config", "profile", "set", "iva.regime", "GENERAL"])
    assert set_via_config.exit_code == 0, set_via_config.output
    assert "GENERAL" in set_via_config.output

    get_via_config = _RUNNER.invoke(app, ["config", "profile", "get", "iva.regime"])
    assert get_via_config.exit_code == 0, get_via_config.output
    assert "GENERAL" in get_via_config.output

    from aeat.application.profile._repository import profile_bucket_repository
    from aeat.application.workflow._persistence import workflow_state_repository

    workflow_state = workflow_state_repository().load()
    assert workflow_state.profiles["default"] == {"bucket_id": "default"}
    bucket = profile_bucket_repository().load("default")
    assert bucket is not None
    assert bucket.values["iva.regime"] == "GENERAL"


def test_config_set_then_config_status_surfaces_assigned_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written via config profile set surfaces in config profile status.

    Mirror direction: the set writer feeds the readiness summary. The
    status command reads the same profile-associated secure bucket the
    set verb writes.
    """

    _isolate(monkeypatch, tmp_path)
    _seed_active_profile()

    from aeat.entrypoints.cli import app

    set_via_config = _RUNNER.invoke(app, ["config", "profile", "set", "iva.regime", "SIMPLIFICADO"])
    assert set_via_config.exit_code == 0, set_via_config.output

    status_result = _RUNNER.invoke(app, ["config", "profile", "status"])
    assert status_result.exit_code == 0, status_result.output
    assert "SIMPLIFICADO" in status_result.output


def test_config_set_refuses_unknown_key_with_typed_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unknown keys must be rejected with a typed CLI usage error."""

    _isolate(monkeypatch, tmp_path)
    _seed_active_profile()

    from aeat.entrypoints.cli import app

    result = _RUNNER.invoke(app, ["config", "profile", "set", "not.a.real.key", "value"])
    assert result.exit_code != 0
    assert "not.a.real.key" in result.output
