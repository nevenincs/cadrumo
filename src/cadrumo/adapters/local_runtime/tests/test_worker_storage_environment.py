"""Storage-only controls cross the isolated worker boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import profile_worker

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_linux_worker_receives_only_declared_storage_controls_and_managed_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "configured"))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "local"))
    monkeypatch.setenv("CADRUMO_TEMP_DIR", "worker-temp")
    monkeypatch.setenv("CADRUMO_OLLAMA_MODELS_DIR", "models/ollama-test")
    monkeypatch.setenv("CADRUMO_LLM_OPENAI_API_KEY", "must-not-cross-worker-boundary")
    monkeypatch.setenv("PYTHONPATH", "must-not-cross-worker-boundary")

    storage_root = tmp_path / "worker-storage"
    environment = profile_worker._worker_launch_environment(storage_root=storage_root)

    temporary_root = storage_root / "worker-temp"
    assert environment["PATH"] == "/usr/bin:/bin"
    assert environment["LANG"] == "C" and environment["LC_ALL"] == "C"
    assert environment["CADRUMO_STORAGE_ROOT"] == str(tmp_path / "configured")
    # The worker inherits the root it serves; it never re-resolves the parent's override.
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(storage_root.resolve())
    assert environment["CADRUMO_TEMP_DIR"] == "worker-temp"
    assert environment["CADRUMO_OLLAMA_MODELS_DIR"] == "models/ollama-test"
    assert not any("OPENAI_API_KEY" in name or name == "PYTHONPATH" for name in environment)
    assert {environment[name] for name in ("TEMP", "TMP", "TMPDIR")} == {str(temporary_root.resolve())}
    assert temporary_root.is_dir()


def test_windows_worker_keeps_the_packaged_cache_pin_and_drops_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "pinned-cache"))
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(tmp_path / "authority"))
    monkeypatch.setenv("CADRUMO_LLM_OPENAI_API_KEY", "must-not-cross-worker-boundary")
    monkeypatch.setenv("PYTHONPATH", "must-not-cross-worker-boundary")

    storage_root = tmp_path / "worker-storage"
    environment = profile_worker._worker_launch_environment(storage_root=storage_root)

    assert environment["XDG_CACHE_HOME"] == str(tmp_path / "pinned-cache")
    assert environment["CADRUMO_AUTHORITY_ROOT"] == str(tmp_path / "authority")
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(storage_root.resolve())
    assert not any("OPENAI_API_KEY" in name or name.upper().startswith("PYTHON") for name in environment)
