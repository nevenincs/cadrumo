"""Typed external-dependency probes for graceful degradation and ``config check``.

This module is the read-only application doctor surface: each probe asks whether
one external service or optional package extra is usable on this workstation and
returns a typed :class:`DependencyStatus` with the exact remediation command when
it is not. Probes do not provision, unlock, write profile state, or raise on
absence; a missing dependency is report data, not an exception path.

The vision read consults :func:`probe_ollama_vision` before expensive inference,
so a down server or an unpulled model becomes an instructive refusal instead of
a raw stack trace. The ``aeat config check`` command renders this module's
statuses as
:class:`~cadrumo.entrypoints.cli._config._check_payloads.CheckDependencyPayload`
rows beside the active profile's capability posture from
:func:`~cadrumo.application.user_profile.resolve_active_capability`. Optional-extra
probes walk the core :data:`~cadrumo.core.OPTIONAL_EXTRAS` catalogue of
:class:`~cadrumo.core.OptionalExtra` records, so CLI diagnostics and adapter import
guards share one registry.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import httpx
from pydantic import BaseModel, Field

from ..core import OPTIONAL_EXTRAS, STRICT_FROZEN_CONFIG, ExternalPathRole, OptionalExtra, optional_extra_available
from ..core.config import Settings, load_settings

__all__ = [
    "OPTIONAL_EXTRAS",
    "DependencyStatus",
    "OptionalExtra",
    "probe_model_runtime_hardware_floor",
    "probe_ollama_vision",
    "probe_optional_extra",
    "probe_optional_extras",
    "probe_playwright_browser",
    "probe_subprocess_providers",
]

_OLLAMA_PROBE_TIMEOUT_S = 2.0


class DependencyStatus(BaseModel):
    """Availability result for one external dependency.

    ``service`` is the stable row id shown by ``aeat config check``; ``detail``
    explains the observed state; ``remediation`` is the command or action the
    operator can run when ``available`` is false. The model is intentionally
    generic so Ollama, subprocess CLIs, Playwright browser binaries, and
    :class:`~cadrumo.core.OptionalExtra` package extras all render through the same
    payload shape and can be validated into
    :class:`~cadrumo.entrypoints.cli._config._check_payloads.CheckDependencyPayload`.
    """

    model_config = STRICT_FROZEN_CONFIG

    service: str = Field(min_length=1)
    available: bool
    detail: str = ""
    remediation: str = ""


def _ollama_tags_url(chat_url: str) -> str:
    """Derive the lightweight ``/api/tags`` model-list URL from the configured chat URL."""
    base = chat_url.rsplit("/api/", 1)[0] if "/api/" in chat_url else chat_url.rstrip("/")
    return f"{base}/api/tags"


def probe_ollama_vision(settings: Settings | None = None) -> DependencyStatus:
    """Probe Ollama and the configured vision model, returning a :class:`DependencyStatus`.

    Reads ``cadrumo_llm_ollama_chat_url`` and ``cadrumo_llm_ollama_vision_model`` from
    :class:`~cadrumo.core.config.Settings`, then performs a short-timeout
    ``GET /api/tags``. The probe never runs inference and returns unavailable
    when the server is unreachable (``ollama serve``) or the configured model is
    not pulled (``ollama pull <model>``). Ledger evidence reading uses this
    result before local-vision inference so
    :class:`~cadrumo.domain.transactions.LLMClassifierError` can carry the exact
    remediation.
    """
    resolved = settings if settings is not None else load_settings()
    model = resolved.cadrumo_llm_ollama_vision_model
    url = _ollama_tags_url(resolved.cadrumo_llm_ollama_chat_url)
    try:
        with httpx.Client(timeout=_OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Ollama tags response must be a JSON object")
            # CAST-RATIONALE-OLLAMA-TAGS-PAYLOAD: httpx.Response.json() returns
            # Any; isinstance narrows to dict but not its type parameters.
            payload_object = cast(dict[str, object], payload)
            models = payload_object.get("models")
            if not isinstance(models, list):
                raise ValueError("Ollama tags response must contain model objects with string names")
            # CAST-RATIONALE-OLLAMA-TAGS-MODELS: isinstance narrows to list but
            # not its element type; entries are validated individually below.
            models = cast(list[object], models)
            names: set[str] = set()
            for entry in models:
                if not isinstance(entry, dict):
                    raise ValueError("Ollama tags response must contain model objects with string names")
                # CAST-RATIONALE-OLLAMA-TAGS-MODEL-ENTRY: isinstance narrows to
                # dict but not its type parameters.
                name = cast(dict[str, object], entry).get("name")
                if not isinstance(name, str):
                    raise ValueError("Ollama tags response must contain model objects with string names")
                names.add(name)
    except (httpx.HTTPError, ValueError):
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            detail=f"Ollama is not reachable at {url}",
            remediation="start Ollama (ollama serve) and ensure it listens on cadrumo_llm_ollama_chat_url",
        )
    # Ollama lists names with the tag (e.g. "qwen2.5vl:3b"); match the configured
    # model exactly or by its untagged stem.
    present = model in names or any(name.split(":", 1)[0] == model.split(":", 1)[0] for name in names)
    if not present:
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            detail=f"Ollama is running but the vision model {model!r} is not pulled",
            remediation=f"ollama pull {model}",
        )
    return DependencyStatus(
        service="ollama-vision",
        available=True,
        detail=f"Ollama is reachable and {model!r} is pulled",
    )


def probe_subprocess_providers() -> tuple[DependencyStatus, ...]:
    """Probe each subprocess LLM CLI provider on ``PATH``.

    Delegates provider discovery to the ledger classification surface and adapts
    each availability row into the common :class:`DependencyStatus` shape. The
    probe resolves binaries only; it does not spawn provider processes.
    ``aeat config check`` combines these rows with
    :class:`~cadrumo.core.ServiceCapability` decisions to flag opted-in cloud
    evidence uploads that lack a provider CLI.
    """
    from .ledger import available_llm_providers

    statuses: list[DependencyStatus] = []
    for listing in available_llm_providers():
        statuses.append(
            DependencyStatus(
                service=f"llm-provider:{listing.provider.value}",
                available=listing.available,
                detail=(
                    f"{listing.cli_binary} resolved at {listing.resolved_path}"
                    if listing.available
                    else f"{listing.cli_binary} not found on PATH"
                ),
                remediation="" if listing.available else f"install the {listing.cli_binary!r} CLI and put it on PATH",
            ),
        )
    return tuple(statuses)


PLAYWRIGHT_BROWSERS_ROOT_ROLE = ExternalPathRole.THIRD_PARTY_CACHE
"""Why the Playwright browser cache sits outside the storage taxonomy.

