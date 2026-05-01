"""Immutable transaction catalogue surface for the financial pipeline.

Public surface — callers must import transaction models, errors, and
service functions exclusively from ``aeat.domain.transactions`` and
must not reach into the private underscore modules inside this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._enums import CLASSIFIED_STATES, BusinessClassification, TransactionDirection, is_classified
from ._errors import (
    TransactionCatalogueError,
    TransactionError,
    TransactionNotFoundError,
    TransactionPersistenceError,
)
from ._llm import (
    MINIMUM_CLASSIFICATION_TIER,
    PIPELINE_ONLY_CLASSIFICATIONS,
    CategoryChoice,
    ClassificationChoice,
    LLMClassificationResponse,
    LLMClassifier,
    LLMClassifierError,
    ModelProfile,
    ModelTier,
    PromptSpec,
    SubprocessLLMClassifier,
    build_claude_classifier,
    build_codex_classifier,
    build_gemini_classifier,
    default_classification_choices,
    default_prompt_spec,
    prompt_spec_with_every_spending_category,
    register_classifier,
    resolve_classifier,
    unregister_classifier,
)
from ._model_tier import ModelCapability, catalogue, profiles_for_provider, resolve_profile
from ._models import ClassificationHistoryEntry, Transaction, TransactionCatalogue
from ._service import (
    find_transaction,
    link_invoice,
    set_classification,
    snapshot_classification_state,
)

if TYPE_CHECKING:
    from ._repository import ImportSummary, TransactionCatalogueRepository


def __getattr__(name: str):
    """Lazy-import the persistence repository so importing this package does
    not eagerly pull in SQLAlchemy + Alembic (whose plugin setup logs to
    stderr and breaks JSON-pipe-safety contracts in CLI test scope)."""
    if name in ("ImportSummary", "TransactionCatalogueRepository"):
        from . import _repository

        return getattr(_repository, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CLASSIFIED_STATES",
    "MINIMUM_CLASSIFICATION_TIER",
    "PIPELINE_ONLY_CLASSIFICATIONS",
    "BusinessClassification",
    "CategoryChoice",
    "ClassificationChoice",
    "ClassificationHistoryEntry",
    "ImportSummary",
    "LLMClassificationResponse",
    "LLMClassifier",
    "LLMClassifierError",
    "ModelCapability",
    "ModelProfile",
    "ModelTier",
    "PromptSpec",
    "SubprocessLLMClassifier",
    "Transaction",
    "TransactionCatalogue",
    "TransactionCatalogueError",
    "TransactionCatalogueRepository",
    "TransactionDirection",
    "TransactionError",
    "TransactionNotFoundError",
    "TransactionPersistenceError",
    "build_claude_classifier",
    "build_codex_classifier",
    "build_gemini_classifier",
    "catalogue",
    "default_classification_choices",
    "default_prompt_spec",
    "find_transaction",
    "is_classified",
    "link_invoice",
    "profiles_for_provider",
    "prompt_spec_with_every_spending_category",
    "register_classifier",
    "resolve_classifier",
    "resolve_profile",
    "set_classification",
    "snapshot_classification_state",
    "unregister_classifier",
]
