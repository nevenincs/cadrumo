"""LLM provider, cache, run-record, and usage-retention settings.

Split from :mod:`~core.config` to keep the central settings facade within the
line budget. :class:`~core.config.Settings` inherits these fields (through the
mixin) with
their declared validation and defaults. The path fields declared here are
normalized and lifecycle-classified on :class:`~core.config.Settings` by name
through inheritance.

See Also:
    :class:`~core.config.Settings`
        Central environment facade that inherits this mixin and normalizes its path
        fields.
    :func:`~core.config.load_settings`
        Runtime entry point used by LLM consumers to read these fields.
"""

from __future__ import annotations

from pydantic import Field

from .config_integration_fields import CadrumoIntegrationSettings


class CadrumoLlmSettings(CadrumoIntegrationSettings):
    """Settings for the LLM provider, its on-disk caches, and retention windows."""

    # ── LLM ─────────────────────────────────────────────────────────────────
    cadrumo_llm_run_record_retention_days: int = Field(
        default=30,
        ge=1,
        description="Retention window in days for local LLM run-record records; older records are pruned",
    )
    cadrumo_llm_run_record_max_records: int = Field(
        default=5000,
        ge=1,
        description="Maximum number of local LLM run-record records retained; oldest excess records are pruned",
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


__all__ = ["CadrumoLlmSettings"]
