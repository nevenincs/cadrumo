"""Live-to-local cross-validation runner.

This subpackage provides the synchronization engine against AEAT.
See the ADR at ``.vault/adr/2026-04-12-self-healing-sync-adr.md`` for
the architectural contract, including the bounded auto-heal invariant
and the Protocol-stub strategy for in-flight cross-module dependencies.
"""

from __future__ import annotations

from ._classifier import DivergenceClassifier
from ._dispatcher import HealingDispatcher, HealingPlan
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
)
from ._errors import (
    DivergenceClassificationError,
    DivergenceRepositoryError,
    HealingError,
    SyncError,
    WireValidationError,
)
from ._protocols import (
    CertificateBackend,
    CorpusLoader,
    LLMClient,
    LLMRequest,
    ManualRulesLoader,
    ModeloIdentifier,
    ModeloSchema,
    PortalIdentifier,
    Rule,
    SchemaLoader,
)
from ._repository import (
    DivergenceRecordRepository,
    JsonFileDivergenceRepository,
    StorageDivergenceRepository,
)
from ._strategies import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    EscalateStrategy,
    HealingStrategy,
    StrategyAction,
    StrategyOutcome,
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
    "AdditiveAllowlistStrategy",
    "BenignRecordStrategy",
    "CasillaAddedWithDefault",
    "CasillaRemoved",
    "CasillaTypeChanged",
    "CertificateBackend",
    "CorpusLoader",
    "DivergenceClassification",
    "DivergenceClassificationError",
    "DivergenceClassifier",
    "DivergenceKind",
    "DivergencePayload",
    "DivergenceRecord",
    "DivergenceRecordRepository",
    "DivergenceRepositoryError",
    "EscalateStrategy",
    "FilingStatusChanged",
    "FormulaChanged",
    "HealingDispatcher",
    "HealingError",
    "HealingPlan",
    "HealingStrategy",
    "JsonFileDivergenceRepository",
    "LLMClient",
    "LLMRequest",
    "LabelEsChanged",
    "LabelTranslationAdded",
    "ManualRulesLoader",
    "ModeloIdentifier",
    "ModeloSchema",
    "PortalIdentifier",
    "PortalUrlChanged",
    "ResolutionState",
    "Rule",
    "SchemaLoader",
    "StorageDivergenceRepository",
    "StrategyAction",
    "StrategyOutcome",
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
]
