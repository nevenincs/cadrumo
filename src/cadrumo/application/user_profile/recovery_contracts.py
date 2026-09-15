"""Application-owned public contracts for portable profile recovery."""

from __future__ import annotations

from enum import StrEnum, auto


class ProfileCustodyRecoveryArtifactWarning(StrEnum):
    """Stable operator warnings accompanying every recovery artifact export."""

    @staticmethod
    def _generate_next_value_(
        name: str,
        _start: int,
        _count: int,
        _last_values: list[str],
    ) -> str:
        return name

    OFFLINE_GUESSING_EXPOSURE = "OFFLINE_GUESSING_EXPOSURE"
    STORE_SEPARATELY = "STORE_SEPARATELY"
    RETAINED_EXPORTED_COPY = "RETAINED_EXPORTED_COPY"
    LOSS_DOES_NOT_BLOCK_PASSWORD_LOGIN = auto()


__all__ = ["ProfileCustodyRecoveryArtifactWarning"]
