"""The managing runtime owns composition and integration of the tax interfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SOURCE = Path(__file__).resolve().parents[4]


def test_installed_composition_and_native_journeys_are_runtime_owned() -> None:
    product = _SOURCE / "cadrumo" / "entrypoints" / "tui"
    host = _SOURCE / "cadrumo_runtime" / "host"
    assert not (product / "installed_session.py").exists()
    assert not (product / "runtime_admission.py").exists()
    assert (host / "frontend" / "tui" / "installed_session.py").is_file()
    assert (host / "frontend" / "cli" / "app.py").is_file()
    assert (host / "tests" / "frontend" / "tui" / "test_profile_wizard_native.py").is_file()
