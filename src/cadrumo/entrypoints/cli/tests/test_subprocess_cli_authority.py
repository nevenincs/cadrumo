"""Authority propagation at the shared fresh-process CLI boundary."""

from __future__ import annotations

import pytest

from .subprocess_cli import subprocess_cli_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_authority_selector_survives_a_full_product_environment_scrub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the read-only authority selector while isolating storage settings."""
    authority_root = r"Y:\authority-snapshot"
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", authority_root)
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", r"Y:\ambient-storage")
    monkeypatch.setenv("CADRUMO_SECRET_PASSPHRASE", "ambient-secret")

    environment = subprocess_cli_env(strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"))

    assert environment["CADRUMO_AUTHORITY_ROOT"] == authority_root
    assert "CADRUMO_LOCAL_STORAGE_ROOT" not in environment
    assert "CADRUMO_SECRET_PASSPHRASE" not in environment


def test_explicit_authority_override_wins_over_the_parent_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers can select a different published authority deliberately."""
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", r"Y:\parent-authority")

    environment = subprocess_cli_env(
        strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
        extra={"CADRUMO_AUTHORITY_ROOT": r"Y:\explicit-authority"},
    )

    assert environment["CADRUMO_AUTHORITY_ROOT"] == r"Y:\explicit-authority"
