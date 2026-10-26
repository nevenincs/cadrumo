"""Detect the local model runtime: where it is and whether it answers.

The model-level verbs in :mod:`.provisioning_runtime` assume a runtime is
already listening. This module answers whether one is. The local AI is located
from the native component engine's record -- the program it installed and the
fixed address the runtime manager's server answers on -- and only that address
is asked. An operator's own endpoint is asked as configured, with the runtime
looked for on ``PATH`` and in each platform's standard install location.

Nothing here installs, starts, stops or removes a program: the native component
engine installs the local AI and the runtime manager runs its server.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path

import httpx
from pydantic import Field, model_validator

from ..core.component_records import component_records_root, locate_local_ai, uses_managed_local_ai
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.loopback_endpoint import endpoint_host_is_loopback
from ..core.type_guards import is_object_dict
from .provisioning_contracts import (
    OLLAMA_PROBE_TIMEOUT_S,
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)
from .provisioning_runtime import ollama_endpoint

__all__ = [
    "ExecutableLookup",
    "RuntimeHostPlatform",
    "RuntimeHostStatus",
    "current_runtime_platform",
    "locate_runtime_executable",
    "probe_runtime_host",
    "read_runtime_version",
]


class RuntimeHostPlatform(StrEnum):
    """The operating-system families whose standard install locations differ."""

    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    OTHER = "other"


type ExecutableLookup = Callable[[str], str | None]


def current_runtime_platform(platform: str | None = None) -> RuntimeHostPlatform:
    """Classify ``sys.platform`` (or the given value) into a runtime host platform."""
    value = sys.platform if platform is None else platform
    if value == "win32":
        return RuntimeHostPlatform.WINDOWS
    if value == "darwin":
        return RuntimeHostPlatform.MACOS
    if value.startswith("linux"):
        return RuntimeHostPlatform.LINUX
    return RuntimeHostPlatform.OTHER


def _standard_executable_paths(platform: RuntimeHostPlatform, env: Mapping[str, str]) -> tuple[Path, ...]:
    """Return where each platform's official installer places the runtime binary."""
    if platform is RuntimeHostPlatform.WINDOWS:
        local = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return (Path(local) / "Programs" / "Ollama" / "ollama.exe",)
    if platform is RuntimeHostPlatform.MACOS:
        return (
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path("/opt/homebrew/bin/ollama"),
            Path("/usr/local/bin/ollama"),
        )
    if platform is RuntimeHostPlatform.LINUX:
        return (Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama"))
    return ()


def locate_runtime_executable(
    *,
    platform: RuntimeHostPlatform | None = None,
    env: Mapping[str, str] | None = None,
    which: ExecutableLookup = shutil.which,
) -> Path | None:
    """Return the runtime executable on ``PATH`` or in a standard location, or ``None``.

    The standard locations matter as much as ``PATH``: an installer that has
    just finished updates the user's ``PATH`` for new shells only, so a process
    started before it would otherwise not find what it installed.
    """
    found = which("ollama")
    if found is not None and found:
        return Path(found)
    resolved_platform = platform if platform is not None else current_runtime_platform()
    environment = os.environ if env is None else env
    for candidate in _standard_executable_paths(resolved_platform, environment):
        if candidate.is_file():
            return candidate
    return None


def read_runtime_version(settings: Settings | None = None) -> str | None:
    """Return the runtime's reported version, or ``None`` when nothing answers."""
    resolved = settings if settings is not None else load_settings()
    url = ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "version")
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    version = payload.get("version") if is_object_dict(payload) else None
    return version if isinstance(version, str) and version else "unknown"


class RuntimeHostStatus(ProvisioningOutcome):
    """Whether the local model runtime is installed, and whether it answers.

    ``available`` is the reachability claim; everything else explains it. An
    installed runtime that does not answer is a start away from ready, and an
    absent one is an install away -- the verdict names which.
    """

    platform: RuntimeHostPlatform
    endpoint_url: str = Field(min_length=1)
    endpoint_local: bool
    executable_located: bool
    reachable: bool
    version: str | None = None
    available: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_host_outcome(self) -> RuntimeHostStatus:
        require_provisioning_verdict(failed=not self.available, verdict=self.precondition_verdict)
        return self


def probe_runtime_host(
    settings: Settings | None = None,
    *,
    platform: RuntimeHostPlatform | None = None,
    which: ExecutableLookup = shutil.which,
) -> RuntimeHostStatus:
    """Detect the runtime installation and whether its endpoint answers. Never raises.

    The local AI the runtime manager runs is located from its component record
    alone, and only its recorded address is asked; without a record that
    locates it, nothing is asked. An operator's own endpoint is asked as
    configured.
    """
    resolved = settings if settings is not None else load_settings()
    host_platform = platform if platform is not None else current_runtime_platform()
    endpoint = resolved.cadrumo_llm_ollama_chat_url
    if uses_managed_local_ai(resolved):
        located = locate_local_ai(records_root=component_records_root(resolved))
        executable_located = located.located
        endpoint = located.chat_url if located.located and located.chat_url is not None else endpoint
        aimed = resolved.model_copy(update={"cadrumo_llm_ollama_chat_url": endpoint})
        version = read_runtime_version(aimed) if executable_located else None
    else:
        executable_located = locate_runtime_executable(platform=host_platform, which=which) is not None
        version = read_runtime_version(resolved)
    local = endpoint_host_is_loopback(endpoint)
    facts: dict[str, ProvisioningFactValue] = {
        "platform": host_platform.value,
        "runtime_url": endpoint,
        "endpoint_local": local,
        "executable_located": executable_located,
        "runtime_reachable": version is not None,
    }
    verdict = None
    if version is None:
        condition = (
            ProvisioningPreconditionCondition.RUNTIME_INSTALLED
            if local and not executable_located
            else ProvisioningPreconditionCondition.RUNTIME_REACHABLE
        )
        verdict = provisioning_no_recovery_verdict(condition, facts=facts)
    return RuntimeHostStatus(
        platform=host_platform,
        endpoint_url=endpoint,
        endpoint_local=local,
        executable_located=executable_located,
        reachable=version is not None,
        version=version,
        available=version is not None,
        facts=facts,
        precondition_verdict=verdict,
    )
