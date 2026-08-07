"""Strict Pydantic models for the LLM package.

The public :mod:`adapters.outbound.llm` facade re-exports these records.
:class:`~adapters.outbound.llm.LLMRequest`,
:class:`~adapters.outbound.llm.LLMResponse`, and
:class:`~adapters.outbound.llm.LLMProvider` form the
:class:`~adapters.outbound.llm.LLMClient` boundary.
:class:`~adapters.outbound.llm.CachedEntry`,
:class:`~adapters.outbound.llm.CacheKey`, and
:class:`~adapters.outbound.llm.CacheStats` support
:class:`~adapters.outbound.llm.LLMCache`, while
:class:`~adapters.outbound.llm.UsageRecord` and
:class:`~adapters.outbound.llm.UsageSummary` support
:class:`~adapters.outbound.llm.UsageRecorder`. Prompt definitions are
managed through :class:`~adapters.outbound.llm.PromptRegistry`; validation
helpers raise :exc:`~adapters.outbound.llm.LLMValidationError`.
"""

from __future__ import annotations

import base64
import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core import ImageMediaType
from ..core.config import LLMProvider
from ..core.hashing import sha256_hex
from ._consent import EvidenceConsentToken
from ._errors import LLMValidationError

_PROMPT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


class MultimodalImageInput(BaseModel):
    """One on-host-prepared image attached to a multimodal LLM request.

    Transient and in-memory only. Carries the base64-encoded image bytes the
    provider adapter forwards to a vision model and the content address
    (an attachment-store SHA-256) that
    :class:`~adapters.outbound.llm.LLMCache` folds into
    :class:`~adapters.outbound.llm.CacheKey`. The base64 payload is never
    persisted -- only its content address enters the cache key
    (``sensitive-financial-data-secure-storage-only``).

    ``media_type`` has no default on purpose. A local runtime sniffs the bytes,
    but a cloud provider validates the declared type against them and refuses
    the pair when they disagree -- so a defaulted media type is exactly how a
    JPEG attachment gets sent as a PNG and the read fails or, worse, is
    silently misinterpreted. The producer knows what it built; it declares it.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    content_sha256: str = Field(
        min_length=64,
        max_length=64,
        description="Lowercase hex SHA-256 content address of the source evidence bytes.",
    )
    base64_data: str = Field(
        min_length=1,
        repr=False,
        description="Base64-encoded image bytes forwarded to the provider; never persisted.",
    )
    media_type: ImageMediaType = Field(
        description="IANA media type of the encoded bytes, declared by the producer.",
    )

    @classmethod
    def from_base64(cls, base64_data: str, media_type: ImageMediaType) -> MultimodalImageInput:
        """Build one input from encoded image bytes and their known media type.

        The single place the content address is derived, so a producer cannot
        pair one image's payload with another's digest. The address is the
        SHA-256 of the DECODED bytes, matching the attachment store's own
        content addressing.

        Args:
            base64_data: Base64-encoded image bytes.
            media_type: The type those bytes actually are -- from the producer's
                own knowledge (the page rasteriser only ever emits PNG) or from
                :func:`~core.detect_image_media_type` over the raw bytes.

        Returns:
            The transient multimodal input carrying all three fields.
        """
        return cls(
            content_sha256=sha256_hex(base64.b64decode(base64_data)),
            base64_data=base64_data,
            media_type=media_type,
        )


class LLMRequest(BaseModel):
    """User-facing completion request accepted by :class:`~adapters.outbound.llm.LLMClient`.

    Provider and model override fields select
    :class:`~adapters.outbound.llm.LLMProvider` values for one call, and
    ``images`` carries transient
    :class:`~adapters.outbound.llm.MultimodalImageInput` payloads for
    local vision flows.

    ``evidence_derived`` defaults to ``False`` because most requests carry no
    taxpayer content at all -- a column-role mapping reads spreadsheet headers,
    a corpus measurement reads a public synthetic document. The fail-closed
    default lives one level up, at the evidence READERS, which mark every
    request they build unless the caller names a public corpus: an unmarked
    request is therefore a deliberate statement about the content, not an
    omission. ``consent_token`` enters neither the cache key nor any persisted
    record; it exists only between its minting site and the dispatch point.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    prompt: str = Field(description="Prompt content passed to the provider.")
    system: str | None = Field(default=None, description="Optional system instruction.")
    max_tokens: int | None = Field(default=None, ge=1, description="Maximum output tokens to request.")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0, description="Sampling temperature.")
    language: str | None = Field(default=None, description="ISO 639-1 language code for the requested output.")
    cache_key: str | None = Field(default=None, description="Optional cache grouping key.")
    provider_override: LLMProvider | None = Field(default=None, description="Override the configured provider.")
    model_override: str | None = Field(default=None, min_length=1, description="Override the configured model.")
    images: tuple[MultimodalImageInput, ...] = Field(
        default=(),
        description="On-host-prepared multimodal image inputs (empty for a text-only request).",
    )
    evidence_derived: bool = Field(
        default=False,
        description=(
            "Whether this request's content derives from a taxpayer's evidence document. "
            "Marked requests may not be dispatched off-host without a consent token."
        ),
    )
    consent_token: EvidenceConsentToken | None = Field(
        default=None,
        exclude=True,
        description="Per-invocation off-host consent proof; never persisted and never cached.",
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        """Ensure prompts are not empty or whitespace-only.

        Raises:
            :exc:`~adapters.outbound.llm.LLMValidationError`: When the
            prompt is blank after trimming.
        """
        normalized = value.strip()
        if not normalized:
            msg = "Prompt must not be empty."
            raise LLMValidationError(msg)
        return normalized

    @field_validator("system")
    @classmethod
    def validate_system(cls, value: str | None) -> str | None:
        """Normalize empty system prompts to ``None``."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        """Validate optional ISO 639-1 language codes."""
        if value is None:
            return None
        return value


class LLMResponse(BaseModel):
    """Completion response returned by :meth:`~adapters.outbound.llm.LLMClient.complete`.

    Responses are persisted inside
    :class:`~adapters.outbound.llm.CachedEntry` records and converted into
    :class:`~adapters.outbound.llm.UsageRecord` values for cost tracking.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    text: str = Field(description="Generated text returned by the provider.")
    provider: LLMProvider = Field(description="Provider that produced the response.")
    model: str = Field(description="Resolved model identifier.")
    input_tokens: int = Field(ge=0, description="Prompt-side token count.")
    output_tokens: int = Field(ge=0, description="Completion-side token count.")
    cost_estimate_usd: Decimal = Field(description="Estimated call cost in USD.")
    cache_hit: bool = Field(description="Whether the response came from the local cache.")
    created_at: datetime = Field(description="Creation timestamp in UTC.")
    request_id: str = Field(description="Stable hash of the public request.")


class PromptDefinition(BaseModel):
    """Prompt metadata stored by :class:`~adapters.outbound.llm.PromptRegistry`."""

    model_config = ConfigDict(strict=True, frozen=True, arbitrary_types_allowed=True)

    id: str = Field(description="Stable kebab-case prompt identifier.")
    version: int = Field(ge=1, description="Prompt version.")
    template: str = Field(description="Renderable template text.")
    expected_output_schema: type[BaseModel] | None = Field(
        default=None,
        description="Optional structured response schema for downstream validation.",
    )
    description: str = Field(description="Human-readable prompt purpose.")

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Ensure prompt identifiers are kebab-case."""
        if not _PROMPT_ID_PATTERN.fullmatch(value):
            msg = f"Prompt id must be kebab-case, got {value!r}"
            raise LLMValidationError(msg)
        return value


class PromptRegistry(BaseModel):
    """Registry of versioned :class:`~adapters.outbound.llm.PromptDefinition` values."""

    model_config = ConfigDict(strict=True)

    definitions: dict[str, PromptDefinition] = Field(
        default_factory=dict,
        description="Mapping of ``prompt-id:vN`` keys to prompt definitions.",
    )

    def register(self, definition: PromptDefinition) -> None:
        """Add or replace a prompt definition."""
        self.definitions[self._composite_key(definition.id, definition.version)] = definition

    def get(self, prompt_id: str, version: int | None = None) -> PromptDefinition:
        """Return a :class:`~adapters.outbound.llm.PromptDefinition` by id and optional version."""
        if version is not None:
            return self.definitions[self._composite_key(prompt_id, version)]
        candidates = [item for item in self.definitions.values() if item.id == prompt_id]
        if not candidates:
            raise KeyError(prompt_id)
        return max(candidates, key=lambda item: item.version)

    def prompt_ids(self) -> tuple[str, ...]:
        """Return the distinct prompt identifiers in the registry."""
        return tuple(sorted({item.id for item in self.definitions.values()}))

    @classmethod
    def seeded(cls) -> PromptRegistry:
        """Return a default :class:`~adapters.outbound.llm.PromptRegistry`."""
        registry = cls()
        registry.register(
            PromptDefinition(
                id="translation_v1",
                version=1,
                template=(
                    "Translate the following AEAT-related text from {source_lang} to {target_lang}. "
                    "Preserve legal meaning, tax terminology, and numbers exactly.\n\n"
                    "Context:\n{context}\n\n"
                    "Text:\n{text}"
                ),
                expected_output_schema=None,
                description="Faithful legal- and tax-aware translation prompt.",
            ),
        )
        registry.register(
            PromptDefinition(
                id="casilla_extract_v1",
                version=1,
                template=("Extract structured casilla information from the supplied source text.\n\nSource:\n{text}"),
                expected_output_schema=None,
                description="Placeholder seed for casilla extraction workflows.",
            ),
        )
        registry.register(
            PromptDefinition(
                id="manual_rule_extract_v1",
                version=1,
                template=("Extract structured tax rules from the supplied manual excerpt.\n\nManual excerpt:\n{text}"),
                expected_output_schema=None,
                description="Placeholder seed for manual rule extraction workflows.",
            ),
        )
        return registry

    @staticmethod
    def _composite_key(prompt_id: str, version: int) -> str:
        """Build the storage key for a versioned prompt."""
        return f"{prompt_id}:v{version}"


class CachedEntry(BaseModel):
    """Encrypted cache record persisted by :class:`~adapters.outbound.llm.LLMCache`."""

    model_config = ConfigDict(strict=True, frozen=True)

    provider: LLMProvider = Field(description="Provider used for the original call.")
    model: str = Field(description="Resolved provider model.")
    prompt_hash: str = Field(description="Hash of rendered prompt text.")
    args_hash: str = Field(description="Hash of request-side arguments.")
    response: LLMResponse = Field(description="Original response payload.")
    created_at: datetime = Field(description="Timestamp when the cache entry was written.")


class UsageRecord(BaseModel):
    """Append-only usage record persisted by :class:`~adapters.outbound.llm.UsageRecorder`."""

    model_config = ConfigDict(strict=True, frozen=True)

    prompt_id: str = Field(description="Prompt id associated with the call.")
    caller: str = Field(description="Logical caller that initiated the request.")
    text: str = Field(description="Generated text returned by the provider.")
    provider: LLMProvider = Field(description="Provider used for the call.")
    model: str = Field(description="Resolved model identifier.")
    input_tokens: int = Field(ge=0, description="Prompt-side token count.")
    output_tokens: int = Field(ge=0, description="Completion-side token count.")
    cost_estimate_usd: Decimal = Field(description="Estimated call cost in USD.")
    cache_hit: bool = Field(description="Whether the response came from cache.")
    created_at: datetime = Field(description="Timestamp when the record was written.")
    request_id: str = Field(description="Stable request hash.")


class Translation(BaseModel):
    """Translation response built on top of :class:`~adapters.outbound.llm.LLMResponse`."""

    model_config = ConfigDict(strict=True, frozen=True)

    text: str = Field(description="Translated text.")
    source_lang: str = Field(description="ISO 639-1 source language code.")
    target_lang: str = Field(description="ISO 639-1 target language code.")
    provider: LLMProvider = Field(description="Provider used for the translation.")
    model: str = Field(description="Resolved model identifier.")
    input_tokens: int = Field(ge=0, description="Prompt-side token count.")
    output_tokens: int = Field(ge=0, description="Completion-side token count.")
    created_at: datetime = Field(description="Translation timestamp in UTC.")

    @field_validator("source_lang", "target_lang")
    @classmethod
    def validate_translation_language(cls, value: str) -> str:
        """Validate translation language codes."""
        return value


class CacheKey(BaseModel):
    """Derived cache key used by :class:`~adapters.outbound.llm.LLMCache`."""

    model_config = ConfigDict(strict=True, frozen=True)

    provider: LLMProvider = Field(description="Provider namespace for the cache entry.")
    model: str = Field(description="Resolved model namespace for the cache entry.")
    prompt_hash: str = Field(description="Hash of rendered prompt text.")
    args_hash: str = Field(description="Hash of request arguments.")


class CacheStats(BaseModel):
    """Basic :class:`~adapters.outbound.llm.LLMCache` statistics for CLI reporting."""

    model_config = ConfigDict(strict=True, frozen=True)

    entries: int = Field(ge=0, description="Number of cached files.")
    total_bytes: int = Field(ge=0, description="Total size of cache files in bytes.")


class UsageSummary(BaseModel):
    """Aggregated :class:`~adapters.outbound.llm.UsageRecorder` statistics."""

    model_config = ConfigDict(strict=True, frozen=True)

    entries: int = Field(ge=0, description="Number of usage records included.")
    total_input_tokens: int = Field(ge=0, description="Sum of input tokens.")
    total_output_tokens: int = Field(ge=0, description="Sum of output tokens.")
    total_cost_estimate_usd: Decimal = Field(description="Sum of estimated cost in USD.")
    since: date | None = Field(default=None, description="Inclusive lower date bound.")
    until: date | None = Field(default=None, description="Inclusive upper date bound.")
