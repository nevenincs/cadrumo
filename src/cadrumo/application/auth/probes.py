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


__all__ = ["ProviderProbeResult"]
