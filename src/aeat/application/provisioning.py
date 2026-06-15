"""Typed external-dependency probes for graceful degradation and the doctor.

Each probe answers "is this external service available right now?" and returns a
typed :class:`DependencyStatus` carrying the exact remediation command when it is
not. Probes NEVER raise on absence — a missing dependency is data, not an
exception (``dependency-provisioning`` ADR). The vision read consults
:func:`probe_ollama_vision` before the expensive inference so a down server or an
unpulled model becomes an instructive refusal instead of a raw stack trace; the
``aeat config doctor`` surface renders every probe in one report.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG
from ..core.config import Settings, load_settings

__all__ = [
    "DependencyStatus",
    "probe_ollama_vision",
    "probe_playwright_browser",
    "probe_subprocess_providers",
]

_OLLAMA_PROBE_TIMEOUT_S = 2.0


class DependencyStatus(BaseModel):
    """Whether one external dependency is available, with its remediation."""

    model_config = STRICT_FROZEN_CONFIG

    service: str = Field(min_length=1)
    available: bool
    detail: str = ""
    remediation: str = ""


def _ollama_tags_url(chat_url: str) -> str:
    """Derive the ``/api/tags`` model-list URL from the configured chat URL."""
    base = chat_url.rsplit("/api/", 1)[0] if "/api/" in chat_url else chat_url.rstrip("/")
    return f"{base}/api/tags"


def probe_ollama_vision(settings: Settings | None = None) -> DependencyStatus:
    """Probe Ollama and the configured vision model, returning a :class:`DependencyStatus`.

    A fast ``GET /api/tags`` (short timeout). Returns unavailable — never raises —
    when the server is unreachable (``ollama serve``) or the configured vision
    model is not pulled (``ollama pull <model>``).
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
    """Probe each subprocess LLM CLI provider on PATH, one :class:`DependencyStatus` per provider."""
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


def probe_playwright_browser() -> DependencyStatus:
    """Probe the Playwright Chromium browser binary, returning a :class:`DependencyStatus`.

    Reads Chromium's registered executable path without launching a browser, and
    checks it exists on disk. Returns unavailable — never raises — when Playwright
    or the browser binary is absent (``playwright install chromium``).
    """
    from pathlib import Path

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = playwright.chromium.executable_path
    except Exception as exc:
        return DependencyStatus(
            service="playwright-chromium",
            available=False,
            detail=f"Playwright could not resolve the Chromium binary: {exc}",
            remediation="playwright install chromium",
        )
    if not executable or not Path(executable).exists():
        return DependencyStatus(
            service="playwright-chromium",
            available=False,
            detail="the Playwright Chromium browser binary is not installed",
            remediation="playwright install chromium",
        )
    return DependencyStatus(
        service="playwright-chromium",
        available=True,
        detail=f"Chromium binary present at {executable}",
    )
