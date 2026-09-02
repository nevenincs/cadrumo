"""Detector-teeth tests for runtime-specific sealed dependency wheelhouses."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..runtime_wheelhouse import (
    PLATFORM_FLOORS,
    SUPPORTED_TARGETS,
    WHEELHOUSE_SCHEMA,
    extract_runtime_wheelhouse,
    load_runtime_wheelhouse,
    plan_runtime_wheelhouses,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCK_SHA256 = "a" * 64


def _runtime_entry(runtime: str, filename: str, payload: bytes) -> dict[str, object]:
    """Build one strict ready entry whose bytes are supplied by the archive."""
    return {
        "platforms": {
            target.name: {"native-dependency": filename} for target in SUPPORTED_TARGETS
        },
        "python": runtime,
        "status": "ready",
        "wheels": {
            filename: {
                "distribution": "native-dependency",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
                "version": "1.0.0",
            }
        },
    }


def _wheelhouse_fixture(tmp_path: Path) -> Path:
    """Write two runtime closures plus an attributable advisory canary row."""
    cp313_name = "native_dependency-1.0.0-cp313-cp313-win_amd64.whl"
    cp314_name = "native_dependency-1.0.0-cp314-cp314-win_amd64.whl"
    cp313_payload = b"sealed cp313 dependency"
    cp314_payload = b"sealed cp314 dependency"
    manifest = {
        "lock_sha256": _LOCK_SHA256,
        "platform_floors": PLATFORM_FLOORS,
        "runtimes": {
            "3.13": _runtime_entry("3.13", cp313_name, cp313_payload),
            "3.14": _runtime_entry("3.14", cp314_name, cp314_payload),
            "3.15": {
                "missing": [
                    {
                        "distribution": "native-dependency",
                        "platform": "windows-x86-64",
                        "reason": "no-compatible-wheel",
                        "requirement": "native-dependency==1.0.0",
                    }
                ],
                "python": "3.15",
                "status": "missing-wheel",
            },
        },
        "schema": WHEELHOUSE_SCHEMA,
    }
    archive_path = tmp_path / "runtime-wheelhouse.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("runtime-wheelhouse.json", json.dumps(manifest, sort_keys=True))
        archive.writestr(f"wheels/3.13/{cp313_name}", cp313_payload)
        archive.writestr(f"wheels/3.14/{cp314_name}", cp314_payload)
    return archive_path


def test_load_and_extract_select_the_observed_runtime_closure(tmp_path: Path) -> None:
    """A 3.14 extraction cannot accidentally expose the 3.13 wheel bytes."""
    archive = _wheelhouse_fixture(tmp_path)
    loaded = load_runtime_wheelhouse(
        archive,
        expected_lock_sha256=_LOCK_SHA256,
        expected_python="3.14",
    )
    assert loaded.manifest["runtimes"]["3.14"]["status"] == "ready"

    extracted = tmp_path / "extracted-3.14"
    extract_runtime_wheelhouse(archive, extracted, python_version="3.14")
    assert (extracted / "native_dependency-1.0.0-cp314-cp314-win_amd64.whl").read_bytes() == (
        b"sealed cp314 dependency"
    )
    assert not (extracted / "native_dependency-1.0.0-cp313-cp313-win_amd64.whl").exists()


def test_advisory_missing_runtime_is_not_presented_as_ready(tmp_path: Path) -> None:
    """An incomplete 3.15 row remains attributable and cannot be extracted."""
    archive = _wheelhouse_fixture(tmp_path)
    loaded = load_runtime_wheelhouse(archive, expected_lock_sha256=_LOCK_SHA256)
    missing = loaded.manifest["runtimes"]["3.15"]
    assert missing["status"] == "missing-wheel"
    assert missing["missing"][0]["distribution"] == "native-dependency"

    with pytest.raises(SystemExit, match=r"no ready entry for Python 3\.15"):
        load_runtime_wheelhouse(archive, expected_python="3.15")


def test_runtime_wheelhouse_rejects_unmanifested_runtime_member(tmp_path: Path) -> None:
    """A stray runtime wheel cannot cross the sealed archive boundary."""
    archive = _wheelhouse_fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("wheels/3.14/unmanifested.whl", b"stowaway")

    with pytest.raises(SystemExit, match="member inventory drifted"):
        load_runtime_wheelhouse(archive)


def test_current_lock_selects_distinct_stable_runtime_wheels() -> None:
    """The real lock has ready 3.13/3.14 closures and an explicit 3.15 gap."""
    plans = plan_runtime_wheelhouses(REPO_ROOT)
    assert plans["3.13"].missing == ()
    assert plans["3.14"].missing == ()
    assert "cp313-cp313" in plans["3.13"].platforms["linux-x86-64"]["cffi"]
    assert "cp314-cp314" in plans["3.14"].platforms["linux-x86-64"]["cffi"]
    assert {item["distribution"] for item in plans["3.15"].missing} == {"pydantic-core", "pyyaml"}
