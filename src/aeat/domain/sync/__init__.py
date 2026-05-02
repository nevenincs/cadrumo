"""Sync domain package."""

from __future__ import annotations

from ._classifier import DivergenceClassifier
from ._divergence import (
    CasillaAddedWithDefault,
    CasillaRemoved,
    CasillaTypeChanged,
    DivergenceClassification,
    DivergenceKind,
    DivergencePayload,
    DivergenceRecord,
    FilingStatusChanged,
    FormulaChanged,
    LabelEsChanged,
    LabelTranslationAdded,
    PortalUrlChanged,
    ResolutionState,
    UnknownShape,
    VigenciaExtended,
    classify_kind,
)
from ._errors import (
    DivergenceClassificationError,
    DivergenceRepositoryError,
    HealingError,
    SyncError,
    WireValidationError,
)
from ._protocols import (
    CertificateContextPreloader,
    LocalCatalogueLoader,
    ModeloIdentifier,
    PortalIdentifier,
)
from ._validator import WireValidator
from ._wire import (
    WireCasilla,
    WireFilingEntry,
    WireFilingHistory,
    WireModeloDefinition,
    WirePayloadBase,
    WirePortalLink,
    WirePortalManifest,
)

__all__ = [
    "CasillaAddedWithDefault",
    "CasillaRemoved",
    "CasillaTypeChanged",
    "CertificateContextPreloader",
    "DivergenceClassification",
    "DivergenceClassificationError",
    "DivergenceClassifier",
    "DivergenceKind",
    "DivergencePayload",
    "DivergenceRecord",
    "DivergenceRepositoryError",
    "FilingStatusChanged",
    "FormulaChanged",
    "HealingError",
    "LabelEsChanged",
    "LabelTranslationAdded",
    "LocalCatalogueLoader",
    "ModeloIdentifier",
    "PortalIdentifier",
    "PortalUrlChanged",
    "ResolutionState",
    "SyncError",
    "UnknownShape",
    "VigenciaExtended",
    "WireCasilla",
    "WireFilingEntry",
    "WireFilingHistory",
    "WireModeloDefinition",
    "WirePayloadBase",
    "WirePortalLink",
    "WirePortalManifest",
    "WireValidationError",
    "WireValidator",
    "classify_kind",
]
