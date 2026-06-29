"""Typed external-dependency probes for graceful degradation and ``config check``.

This module is the read-only application doctor surface: each probe asks whether
one external service or optional package extra is usable on this workstation and
returns a typed :class:`DependencyStatus` with the exact remediation command when
it is not. Probes do not provision, unlock, write profile state, or raise on
absence; a missing dependency is report data under the ``dependency-provisioning``
ADR, not an exception path.

The vision read consults :func:`probe_ollama_vision` before expensive inference,
so a down server or an unpulled model becomes an instructive refusal instead of
a raw stack trace. The ``aeat config check`` command renders this module's
statuses beside the active profile's capability posture. Optional-extra probes
walk the core :data:`~aeat.core.OPTIONAL_EXTRAS` catalogue of
:class:`~aeat.core.OptionalExtra` records, so CLI diagnostics and adapter import
guards share one registry.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from ..core import OPTIONAL_EXTRAS, STRICT_FROZEN_CONFIG, OptionalExtra, optional_extra_available
from ..core.config import Settings, load_settings

__all__ = [
    "OPTIONAL_EXTRAS",
    "DependencyStatus",
    "OptionalExtra",
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
    :class:`~aeat.core.OptionalExtra` package extras all render through the same
    payload shape.
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

    Reads ``aeat_llm_ollama_chat_url`` and ``aeat_llm_ollama_vision_model`` from
    :class:`~aeat.core.config.Settings`, then performs a short-timeout
    ``GET /api/tags``. The probe never runs inference and returns unavailable
    when the server is unreachable (``ollama serve``) or the configured model is
    not pulled (``ollama pull <model>``).
    """
    resolved = settings if settings is not None else load_settings()
    model = resolved.aeat_llm_ollama_vision_model
    url = _ollama_tags_url(resolved.aeat_llm_ollama_chat_url)
    try:
        with httpx.Client(timeout=_OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            detail=f"Ollama is not reachable at {url}",
            remediation="start Ollama (ollama serve) and ensure it listens on aeat_llm_ollama_chat_url",
        )
    names = {str(entry.get("name", "")) for entry in payload.get("models", []) if isinstance(entry, dict)}
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


def _playwright_browsers_root(cache_root: Path | None = None) -> Path:
    """Return the directory Playwright installs browser binaries into.

    Uses an explicit ``cache_root`` when supplied, otherwise honours
    ``PLAYWRIGHT_BROWSERS_PATH`` then falls back to the per-OS default cache. A
    filesystem read only — it never launches the Playwright driver (which can
    hang inside the CLI process), so the probe stays fast and non-blocking.
    """
    if cache_root is not None:
        return cache_root
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
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
    directory.
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


def probe_optional_extra(extra: OptionalExtra) -> DependencyStatus:
    """Probe whether an optional package extra is importable, never raising.

    Wraps the core :func:`optional_extra_available` spec-only check for one
    :class:`~aeat.core.OptionalExtra` (no import, no side effects) in the doctor's
    :class:`DependencyStatus`, naming the extra's ``install_hint`` as remediation
    when absent. The feature-boundary guard is the sibling core
    :func:`~aeat.core.require_optional_extra`.
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
    """Probe every capability-gated :class:`~aeat.core.OptionalExtra` into :class:`DependencyStatus` rows."""
    return tuple(probe_optional_extra(extra) for extra in OPTIONAL_EXTRAS)
