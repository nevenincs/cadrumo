"""Central settings module for AEAT automation.

Single source of truth for all environment variables. Every field in
:class:`Settings` maps 1:1 to an uppercase environment variable
(e.g. ``google_oauth_client_id`` → ``GOOGLE_OAUTH_CLIENT_ID``).

The companion test ``tests/test_config.py`` enforces that ``.env.example``
and this module stay fully aligned.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import (
    normalize_project_relative_path,
    normalize_project_relative_str,
)


class DivergenceSink(StrEnum):
    """Supported sinks for :class:`aeat.application.sync.DivergenceRecord` persistence."""

    FILE = "FILE"


class SecretStoreBackend(StrEnum):
    """Supported backends for the master-key secret store.

    Members:
        AUTO: Try the OS keychain first; fall back to the encrypted
            file when the keychain is unavailable. Default.
        KEYRING: OS keychain only (Windows Credential Manager, macOS
            Keychain, Linux Secret Service). Refuses to fall back.
        FILE: Encrypted file only — passphrase-derived KEK wraps the
            master key. Required for headless / CI execution where no
            usable keychain backend is available.
        UNSECURED: **Testing / throwaway only.** Master key is a
            published deterministic constant — provides ZERO
            confidentiality. Refused unless ``AEAT_ALLOW_UNENCRYPTED=1``
            is set, AND refused at profile-load time when the active
            operator profile carries a real NIF/NIE/CIF (NIF-canary).
    """

    AUTO = "auto"
    KEYRING = "keyring"
    FILE = "file"
    UNSECURED = "unsecured"


# Project root: four levels up from src/aeat/core/config.py
# (file → core/ → aeat/ → src/ → REPO_ROOT).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class LLMProviderSetting(StrEnum):
    """Closed set of provider names accepted by Settings."""

    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    LOCAL = "LOCAL"


class GoogleAuthPathSetting(StrEnum):
    """Settings-shape mirror of :class:`aeat.adapters.outbound.google.GoogleAuthPath`."""

    DESKTOP_OAUTH_LOCAL_DEV = "desktop-oauth-local-dev"
    SERVICE_ACCOUNT_AUTOMATION = "service-account-automation"


class CertificateBackendSetting(StrEnum):
    """Settings-shape selector for the AEAT certificate-handshake backend."""

    PLAYWRIGHT_CONTEXT = "playwright_context"
    HTTPX_FALLBACK = "httpx_fallback"


class AuthProviderKindSetting(StrEnum):
    """Settings-shape selector for the active AEAT authentication provider."""

    CERTIFICATE = "certificate"
    CLAVE_MOVIL = "clave_movil"


class JustificanteParserBackendSetting(StrEnum):
    """Settings-shape selector for the justificante PDF parsing backend."""

    PDFPLUMBER = "pdfplumber"
    PYMUPDF = "pymupdf"


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
    google_auth_path: GoogleAuthPathSetting | StrEnum | None = Field(
        default=None,
        description="Active Google auth path: desktop-oauth-local-dev or service-account-automation",
    )
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
    aeat_log_level: str = Field(
        default="",
        description="Optional default CLI log level override: quiet, default, verbose, or debug",
    )
    aeat_tax_residence_profile_path: Path | None = Field(
        default=None,
        description=(
            "Optional override for the operator's tax-residence profile JSON. "
            "When unset, aeat.adapters.persistence.profile uses the OS config directory."
        ),
    )

    # ── Financial ingest ───────────────────────────────────────────────────
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
        description="Directory where the invoice catalogue JSON file is stored",
    )
    aeat_attachments_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "attachments",
        description="Root directory for the attachment byte and manifest store",
    )
    aeat_usage_ratios_path: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json",
        description="User-configured per-category usage ratio overrides",
    )
    aeat_ledgers_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "ledgers",
        description="Directory for encrypted inventory and amortization ledgers",
    )

    # ── Multilingual i18n (es, en, ca, hu) ──────────────────────────────────
    aeat_output_language: str = Field(
        default="es",
        description=(
            "Target output language for user-facing content. "
            "Accepts ISO 639-1 codes from the multilingual contract: "
            "es (default, AEAT canonical), en, ca, hu."
        ),
    )
    aeat_authoritative_language_aeat_terms: str = Field(
        default="es",
        description=(
            "Authoritative language for AEAT domain terminology "
            "(modelos, registry definitions, BOE references). Must be 'es' — "
            "the project's contract pins Spanish as the legal canonical."
        ),
    )
    aeat_authoritative_language_project_docs: str = Field(
        default="en",
        description="Authoritative language for internal code and documentation",
    )
    aeat_fallback_languages: str = Field(
        default="es,en,ca,hu",
        description=(
            "Comma-separated fallback chain consulted when the target "
            "language is missing on a Translatable. Default puts Spanish "
            "first so AEAT legal text stays canonical, then English, then "
            "the remaining co-official locales."
        ),
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

    # ── Google test fixture identifiers ────────────────────────────────────
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
    aeat_secret_store_backend: SecretStoreBackend = Field(
        default=SecretStoreBackend.AUTO,
        description=(
            "Master-key backend for the secret store. "
            "auto = OS keychain when available, encrypted file fallback otherwise. "
            "keyring = OS keychain only (refuses to fall back). "
            "file = encrypted file only (required for CI / headless). "
            "unsecured = testing-only mode with a published deterministic "
            "key; requires aeat_allow_unencrypted=true and refuses real NIFs."
        ),
    )
    aeat_allow_unencrypted: bool = Field(
        default=False,
        description=(
            "Hostile-named opt-out gate for the unsecured backend. Must be "
            "set to true (env var: AEAT_ALLOW_UNENCRYPTED=1) to use "
            "aeat_secret_store_backend=unsecured. The unsecured backend "
            "is intended for testing / educational / throwaway scenarios "
            "only and provides ZERO confidentiality. The substrate refuses "
            "to load an operator profile that carries a real NIF/NIE/CIF "
            "while running in unsecured mode."
        ),
    )
    aeat_secret_store_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "secrets",
        description="Directory for the encrypted secret-store master-key file and ciphertext records",
    )
    aeat_blob_store_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "blobs",
        description="Directory containing the encrypted blob store (content-addressed, classification-aware)",
    )
    aeat_audit_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "audit",
        description="Directory for the governed audit sink (redacted, classification-aware)",
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

    # ── Manuals corpus (aeat.domain.manuals) ───────────────────────────────────────
    aeat_manuals_root: Path = Field(
        default=PROJECT_ROOT / "corpus" / "manuals",
        description="Root directory for the structured AEAT Manual práctico corpus",
    )
    aeat_manuals_review_required: bool = Field(
        default=True,
        description=(
            "When True, manual corpus verification rejects any Manual/Section/Rule record "
            "missing definition-review metadata; when False the rejection is downgraded to a warning"
        ),
    )

    # ── Normatives corpus (aeat.domain.normatives) ─────────────────────────────────
    aeat_normatives_root: Path = Field(
        default=PROJECT_ROOT / "corpus" / "normatives",
        description="Root directory for the Spanish tax normatives JSON catalogue",
    )

    # ── VAT catalogue (aeat.domain.vat) ──────────────────────────────────
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

    # ── Site-health detection ───────────────────────────────────────────────
    site_health_probe_url: str = Field(
        default="https://sede.agenciatributaria.gob.es/",
        description="AEAT Sede URL the site-health probe navigates to",
    )
    site_health_rate_limit_retry_after_default: int = Field(
        default=300,
        ge=1,
        description="Fallback Retry-After seconds when a 429/503 omits the header",
    )

    # ── AEAT certificate authentication ─────────────────────────────────────
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
    aeat_certificate_backend: CertificateBackendSetting = Field(
        default=CertificateBackendSetting.PLAYWRIGHT_CONTEXT,
        description="Which cert backend to use (PLAYWRIGHT_CONTEXT by default)",
    )
    aeat_certificate_verify_url: str = Field(
        default="https://sede.agenciatributaria.gob.es/",
        description="Target URL for aeat.adapters.outbound.aeat.auth.verify_handshake() mTLS smoke test",
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
            "must be renewed before authenticated AEAT work continues"
        ),
    )

    # ── AEAT auth provider default ──────────────────────────────────────────
    aeat_auth_provider: AuthProviderKindSetting | None = Field(
        default=None,
        description=(
            "Default auth provider for `aeat setup auth login` / `status` when "
            "--provider is omitted. When None, the CLI auto-selects the "
            "first configured provider from the canonical registry order."
        ),
    )

    # ── Cl@ve Móvil ─────────────────────────────────────────────────────────
    aeat_clave_movil_dni_nie: str | None = Field(
        default=None,
        description=(
            "Taxpayer DNI/NIE for `aeat setup auth login` using Clave Movil. "
            "Used to stamp the persisted session with the operator's "
            "identity and to pre-fill the non-QR fallback form. Not a "
            "secret on its own — the Cl@ve app on the operator's phone is "
            "the actual second factor."
        ),
    )
    aeat_clave_movil_dni_fecha: str | None = Field(
        default=None,
        description=(
            "DNI validity / expiry date (YYYY-MM-DD) used by the "
            "non-QR Cl@ve Móvil fallback form. Applies when the "
            "configured identity is a DNI."
        ),
    )
    aeat_clave_movil_nie_soporte: str | None = Field(
        default=None,
        description=(
            "NIE support number (número de soporte) used by the "
            "non-QR Cl@ve Móvil fallback form. Applies when the "
            "configured identity is a NIE."
        ),
    )
    aeat_clave_prefer_non_qr: bool = Field(
        default=False,
        description=(
            "When true, the Cl@ve Móvil provider uses the non-QR fallback "
            "(DNI/NIE + contraste) rather than the QR code. Still requires "
            "the operator to approve the push notification on the Cl@ve app."
        ),
    )
    aeat_clave_movil_timeout_ms: int = Field(
        default=300_000,
        ge=30_000,
        le=600_000,
        description=(
            "Maximum time (milliseconds) the Cl@ve Móvil provider waits for "
            "the operator to approve the push notification on their phone "
            "before aborting. AEAT's own window is ~5 minutes; 300000 matches that."
        ),
    )
    aeat_clave_sede_access_url_template: str = Field(
        default=(
            "https://sede.agenciatributaria.gob.es/static_files/common/html/"
            "selector_acceso/SelectorAccesos.html?rep=S&ref={target}&aut=CP"
        ),
        description=(
            "URL template for AEAT's auth-method selector page. `{target}` "
            "is replaced with the URL-encoded target path (e.g. "
            "`/wlpl/TEWV-CORE/ResumenVlt` for Mis expedientes)."
        ),
    )
    aeat_sede_expedientes_path: str = Field(
        default="/wlpl/TEWV-CORE/ResumenVlt",
        description=(
            "AEAT Sede path for 'Mis expedientes' — the default post-auth "
            "target used by Cl@ve Móvil login and the expedientes reader."
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

    # ── Filing-deadline engine ──────────────────────────────────────────────
    aeat_default_profile_path: Path | None = Field(
        default=None,
        description=(
            "Optional path to a JSON file with the default AutonomoProfile "
            "loaded by the filing-deadline engine when a profile path is omitted"
        ),
    )
    aeat_deadline_due_soon_days: int = Field(
        default=14,
        description=(
            "Days before an obligation's closes_on date that flag ObligationStatus.DUE_SOON in the deadline engine"
        ),
    )

    # ── Submission engine ───────────────────────────────────────────────────
    aeat_submissions_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "submissions",
        description="Directory where SubmittedFiling JSON audit records are persisted",
    )
    aeat_submission_browser_trace_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "browser-traces",
        description="Directory where submission-engine Playwright traces and screenshots are written",
    )

    # ── Self-healing sync runner ────────────────────────────────────────────
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
        description="Divergence record sink (currently only FILE is implemented)",
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

    # ── Notifications inbox ─────────────────────────────────────────────────
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

    # ── Workflow engine ─────────────────────────────────────────────────────
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

    # ── Filing draft engine ─────────────────────────────────────────────────
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

    # ── Status reader ───────────────────────────────────────────────────────
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
    aeat_status_notificaciones_path: str = Field(
        default="/wlpl/TC-UTIL/NOT-L/Notificacion",
        description=(
            "URL path for the 'Mis notificaciones' listing page. "
            "Joined against aeat_base_url. Overrideable for campaign drift."
        ),
    )

    # ── Schema extraction/cache ──────────────────────────────────────────────────
    aeat_schema_cache_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "schema-cache",
        description=("Directory where inbound schema extraction persists Modelo schemas and provenance manifests."),
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

    # ── Observability ──────────────────────────────────────────────────────
    aeat_runs_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "runs",
        description=(
            "Directory where run traces and JSONL event logs are persisted "
            "(one subdirectory per run_id, containing trace.json + events.jsonl)"
        ),
    )

    # ── Justificante parser ─────────────────────────────────────────────────
    aeat_justificantes_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "justificantes",
        description="Directory where parsed justificante PDFs and metadata are stored",
    )
    aeat_justificante_parser_backend: JustificanteParserBackendSetting = Field(
        default=JustificanteParserBackendSetting.PDFPLUMBER,
        description=(
            "Parser backend for `aeat.adapters.inbound.justificante` (PDFPLUMBER for fidelity, PYMUPDF reserved)"
        ),
    )

    # ── Filing history ──────────────────────────────────────────────────────
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
        "aeat_tax_residence_profile_path",
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

    @field_validator("aeat_certificate_backend", mode="before")
    @classmethod
    def _certificate_backend_accepts_adapter_enum_values(cls, value: object) -> object:
        """Accept legacy adapter enum names while storing settings-shape values."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"playwright_context", "httpx_fallback"}:
                return normalized
        return value

    @field_validator("aeat_status_detail_url_template")
    @classmethod
    def _detail_url_template_has_expediente_id(cls, value: str) -> str:
        """Reject templates that omit the ``{expediente_id}`` placeholder."""
        if "{expediente_id}" not in value:
            raise ValueError("aeat_status_detail_url_template must contain '{expediente_id}'")
        return value

    @field_validator(
        "aeat_clave_movil_dni_nie",
        "aeat_clave_movil_dni_fecha",
        "aeat_clave_movil_nie_soporte",
        mode="before",
    )
    @classmethod
    def _empty_optional_clave_fields_are_none(cls, value: object) -> object:
        """Treat blank env vars for optional Cl@ve Móvil identity fields as unset."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("aeat_clave_movil_dni_fecha")
    @classmethod
    def _clave_dni_fecha_is_iso_date(cls, value: str | None) -> str | None:
        """Reject DNI validity dates that are not canonical ``YYYY-MM-DD``.

        Python 3.11's ``date.fromisoformat`` also accepts the compact
        ``YYYYMMDD`` form and ISO week dates, but AEAT's Cl@ve Móvil
        ``FECHA`` input expects the hyphenated canonical form. The
        regex rejects anything else before we delegate the semantic
        check to the stdlib parser.
        """
        if value is None:
            return None
        import re as _re

        if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("AEAT_CLAVE_MOVIL_DNI_FECHA must be YYYY-MM-DD (e.g. 2030-01-01)")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("AEAT_CLAVE_MOVIL_DNI_FECHA must be a valid YYYY-MM-DD date") from exc
        return value

    @field_validator("aeat_clave_sede_access_url_template")
    @classmethod
    def _clave_sede_access_url_template_has_target(cls, value: str) -> str:
        """Reject templates that omit the ``{target}`` placeholder."""
        if "{target}" not in value:
            raise ValueError(
                "aeat_clave_sede_access_url_template must contain '{target}' for the URL-encoded post-auth path"
            )
        return value

    @classmethod
    def env_var_names(cls) -> set[str]:
        """Return the set of environment variable names this model reads."""
        return {name.upper() for name in cls.model_fields}

    @field_validator(
        "aeat_token_dir",
        "aeat_usage_ratios_path",
        "aeat_financial_txs_dir",
        "aeat_invoices_dir",
        "aeat_attachments_dir",
        "aeat_ledgers_dir",
        "aeat_storage_backup_dir",
        "aeat_secret_store_dir",
        "aeat_blob_store_dir",
        "aeat_audit_dir",
        "aeat_manuals_root",
        "aeat_normatives_root",
        "aeat_vat_catalogue_root",
        "aeat_certificate_path",
        "aeat_llm_cache_dir",
        "aeat_llm_usage_dir",
        "aeat_default_profile_path",
        "aeat_tax_residence_profile_path",
        "aeat_submissions_dir",
        "aeat_submission_browser_trace_dir",
        "aeat_sync_divergence_file_dir",
        "aeat_inbox_dir",
        "aeat_inbox_pdf_dir",
        "aeat_workflow_runs_dir",
        "aeat_workflow_draft_inputs_path",
        "aeat_drafts_dir",
        "aeat_runs_dir",
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
