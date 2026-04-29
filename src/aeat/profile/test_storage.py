"""Unit tests for tax-residence JSON storage."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from . import CCAA, KentTaxResidence, load_tax_residence, save_tax_residence
from ._storage import _default_path, clear_json, load_json

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_round_trip_json_serialization(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    residence = KentTaxResidence(ccaa=CCAA.GALICIA)
    save_tax_residence(residence, target)
    assert load_tax_residence(target) == residence


def test_atomic_write_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    save_tax_residence(KentTaxResidence(ccaa=CCAA.MADRID), target)
    save_tax_residence(KentTaxResidence(ccaa=CCAA.CATALUNA), target)
    residence = load_tax_residence(target)
    assert residence is not None
    assert residence.ccaa is CCAA.CATALUNA
    assert not list(tmp_path.glob("*.tmp"))


def test_clear_removes_profile(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    save_tax_residence(KentTaxResidence(ccaa=CCAA.MURCIA), target)
    clear_json(target)
    assert load_json(target) is None


def test_default_path_resolution_linux_xdg() -> None:
    path = _default_path({"XDG_CONFIG_HOME": "/home/kent/.config"}, "posix")
    assert path == Path("/home/kent/.config") / "aeat" / "tax-residence.json"


def test_default_path_resolution_windows_appdata() -> None:
    path = _default_path({"APPDATA": r"C:\Users\Kent\AppData\Roaming"}, "nt")
    assert str(path).endswith(os.path.join("aeat", "tax-residence.json"))
    assert "AppData" in str(path)
