"""Local model runtime host lifecycle: detect, start and install the runtime itself.

The model-level verbs in :mod:`.provisioning_runtime` assume a runtime is
already listening. This module owns the step before that, per platform:

* **Detect.** Locate the runtime executable on ``PATH`` and in each platform's
  standard install location, and ask the configured endpoint whether it answers.
* **Start.** Spawn ``<runtime> serve`` detached when the endpoint is local, the
  executable is present and nothing answers yet. Starting an already running
  runtime is a successful no-op, so the verb is idempotent.
* **Install.** Run the platform package manager -- ``winget`` on Windows,
  Homebrew on macOS -- only with explicit operator consent. Linux has no
  unprivileged installer: the upstream script needs root, so the operator runs
  it and this module reports the typed refusal.

Nothing here stops, signals or replaces a process Cadrumo did not spawn, and a
remote endpoint is never started or installed on the operator's behalf.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator

from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.type_guards import is_object_dict
from .provisioning_contracts import (
    OLLAMA_INSTALL_TIMEOUT_S,
    OLLAMA_PROBE_TIMEOUT_S,
    OLLAMA_START_TIMEOUT_S,
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)
from .provisioning_runtime import forget_runtime_unreachable, ollama_endpoint

__all__ = [
    "ExecutableLookup",
    "InstallerRunner",
    "RuntimeHostPlatform",
    "RuntimeHostStatus",
    "RuntimeInstallOutcome",
    "RuntimeInstaller",
    "RuntimeSpawner",
    "RuntimeStartOutcome",
    "available_runtime_installer",
    "current_runtime_platform",
    "install_runtime",
    "locate_runtime_executable",
    "probe_runtime_host",
    "read_runtime_version",
    "runtime_endpoint_is_local",
    "start_runtime",
]

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_START_POLL_INTERVAL_S = 0.5


class RuntimeHostPlatform(StrEnum):
    """The operating-system families whose install and start paths differ."""

    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    OTHER = "other"


class RuntimeInstaller(StrEnum):
    """The package manager an install would run, or none this host offers."""

    WINGET = "winget"
    HOMEBREW = "homebrew"
    NONE = "none"


type ExecutableLookup = Callable[[str], str | None]
type RuntimeSpawner = Callable[[Path, Mapping[str, str]], int]
"""Starts ``<executable> serve`` detached with the given environment; returns its pid."""
type InstallerRunner = Callable[[RuntimeInstaller, Path, float], int]
"""Runs the installer's non-interactive runtime install; returns its exit code."""


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
    just finished updates the user's ``PATH`` for new shells only, so the
    process that ran it would otherwise not find what it installed.
    """
    found = which("ollama")
    if found:
        return Path(found)
    resolved_platform = platform if platform is not None else current_runtime_platform()
    environment = os.environ if env is None else env
    for candidate in _standard_executable_paths(resolved_platform, environment):
        if candidate.is_file():
            return candidate
    return None


def _located_installer(
    platform: RuntimeHostPlatform,
    which: ExecutableLookup,
) -> tuple[RuntimeInstaller, Path | None]:
    if platform is RuntimeHostPlatform.WINDOWS:
        found = which("winget")
        if found:
            return RuntimeInstaller.WINGET, Path(found)
    if platform is RuntimeHostPlatform.MACOS:
        found = which("brew")
        if found:
            return RuntimeInstaller.HOMEBREW, Path(found)
    return RuntimeInstaller.NONE, None


def available_runtime_installer(
    *,
    platform: RuntimeHostPlatform | None = None,
    which: ExecutableLookup = shutil.which,
) -> RuntimeInstaller:
    """Return the package manager this host can install the runtime with."""
    resolved = platform if platform is not None else current_runtime_platform()
    return _located_installer(resolved, which)[0]


def runtime_endpoint_is_local(chat_url: str) -> bool:
    """Return whether the configured endpoint names this machine's loopback interface."""
    host = urlsplit(chat_url).hostname or ""
    return host.lower() in _LOOPBACK_HOSTS


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
    installer: RuntimeInstaller
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
    """Detect the runtime installation and whether its endpoint answers. Never raises."""
    resolved = settings if settings is not None else load_settings()
    host_platform = platform if platform is not None else current_runtime_platform()
    endpoint = resolved.cadrumo_llm_ollama_chat_url
    local = runtime_endpoint_is_local(endpoint)
    executable = locate_runtime_executable(platform=host_platform, which=which)
    version = read_runtime_version(resolved)
    installer = available_runtime_installer(platform=host_platform, which=which)
    facts: dict[str, ProvisioningFactValue] = {
        "platform": host_platform.value,
        "runtime_url": endpoint,
        "endpoint_local": local,
        "executable_located": executable is not None,
        "runtime_reachable": version is not None,
        "installer": installer.value,
    }
    verdict = None
    if version is None:
        condition = (
            ProvisioningPreconditionCondition.RUNTIME_INSTALLED
            if local and executable is None
            else ProvisioningPreconditionCondition.RUNTIME_REACHABLE
        )
        verdict = provisioning_no_recovery_verdict(condition, facts=facts)
    return RuntimeHostStatus(
        platform=host_platform,
        endpoint_url=endpoint,
        endpoint_local=local,
        executable_located=executable is not None,
        reachable=version is not None,
        version=version,
        installer=installer,
        available=version is not None,
        facts=facts,
        precondition_verdict=verdict,
    )


