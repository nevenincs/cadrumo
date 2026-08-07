"""Opt-in local-inference document reading, gated behind the ``llm`` extra.

This subpackage holds the probabilistic half of document ingestion: reading a
document that carries **no** structured record, by rasterising it on-host and
handing the pages to a local model. Everything exact -- the EN16931 and
Facturae readers -- stays in the deterministic core under
``adapters/inbound/einvoice``, because parsing a document that already carries
a machine-readable record is not inference and must not be gated behind an
optional extra.

**Why a subpackage rather than a sibling top-level package.** Every AST gate
enforcing secure-storage-only persistence derives its corpus from
``src/cadrumo``, and ``.importlinter`` sets ``root_package = cadrumo``. Code in
a sibling package is invisible to all of them -- which would move the code that
handles decrypted invoice bytes to the one place in the repository where the
gates forbidding temp files and plaintext side stores do not look. That inverts
the goal: the most sensitive code would become the least supervised. Staying
inside the scanned root does not grant that supervision automatically; it makes
it *reachable*, which is why this package is explicitly enumerated in the
sensitive-surface list and explicitly enrolled in the layering contract rather
than assumed to inherit either.

**The encryption ruling, and the line it does not cross.** In-memory reading,
rasterising and local inference need no encryption and no consent gate: a user
who points a local tool at a file has by that action accepted the file will be
processed, and the secure-storage rule binds persistence rather than
processing. The exemption covers PROCESSING ONLY. Anything durable -- an
extracted-document cache, a rasterised page, a debug dump, a temp file, an
extracted field draft -- returns to the core's encrypted secure storage. This
package therefore holds no repository handle, constructs no ``AttachmentStore``
and imports nothing from ``adapters.persistence``.

**Layer position.** Adapter tier: it receives already-resolved bytes and
returns a typed payload, so application code may call it while it may not reach
inward past its own tier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Static counterpart to the ``__getattr__`` below. A type checker cannot see
    # through module ``__getattr__`` -- neither the name checks nor the
    # membership test against the export set -- so without this every lazily
    # resolved symbol degrades to ``object`` at its use sites, which reads as
    # "not callable" at construction and "not allowed in a parameter
    # annotation" wherever one is declared. This block never executes, so the
    # import cycle the lazy resolution exists to break stays broken.
    from ._evidence_draft_vision import extract_invoice_fields_from_images
    from ._suggestions import (
        ExtractionPayload,
        ExtractionProducer,
        ExtractionSourceKind,
        LLMClassificationSuggestion,
        LLMProviderAvailability,
        LLMSaturatedSuggestion,
        LLMSplitApplyResult,
        LLMSplitChildSuggestion,
        LLMSplitSuggestion,
        LLMSuggestionRejectionResult,
        OperatorIvaDerivationResult,
        SubprocessProvider,
    )
    from ._vision_classifier import LocalVisionLLMClassifier

from ._client import LLMClient
from ._errors import (
    LLMCacheError,
    LLMConfigError,
    LLMError,
    LLMPdfRasterisationError,
    LLMProviderError,
    LLMRateLimitError,
)
from ._models import (
    CachedEntry,
    CacheKey,
    CacheStats,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MultimodalImageInput,
    PromptDefinition,
    PromptRegistry,
    Translation,
    UsageRecord,
    UsageSummary,
)
from ._providers import rasterise_pdf_pages_to_base64_png
from ._retention import select_retention_removal_keys
from ._text_classifier import LocalTextLLMClassifier

__all__ = [
    "CacheKey",
    "CacheStats",
    "CachedEntry",
    "ExtractionPayload",
    "ExtractionProducer",
    "ExtractionSourceKind",
    "LLMCacheError",
    "LLMClassificationSuggestion",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMPdfRasterisationError",
    "LLMProvider",
    "LLMProviderAvailability",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMResponse",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "LocalTextLLMClassifier",
    "LocalVisionLLMClassifier",
    "MultimodalImageInput",
    "OperatorIvaDerivationResult",
    "PromptDefinition",
    "PromptRegistry",
    "SubprocessProvider",
    "Translation",
    "UsageRecord",
    "UsageSummary",
    "extract_invoice_fields_from_images",
    "rasterise_pdf_pages_to_base64_png",
    "select_retention_removal_keys",
]


_SUGGESTION_EXPORTS = frozenset({
    "ExtractionPayload",
    "ExtractionProducer",
    "ExtractionSourceKind",
    "LLMClassificationSuggestion",
    "SubprocessProvider",
    "LLMProviderAvailability",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "OperatorIvaDerivationResult",
})
"""Interchange DTOs resolved lazily from :mod:`._suggestions`.

They live HERE rather than in the ledger because every LLM definition belongs
to this package; the ledger consumes them. Lazy because the DTO module reaches
back into ``application.ledger`` for one result type, so an eager binding would
close the loop at import time.
"""


def __getattr__(name: str) -> object:
    """Resolve the application-facing readers and interchange DTOs lazily.

    These need deferring for one specific reason: they import
    ``application.ledger`` for the draft and classification shapes they
    produce, while the ledger's own paths import this package to reach them --
    so an eager binding would close that loop at import time. Everything above
    is bound eagerly because nothing in it reaches back into the application
    layer. Lazy resolution governs WHEN a module executes, never WHERE a symbol
    lives: each still has exactly one canonical home and one import path.
    """
    if name in _SUGGESTION_EXPORTS:
        from . import _suggestions

        return getattr(_suggestions, name)
    if name == "LocalVisionLLMClassifier":
        from ._vision_classifier import LocalVisionLLMClassifier

        return LocalVisionLLMClassifier
    if name == "extract_invoice_fields_from_images":
        from ._evidence_draft_vision import extract_invoice_fields_from_images

        return extract_invoice_fields_from_images
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
