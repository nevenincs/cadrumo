"""Storage-only controls cross the isolated worker boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import profile_worker
from ..agent_programs import PACKAGE_AGENT_VARIABLE
from ..worker_environment import worker_path_environment_names

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
    # The development root variable is not a product control; the pinned root replaces it.
    assert "CADRUMO_STORAGE_ROOT" not in environment
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
    monkeypatch.setenv("CADRUMO_LOG_LEVEL", "DEBUG")

    storage_root = tmp_path / "worker-storage"
    environment = profile_worker._worker_launch_environment(storage_root=storage_root)

    assert environment["XDG_CACHE_HOME"] == str(tmp_path / "pinned-cache")
    assert environment["CADRUMO_AUTHORITY_ROOT"] == str(tmp_path / "authority")
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(storage_root.resolve())
    assert not any("OPENAI_API_KEY" in name for name in environment)
    # A setting of this command line that is not a location stays with the runtime.
    assert "CADRUMO_LOG_LEVEL" not in environment


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_the_worker_receives_the_agent_location_the_runtime_holds_and_no_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform=platform))
    image = tmp_path / "package" / "bin" / "agent-image"
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))

    environment = profile_worker._worker_launch_environment(storage_root=tmp_path / "worker-storage")

    assert environment[PACKAGE_AGENT_VARIABLE] == str(image)
    # The POSIX containment and its guardian keep only the worker's declared names; this is one.
    assert PACKAGE_AGENT_VARIABLE in worker_path_environment_names()
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE)
    assert PACKAGE_AGENT_VARIABLE not in profile_worker._worker_launch_environment(
        storage_root=tmp_path / "worker-storage"
    )
