"""Parity tests: aeat config and aeat setup profile read the same backend."""

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


def test_config_set_round_trips_through_setup_profile_get(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written via 'aeat config set' must be readable via 'aeat setup profile get'.

    Pins the W13 alias contract: both surfaces read and write the same
    WorkflowState.profiles backend. Without that contract operators
    would maintain two divergent stores; this test fails if either
    surface gets carved out into a parallel store.
    """
    _isolate(monkeypatch, tmp_path)
    from aeat.entrypoints.cli import app

    init = _RUNNER.invoke(app, ["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "design"])
    assert init.exit_code == 0, init.output

    set_via_config = _RUNNER.invoke(app, ["config", "set", "iva.regime", "general"])
    assert set_via_config.exit_code == 0, set_via_config.output
    assert "general" in set_via_config.output

    get_via_setup = _RUNNER.invoke(app, ["setup", "profile", "get", "iva.regime"])
    assert get_via_setup.exit_code == 0, get_via_setup.output
    assert "general" in get_via_setup.output


def test_setup_profile_set_round_trips_through_config_get(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A value written via 'aeat setup profile set' must be readable via 'aeat config get'.

    Mirror test in the opposite direction: setup-profile writer feeds
    the config reader.
    """
    _isolate(monkeypatch, tmp_path)
    from aeat.entrypoints.cli import app

    init = _RUNNER.invoke(app, ["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "design"])
    assert init.exit_code == 0, init.output

    set_via_setup = _RUNNER.invoke(app, ["setup", "profile", "set", "iva.regime", "simplificado"])
    assert set_via_setup.exit_code == 0, set_via_setup.output

    get_via_config = _RUNNER.invoke(app, ["config", "get", "iva.regime"])
    assert get_via_config.exit_code == 0, get_via_config.output
    assert "simplificado" in get_via_config.output


def test_config_set_refuses_unknown_key_with_typed_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unknown keys must be rejected with a typed CLI usage error."""
    _isolate(monkeypatch, tmp_path)
    from aeat.entrypoints.cli import app

    init = _RUNNER.invoke(app, ["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "design"])
    assert init.exit_code == 0, init.output

    result = _RUNNER.invoke(app, ["config", "set", "not.a.real.key", "value"])
    assert result.exit_code != 0
    assert "not.a.real.key" in result.output
