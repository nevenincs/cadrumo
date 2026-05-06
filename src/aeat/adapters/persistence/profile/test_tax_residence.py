"""Unit tests for tax-residence JSON persistence.

Covers round-tripping :class:`aeat.domain.profile.TaxResidenceProfile`,
atomic write semantics (no orphan tempfiles, even on serialization failure),
clear semantics, and OS-specific default-path resolution for both
:envvar:`XDG_CONFIG_HOME` (POSIX) and :envvar:`APPDATA` (Windows).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....domain.profile import CCAA, TaxResidenceProfile
from ....domain.profile._errors import TaxResidenceProfileError
from ..storage import EphemeralMasterKeyProvider, override_master_key_provider
from ..storage.sql import dispose_engine
from .tax_residence import (
    _default_path,
    clear_json,
    load_json,
    load_tax_residence,
    save_json,
    save_tax_residence,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


@pytest.fixture(autouse=True)
def _secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)
        dispose_engine()


def test_round_trip_json_serialization(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    residence = TaxResidenceProfile(ccaa=CCAA.GALICIA)
    save_tax_residence(residence, target)
    assert load_tax_residence(target) == residence
    assert not target.exists()


def test_atomic_write_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    save_tax_residence(TaxResidenceProfile(ccaa=CCAA.MADRID), target)
    save_tax_residence(TaxResidenceProfile(ccaa=CCAA.CATALUNA), target)
    residence = load_tax_residence(target)
    assert residence is not None
    assert residence.ccaa is CCAA.CATALUNA
    assert not list(tmp_path.glob("*.tmp"))
    assert not target.exists()


def test_atomic_write_cleans_temp_file_when_serialization_fails(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    with pytest.raises(TaxResidenceProfileError):
        save_json({"schema_version": "1", "ccaa": object()}, target)
    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_clear_removes_profile(tmp_path: Path) -> None:
    target = tmp_path / "tax-residence.json"
    save_tax_residence(TaxResidenceProfile(ccaa=CCAA.MURCIA), target)
    clear_json(target)
    assert load_json(target) is None
    assert not target.exists()


def test_default_path_resolution_linux_xdg() -> None:
    path = _default_path({"XDG_CONFIG_HOME": "/home/operator/.config"}, "posix")
    assert path == Path("/home/operator/.config") / "aeat" / "tax-residence.json"


def test_default_path_resolution_windows_appdata() -> None:
    path = _default_path({"APPDATA": r"C:\Users\Operator\AppData\Roaming"}, "nt")
    assert str(path).endswith(os.path.join("aeat", "tax-residence.json"))
    assert "AppData" in str(path)
