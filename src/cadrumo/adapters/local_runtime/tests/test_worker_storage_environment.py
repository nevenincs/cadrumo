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
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(tmp_path / "local")
    assert environment["CADRUMO_TEMP_DIR"] == "worker-temp"
    assert environment["CADRUMO_OLLAMA_MODELS_DIR"] == "models/ollama-test"
    assert not any("OPENAI_API_KEY" in name or name == "PYTHONPATH" for name in environment)
    assert {environment[name] for name in ("TEMP", "TMP", "TMPDIR")} == {str(temporary_root.resolve())}
    assert temporary_root.is_dir()
