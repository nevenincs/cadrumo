"""Application-owned capability for the Modelo 720 foreign-asset register.

Registered operations and the 720 resolver consume this contract; an executable
composition root binds the bucket-scoped encrypted adapter.
"""

from __future__ import annotations

from typing import Protocol

from ...domain.foreign_assets.register import (
    ForeignAssetRegister,
)


class ForeignAssetRegisterRepositoryProtocol(Protocol):
    """Required bucket-bound read capability for the foreign-asset register."""

    def load(self) -> ForeignAssetRegister:
        """Load the register, returning an empty register when no state exists."""
        ...


__all__ = ["ForeignAssetRegisterRepositoryProtocol"]
