"""Storage-only controls cross the isolated worker boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from cadrumo.core.profile_root_environment import PROFILE_ROOT_VARIABLE, profile_root

from .. import profile_worker
from ..worker_environment import worker_path_environment_names

_PACKAGE_AGENT_VARIABLE = "CADRUMO_PACKAGE_AGENT_EXECUTABLE"
_PROFILE = UUID("7f5b1a6d-0c9e-4d8f-9a3b-2c1d0e9f8a7b")

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_linux_worker_receives_the_pinned_storage_root_and_managed_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "configured"))
    monkeypatch.setenv("CADRUMO_LLM_OPENAI_API_KEY", "must-not-cross-worker-boundary")
    monkeypatch.setenv("PYTHONPATH", "must-not-cross-worker-boundary")

    storage_root = tmp_path / "worker-storage"
    environment = profile_worker._worker_launch_environment(storage_root=storage_root, profile_id=_PROFILE)

    temporary_root = storage_root / "tmp"
    assert environment["PATH"] == "/usr/bin:/bin"
    assert environment["LANG"] == "C" and environment["LC_ALL"] == "C"
    # The worker inherits the root it serves; it never re-resolves the parent's override.
    assert environment["CADRUMO_STORAGE_ROOT"] == str(storage_root.resolve())
    assert not any("OPENAI_API_KEY" in name or name == "PYTHONPATH" for name in environment)
    assert {environment[name] for name in ("TEMP", "TMP", "TMPDIR")} == {str(temporary_root.resolve())}
    assert temporary_root.is_dir()
    # A worker serves one profile and is told that profile's folder, not one it inherited.
    assert environment[PROFILE_ROOT_VARIABLE] == str(profile_root(storage_root.resolve(), _PROFILE))


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
    monkeypatch.setenv(PROFILE_ROOT_VARIABLE, str(tmp_path / "another-profiles-folder"))
    environment = profile_worker._worker_launch_environment(storage_root=storage_root, profile_id=_PROFILE)

    assert environment[PROFILE_ROOT_VARIABLE] == str(profile_root(storage_root.resolve(), _PROFILE))
    assert environment["XDG_CACHE_HOME"] == str(tmp_path / "pinned-cache")
    assert environment["CADRUMO_AUTHORITY_ROOT"] == str(tmp_path / "authority")
    assert environment["CADRUMO_STORAGE_ROOT"] == str(storage_root.resolve())
    assert not any("OPENAI_API_KEY" in name for name in environment)
    # A setting of this command line that is not a location stays with the runtime.
    assert "CADRUMO_LOG_LEVEL" not in environment


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_worker_drops_service_agent_executable_from_operator_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform=platform))
    image = tmp_path / "package" / "bin" / "agent-image"
    monkeypatch.setenv(_PACKAGE_AGENT_VARIABLE, str(image))

    environment = profile_worker._worker_launch_environment(
        storage_root=tmp_path / "worker-storage", profile_id=_PROFILE
    )

    assert _PACKAGE_AGENT_VARIABLE not in environment
    # Service executable locations are not part of the operator worker path allowlist.
    assert _PACKAGE_AGENT_VARIABLE not in worker_path_environment_names()
    monkeypatch.delenv(_PACKAGE_AGENT_VARIABLE)
    assert _PACKAGE_AGENT_VARIABLE not in profile_worker._worker_launch_environment(
        storage_root=tmp_path / "worker-storage", profile_id=_PROFILE
    )


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_the_launch_environment_of_a_profile_worker_passes_its_isolated_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    from ..macos_worker_process import _validated_environment

    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform=platform))
    environment = profile_worker._worker_launch_environment(
        storage_root=tmp_path / "worker-storage", profile_id=_PROFILE
    )
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    assert PROFILE_ROOT_VARIABLE in environment
    assert _validated_environment(environment) == environment
