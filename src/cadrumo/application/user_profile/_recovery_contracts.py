"""Application-owned public contracts for portable profile recovery."""

from __future__ import annotations

from enum import StrEnum


class ProfileCustodyRecoveryArtifactWarning(StrEnum):
    """Stable operator warnings accompanying every recovery artifact export."""

    OFFLINE_GUESSING_EXPOSURE = "OFFLINE_GUESSING_EXPOSURE"
    STORE_SEPARATELY = "STORE_SEPARATELY"
    RETAINED_EXPORTED_COPY = "RETAINED_EXPORTED_COPY"
    LOSS_DOES_NOT_BLOCK_PASSWORD_LOGIN = "LOSS_DOES_NOT_BLOCK_PASSWORD_LOGIN"  # noqa: S105


__all__ = ["ProfileCustodyRecoveryArtifactWarning"]