Declared as a positive statement rather than left as the root's plain absence
from :data:`~core.STORAGE_TAXONOMY` or :data:`~core.EXTERNAL_PATH_SETTINGS_FIELDS`:
Playwright installs its own Chromium build under a vendor-owned layout
convention (``PLAYWRIGHT_BROWSERS_PATH`` or a per-OS default cache directory),
so the application neither chooses this location nor writes the binaries there
-- it fails the choose test :class:`~core.ExternalPathRole` exists to name.
There is no :class:`~core.config.Settings` field to carry the declaration on
(the root is resolved from a vendor environment variable and a platform
default, never a Cadrumo setting), so it lives beside the resolver it
describes rather than in :data:`~core.EXTERNAL_PATH_SETTINGS_FIELDS`, which is
keyed by settings field name.
"""


def _playwright_browsers_root(cache_root: Path | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    """Return the directory Playwright installs browser binaries into.

    Uses an explicit ``cache_root`` when supplied, otherwise honours
    ``PLAYWRIGHT_BROWSERS_PATH`` then falls back to the per-OS default cache. A
    filesystem read only — it never launches the Playwright driver (which can
    hang inside the CLI process), so the probe stays fast and non-blocking.

    Reads ``env`` (an injectable mapping so the vendor-override precedence is
    unit-tested against real dict inputs without mutating process environment
    state; defaults to ``os.environ`` for the live probe). ``cache_root`` is not
    a substitute for it: that argument short-circuits resolution entirely, so it
    exercises a different branch than the one the override precedence lives on.

    A third-party-owned cache (see :data:`PLAYWRIGHT_BROWSERS_ROOT_ROLE`): the
    application reads this location to probe for an installed build and never
    chooses or writes to it.
    """
    if cache_root is not None:
        return cache_root
    environment = os.environ if env is None else env
    override = environment.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = environment.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def probe_playwright_browser(cache_root: Path | None = None) -> DependencyStatus:
    """Probe the Playwright Chromium browser binary, returning a :class:`DependencyStatus`.

    Scans the Playwright browsers cache for an installed ``chromium*`` build using
    a fast filesystem check. The Playwright sync driver can hang inside the CLI
    process, so this probe deliberately never launches it. Missing, unreadable, or
    empty cache roots return unavailable with the ``playwright install chromium``
    remediation. ``cache_root`` is a testable override for the browser cache
    directory. The row complements the browser health probe in
    :mod:`cadrumo.application.diagnostics`; it checks workstation provisioning, not
    AEAT site reachability.
    """
    root = _playwright_browsers_root(cache_root)
    try:
        installed = root.is_dir() and any(child.name.startswith("chromium") for child in root.iterdir())
    except OSError:
        installed = False
    if not installed:
        return DependencyStatus(
            service="playwright-chromium",
            available=False,
            detail=f"no Playwright Chromium build found under {root}",
            remediation="playwright install chromium",
        )
    return DependencyStatus(
        service="playwright-chromium",
        available=True,
        detail=f"Chromium build present under {root}",
    )


def read_total_system_memory_bytes() -> int | None:
    """Return total physical system memory in bytes, or ``None`` when unreadable.

    Dependency-free on every supported platform: POSIX reads the pair of
    ``sysconf`` values, Windows calls ``GlobalMemoryStatusEx`` through
    :mod:`ctypes`. Returns ``None`` rather than raising or guessing when the
    platform answers nothing, because an unknown quantity must not be reported
    as a shortfall -- see :func:`probe_model_runtime_hardware_floor`.
    """
    if sys.platform != "win32":
        # Guarded on the platform rather than on getattr so a type checker can
        # follow it: os.sysconf is absent from the Windows stubs entirely. The
        # inner membership check stays for POSIX variants that omit the two
        # constants themselves.
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_PHYS_PAGES" in names:
            try:
                return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
            except (OSError, ValueError):
                return None
    if sys.platform == "win32":
        import ctypes

        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = (
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            )

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except (OSError, AttributeError):
            return None
    return None


def probe_model_runtime_hardware_floor(
    settings: Settings | None = None,
    *,
    total_memory_bytes: int | None = None,
) -> DependencyStatus:
    """Report whether this machine meets the local model runtime's memory floor.

    The third capability axis. The product already distinguishes *installed*
    (:class:`~cadrumo.core.OptionalExtra`) from *permitted*
    (:class:`~cadrumo.core.ServiceCapability`); this answers *capable* -- and is
    named for the floor it measures rather than for the word "capability",
    which already denotes four unrelated concepts in this tree (modelo-revision
    capability, terminal capability, operator service capability, optional-extra
    capability).

    Below the floor the local runtime does not refuse. It loads and thrashes, or
    is killed mid-read, and the operator sees an unexplained timeout. This probe
    turns that into a typed row naming the shortfall and the accepted floor.

    Unknown memory reports ``available`` **true** with a detail saying so. That
    is deliberate and is the safe direction for a *diagnostic*: an unreadable
    platform must not manufacture a shortfall that blocks a machine which may be
    perfectly adequate. The refusal is raised only on a *measured* shortfall.

    Args:
        settings: Settings carrying the configured floor; loaded when omitted.
        total_memory_bytes: Observed total memory, for callers that have already
            measured it. Defaults to :func:`read_total_system_memory_bytes`.

    Returns:
        A :class:`DependencyStatus` on the ``model-runtime-hardware-floor`` row.
    """
    resolved = settings if settings is not None else load_settings()
    floor = resolved.cadrumo_llm_model_runtime_memory_floor_bytes
    observed = total_memory_bytes if total_memory_bytes is not None else read_total_system_memory_bytes()
    floor_gib = floor / 1024**3
    if observed is None:
        return DependencyStatus(
            service="model-runtime-hardware-floor",
            available=True,
            detail=(
                f"total system memory could not be read on this platform; the local model "
                f"runtime floor of {floor_gib:.1f} GiB was not verified"
            ),
        )
    observed_gib = observed / 1024**3
    if observed < floor:
        return DependencyStatus(
            service="model-runtime-hardware-floor",
            available=False,
            detail=(
                f"total system memory {observed_gib:.1f} GiB is below the local model "
                f"runtime floor of {floor_gib:.1f} GiB for model "
                f"{resolved.cadrumo_llm_ollama_vision_model!r}"
            ),
            remediation=(
                "use a smaller local vision model (set cadrumo_llm_ollama_vision_model to "
                "moondream for low-memory hardware), or lower "
                "cadrumo_llm_model_runtime_memory_floor_bytes if this machine is known good"
            ),
        )
    return DependencyStatus(
        service="model-runtime-hardware-floor",
        available=True,
        detail=f"total system memory {observed_gib:.1f} GiB meets the {floor_gib:.1f} GiB local model runtime floor",
    )


def probe_optional_extra(extra: OptionalExtra) -> DependencyStatus:
    """Probe whether an optional package extra is importable, never raising.

    Wraps the core :func:`optional_extra_available` spec-only check for one
    :class:`~cadrumo.core.OptionalExtra` (no import, no side effects) in the doctor's
    :class:`DependencyStatus`, naming the extra's ``install_hint`` as remediation
    when absent. The feature-boundary guard is the sibling core
    :func:`~cadrumo.core.require_optional_extra`, which raises the typed
    :class:`~cadrumo.core.MissingOptionalExtraError` when a command actually
    requires the feature.
    """
    if not optional_extra_available(extra):
        return DependencyStatus(
            service=f"extra:{extra.extra}",
            available=False,
            detail=f"{extra.feature} needs the '{extra.extra}' extra ({extra.import_name} not importable)",
            remediation=extra.install_hint,
        )
    return DependencyStatus(
        service=f"extra:{extra.extra}",
        available=True,
        detail=f"{extra.feature} is available ({extra.import_name} importable)",
    )


def probe_optional_extras() -> tuple[DependencyStatus, ...]:
    """Probe every capability-gated :class:`~cadrumo.core.OptionalExtra` into :class:`DependencyStatus` rows.

    The result set is keyed by the same :data:`~cadrumo.core.OPTIONAL_EXTRAS`
    catalogue used by :func:`~cadrumo.core.require_optional_extra`, keeping
    ``aeat config check`` and runtime feature guards aligned.
    """
    return tuple(probe_optional_extra(extra) for extra in OPTIONAL_EXTRAS)
