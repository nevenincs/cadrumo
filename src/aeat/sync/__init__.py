"""Live-to-local cross-validation runner.

This subpackage provides the synchronization engine against AEAT.
See the ADR at ``.vault/adr/2026-04-12-self-healing-sync-adr.md`` for
the architectural contract, including the bounded auto-heal invariant
and the Protocol-stub strategy for in-flight cross-module dependencies.
"""

from __future__ import annotations

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
    "CertificateBackend",
    "CorpusLoader",
    "DivergenceClassificationError",
    "DivergenceRepositoryError",
    "HealingError",
    "LLMClient",
    "LLMRequest",
    "ManualRulesLoader",
    "ModeloIdentifier",
    "ModeloSchema",
    "PortalIdentifier",
    "Rule",
    "SchemaLoader",
    "SyncError",
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
