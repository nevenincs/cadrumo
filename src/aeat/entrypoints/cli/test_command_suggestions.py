"""Tests for the AEAT CLI command-suggestion group.

The base Typer group only suggests typo-distance near misses. These
tests cover the two operator-facing gaps :class:`AeatTyperGroup`
closes: a semantic synonym (``modify`` -> ``edit``) and a cross-path
command (``app status`` -> ``app overview status``).
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
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'suggest.db').as_posix()}")


def test_profile_modify_suggests_edit() -> None:
    """``config profile modify`` suggests the canonical ``edit`` verb.

    The edit distance between ``modify`` and ``edit`` is too large for
    Typer's fuzzy matcher; the synonym table bridges the gap.
    """

    result = invoke_cached_cli(["config", "profile", "modify", "alice"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "modify" in flat
    assert "edit" in flat


def test_app_status_suggests_overview_status() -> None:
    """``app status`` suggests the cross-path ``app overview status``."""

    result = invoke_cached_cli(["app", "status"])

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "overview status" in flat


def test_unknown_command_with_no_synonym_still_fails_cleanly() -> None:
    """A genuinely unknown command with no synonym still fails without a trace."""

    result = invoke_cached_cli(["config", "profile", "zzzznonsense"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
