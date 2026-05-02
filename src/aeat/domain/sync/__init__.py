"""Self-healing sync domain package.

Re-exports the typed building blocks consumed by the sync runner:

- :class:`DivergenceClassifier` -- diffs paired wire payloads and emits
  :class:`DivergenceRecord` instances.
- :class:`WireValidator` -- strict JSON-to-pydantic validator for AEAT
  wire payloads.
- :class:`DivergencePayload` discriminated union and the concrete
  :class:`CasillaAddedWithDefault` / :class:`CasillaRemoved` /
  :class:`CasillaTypeChanged` / :class:`FormulaChanged` /
  :class:`LabelEsChanged` / :class:`LabelTranslationAdded` /
  :class:`PortalUrlChanged` / :class:`FilingStatusChanged` /
  :class:`UnknownShape` / :class:`VigenciaExtended` payload variants.
- :class:`DivergenceClassification`, :class:`DivergenceKind`,
  :class:`ResolutionState`, :class:`DivergenceRecord` -- taxonomy and
  record types persisted by the divergence repository.
- :class:`WireCasilla` / :class:`WireFilingEntry` /
  :class:`WireFilingHistory` / :class:`WireModeloDefinition` /
  :class:`WirePayloadBase` / :class:`WirePortalLink` /
  :class:`WirePortalManifest` -- strict frozen wire payload schemas.
- :class:`SyncError` and its subclasses
  (:class:`WireValidationError`, :class:`DivergenceClassificationError`,
  :class:`HealingError`, :class:`DivergenceRepositoryError`).
- :class:`ModeloIdentifier`, :class:`PortalIdentifier`,
  :class:`CertificateContextPreloader`, :class:`LocalCatalogueLoader` --
  Protocol surfaces and typed identifiers used at the live boundary.
- :func:`classify_kind` -- looks up the static classification bucket
  for a given :class:`DivergenceKind`.
"""

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