class RuntimeStartOutcome(ProvisioningOutcome):
    """The result of asking for a running runtime, including one already running."""

    running: bool
    already_running: bool = False
    started_pid: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_start_outcome(self) -> RuntimeStartOutcome:
        require_provisioning_verdict(failed=not self.running, verdict=self.precondition_verdict)
        return self


def _start_refusal(
    condition: ProvisioningPreconditionCondition,
    facts: Mapping[str, ProvisioningFactValue],
) -> RuntimeStartOutcome:
    return RuntimeStartOutcome(
        running=False,
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
    )


def start_runtime(
    settings: Settings | None = None,
    *,
    spawn: RuntimeSpawner,
    timeout_s: float | None = None,
    which: ExecutableLookup = shutil.which,
) -> RuntimeStartOutcome:
    """Make the configured local runtime answer, starting it only when it does not.

    Idempotent: a runtime that already answers is reported running and nothing
    is spawned. A remote endpoint is refused rather than started, because a
    process on this machine cannot make another machine's server answer.

    Args:
        settings: Settings carrying the endpoint; loaded when omitted.
        timeout_s: How long to wait for a spawned runtime to answer.
        spawn: Starts ``<executable> serve`` detached and returns its process id.
        which: Executable lookup used to locate the runtime.

    Returns:
        A :class:`RuntimeStartOutcome`. Never raises.
    """
    resolved = settings if settings is not None else load_settings()
    endpoint = resolved.cadrumo_llm_ollama_chat_url
    if read_runtime_version(resolved) is not None:
        forget_runtime_unreachable(resolved)
        return RuntimeStartOutcome(
            running=True,
            already_running=True,
            facts={"runtime_url": endpoint, "runtime_reachable": True, "already_running": True},
        )
    if not runtime_endpoint_is_local(endpoint):
        return _start_refusal(
            ProvisioningPreconditionCondition.RUNTIME_ENDPOINT_LOCAL,
            {"runtime_url": endpoint, "endpoint_local": False},
        )
    executable = locate_runtime_executable(which=which)
    if executable is None:
        return _start_refusal(
            ProvisioningPreconditionCondition.RUNTIME_INSTALLED,
            {"runtime_url": endpoint, "executable_located": False},
        )
    parts = urlsplit(endpoint)
    environment = dict(os.environ)
    environment["OLLAMA_HOST"] = f"{parts.hostname}:{parts.port or 11434}"
    try:
        pid = spawn(executable, environment)
    except OSError as exc:
        return _start_refusal(
            ProvisioningPreconditionCondition.RUNTIME_START_SUCCEEDED,
            {"runtime_url": endpoint, "spawned": False, "start_error_type": exc.__class__.__name__},
        )
    bound = timeout_s if timeout_s is not None else OLLAMA_START_TIMEOUT_S
    started = time.monotonic()
    while time.monotonic() - started < bound:
        if read_runtime_version(resolved) is not None:
            forget_runtime_unreachable(resolved)
            return RuntimeStartOutcome(
                running=True,
                started_pid=pid,
                facts={"runtime_url": endpoint, "runtime_reachable": True, "started_pid": pid},
            )
        time.sleep(_START_POLL_INTERVAL_S)
    return _start_refusal(
        ProvisioningPreconditionCondition.RUNTIME_START_SUCCEEDED,
        {
            "runtime_url": endpoint,
            "spawned": True,
            "started_pid": pid,
            "waited_ms": int((time.monotonic() - started) * 1000),
        },
    )


