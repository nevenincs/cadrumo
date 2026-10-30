"""How the register words the facts of its records, derived from the models that hold them.

A token of a closed enum is worded by the catalogue under
``ledger.actividad_asset.<family>.<token>``.  The family of each enum is named
once here.  A record's fields that carry a token, a flag, a share or a table
class are found by walking the record's model, so a field added to a model is
worded or refused at import and never shown as a raw value.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

from ...core.tipos_actividad import TipoActividad
from ...domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason, PriorFreeDepreciationRegime
from ...domain.renta.actividad_asset.election import (
    AcquiredCondition,
    AmortizationMethod,
    DigitOrder,
    DirectEstimationRegime,
    OriginalPriceDetermination,
    PlanApprovalKind,
    RenewableDocumentationKind,
    RenewableInstallationPurpose,
)
from ...domain.renta.actividad_asset.fact_leaves import FactKind, fact_leaves
from ...domain.renta.actividad_asset.lifecycle import (
    AcquisitionShape,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningHistoryStatus,
    OwnershipMode,
)
from ...domain.renta.actividad_asset.register_records import AcquisitionDocumentKind, ActivityAssetDescriptorFacts
from ...domain.renta.actividad_asset.vehicle_affectation import (
    ElectricPropulsion,
    VehicleCategory,
    VehicleListedUse,
    VehiclePrivateUse,
)


class ActivityAssetFlag(StrEnum):
    """The two states of a yes-or-no fact, worded like any other token."""

    TRUE = "true"
    FALSE = "false"


_TOKEN_FAMILY_BY_ENUM: Final[Mapping[type[StrEnum], str]] = MappingProxyType(
    {
        AcquiredCondition: "acquired_condition",
        AcquisitionDocumentKind: "document_kind",
        AcquisitionShape: "acquisition_shape",
        ActivityAssetDisposalReason: "disposal_reason",
        ActivityAssetFlag: "flag",
        AmortizationMethod: "method",
        AssetBasisStage: "basis_stage",
        AssetKind: "asset_kind",
        DigitOrder: "digit_order",
        DirectEstimationRegime: "regime",
        TipoActividad: "declared_activity",
        ElectricPropulsion: "electric_propulsion",
        OpeningHistoryStatus: "opening_history_status",
        OriginalPriceDetermination: "original_price_determination",
        OwnershipMode: "ownership_mode",
        PlanApprovalKind: "plan_approval_kind",
        PriorFreeDepreciationRegime: "prior_free_depreciation_regime",
        RenewableDocumentationKind: "renewable_documentation_kind",
        RenewableInstallationPurpose: "renewable_installation_purpose",
        VehicleCategory: "vehicle_category",
        VehicleListedUse: "vehicle_listed_use",
        VehiclePrivateUse: "vehicle_private_use",
    }
)
"""The catalogue family that words each enum a register record carries."""

_RECORD_MODELS: Final[tuple[type[BaseModel], ...]] = (ActivityAssetRevision, ActivityAssetDescriptorFacts)


def token_family(enum: type[StrEnum]) -> str:
    """Name the catalogue family that words an enum's tokens.

    Raises:
        KeyError: When no family words the enum, so it cannot be served as a token.
    """
    return _TOKEN_FAMILY_BY_ENUM[enum]


def timeline_token_families() -> Mapping[str, tuple[str, type[StrEnum]]]:
    """Map each field of a register record that carries a token or a flag to its family and enum.

    A flag is a token of the ``flag`` family, so a yes-or-no fact reads like any other.
    """
    families: dict[str, tuple[str, type[StrEnum]]] = {}
    for model in _RECORD_MODELS:
        for leaf in fact_leaves(model):
            if leaf.kind is FactKind.CHOICE and leaf.tokens is not None:
                families[leaf.dotted] = (token_family(leaf.tokens), leaf.tokens)
            elif leaf.kind is FactKind.FLAG:
                families[leaf.dotted] = (token_family(ActivityAssetFlag), ActivityAssetFlag)
    return MappingProxyType(families)


def timeline_labelled_fields() -> Mapping[str, FactKind]:
    """Map each field of a register record whose value is worded by a label to the kind of label.

    A share reads as a percentage and a table class by the official name of the class.
    """
    labelled = {
        leaf.dotted: leaf.kind
        for model in _RECORD_MODELS
        for leaf in fact_leaves(model)
        if leaf.kind in {FactKind.SHARE, FactKind.CLASS}
    }
    return MappingProxyType(labelled)


def share_label(fraction: str) -> str:
    """Word a fraction as a percentage: ``0.5`` reads ``50%``."""
    percent = Decimal(fraction) * 100
    return f"{percent.normalize():f}%"


__all__ = [
    "ActivityAssetFlag",
    "share_label",
    "timeline_labelled_fields",
    "timeline_token_families",
    "token_family",
]
