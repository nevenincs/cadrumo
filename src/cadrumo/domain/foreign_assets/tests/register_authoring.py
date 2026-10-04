"""Finite fixture authoring over real typed and atomic storage kernels."""

from __future__ import annotations

from ..register import ForeignAssetDeclarationEntry, ForeignAssetRegister, ForeignAssetRegisterEntry


def with_asset(self: ForeignAssetRegister, entry: ForeignAssetRegisterEntry) -> ForeignAssetRegister:
    """Return a register with ``entry`` added; the document invariants refuse collisions."""
    return ForeignAssetRegister(assets=(*self.assets, entry), declarations=self.declarations)


def with_declaration(self: ForeignAssetRegister, entry: ForeignAssetDeclarationEntry) -> ForeignAssetRegister:
    """Return a register with ``entry`` added; an unknown asset or repeated key is refused."""
    return ForeignAssetRegister(assets=self.assets, declarations=(*self.declarations, entry))