class RuntimeInstallOutcome(ProvisioningOutcome):
    """The result of an install request, including one that needed no install."""

    installed: bool
    already_installed: bool = False
    installer: RuntimeInstaller
    consented: bool
    installer_exit_code: int | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_install_outcome(self) -> RuntimeInstallOutcome:
        require_provisioning_verdict(failed=not self.installed, verdict=self.precondition_verdict)
        return self


def install_runtime(
    *,
    consent: bool,
    run: InstallerRunner,
    platform: RuntimeHostPlatform | None = None,
    which: ExecutableLookup = shutil.which,
) -> RuntimeInstallOutcome:
    """Install the local runtime through the platform package manager, with consent.

    Idempotent: an executable that is already present is reported installed
    and nothing runs, with or without consent. Without consent nothing is
    downloaded; the refusal names the installer that would run so the operator
    can decide.

    Args:
        consent: The operator's explicit agreement to run the installer.
        platform: Host platform; detected when omitted.
        which: Executable lookup for the runtime and the package manager.
        run: Runs the install invocation and returns its exit code.

    Returns:
        A :class:`RuntimeInstallOutcome`. Never raises.
    """
    host_platform = platform if platform is not None else current_runtime_platform()
    installer, installer_path = _located_installer(host_platform, which)
    base_facts: dict[str, ProvisioningFactValue] = {"platform": host_platform.value, "installer": installer.value}
    if locate_runtime_executable(platform=host_platform, which=which) is not None:
        return RuntimeInstallOutcome(
            installed=True,
            already_installed=True,
            installer=installer,
            consented=consent,
            facts={**base_facts, "executable_located": True},
        )

    def refusal(
        condition: ProvisioningPreconditionCondition,
        extra: Mapping[str, ProvisioningFactValue],
        exit_code: int | None = None,
    ) -> RuntimeInstallOutcome:
        facts = {**base_facts, **extra}
        return RuntimeInstallOutcome(
            installed=False,
            installer=installer,
            consented=consent,
            installer_exit_code=exit_code,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
        )

    if installer_path is None:
        return refusal(ProvisioningPreconditionCondition.RUNTIME_INSTALLER_AVAILABLE, {"executable_located": False})
    if not consent:
        return refusal(ProvisioningPreconditionCondition.RUNTIME_INSTALL_CONSENTED, {"consented": False})
    try:
        exit_code = run(installer, installer_path, OLLAMA_INSTALL_TIMEOUT_S)
    except (OSError, ValueError, TimeoutError) as exc:
        return refusal(
            ProvisioningPreconditionCondition.RUNTIME_INSTALL_SUCCEEDED,
            {"installer_ran": False, "install_error_type": exc.__class__.__name__},
        )
    located = locate_runtime_executable(platform=host_platform, which=which) is not None
    if exit_code != 0 or not located:
        return refusal(
            ProvisioningPreconditionCondition.RUNTIME_INSTALL_SUCCEEDED,
            {"installer_ran": True, "installer_exit_code": exit_code, "executable_located": located},
            exit_code=exit_code,
        )
    return RuntimeInstallOutcome(
        installed=True,
        installer=installer,
        consented=True,
        installer_exit_code=exit_code,
        facts={**base_facts, "installer_ran": True, "installer_exit_code": 0, "executable_located": True},
    )
