"""Central settings module for AEAT automation.

Single source of truth for all environment variables. Every field in
:class:`Settings` maps 1:1 to an uppercase environment variable
(e.g. ``google_oauth_client_id`` → ``GOOGLE_OAUTH_CLIENT_ID``).

The companion test ``tests/test_config.py`` enforces that ``.env.example``
and this module stay fully aligned.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._paths import (
    normalize_project_relative_path,
    normalize_project_relative_str,
)
from .auth import CertificateBackend
from .justificante import JustificanteParserBackend


class DivergenceSink(StrEnum):
    """Supported sinks for :class:`aeat.sync.DivergenceRecord` persistence."""

    FILE = "FILE"
    STORAGE = "STORAGE"


# Project root: three levels up from src/aeat/config.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LLMProviderSetting(StrEnum):
    """Closed set of provider names accepted by Settings."""

    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    LOCAL = "LOCAL"


class Settings(BaseSettings):
    """Application settings populated from environment variables and ``.env``.

    Field names map directly to env var names (uppercased). For example,
    ``google_oauth_client_id`` reads ``GOOGLE_OAUTH_CLIENT_ID``.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "env" / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    # ── Google OAuth 2.0 (Desktop / Interactive) ────────────────────────────
    google_oauth_client_id: str = Field(
        default="",
        description="OAuth 2.0 client ID from Google Cloud Console",
    )
    google_oauth_client_secret: str = Field(
        default="",
        description="OAuth 2.0 client secret",
    )
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:8080",
        description="OAuth redirect URI for local dev server",
    )
    google_oauth_client_json: str = Field(
        default="",
        description="Path to the downloaded OAuth Desktop client JSON (used by gcloud --client-id-file)",
    )

    # ── Google Service Account (Server / Automation) ────────────────────────
    google_application_credentials: str = Field(
        default="",
        description="Path to service account JSON key file",
    )
    google_impersonate_email: str = Field(
        default="",
        description="Email to impersonate via domain-wide delegation",
    )

    # ── Google Cloud Project ────────────────────────────────────────────────
    google_cloud_project: str = Field(
        default="",
        description="GCP project ID (not project number)",
    )

    # ── Google Resource IDs ─────────────────────────────────────────────────
    google_sheets_spreadsheet_id: str = Field(
        default="",
        description="Target Google Sheets spreadsheet ID",
    )
    google_drive_folder_id: str = Field(
        default="",
        description="Target Google Drive folder ID",
    )
    google_cloud_storage_bucket: str = Field(
        default="",
        description="Cloud Storage bucket name (without gs:// prefix)",
    )

    # ── Token Storage ───────────────────────────────────────────────────────
    aeat_token_dir: Path = Field(
        default=PROJECT_ROOT / ".tokens",
        description="Directory for cached OAuth tokens",
    )

    # ── AEAT ────────────────────────────────────────────────────────────────
    aeat_base_url: str = Field(
        default="https://sede.agenciatributaria.gob.es",
        description="AEAT sede electrónica base URL",
    )

    # ── Financial ingest (#73) ─────────────────────────────────────────────
    financial_base_currency: str = Field(
        default="EUR",
        description="Fallback ISO 4217 currency used when a financial source omits a per-row currency",
    )
    financial_default_csv_encoding: str = Field(
        default="utf-8",
        description="Preferred encoding attempted first when decoding financial CSV sources",
    )
    aeat_financial_txs_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "transactions",
        description="Directory where the transaction catalogue JSON file is stored",
    )
    aeat_invoices_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "invoices",
        description="Directory where the invoice catalogue JSON file is stored (#75)",
    )
    aeat_attachments_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "attachments",
        description="Root directory for the attachment byte and manifest store",
    )
    aeat_usage_ratios_path: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json",
        description="User-configured per-category usage ratio overrides (#259)",
    )

    # ── Trilingual i18n ─────────────────────────────────────────────────────
    aeat_output_language: str = Field(
        default="es",
        description="Target output language for user-facing content (es, en, hu)",
    )
    aeat_authoritative_language_aeat_terms: str = Field(
        default="es",
        description="Authoritative language for AEAT domain terminology",
    )
    aeat_authoritative_language_project_docs: str = Field(
        default="en",
        description="Authoritative language for internal code and documentation",
    )
    aeat_fallback_languages: str = Field(
        default="en,es",
        description="Comma-separated list of fallback languages if the target language is missing",
    )

    # ── Scratch resources (provisioned by `aeat bootstrap`) ─────────────────
    aeat_scratch_folder_id: str = Field(
        default="",
        description="Drive folder ID for the aeat-scratch sandbox",
    )
    aeat_scratch_sheet_id: str = Field(
        default="",
        description="Spreadsheet ID for the aeat-scratch sandbox sheet",
    )
    aeat_scratch_doc_id: str = Field(
        default="",
        description="Document ID for the aeat-scratch sandbox doc",
    )

    # ── Google test fixtures (provisioned by scripts/provision_google_fixtures.py) ──
    aeat_google_test_fixtures_folder_id: str = Field(
        default="",
        description="Drive folder ID that roots every Google Workspace test fixture",
    )
    aeat_google_test_fixture_smoke_sheet_id: str = Field(
        default="",
        description="Spreadsheet ID for the smoke-test fixture Sheet (A1 seeded sentinel)",
    )
    aeat_google_test_fixture_smoke_doc_id: str = Field(
        default="",
        description="Document ID for the smoke-test fixture Doc (body seeded sentinel)",
    )

    # ── Storage ─────────────────────────────────────────────────────────────
    aeat_database_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'var' / 'aeat.db').as_posix()}",
        description="SQLAlchemy URL for the primary persistence backend (default: local SQLite)",
    )
    aeat_storage_auto_migrate: bool = Field(
        default=False,
        description="If true, run `alembic upgrade head` automatically on engine creation (default: false)",
    )
    aeat_storage_backup_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "backups",
        description="Directory where the storage layer writes database backups",
    )

    # ── Casilla corpus ──────────────────────────────────────────────────────
    aeat_casillas_root: Path = Field(
        default=PROJECT_ROOT / "corpus" / "casillas",
        description="Root directory for canonical casilla catalogue JSON files",
    )
    aeat_casillas_review_required: bool = Field(
        default=True,
        description="If true, verify rejects casilla records lacking definition-review metadata",
    )

    # ── Live tests ──────────────────────────────────────────────────────────
    aeat_live_tests_enabled: bool = Field(
        default=False,
        description="Opt-in flag to run @pytest.mark.live_read tests against real external services",
    )
    aeat_live_tests_google: bool = Field(
        default=False,
        description="Secondary opt-in specifically for Google Workspace fixture live tests",
    )

    # ── Live-write bypass (charter #116 R1) ─────────────────────────────────
    aeat_live_write_unsafe_bypass: bool = Field(
        default=False,
        description=(
            "UNSAFE. Pytest collection bypass factor 1 of 3 for @pytest.mark.live_write tests. "
            "NEVER set outside an interactive live-filing session. See charter #116."
        ),
    )
    aeat_live_write_unsafe_bypass_confirm: str = Field(
        default="",
        description=(
            "UNSAFE. Pytest collection bypass factor 2 of 3. Must equal the phrase: "
            "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN. NEVER set outside an interactive live-filing session."
        ),
    )

    # ── Manuals corpus (aeat.manuals, #25) ──────────────────────────────────
    aeat_manuals_root: Path = Field(
        default=PROJECT_ROOT / "corpus" / "manuals",
        description="Root directory for the structured AEAT Manual práctico corpus",
    )
    aeat_manuals_review_required: bool = Field(
        default=True,
        description=(
            "When True, 'aeat manual verify' rejects any Manual/Section/Rule record "
            "missing definition-review metadata; when False the rejection is downgraded to a warning"
        ),
    )

    # ── Normatives corpus (aeat.normatives, #45) ────────────────────────────
    aeat_normatives_root: Path = Field(
        default=PROJECT_ROOT / "corpus" / "normatives",
        description="Root directory for the Spanish tax normatives JSON catalogue",
    )

    # ── VAT catalogue (aeat.financial.vat, #85) ─────────────────────────────
    aeat_vat_catalogue_root: Path = Field(
        default=PROJECT_ROOT / "corpus" / "financial" / "vat",
        description="Root directory for the hand-reviewed VAT taxonomy catalogue",
    )

    # ── Browser Automation ──────────────────────────────────────────────────
    aeat_browser_channel: str = Field(
        default="chrome",
        description="Playwright browser channel to use (e.g., 'chrome', 'chromium', 'msedge')",
    )
    aeat_browser_headless: bool = Field(
        default=True,
        description="Run browser in headless mode",
    )
    aeat_default_profile_name: str = Field(
        default="default",
        description="Default profile name for the browser session",
    )
    aeat_proxy_url: str = Field(
        default="",
        description="Proxy URL (e.g., 'http://proxy.example.com:8080')",
    )
    aeat_proxy_username: str = Field(
        default="",
        description="Username for proxy authentication",
    )
    aeat_proxy_password_secret: str = Field(
        default="",
        description="Password for proxy authentication",
    )
    aeat_proxy_bypass: str = Field(
        default="",
        description="Comma-separated list of domains to bypass the proxy",
    )
    aeat_rate_limit_delay_seconds: float = Field(
        default=2.0,
        description="Minimum delay between AEAT requests in seconds",
    )

    # ── Site-health detection (#95) ─────────────────────────────────────────
    site_health_probe_url: str = Field(
        default="https://sede.agenciatributaria.gob.es/",
        description="AEAT Sede URL the site-health probe navigates to",
    )
    site_health_rate_limit_retry_after_default: int = Field(
        default=300,
        ge=1,
        description="Fallback Retry-After seconds when a 429/503 omits the header",
    )

    # ── AEAT certificate authentication (#8) ────────────────────────────────
    aeat_certificate_path: Path | None = Field(
        default=None,
        description="Filesystem path to the operator's PKCS#12 (.p12/.pfx) bundle",
    )
    aeat_certificate_password_secret: SecretStr | None = Field(
        default=None,
        description="PKCS#12 passphrase (env only, never logged or persisted)",
    )
    aeat_certificate_friendly_name: str | None = Field(
        default=None,
        description="Optional human-readable label for the certificate",
    )
    aeat_certificate_backend: CertificateBackend = Field(
        default=CertificateBackend.PLAYWRIGHT_CONTEXT,
        description="Which cert backend to use (PLAYWRIGHT_CONTEXT by default)",
    )
    aeat_certificate_verify_url: str = Field(
        default="https://sede.agenciatributaria.gob.es/",
        description="Target URL for aeat.auth.verify_handshake() mTLS smoke test",
    )
    aeat_auth_timeout_ms: int = Field(
        default=30_000,
        ge=1,
        description="Playwright navigation timeout for AEAT authentication probes in milliseconds",
    )
    aeat_strict_security: bool = Field(
        default=False,
        description="Raise instead of warn when AEAT credential artifact permission hardening fails",
    )
    aeat_cert_warn_days: int = Field(
        default=60,
        gt=0,
        description=(
            "Warning threshold (days) for the certificate pre-expiry gate: "
            "certificates with <= this many days remaining are surfaced as WARN"
        ),
    )
    aeat_cert_critical_days: int = Field(
        default=14,
        gt=0,
        description=(
            "Critical threshold (days) for the certificate pre-expiry gate: "
            "certificates with <= this many days remaining are CRITICAL and "
            "block live submission unless --force-expiring-cert is passed"
        ),
    )

    # ── LLM ─────────────────────────────────────────────────────────────────
    aeat_llm_provider: LLMProviderSetting = Field(
        default=LLMProviderSetting.ANTHROPIC,
        description="Default LLM provider name",
    )
    aeat_llm_model: str = Field(
        default="claude-sonnet-4-6",
        description="Default LLM model identifier",
    )
    aeat_llm_anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key (env only, never logged)",
    )
    aeat_llm_openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key (optional)",
    )
    aeat_llm_gemini_api_key: SecretStr | None = Field(
        default=None,
        description="Google Gemini API key (optional)",
    )
    aeat_llm_cache_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "llm-cache",
        description="Directory for on-disk LLM cache entries",
    )
    aeat_llm_usage_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "llm-usage",
        description="Directory for append-only LLM usage JSONL logs",
    )
    aeat_llm_default_timeout_s: int = Field(
        default=60,
        description="Default timeout for LLM provider calls in seconds",
    )
    aeat_llm_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for retryable LLM failures",
    )

    # ── Filing-deadline engine (#38) ────────────────────────────────────────
    aeat_default_profile_path: Path | None = Field(
        default=None,
        description=(
            "Optional path to a JSON file with the default AutonomoProfile "
            "loaded by `aeat deadlines` when --profile is omitted"
        ),
    )
    aeat_deadline_due_soon_days: int = Field(
        default=14,
        description=(
            "Days before an obligation's closes_on date that flag ObligationStatus.DUE_SOON in the deadline engine"
        ),
    )

    # ── Submission engine (#42) ─────────────────────────────────────────────
    aeat_submissions_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "submissions",
        description="Directory where SubmittedFiling JSON audit records are persisted",
    )
    aeat_live_submit_enabled: bool = Field(
        default=False,
        description=(
            "Interactive-only opt-in for real AEAT writes. Must never be enabled "
            "from pytest, CI, fixtures, or background jobs."
        ),
    )
    aeat_submission_browser_trace_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "browser-traces",
        description="Directory where submission-engine Playwright traces and screenshots are written",
    )

    # ── Self-healing sync runner (#11) ──────────────────────────────────────
    aeat_sync_concurrency: int = Field(
        default=4,
        description="Maximum number of concurrent sync fetches",
    )
    aeat_sync_auto_heal_allowlist: str = Field(
        default="casilla_added_with_default,label_translation_added,vigencia_extended",
        description=(
            "CSV list of DivergenceKind values the runner is permitted to "
            "auto-apply when classification==ADDITIVE and auto_heal=True"
        ),
    )
    aeat_sync_divergence_sink: DivergenceSink = Field(
        default=DivergenceSink.FILE,
        description="Divergence record sink: FILE (default) or STORAGE (pending #10)",
    )
    aeat_sync_divergence_file_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "divergences",
        description="Directory for JSON-file divergence records when sink=FILE",
    )
    aeat_sync_retry_max: int = Field(
        default=3,
        description="Maximum transient-fetch retry attempts during a sync run",
    )
    aeat_sync_retry_backoff_s: float = Field(
        default=5.0,
        description="Initial exponential backoff delay (seconds) between retries",
    )

    # ── Notifications inbox (#46) ───────────────────────────────────────────
    aeat_inbox_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "inbox",
        description="Directory where the persisted Inbox JSON file lives",
    )
    aeat_inbox_pdf_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "inbox" / "pdfs",
        description="Directory where downloaded notification PDFs are stored",
    )
    aeat_inbox_alert_lead_days: int = Field(
        default=7,
        description=(
            "Lead window (days) for `aeat inbox next-deadline`: surface CRITICAL/HIGH "
            "notifications whose appeal_deadline falls within the next N days"
        ),
    )

    # ── Workflow engine (#59) ───────────────────────────────────────────────
    aeat_workflow_runs_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "workflow-runs",
        description="Directory where WorkflowResult JSON audit records are persisted",
    )
    aeat_workflow_sync_first_default: bool = Field(
        default=True,
        description="Default for WorkflowEngine.run_next(sync_first=...) when omitted by the CLI",
    )
    aeat_workflow_draft_inputs_path: Path | None = Field(
        default=None,
        description=(
            "Optional path to a JSON file carrying the user's casilla input values "
            "consumed by the workflow engine's BUILDING_DRAFT stage"
        ),
    )

    # ── Filing draft engine (#39) ───────────────────────────────────────────
    aeat_drafts_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "drafts",
        description="Directory where filing drafts are written as JSON files",
    )
    aeat_draft_fail_on_warning: bool = Field(
        default=False,
        description=(
            "If true, build_draft raises FilingValidationError when any WARNING- or ERROR-severity finding is produced"
        ),
    )

    # ── Status reader (#43) ─────────────────────────────────────────────────
    aeat_status_cache_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "status-cache",
        description="Directory for the short-lived AEAT status-page cache",
    )
    aeat_status_cache_ttl_s: int = Field(
        default=900,
        description="TTL in seconds for status cache entries (default 15 min)",
    )
    aeat_status_browser_trace_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "browser-traces",
        description="Directory where the status reader drops Playwright trace files",
    )
    aeat_status_detail_url_template: str = Field(
        default="/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}",
        description=(
            "URL path template for an expediente detail page. "
            "Must contain '{expediente_id}'. Overrideable per campaign."
        ),
    )

    # ── Schema extraction (aeat.schema, #9) ────────────────────────────────
    aeat_schema_cache_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "schema-cache",
        description=(
            "Directory where extracted Modelo schemas and their provenance manifests are persisted by aeat.schema."
        ),
    )
    aeat_schema_source_urls_override: str = Field(
        default="",
        description=(
            "Optional JSON-encoded mapping of {modelo_code: {boe_ref: url}} "
            "that overrides the built-in BOE URL table (used for offline CI)."
        ),
    )
    aeat_schema_extraction_concurrency: int = Field(
        default=2,
        ge=1,
        description="Maximum number of BOE PDFs fetched in parallel by `aeat schema refresh`.",
    )

    # ── Observability (#99) ────────────────────────────────────────────────
    aeat_runs_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "runs",
        description=(
            "Directory where run traces and JSONL event logs are persisted "
            "(one subdirectory per run_id, containing trace.json + events.jsonl)"
        ),
    )

    # ── Justificante parser (#44) ───────────────────────────────────────────
    aeat_justificantes_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "justificantes",
        description="Directory where parsed justificante PDFs and metadata are stored",
    )
    aeat_justificante_parser_backend: JustificanteParserBackend = Field(
        default=JustificanteParserBackend.PDFPLUMBER,
        description="Parser backend for `aeat.justificante` (PDFPLUMBER for fidelity, PYMUPDF reserved)",
    )

    # ── Filing history (#168) ───────────────────────────────────────────────
    aeat_filing_history_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "filing-history",
        description="Directory where the persisted FilingHistory JSON file lives",
    )
    aeat_filing_history_cache_ttl_s: int = Field(
        default=900,
        description="TTL in seconds for per-expediente filing-history cache entries (default 15 min)",
    )
    aeat_filing_history_archive_html: bool = Field(
        default=False,
        description="If true, archive fetched detail-page HTML under <aeat_filing_history_dir>/pages/",
    )

    # ── Introspection ───────────────────────────────────────────────────────

    @field_validator(
        "aeat_certificate_path",
        "aeat_default_profile_path",
        "aeat_workflow_draft_inputs_path",
        mode="before",
    )
    @classmethod
    def _empty_optional_paths_are_none(cls, value: object) -> object:
        """Treat blank env vars for optional path fields as unset."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "aeat_certificate_password_secret",
        "aeat_llm_anthropic_api_key",
        "aeat_llm_openai_api_key",
        "aeat_llm_gemini_api_key",
        mode="before",
    )
    @classmethod
    def _empty_optional_secrets_are_none(cls, value: object) -> object:
        """Treat blank env vars for optional secret fields as unset."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("aeat_status_detail_url_template")
    @classmethod
    def _detail_url_template_has_expediente_id(cls, value: str) -> str:
        """Reject templates that omit the ``{expediente_id}`` placeholder."""
        if "{expediente_id}" not in value:
            raise ValueError("aeat_status_detail_url_template must contain '{expediente_id}'")
        return value

    @classmethod
    def env_var_names(cls) -> set[str]:
        """Return the set of environment variable names this model reads."""
        return {name.upper() for name in cls.model_fields}

    @field_validator(
        "aeat_token_dir",
        "aeat_usage_ratios_path",
        "aeat_financial_txs_dir",
        "aeat_storage_backup_dir",
        "aeat_casillas_root",
        "aeat_manuals_root",
        "aeat_normatives_root",
        "aeat_vat_catalogue_root",
        "aeat_certificate_path",
        "aeat_llm_cache_dir",
        "aeat_llm_usage_dir",
        "aeat_default_profile_path",
        "aeat_submissions_dir",
        "aeat_submission_browser_trace_dir",
        "aeat_sync_divergence_file_dir",
        "aeat_inbox_dir",
        "aeat_inbox_pdf_dir",
        "aeat_workflow_runs_dir",
        "aeat_workflow_draft_inputs_path",
        "aeat_drafts_dir",
        "aeat_status_cache_dir",
        "aeat_status_browser_trace_dir",
        "aeat_justificantes_dir",
        "aeat_filing_history_dir",
        "aeat_schema_cache_dir",
        mode="after",
    )
    @classmethod
    def _normalize_repo_relative_paths(cls, value: Path | None) -> Path | None:
        """Anchor repo-relative path settings to ``PROJECT_ROOT``."""

        return normalize_project_relative_path(value)

    @field_validator("google_oauth_client_json", "google_application_credentials", mode="after")
    @classmethod
    def _normalize_repo_relative_path_strings(cls, value: str) -> str:
        """Anchor string-backed path settings to ``PROJECT_ROOT``."""

        return normalize_project_relative_str(value)


def load_settings() -> Settings:
    """Create a Settings instance from environment variables and ``.env`` file."""
    return Settings()
