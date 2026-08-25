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
    from ._evidence_draft_text import (
        TextInvoiceFieldExtractor,
        build_text_field_extraction_prompt,
        extract_invoice_fields_from_text,
    )
    from ._evidence_draft_vision import (
        LocalVisionDocumentTranscriber,
        transcribe_document_images,
    )
    from ._invoice_field_grounding import (
        ground_extracted_fields,
        parse_invoice_extraction_response,
    )
    from ._suggestions import (
        ExtractionPayload,
        ExtractionProducer,
        LLMClassificationSuggestion,
        LLMSaturatedSuggestion,
        LLMSplitApplyResult,
        LLMSplitChildSuggestion,
        LLMSplitSuggestion,
        LLMSuggestionRejectionResult,
        OperatorIvaDerivationResult,
    )
    from ._vision_classifier import LocalVisionLLMClassifier

from ._client import (
    LLMClient,
    LLMRetryPolicy,
    provider_pacing_remaining_s,
    reset_provider_pacing,
    transport_retry_permitted,
)
from ._column_role_mapping import (
    COLUMN_ROLE_MAPPING_PROMPT_ID,
    ColumnRoleProposal,
    DiscardedDuplicateClaim,
    ObservedColumn,
    RejectedRoleProposal,
    SemanticColumnRoleMapper,
    UnknownColumnClaim,
    build_column_role_mapping_prompt,
    map_column_roles,
    parse_column_role_mapping_response,
    permitted_column_roles,
)
from ._consent import (
    EvidenceConsentToken,
    cloud_evidence_read_permitted,
    mint_evidence_consent_token,
)
from ._errors import (
    LLMBusyError,
    LLMCacheError,
    LLMConfigError,
    LLMConsentError,
    LLMContentionError,
    LLMError,
    LLMPdfRasterisationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTransientTransportError,
    LLMValidationError,
)
from ._invoice_extraction_prompt import render_invoice_extraction_prompt
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
from ._providers.base import ProviderCompletion, ProviderRequest
from ._retention import select_retention_removal_keys
from ._supply_nature_proposal import (
    SUPPLY_NATURE_PROMPT_ID,
    UNDETERMINED_SUPPLY_NATURE,
    SupplyNatureProposal,
    SupplyNatureProposer,
    build_supply_nature_prompt,
    parse_supply_nature_response,
    permitted_supply_natures,
)
from ._text_classifier import LocalTextLLMClassifier

__all__ = [
    "COLUMN_ROLE_MAPPING_PROMPT_ID",
    "SUPPLY_NATURE_PROMPT_ID",
    "UNDETERMINED_SUPPLY_NATURE",
    "CacheKey",
    "CacheStats",
    "CachedEntry",
    "ColumnRoleProposal",
    "DiscardedDuplicateClaim",
    "EvidenceConsentToken",
    "ExtractionPayload",
    "ExtractionProducer",
    "LLMBusyError",
    "LLMCacheError",
    "LLMClassificationSuggestion",
    "LLMClient",
    "LLMConfigError",
    "LLMConsentError",
    "LLMContentionError",
    "LLMError",
    "LLMPdfRasterisationError",
    "LLMProvider",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMResponse",
    "LLMRetryPolicy",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "LLMTransientTransportError",
    "LLMValidationError",
    "LocalTextLLMClassifier",
    "LocalVisionDocumentTranscriber",
    "LocalVisionLLMClassifier",
    "MultimodalImageInput",
    "ObservedColumn",
    "OperatorIvaDerivationResult",
    "PromptDefinition",
    "PromptRegistry",
    "ProviderCompletion",
    "ProviderRequest",
    "RejectedRoleProposal",
    "SemanticColumnRoleMapper",
    "SupplyNatureProposal",
    "SupplyNatureProposer",
    "TextInvoiceFieldExtractor",
    "Translation",
    "UnknownColumnClaim",
    "UsageRecord",
    "UsageSummary",
    "build_column_role_mapping_prompt",
    "build_supply_nature_prompt",
    "build_text_field_extraction_prompt",
    "cloud_evidence_read_permitted",
    "extract_invoice_fields_from_text",
    "ground_extracted_fields",
    "map_column_roles",
    "mint_evidence_consent_token",
    "parse_column_role_mapping_response",
    "parse_invoice_extraction_response",
    "parse_supply_nature_response",
    "permitted_column_roles",
    "permitted_supply_natures",
    "provider_pacing_remaining_s",
    "rasterise_pdf_pages_to_base64_png",
    "render_invoice_extraction_prompt",
    "reset_provider_pacing",
    "select_retention_removal_keys",
    "transcribe_document_images",
    "transport_retry_permitted",
]


_SUGGESTION_EXPORTS = frozenset(
    {
        "ExtractionPayload",
        "ExtractionProducer",
        "LLMClassificationSuggestion",
        "LLMSaturatedSuggestion",
        "LLMSplitApplyResult",
        "LLMSplitChildSuggestion",
        "LLMSplitSuggestion",
        "LLMSuggestionRejectionResult",
        "OperatorIvaDerivationResult",
    }
)
"""Interchange DTOs resolved lazily from :mod:`._suggestions`.

They live HERE rather than in the ledger because every LLM definition belongs
to this package; the ledger consumes them. Lazy because the DTO module reaches
back into ``application.ledger`` for one result type, so an eager binding would
close the loop at import time.
"""


_VISION_TRANSCRIPTION_EXPORTS = frozenset(
    {
        "LocalVisionDocumentTranscriber",
        "transcribe_document_images",
    }
)
"""Vision transcription surface resolved lazily from :mod:`._evidence_draft_vision`.

Lazy for the reason the text reader beside it is: the module imports
``application.ledger`` for the transcription shape it returns, while the
ledger's own paths import this package, so an eager binding would close that
loop at import time.
"""


_TEXT_EXTRACTION_EXPORTS = frozenset(
    {
        "TextInvoiceFieldExtractor",
        "build_text_field_extraction_prompt",
        "extract_invoice_fields_from_text",
    }
)
"""Text-to-fields reader surface resolved lazily from :mod:`._evidence_draft_text`.

Lazy for the same reason as the vision reader beside it: the module imports
``application.ledger`` for the draft shape it returns, while the ledger's own
paths import this package, so an eager binding would close that loop at import
time.
"""


_INVOICE_FIELD_GROUNDING_EXPORTS = frozenset(
    {
        "ground_extracted_fields",
        "parse_invoice_extraction_response",
    }
)
"""Extraction-response parsing and field grounding, resolved lazily from :mod:`._invoice_field_grounding`.

The two entry points of the invoice reading chain: one turns a model response
into the typed response envelope, the other grounds those fields into a draft
carrying provenance. Lazy for the reason the readers above are: the module
imports ``application.ledger`` for the draft shape it returns, while the
ledger's own paths import this package, so an eager binding would close that
loop at import time.
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
    if name in _VISION_TRANSCRIPTION_EXPORTS:
        from . import _evidence_draft_vision

        return getattr(_evidence_draft_vision, name)
    if name in _TEXT_EXTRACTION_EXPORTS:
        from . import _evidence_draft_text

        return getattr(_evidence_draft_text, name)
    if name in _INVOICE_FIELD_GROUNDING_EXPORTS:
        from . import _invoice_field_grounding

        return getattr(_invoice_field_grounding, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
