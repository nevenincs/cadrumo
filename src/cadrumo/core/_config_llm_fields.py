"""LLM provider, cache, telemetry, and usage-retention settings.

Split from :mod:`~core.config` to keep the central settings facade within the
line budget. :class:`~core.config.Settings` inherits these fields (through the
:class:`~core._config_mcp_serving_fields.CadrumoMcpServingSettings` mixin) with
their declared validation and defaults. The path fields declared here are
normalized and lifecycle-classified on :class:`~core.config.Settings` by name
through inheritance; the optional API-key secrets are blank-to-``None`` coerced
there too.

See Also:
    :class:`~core.config.Settings`
        Central environment facade that inherits this mixin, normalizes its path
        fields, and coerces its optional secret fields.
    :func:`~core.config.load_settings`
        Runtime entry point used by LLM consumers to read these fields.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr

from ._config_integration_fields import CadrumoIntegrationSettings
from ._config_support import LLMProviderSetting
from .paths import PROJECT_ROOT


class CadrumoLlmSettings(CadrumoIntegrationSettings):
    """Settings for the LLM provider, its on-disk caches, and retention windows."""

    # ── LLM ─────────────────────────────────────────────────────────────────
    cadrumo_llm_provider: LLMProviderSetting = Field(
        default=LLMProviderSetting.ANTHROPIC,
        description="Default LLM provider name",
    )
    cadrumo_llm_model: str = Field(
        default="claude-sonnet-4-6",
        description="Default LLM model identifier",
    )
    cadrumo_llm_anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key (env only, never logged)",
    )
    cadrumo_llm_openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key (optional)",
    )
    cadrumo_llm_gemini_api_key: SecretStr | None = Field(
        default=None,
        description="Google Gemini API key (optional)",
    )
    cadrumo_llm_cache_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "llm-cache",
        description="Directory for on-disk LLM cache entries",
    )
    cadrumo_llm_usage_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "llm-usage",
        description="Directory for append-only LLM usage JSONL logs",
    )
    cadrumo_llm_run_telemetry_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "llm-run-telemetry",
        description="Directory for append-only local LLM run-timing telemetry logs",
    )
    cadrumo_llm_run_telemetry_retention_days: int = Field(
        default=30,
        ge=1,
        description="Retention window in days for local LLM run-telemetry records; older records are pruned",
    )
    cadrumo_llm_run_telemetry_max_records: int = Field(
        default=5000,
        ge=1,
        description="Maximum number of local LLM run-telemetry records retained; oldest excess records are pruned",
    )
    cadrumo_llm_cache_retention_days: int = Field(
        default=30,
        ge=1,
        description="Retention window in days for on-disk LLM response-cache entries; older entries are pruned",
    )
    cadrumo_llm_cache_max_records: int = Field(
        default=5000,
        ge=1,
        description="Maximum number of LLM response-cache entries retained; oldest excess entries are pruned",
    )
    cadrumo_llm_usage_retention_days: int = Field(
        default=30,
        ge=1,
        description="Retention window in days for LLM usage records; older records are pruned",
    )
    cadrumo_llm_usage_max_records: int = Field(
        default=5000,
        ge=1,
        description="Maximum number of LLM usage records retained; oldest excess records are pruned",
    )
    cadrumo_llm_default_timeout_s: int = Field(
        default=60,
        description="Default timeout for LLM provider calls in seconds",
    )
    cadrumo_llm_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for retryable LLM failures",
    )


__all__ = ["CadrumoLlmSettings"]
