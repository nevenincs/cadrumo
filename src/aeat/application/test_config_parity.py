"""Parity tests: aeat config set and aeat config get read the same backend.

Pins the contract that ``aeat config set``, ``aeat config get`` and
``aeat config status`` share a single :class:`WorkflowState` backend:
operator-entered values written by one verb are visible to every
other verb in the group. The fixture seeds the workflow state
directly via :func:`workflow_state_repository().update(...)` so the
parity assertion does not depend on a wizard or initialisation
command for its setup.
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
    """Seed an active profile directly through the workflow state repository."""

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
    """A value written via 'aeat config set' must be readable via 'aeat config get'.

    Pins the single-backend contract: both verbs read and write the
    same WorkflowState.profiles record. Without that contract operators
    would maintain two divergent stores; this test fails if either
    verb gets carved out into a parallel store.
    """

    _isolate(monkeypatch, tmp_path)
    _seed_active_profile()

    from aeat.entrypoints.cli import app

    set_via_config = _RUNNER.invoke(app, ["config", "set", "iva.regime", "GENERAL"])
    assert set_via_config.exit_code == 0, set_via_config.output
    assert "GENERAL" in set_via_config.output

    get_via_config = _RUNNER.invoke(app, ["config", "get", "iva.regime"])
    assert get_via_config.exit_code == 0, get_via_config.output
    assert "GENERAL" in get_via_config.output


def test_config_set_then_config_status_surfaces_assigned_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written via 'aeat config set' must surface in 'aeat config status'.

    Mirror direction: the set writer feeds the readiness summary. The
    status command reads the same WorkflowState.profiles record the
    set verb writes; this test fails if the status surface carves
    out a parallel read path.
    """

    _isolate(monkeypatch, tmp_path)
    _seed_active_profile()

    from aeat.entrypoints.cli import app

    set_via_config = _RUNNER.invoke(app, ["config", "set", "iva.regime", "SIMPLIFICADO"])
    assert set_via_config.exit_code == 0, set_via_config.output

    status_result = _RUNNER.invoke(app, ["config", "status"])
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

    result = _RUNNER.invoke(app, ["config", "set", "not.a.real.key", "value"])
    assert result.exit_code != 0
    assert "not.a.real.key" in result.output
