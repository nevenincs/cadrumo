"""Strict pydantic models for the LLM package."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._errors import LLMValidationError

_PROMPT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    LOCAL = "LOCAL"


class LLMRequest(BaseModel):
    """User-facing completion request."""

    model_config = ConfigDict(strict=True, frozen=True)

    prompt: str = Field(description="Prompt content passed to the provider.")
    system: str | None = Field(default=None, description="Optional system instruction.")
    max_tokens: int | None = Field(default=None, ge=1, description="Maximum output tokens to request.")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0, description="Sampling temperature.")
    language: str | None = Field(default=None, description="ISO 639-1 language code for the requested output.")
    cache_key: str | None = Field(default=None, description="Optional cache grouping key.")
    provider_override: LLMProvider | None = Field(default=None, description="Override the configured provider.")
    model_override: str | None = Field(default=None, min_length=1, description="Override the configured model.")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        """Ensure prompts are not empty or whitespace-only."""
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
    """Completion response returned by the public client."""

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
    """Prompt metadata and renderable template."""

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
    """Registry of versioned prompt definitions."""

    model_config = ConfigDict(strict=True)

    definitions: dict[str, PromptDefinition] = Field(
        default_factory=dict,
        description="Mapping of ``prompt-id:vN`` keys to prompt definitions.",
    )

    def register(self, definition: PromptDefinition) -> None:
        """Add or replace a prompt definition."""
        self.definitions[self._composite_key(definition.id, definition.version)] = definition

    def get(self, prompt_id: str, version: int | None = None) -> PromptDefinition:
        """Return a :class:`PromptDefinition` by id and optional version."""
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
        """Return a :class:`PromptRegistry` seeded with the default prompts for current downstream consumers."""
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
    """On-disk cache record."""

    model_config = ConfigDict(strict=True, frozen=True)

    provider: LLMProvider = Field(description="Provider used for the original call.")
    model: str = Field(description="Resolved provider model.")
    prompt_hash: str = Field(description="Hash of rendered prompt text.")
    args_hash: str = Field(description="Hash of request-side arguments.")
    response: LLMResponse = Field(description="Original response payload.")
    created_at: datetime = Field(description="Timestamp when the cache entry was written.")


class UsageRecord(BaseModel):
    """Append-only usage log record."""

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
    """Translation response built on top of ``LLMResponse``."""

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
    """Derived on-disk cache key."""

    model_config = ConfigDict(strict=True, frozen=True)

    provider: LLMProvider = Field(description="Provider namespace for the cache entry.")
    model: str = Field(description="Resolved model namespace for the cache entry.")
    prompt_hash: str = Field(description="Hash of rendered prompt text.")
    args_hash: str = Field(description="Hash of request arguments.")


class CacheStats(BaseModel):
    """Basic cache statistics for CLI reporting."""

    model_config = ConfigDict(strict=True, frozen=True)

    entries: int = Field(ge=0, description="Number of cached files.")
    total_bytes: int = Field(ge=0, description="Total size of cache files in bytes.")


class UsageSummary(BaseModel):
    """Aggregated usage statistics."""

    model_config = ConfigDict(strict=True, frozen=True)

    entries: int = Field(ge=0, description="Number of usage records included.")
    total_input_tokens: int = Field(ge=0, description="Sum of input tokens.")
    total_output_tokens: int = Field(ge=0, description="Sum of output tokens.")
    total_cost_estimate_usd: Decimal = Field(description="Sum of estimated cost in USD.")
    since: date | None = Field(default=None, description="Inclusive lower date bound.")
    until: date | None = Field(default=None, description="Inclusive upper date bound.")
