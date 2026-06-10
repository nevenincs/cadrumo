"""Immutable transaction catalogue surface for the financial pipeline.

The central type is :class:`TransactionCatalogue`, which holds an immutable
mapping of ledger transactions keyed by stable transaction identifiers.
Persistence is handled by :class:`TransactionCatalogueRepository`.
Callers must import transaction models, errors, and service functions
exclusively from ``aeat.domain.transactions`` and must not reach into
the private underscore modules inside this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._classification_rule import LedgerClassificationRule
from ._enums import (
    CLASSIFIED_STATES,
    BusinessClassification,
    SplitRole,
    TransactionDirection,
    TransactionLifecycleState,
    is_classified,
)
from ._errors import (
    LedgerNoActiveBucketError,
    LedgerStorageError,
    StoredTransactionDriftError,
    TransactionCatalogueError,
    TransactionError,
    TransactionIdPrefixError,
    TransactionNotFoundError,
    TransactionPersistenceError,
    TransactionValidationError,
)
from ._llm import (
    MINIMUM_CLASSIFICATION_TIER,
    PIPELINE_ONLY_CLASSIFICATIONS,
    CategoryChoice,
    ClassificationChoice,
    IvaCategoryChoice,
    LLMClassificationResponse,
    LLMClassifier,
    LLMClassifierError,
    LLMSplitChild,
    LLMSplitResponse,
    ModelProfile,
    ModelTier,
    PromptSpec,
    SubprocessLLMClassifier,
    build_antigravity_classifier,
    build_claude_classifier,
    build_codex_classifier,
    build_split_prompt,
    default_classification_choices,
    default_iva_category_choices,
    default_prompt_spec,
    parse_response,
    parse_split_response,
    prompt_spec_with_every_spending_category,
    prompt_spec_with_saturation_fields,
    register_classifier,
    resolve_classifier,
    unregister_classifier,
)
from ._model_tier import ModelCapability, catalogue, profiles_for_provider, resolve_profile
from ._models import (
    BucketTransactionRef,
    ClassificationHistoryEntry,
    SplitLineage,
    Transaction,
    TransactionCatalogue,
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
    derive_import_fingerprint,
    derive_movement_day_key,
    derive_split_group_id,
    derive_transaction_id,
    normalise_movement_reference,
)
from ._protocols import (
    TransactionCatalogueRepositoryProtocol,
)
from ._raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ._service import (
    find_transaction,
    link_invoice,
    set_classification,
    snapshot_classification_state,
)

if TYPE_CHECKING:
    from ._repository import (
        TX_BUCKET_NAMESPACE,
        ImportSummary,
        TransactionCatalogueRepository,
        transaction_catalogue_object_key,
    )


_LAZY_REPOSITORY_NAMES = frozenset(
    {
        "ImportSummary",
        "TX_BUCKET_NAMESPACE",
        "TransactionCatalogueRepository",
        "transaction_catalogue_object_key",
    },
)


def __getattr__(name: str):
    """Lazy-import the persistence repository to avoid eagerly loading SQLAlchemy and Alembic.

    The plugin setup of those packages logs to stderr, which breaks JSON-pipe-safety
    contracts in CLI test scope.
    """
    if name in _LAZY_REPOSITORY_NAMES:
        from . import _repository

        return getattr(_repository, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CLASSIFIED_STATES",
    "MINIMUM_CLASSIFICATION_TIER",
    "PIPELINE_ONLY_CLASSIFICATIONS",
    "TX_BUCKET_NAMESPACE",
    "BucketTransactionRef",
    "BusinessClassification",
    "CategoryChoice",
    "ClassificationChoice",
    "ClassificationHistoryEntry",
    "ImportSummary",
    "IvaCategoryChoice",
    "LLMClassificationResponse",
    "LLMClassifier",
    "LLMClassifierError",
    "LLMSplitChild",
    "LLMSplitResponse",
    "LedgerClassificationRule",
    "LedgerNoActiveBucketError",
    "LedgerStorageError",
    "ModelCapability",
    "ModelProfile",
    "ModelTier",
    "PromptSpec",
    "RawProvenance",
    "RawTransaction",
    "SourceFormat",
    "SplitLineage",
    "SplitRole",
    "StoredTransactionDriftError",
    "SubprocessLLMClassifier",
    "Transaction",
    "TransactionCatalogue",
    "TransactionCatalogueError",
    "TransactionCatalogueRepository",
    "TransactionCatalogueRepositoryProtocol",
    "TransactionDirection",
    "TransactionEditLineageEntry",
    "TransactionError",
    "TransactionEvidenceProvenanceEntry",
    "TransactionIdPrefixError",
    "TransactionLifecycleLineageEntry",
    "TransactionLifecycleState",
    "TransactionNotFoundError",
    "TransactionPersistenceError",
    "TransactionValidationError",
    "build_antigravity_classifier",
    "build_claude_classifier",
    "build_codex_classifier",
    "build_split_prompt",
    "catalogue",
    "default_classification_choices",
    "default_iva_category_choices",
    "default_prompt_spec",
    "derive_import_fingerprint",
    "derive_movement_day_key",
    "derive_split_group_id",
    "derive_transaction_id",
    "find_transaction",
    "is_classified",
    "link_invoice",
    "normalise_movement_reference",
    "parse_response",
    "parse_split_response",
    "profiles_for_provider",
    "prompt_spec_with_every_spending_category",
    "prompt_spec_with_saturation_fields",
    "register_classifier",
    "resolve_classifier",
    "resolve_profile",
    "set_classification",
    "snapshot_classification_state",
    "transaction_catalogue_object_key",
    "unregister_classifier",
]
