"""Negative-shape regression tests for surfaces that must NOT exist.

The CLI's two-root contract (config / app) and its noun-group
ordering encode a small number of "this verb has been retired or
relocated" decisions. These tests assert the rejected surfaces
remain rejected so a future drop or rename never quietly resurrects
the wrong shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'negative.db').as_posix()}")


def test_root_does_not_register_bare_reconcile_alias() -> None:
    """`aeat reconcile` is not a root verb; reconcile only lives
    under `aeat app modelo` per the apex CLI shape."""

    result = invoke_cached_cli(["reconcile", "--help"])
    assert result.exit_code != 0, result.output


def test_app_does_not_register_retired_deadlines_subgroup() -> None:
    """`aeat app deadlines` was retired in favour of the overview
    verb tree. The retired surface must remain unmounted."""

    result = invoke_cached_cli(["app", "deadlines", "--help"])
    assert result.exit_code != 0, result.output


def test_modelo_audit_export_remains_distinct_from_modelo_export() -> None:
    """The audit subgroup carries its own `export` verb; the modelo
    noun group must NOT register a sibling `aeat app modelo export`
    that could be confused with the audit-bundle exporter."""

    audit_help = invoke_cached_cli(["app", "modelo", "audit", "export", "--help"])
    assert audit_help.exit_code == 0, audit_help.output

    sibling = invoke_cached_cli(["app", "modelo", "export", "--help"])
    assert sibling.exit_code != 0, sibling.output
