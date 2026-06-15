"""Application-layer diagnostics: external-dependency probes and the doctor report.

Owns the typed availability probes (``dependency-provisioning`` ADR) that the
graceful-degradation paths and the ``aeat config doctor`` surface consume. Probes
return a typed :class:`DependencyStatus` and never raise on absence.
"""

from __future__ import annotations

from ._dependencies import (
    DependencyStatus,
    probe_ollama_vision,
    probe_playwright_browser,
    probe_subprocess_providers,
)

__all__ = [
    "DependencyStatus",
    "probe_ollama_vision",
    "probe_playwright_browser",
    "probe_subprocess_providers",
]
