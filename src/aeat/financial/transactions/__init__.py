"""Immutable transaction catalogue surface for the financial pipeline.

Public surface — callers must import transaction models, errors, and
service functions exclusively from ``aeat.financial.transactions`` and
must not reach into the private underscore modules inside this package.
"""

from __future__ import annotations

from ._enums import CLASSIFIED_STATES, BusinessClassification, TransactionDirection, is_classified
from ._errors import (
    TransactionCatalogueError,
    TransactionError,
    TransactionNotFoundError,
    TransactionPersistenceError,
)
from ._llm import (
    PIPELINE_ONLY_CLASSIFICATIONS,
    CategoryChoice,
    ClassificationChoice,
    LLMClassificationResponse,
    LLMClassifier,
    LLMClassifierError,
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
from ._models import ClassificationHistoryEntry, Transaction, TransactionCatalogue
from ._service import (
    find_transaction,
    link_invoice,
    load_transactions,
    save_transactions,
    set_classification,
    snapshot_classification_state,
)

__all__ = [
    "CLASSIFIED_STATES",
    "PIPELINE_ONLY_CLASSIFICATIONS",
    "BusinessClassification",
    "CategoryChoice",
    "ClassificationChoice",
    "ClassificationHistoryEntry",
    "LLMClassificationResponse",
    "LLMClassifier",
    "LLMClassifierError",
    "PromptSpec",
    "SubprocessLLMClassifier",
    "Transaction",
    "TransactionCatalogue",
    "TransactionCatalogueError",
    "TransactionDirection",
    "TransactionError",
    "TransactionNotFoundError",
    "TransactionPersistenceError",
    "build_claude_classifier",
    "build_codex_classifier",
    "build_gemini_classifier",
    "default_classification_choices",
    "default_prompt_spec",
    "find_transaction",
    "is_classified",
    "link_invoice",
    "load_transactions",
    "prompt_spec_with_every_spending_category",
    "register_classifier",
    "resolve_classifier",
    "save_transactions",
    "set_classification",
    "snapshot_classification_state",
    "unregister_classifier",
]
