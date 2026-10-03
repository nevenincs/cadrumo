"""Modelo 720 type 2 record composition: source lots joined to the register on asset identity.

The type 2 record is one record per asset, per declarant condition (position
76) and per incorporation date (positions 415-422); the valuation is repeated
in full on each condition's record and never prorated (Orden HAP/72/2013
Anexo, positions 432-446). This module joins each euro-valued source lot to its
register entry and fans it out over the operator's declarations of that asset,
so every record pairs source-owned and operator-owned fields of the SAME asset
before any row index exists.

Unmatched sides refuse rather than default: a lot whose asset is not
registered, whose official identifier disagrees with the register, or which no
declaration covers; and a declaration in a declarable block with no lot for the
ejercicio. The condition is never assumed to be ``1`` nor the share ``100``.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.detail_record_bindings import Modelo720ValuedRow
from .register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
    M720IdentifierScheme,
)


class M720RecordJoinRefusalReason(StrEnum):
    """Why a source lot or a declaration cannot form a type 2 record."""

    UNREGISTERED_ASSET = "unregistered_asset"
    """The lot names an asset reference the register does not hold."""

    REGISTER_MISMATCH = "register_mismatch"
    """The lot's class, country or official identifier differs from its register entry."""

    UNDECLARED_ASSET = "undeclared_asset"
    """No declaration states the declarant's condition and share for the lot's asset."""

    DECLARATION_WITHOUT_SOURCE = "declaration_without_source"
    """A declared asset in a declarable block has no valuation for the ejercicio."""


class ForeignAssetRecordJoinRefusedError(CadrumoError):
    """Raised when a Modelo 720 lot and the operator's declaration do not meet on one asset."""

    def __init__(self, *, asset_ref: str, reason: M720RecordJoinRefusalReason, detail: str = "") -> None:
        """Name the asset and the side that is missing or disagrees."""
        self.asset_ref = asset_ref
        self.reason = reason
        suffix = f": {detail}" if detail else ""
        super().__init__(
            f"Modelo 720 asset {asset_ref} cannot form a type 2 record ({reason.value}){suffix}",
            context={"asset_ref": asset_ref, "reason": reason.value},
        )


class Modelo720Record(BaseModel):
    """One type 2 record: a valued lot, its register entry and one declaration of it."""

    model_config = STRICT_FROZEN_CONFIG

    row: Modelo720ValuedRow
    asset: ForeignAssetRegisterEntry
    declaration: ForeignAssetDeclarationEntry

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_asset(self) -> Modelo720Record:
        refs = {self.row.observation.asset_ref, self.asset.asset_ref, self.declaration.asset_ref}
        if len(refs) != 1:
            raise ValueError("a type 2 record joins one asset's lot, register entry and declaration")
        return self

    @property
    def source_row_identity(self) -> str:
        """The record key: the lot's source identity and the declarant condition."""
        return f"{self.row.observation.source_id}#{self.declaration.condition.value}"


def _register_disagreement(row: Modelo720ValuedRow, asset: ForeignAssetRegisterEntry) -> str:
    obs = row.observation
    if obs.asset_class_code is not asset.asset_class:
        return f"class {obs.asset_class_code.value} differs from the registered {asset.asset_class.value}"
    if obs.country_code != asset.country_code:
        return f"country {obs.country_code} differs from the registered {asset.country_code}"
    if asset.identifier.scheme is not M720IdentifierScheme.NONE and obs.asset_identifier != asset.identifier.value:
        return "official identifier differs from the registered one"
    return ""


def join_modelo_720_records(
    rows: Iterable[Modelo720ValuedRow],
    register: ForeignAssetRegister,
) -> tuple[Modelo720Record, ...]:
    """Join declarable lots to the register and fan each out over its declarations.

    Args:
        rows: The euro-valued lots of the declarable obligation blocks.
        register: The declarant's foreign-asset register and declarations.

    Raises:
        ForeignAssetRecordJoinRefusedError: A lot is unregistered, disagrees with
            its register entry, or is covered by no declaration.
    """
    assets = {asset.asset_ref: asset for asset in register.assets}
    declarations: dict[str, list[ForeignAssetDeclarationEntry]] = {}
    for declaration in register.declarations:
        declarations.setdefault(declaration.asset_ref, []).append(declaration)
    records: list[Modelo720Record] = []
    for row in rows:
        asset_ref = row.observation.asset_ref
        asset = assets.get(asset_ref)
        if asset is None:
            raise ForeignAssetRecordJoinRefusedError(
                asset_ref=asset_ref, reason=M720RecordJoinRefusalReason.UNREGISTERED_ASSET
            )
        disagreement = _register_disagreement(row, asset)
        if disagreement:
            raise ForeignAssetRecordJoinRefusedError(
                asset_ref=asset_ref, reason=M720RecordJoinRefusalReason.REGISTER_MISMATCH, detail=disagreement
            )
        declared = declarations.get(asset_ref)
        if not declared:
            raise ForeignAssetRecordJoinRefusedError(
                asset_ref=asset_ref, reason=M720RecordJoinRefusalReason.UNDECLARED_ASSET
            )
        records.extend(
            Modelo720Record(row=row, asset=asset, declaration=declaration)
            for declaration in sorted(declared, key=lambda entry: entry.condition.value)
        )
    return tuple(records)


__all__ = [
    "ForeignAssetRecordJoinRefusedError",
    "M720RecordJoinRefusalReason",
    "Modelo720Record",
    "join_modelo_720_records",
]
