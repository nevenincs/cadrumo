"""Finite fixture authoring over real typed and atomic storage kernels."""

from __future__ import annotations

from .....domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
)
from .....domain.foreign_assets.tests.register_authoring import with_asset, with_declaration
from ..foreign_assets import ForeignAssetRegisterRepository


def register_asset(self: ForeignAssetRegisterRepository, entry: ForeignAssetRegisterEntry) -> ForeignAssetRegister:
    """Atomically add one asset; the document refuses a repeated ref or official identifier."""
    return self._storage.mutate(lambda current: with_asset(current, entry))


def declare_foreign_asset(
    self: ForeignAssetRegisterRepository, entry: ForeignAssetDeclarationEntry
) -> ForeignAssetRegister:
    """Atomically add one declaration; an unknown asset or a repeated key is refused."""
    return self._storage.mutate(lambda current: with_declaration(current, entry))
