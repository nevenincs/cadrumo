"""Application-owned capability for the Modelo 720 foreign-asset register.

Registered operations and the 720 resolver consume this contract; an executable
composition root binds the bucket-scoped encrypted adapter.
"""

from __future__ import annotations

from typing import Protocol

from ...domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
)


class ForeignAssetRegisterRepositoryProtocol(Protocol):
    """Required bucket-bound read/write capability for the foreign-asset register."""

    def load(self) -> ForeignAssetRegister:
        """Load the register, returning an empty register when no state exists."""
        ...

    def register_asset(self, entry: ForeignAssetRegisterEntry) -> ForeignAssetRegister:
        """Atomically add one asset and return the updated register."""
        ...

    def declare(self, entry: ForeignAssetDeclarationEntry) -> ForeignAssetRegister:
        """Atomically add one declaration and return the updated register."""
        ...


class ForeignAssetRegisterRepositoryFactory(Protocol):
    """Construct the register capability bound to one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ForeignAssetRegisterRepositoryProtocol:
        """Return the required register capability for ``bucket_id``."""
        ...


__all__ = ["ForeignAssetRegisterRepositoryFactory", "ForeignAssetRegisterRepositoryProtocol"]
