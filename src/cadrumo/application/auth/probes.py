"""Canonical result codes for local provider-credential probes."""

from __future__ import annotations

from enum import StrEnum


class ProviderProbeResult(StrEnum):
    """Canonical result codes returned by the per-provider local probe."""

    NO_PROVIDER = "no_provider"
    NO_PATH_SET = "no_path_set"
    FILE_MISSING = "file_missing"
    UNREADABLE = "unreadable"
    CORRUPT = "corrupt"
    EXPIRED = "expired"
    EXPIRING = "expiring"
    OK = "ok"
    IDENTITY_UNSET = "identity_unset"
    INVALID_IDENTITY = "invalid_identity"


PROBE_RESULTS_NEEDING_ATTENTION: frozenset[ProviderProbeResult] = frozenset(
    {
        ProviderProbeResult.EXPIRING,
        ProviderProbeResult.EXPIRED,
    },
)
"""Probe results that warrant an operator-facing warning: the credential is
still usable today but its trustworthiness is degrading or has lapsed."""


__all__ = ["PROBE_RESULTS_NEEDING_ATTENTION", "ProviderProbeResult"]
