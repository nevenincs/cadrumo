"""Central settings facade for AEAT automation.

This module uses :class:`StorageRouteClassification` for SQL database route
classification and ``SettingsConfigDict`` for Pydantic configuration.
The primary export is the :class:`Settings` class, which is built on
:class:`pydantic_settings.BaseSettings` with custom validation rules.
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from ._config_storage_route import classify_storage_route_for_settings, settings_for_bucket_route
from ._config_support import (
    AuthProviderKindSetting,
    CertificateBackend,
    JustificanteParserBackendSetting,
    LLMProviderSetting,
    SecretStoreBackend,
    StorageRouteClassification,
    StorageRouteKind,  # noqa: F401 - public re-export from aeat.core.config
    unwrap_optional_secret,  # noqa: F401 - public re-export from aeat.core.config
)
from ._config_support import coerce_output_language_setting as _coerce_output_language_setting
from ._config_support import default_aeat_sede_origin as _default_aeat_sede_origin
from ._config_support import default_aeat_sede_origin_with_slash as _default_aeat_sede_origin_with_slash
from ._config_support import default_clave_sede_access_url_template as _default_clave_sede_access_url_template
from ._config_support import default_sede_expedientes_path as _default_sede_expedientes_path
from ._config_support import default_status_detail_url_template as _default_status_detail_url_template
from ._config_support import default_status_notificaciones_path as _default_status_notificaciones_path
from ._config_timeouts import AeatTimeoutSettings
from .errors import ActiveProfilePointerError, CoreValidationError
from .external_constants import DEFAULT_CURRENCY, DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from .paths import normalize_project_relative_path
from .resources import bundled_path

if TYPE_CHECKING:
    from .external_constants import ExternalConstants


_LOGGER = logging.getLogger(__name__)


# Project root: four levels up from src/aeat/core/config.py
# (file → core/ → aeat/ → src/ → REPO_ROOT).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEV_TEST_DATABASE_PASSWORD = "aeat-dev-test-database-password"
"""Shared development/test password for database-backed secure-storage tests."""
DEV_TEST_DATABASE_PASSWORD_ENV_VAR = "AEAT_DEV_TEST_DATABASE_PASSWORD"
"""Environment variable backing :attr:`Settings.aeat_dev_test_database_password`."""
LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD = "aeat_live_tests_enabled"
"""Settings field backing the pytest-only live-read opt-in."""
LIVE_READ_TEST_OPT_IN_ENV_VAR = "AEAT_LIVE_TESTS_ENABLED"
"""Environment variable backing :attr:`Settings.aeat_live_tests_enabled`."""


class Settings(AeatTimeoutSettings):
    """Application settings populated from environment variables and ``.env``.

    Field names map directly to env var names (uppercased). For example,
    ``aeat_base_url`` reads ``AEAT_BASE_URL``.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "env" / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    # ── Token Storage ───────────────────────────────────────────────────────
    aeat_token_dir: Path = Field(
        default=PROJECT_ROOT,
        description=(
            "Directory for cached authentication token and lock files. The "
            "``PROJECT_ROOT`` default here is a placeholder: when the field "
            "is not explicitly set, the model validator roots it at "
            "``<aeat_local_storage_root>/tokens`` so every profile store, "
            "token and lock files included, lives under one state root. An "
            "explicit ``AEAT_TOKEN_DIR`` override wins over the derived "
            "default."
        ),
    )

    # ── AEAT ────────────────────────────────────────────────────────────────
    aeat_base_url: str = Field(
        default_factory=_default_aeat_sede_origin,
        description="AEAT sede electrónica base URL",
    )
    aeat_log_level: str = Field(
        default="",
        description="Optional default CLI log level override: quiet, default, verbose, or debug",
    )
    # ── LLM provider endpoints ────────────────────────────────────────────
    aeat_llm_openai_chat_completions_url: str = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="OpenAI Chat Completions endpoint; override for OpenAI-compatible proxies",
    )
    aeat_llm_gemini_generate_content_template: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        description="Google Gemini generateContent endpoint template (``{model}`` is substituted)",
    )
    aeat_llm_ollama_chat_url: str = Field(
        default="http://127.0.0.1:11434/api/chat",
        description="Local Ollama /api/chat endpoint; override for non-localhost Ollama deployments",
    )
    aeat_llm_ollama_num_ctx: int = Field(
        default=8192,
        gt=0,
        description=(
            "Ollama context window (num_ctx) for local requests. The vision read sends "
            "the full registry allow-list prompt plus the encoded invoice image, which "
            "exceeds Ollama's 4096 default; 8192 fits the prompt + image + output with "
            "headroom and still runs on consumer hardware"
        ),
    )
    aeat_llm_vision_read_timeout_s: int = Field(
        default=300,
        gt=0,
        description=(
            "Per-request timeout for the on-host local vision read; larger than the "
            "general LLM timeout because a local vision model on consumer hardware "
            "(CPU or a modest GPU) can take one to several minutes to read an invoice"
        ),
    )
    aeat_llm_ollama_vision_model: str = Field(
        default="qwen2.5vl:3b",
        description=(
            "Local Ollama vision model used to read scanned/image evidence on-host "
            "(the default, gestor-allowed posture); must be a multimodal model pulled "
            "into the local Ollama runtime. Default qwen2.5vl:3b (~3 GB) is "
            "document/OCR-grade and runs on normal consumer hardware (modest GPU or "
            "CPU); override to qwen2.5vl:7b for an 8 GB+ GPU or moondream for "
            "CPU-only/low-memory (see the consumer-hardware vision-model ADR)"
        ),
    )
    aeat_llm_default_max_tokens: int = Field(
        default=1024,
        gt=0,
        description="Default maximum output tokens when an LLM request omits ``max_tokens``",
    )
    aeat_llm_default_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature when an LLM request omits ``temperature``",
    )
    # ── Browser context defaults ───────────────────────────────────────────
    aeat_browser_locale: str = Field(
        default="es-ES",
        min_length=2,
        description="Default browser locale passed to Playwright context (BCP-47 tag)",
    )
    aeat_browser_timezone: str = Field(
        default="Europe/Madrid",
        min_length=1,
        description="Default IANA timezone string passed to Playwright context",
    )
    aeat_browser_viewport_width: int = Field(
        default=1366,
        gt=0,
        description="Default Playwright viewport width (px) for AEAT sede sessions",
    )
    aeat_browser_viewport_height: int = Field(
        default=900,
        gt=0,
        description="Default Playwright viewport height (px) for AEAT sede sessions",
    )
    # ── File-lock acquisition ─────────────────────────────────────────────
    aeat_file_lock_timeout_s: float = Field(
        default=30.0,
        gt=0,
        description="Default exclusive file-lock acquisition timeout (seconds)",
    )
    aeat_file_lock_retry_backoff_s: float = Field(
        default=0.05,
        gt=0,
        description="Sleep interval (seconds) between non-blocking file-lock acquire attempts",
    )
    aeat_bucket_lock_poll_interval_s: float = Field(
        default=0.1,
        gt=0,
        description="Polling interval (seconds) for bucket lockfile acquisition retries",
    )
    aeat_bucket_default_idle_lock_minutes: int = Field(
        default=15,
        gt=0,
        description="Fallback idle-lock window (minutes) when a bucket manifest omits the value",
    )
    # ── Auth provider acquisition locks ──────────────────────────────────
    aeat_auth_clave_movil_lock_buffer_s: int = Field(
        default=90,
        gt=0,
        description="Headroom (seconds) added to ``aeat_clave_movil_timeout_ms`` for the acquisition lock TTL",
    )
    aeat_auth_certificate_lock_ttl_s: int = Field(
        default=180,
        gt=0,
        description="Acquisition lock TTL (seconds) for certificate-backed AEAT auth flows",
    )
    # ── Logging ───────────────────────────────────────────────────────────
    aeat_log_stderr_level: str = Field(
        default="ERROR",
        description="Log level for the stderr handler installed by ``aeat.core.logging``",
    )
    aeat_log_file_level: str = Field(
        default="DEBUG",
        description="Log level for the file handler installed by ``aeat.core.logging``",
    )
    aeat_log_root_level: str = Field(
        default="DEBUG",
        description="Root logger level installed by ``aeat.core.logging``",
    )
    # ── External downloads ──────────────────────────────────────────────
    aeat_manuals_http_timeout_s: float = Field(
        default=60.0,
        gt=0,
        description="HTTP timeout (seconds) for AEAT manual PDF downloads",
    )
    # ── Google integration ───────────────────────────────────────────────
    aeat_google_drive_vault_folder_name: str = Field(
        default="aeat-vault",
        min_length=1,
        description="Folder name created under the Google Drive root for the AEAT vault",
    )
    aeat_google_oauth_access_refresh_buffer_s: int = Field(
        default=300,
        gt=0,
        description="Clock-skew buffer (seconds) before nominal expiry when refreshing Google access tokens",
    )
    # ── Workbook parity / Sheets ─────────────────────────────────────────
    aeat_workbook_parity_per_file_timeout_s: float = Field(
        default=15.0,
        gt=0,
        description="Default per-file timeout (seconds) for workbook-parity scans",
    )
    aeat_workbook_parity_recalc_timeout_s: int = Field(
        default=60,
        gt=0,
        description="Subprocess timeout (seconds) when forcing workbook recalculation",
    )
    aeat_workbook_parity_libreoffice_timeout_s: int = Field(
        default=120,
        gt=0,
        description="Subprocess timeout (seconds) for the LibreOffice binary XLS conversion fall-back",
    )
    aeat_registry_parity_store_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "audit" / "registry" / "parity",
        description="Directory where registry parity tape artifacts are archived by default",
    )
    aeat_calc_sheets_recalc_delay_s: float = Field(
        default=2.0,
        gt=0,
        description="Delay (seconds) waiting for Google Sheets server-side recalculation between parity polls",
    )
    # ── Financial ingest ───────────────────────────────────────────────────
    financial_base_currency: str = Field(
        default=DEFAULT_CURRENCY,
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
    aeat_purchase_invoice_evidence_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "purchase-invoice-evidence",
        description="Root directory for purchase invoice evidence record manifests",
    )
    aeat_usage_ratios_path: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json",
        description="User-configured per-category usage ratio overrides",
    )
    aeat_ledgers_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "ledgers",
        description="Directory for encrypted inventory and amortization ledgers",
    )

    # ── Multilingual i18n ───────────────────────────────────────────────────
    aeat_output_language: Annotated[
        OutputLanguage | None,
        BeforeValidator(_coerce_output_language_setting),
    ] = Field(
        default=DEFAULT_OUTPUT_LANGUAGE,
        description=(
            "Target ISO 639-1 language code for user-facing content. Invalid values coerce to None "
            "and fall back to the default."
        ),
    )
    aeat_authoritative_language_aeat_terms: str = Field(
        default="es",
        description=("Authoritative language for domain terminology (modelos, registry definitions, references)."),
    )
    aeat_authoritative_language_project_docs: str = Field(
        default="en",
        description="Authoritative language for internal code and documentation",
    )
    aeat_fallback_languages: str = Field(
        default="es,en",
        description=("Comma-separated fallback chain consulted when the target language is missing."),
    )

    # ── Storage ─────────────────────────────────────────────────────────────
    aeat_database_url: str = Field(
        default="",
        description=(
            "SQLAlchemy URL for the primary persistence backend. When empty, "
            "the model validator resolves the URL through the active-profile "
            "precedence chain to "
            "``sqlite:///<aeat_local_storage_root>/buckets/<bucket-id>/db/aeat.db``; "
            "with no active profile it derives a root-level fallback at "
            "``sqlite:///<aeat_local_storage_root>/aeat.db`` so the URL is "
            "never empty when the storage root is set. Tests that need a "
            "deterministic location supply this field explicitly; production "
            "reads the computed value."
        ),
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
    # Typed as ``str`` (not ``bool``) to preserve the strict-"1"-only
    # kill-switch semantic. Pydantic's bool coercion would widen the
    # opt-in surface to accept "true"/"yes"/"on" — a softer gate than
    # the safety-critical "no confidentiality" surface allows. The
    # consumer in master_key checks ``settings.aeat_allow_unencrypted
    # == "1"`` rather than truth-testing.
    aeat_allow_unencrypted: str = Field(
        default="",
        description=(
            "Hostile-named opt-out gate for the unsecured backend. Must be "
            "set to the literal '1' (env var: AEAT_ALLOW_UNENCRYPTED=1) to "
            "use aeat_secret_store_backend=unsecured. The unsecured backend "
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
    aeat_dev_test_database_password: SecretStr = Field(
        default=SecretStr(DEV_TEST_DATABASE_PASSWORD),
        description="Development/test-only password used by secure-storage subprocess tests.",
    )
    aeat_blob_store_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "blobs",
        description="Directory containing the encrypted blob store (content-addressed, classification-aware)",
    )
    aeat_audit_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "audit",
        description="Directory for the governed audit sink (redacted, classification-aware)",
    )

    # ── Outbound storage provider ───────────────────────────────────────────
    aeat_storage_provider_kind: str = Field(
        default="local_filesystem",
        description=(
            "Backend for `aeat.adapters.outbound.storage`. "
            "Accepted values: local_filesystem (default), google_drive, in_memory. "
            "google_drive additionally requires aeat_google_drive_root_folder_id "
            "and a per-profile registered OAuth client + token via `aeat config google`."
        ),
    )
    aeat_local_storage_root: Path = Field(
        default=PROJECT_ROOT / "var" / "storage",
        description=(
            "Root directory for the LocalFileSystemProvider backend. Each namespace "
            "becomes a subdirectory; each object is a `<hmac_prefix_8>--<label>.bin` file "
            "paired with a `.meta.json` sidecar."
        ),
    )
    aeat_google_drive_root_folder_id: str | None = Field(
        default=None,
        description=(
            "Drive folder ID under which `aeat-vault/` is created and used. "
            "Required when aeat_storage_provider_kind=google_drive. Operator obtains "
            "this from the Cloud Console / Drive web UI; the app creates `aeat-vault/` "
            "lazily on first probe."
        ),
    )

    # ── Live tests ──────────────────────────────────────────────────────────
    # Typed as ``str`` (not ``bool``) so the strict-match safety property is
    # preserved for pytest live-test opt-in: only the literal "1" enables
    # live tests. Pydantic's bool coercion would accept "true"/"yes"/"on" —
    # a wider opt-in surface than the test-gate intent allows.
    aeat_live_tests_enabled: str = Field(
        default="",
        description="Opt-in flag (set to '1') to run @pytest.mark.aeat_live tests against real external services",
    )

    # ── Replay IPC ──────────────────────────────────────────────────────────
    # Set by ``aeat.core.observability._replay.replay_run`` on the parent
    # process before it re-enters the CLI, then read by ``run_context`` in
    # the child invocation so the persisted trace can label its
    # ``replay_of`` field with the original run id. Subprocess IPC writes
    # still go through ``os.environ[REPLAY_ACTIVE_ENV_VAR] = run_id``
    # (Settings is read-only and ``Settings()`` is re-instantiated by
    # ``load_settings()`` on each call, so the write is visible to the
    # next read).
    aeat_replay_active: str = Field(
        default="",
        description="Subprocess-IPC marker carrying the original run_id when a CLI invocation is a replay re-entry",
    )

    # ── TTY / colour ────────────────────────────────────────────────────────
    aeat_force_color: bool = Field(
        default=False,
        description=(
            "Force ANSI colour output even when stdout is not a TTY. "
            "Operators set this when piping aeat output through a terminal "
            "renderer (less -R, gh actions, etc.). Defaults to False; the "
            "should_use_color() helper consults this and the standard NO_COLOR "
            "convention through Settings rather than reading os.environ directly."
        ),
    )
    no_color: bool = Field(
        default=False,
        description=(
            "Disable ANSI colour output regardless of TTY state. Mirrors the "
            "widely-adopted no-color.org convention via the NO_COLOR environment "
            "variable; pydantic-settings reads NO_COLOR (uppercased field name) "
            "out of os.environ on Settings() instantiation, so the no-color "
            "convention is honoured without per-call-site os.environ reads."
        ),
    )
    aeat_cli_reveal_identifiers: bool = Field(
        default=False,
        description=(
            "Reveal raw profile and bucket identifiers in CLI success output "
            "instead of the paste-safe ``<profile-id>`` / ``<bucket-id>`` "
            "placeholders. Default off keeps the centralised-output-redaction "
            "policy (profile/bucket UUIDs are redacted so diagnostics are safe "
            "to paste into shared notes). A multi-client gestor who must "
            "disambiguate which bucket a command addressed sets "
            "``AEAT_CLI_REVEAL_IDENTIFIERS=1`` to opt out. This only un-redacts "
            "the opaque profile/bucket UUIDs; NIF/NIE/CIF tax identities, "
            "bearer tokens, URLs, and secure-object keys stay redacted "
            "unconditionally."
        ),
    )

    # ── Diagnostic logging ──────────────────────────────────────────────────
    aeat_log_dir: Path | None = Field(
        default=None,
        description=(
            "Diagnostic-log root directory. The ``None`` default here is a "
            "placeholder: when the field is not explicitly set, the model "
            "validator roots it at ``<aeat_local_storage_root>/logs`` so the "
            "diagnostic log lives under the one state root that "
            "``AEAT_LOCAL_STORAGE_ROOT`` scopes, isolating each workspace's "
            "log. An explicit ``AEAT_LOG_DIR`` override wins over the "
            "derived default."
        ),
    )

    # ── Workbook parity scanner ─────────────────────────────────────────────
    aeat_libreoffice_executable: Path | None = Field(
        default=None,
        description=(
            "Optional explicit path to the soffice / libreoffice binary used by "
            "the workbook-parity scanner. When None the scanner resolves it from "
            "PATH."
        ),
    )

    # ── Master-key passphrase (live-write security perimeter) ───────────────
    aeat_secret_passphrase: SecretStr | None = Field(
        default=None,
        description=(
            "Passphrase that derives the encrypted-secret-store master key. "
            "Default None — the master-key loader refuses operation on None or "
            "empty value to preserve fail-closed behaviour. Operator-facing "
            "env var is AEAT_SECRET_PASSPHRASE."
        ),
    )

    # ── Manuals corpus (aeat.domain.manuals) ───────────────────────────────────────
    aeat_manuals_root: Path = Field(
        default_factory=lambda: bundled_path("corpus", "manuals"),
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
        default_factory=lambda: bundled_path("corpus", "normatives"),
        description="Root directory for the Spanish tax normatives JSON catalogue",
    )

    # ── IVA catalogue (aeat.domain.iva) ──────────────────────────────────
    aeat_iva_catalogue_root: Path = Field(
        default_factory=lambda: bundled_path("registry", "aeat", "iva", "catalogues"),
        description="Root directory for the hand-reviewed IVA taxonomy catalogue",
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
    aeat_wallet_diagnostic_dump_dir: Path | None = Field(
        default=None,
        description=(
            "Opt-in diagnostic capture directory for the IVA compensation "
            "wallet (cartera) read. The ``None`` default disables capture and "
            "is the only production posture: with it unset the wallet read "
            "path is byte-for-byte unchanged. When set via "
            "``AEAT_WALLET_DIAGNOSTIC_DUMP_DIR`` the read dumps the full "
            "captured page tree — main document, every popup page, every child "
            "frame, and per-page screenshots — to this directory so AEAT DOM "
            "drift on the cartera surface can be diagnosed offline "
            "against real evidence. The capture may contain live taxpayer "
            "amounts; it is written only to this operator-chosen directory and "
            "must never be committed or reused as a fixture without "
            "sanitisation."
        ),
    )
    aeat_active_profile: str | None = Field(
        default=None,
        description=(
            "Per-shell override for the active operator profile. When set, "
            "wins over the <aeat-root>/active-profile pointer file in the "
            "active-profile precedence chain. Leave unset for normal "
            "installs; the pointer file is the canonical default."
        ),
    )
    aeat_proxy_url: str = Field(
        default="",
        description="Proxy URL (e.g., 'http://proxy.example.com:8080')",
    )
    aeat_proxy_username: str = Field(
        default="",
        description="Username for proxy authentication",
    )
    aeat_proxy_password_secret: SecretStr | None = Field(
        default=None,
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
        default_factory=_default_aeat_sede_origin_with_slash,
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
    aeat_certificate_backend: CertificateBackend = Field(
        default=CertificateBackend.PLAYWRIGHT_CONTEXT,
        description="Which certificate backend to use: playwright_context or httpx_fallback",
    )
    aeat_certificate_verify_url: str = Field(
        default_factory=_default_aeat_sede_origin_with_slash,
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
            "Default auth provider for `aeat config auth status` / `test` when "
            "--provider is omitted. When None, the CLI auto-selects the "
            "first configured provider from the canonical registry order."
        ),
    )

    # ── Cl@ve Móvil ─────────────────────────────────────────────────────────
    aeat_clave_movil_dni_nie: SecretStr | None = Field(
        default=None,
        description=(
            "Taxpayer DNI/NIE for `aeat config auth configure --provider clave_movil`. "
            "Used to stamp the persisted session with the operator's "
            "identity and to pre-fill the non-QR fallback form. AEAT-regulated "
            "personal identifier under Spanish tax law; typed as SecretStr to "
            "prevent leakage through repr / model_dump / ValidationError."
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
    aeat_clave_movil_nie_soporte: SecretStr | None = Field(
        default=None,
        description=(
            "NIE support number (número de soporte) used by the "
            "non-QR Cl@ve Móvil fallback form. Applies when the "
            "configured identity is a NIE. AEAT-regulated personal "
            "identifier; typed as SecretStr to prevent leakage."
        ),
    )
    aeat_clave_prefer_non_qr: bool = Field(
        default=False,
        description=(
            "When true, the Cl@ve Móvil provider uses the non-QR fallback "
            "(DNI/NIE + contraste) rather than the QR code. This still "
            "requires operator-mediated completion in Cl@ve."
        ),
    )
    aeat_clave_movil_timeout_ms: int = Field(
        default=120_000,
        ge=30_000,
        le=120_000,
        description=(
            "Maximum time (milliseconds) the Cl@ve Móvil provider waits for "
            "AEAT browser-side authentication completion "
            "before aborting. Production runs must fail fast enough for an "
            "operator to retry deliberately rather than leaving a pending "
            "request dangling."
        ),
    )
    aeat_clave_sede_access_url_template: str = Field(
        default_factory=_default_clave_sede_access_url_template,
        description=(
            "URL template for AEAT's auth-method selector page. `{target}` "
            "is replaced with the URL-encoded target path. The default "
            "template is sourced from the external constants registry."
        ),
    )
    aeat_sede_expedientes_path: str = Field(
        default_factory=_default_sede_expedientes_path,
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

    # ── Evidence reading: cloud-upload consent posture ──────────────────────
    # Default and serious-usage posture is on-host reading; sensitive evidence
    # never leaves the machine. Transmitting evidence to a cloud model is a
    # deployment-permitted, per-invocation, acknowledged exception only and is
    # categorically barred in gestor/professional deployments
    # (sensitive-financial-data-secure-storage-only).
    aeat_evidence_cloud_upload_permitted: bool = Field(
        default=False,
        description=(
            "Whether this deployment permits transmitting evidence to a cloud model at all. "
            "Default off: evidence reading is on-host only. When True, a per-invocation operator "
            "consent acknowledgement is still required for each cloud read."
        ),
    )
    aeat_evidence_gestor_mode: bool = Field(
        default=False,
        description=(
            "Gestor/professional deployment flag. When True, cloud evidence upload is categorically "
            "refused regardless of aeat_evidence_cloud_upload_permitted or per-invocation consent."
        ),
    )

    # ── Filing-deadline engine ──────────────────────────────────────────────
    aeat_deadline_due_soon_days: int = Field(
        default=14,
        description=(
            "Days before an obligation's closes_on date that flag ObligationStatus.DUE_SOON in the deadline engine"
        ),
    )

    # ── Submission engine ───────────────────────────────────────────────────
    aeat_submissions_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "submissions",
        description="Directory where ModeloPresentado JSON audit records are persisted",
    )
    aeat_submission_browser_trace_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "browser-traces",
        description="Directory where submission-engine Playwright traces and screenshots are written",
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
    aeat_m210_engine_live: bool = Field(
        default=False,
        description=(
            "Gate the M210 IRNR Phase 1 engine. When False (default) `aeat app modelo "
            "work create --modelo 210` emits the Path-B refusal stub. When True "
            "the stub guard is skipped and the engine path runs (m210_resolve_rate "
            "dispatch + representante-fiscal predicate + cuota composition). "
            "Flipped to True only after persona-replay acceptance gates pass per "
            "the m210-irnr-full-engine ADR section D5."
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
        default_factory=_default_status_detail_url_template,
        description=(
            "URL path template for an expediente detail page. "
            "Must contain '{expediente_id}'. Overrideable per campaign."
        ),
    )
    aeat_status_notificaciones_path: str = Field(
        default_factory=_default_status_notificaciones_path,
        description=(
            "URL path for the 'Mis notificaciones' listing page. "
            "Joined against aeat_base_url. Overrideable for campaign drift."
        ),
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
        description="Parser backend for `aeat.adapters.inbound.justificante`",
    )

    # ── Filing history ──────────────────────────────────────────────────────
    aeat_filing_history_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "filing-history",
        description="Directory where the persisted ModeloHistory JSON file lives",
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

    @model_validator(mode="after")
    def _validate_live_iva_timeout_hierarchy(self) -> Settings:
        if self.aeat_live_iva_declaration_capture_timeout_ms >= self.aeat_live_iva_surface_timeout_ms:
            raise ValueError(
                "aeat_live_iva_declaration_capture_timeout_ms must be lower than aeat_live_iva_surface_timeout_ms",
            )
        return self

    @model_validator(mode="after")
    def _resolve_database_url_for_active_profile(self) -> Settings:
        """Resolve ``aeat_database_url`` through the active-profile chain.

        When the field is left empty (the production default), this
        validator computes the per-bucket SQLite URL at
        ``sqlite:///<aeat_local_storage_root>/buckets/<bucket-id>/db/aeat.db``.
        Tests that pass an explicit URL bypass the resolution — the
        validator only fires the computation when the field is empty.

        Active-profile resolution honours the operator-facing
        precedence chain:

        1. ``self.aeat_active_profile`` (from ``AEAT_ACTIVE_PROFILE``
           env var, or an ``override_settings`` block in tests).
        2. ``<aeat_local_storage_root>/active-profile`` plaintext
           pointer file written by ``profile create`` / ``profile
           switch``.

        When neither rung resolves, the field derives a root-level
        fallback at ``sqlite:///<aeat_local_storage_root>/aeat.db`` so
        the two storage settings stay coherent: setting
        ``AEAT_LOCAL_STORAGE_ROOT`` alone never leaves
        ``aeat_database_url`` empty. Cold-start commands still refuse
        before touching this fallback database — every profile-scoped
        path checks for an active profile first — so the fallback
        database is a placeholder that real per-profile data never
        lands in.
        """
        if self.aeat_database_url:
            return self
        bucket_id = (self.aeat_active_profile or "").strip()
        if not bucket_id:
            # Delegate to the canonical pointer-file reader rather
            # than re-implementing the TOML parse inline. The reader
            # uses strict pydantic validation; this preserves the
            # one-resolver invariant the disaster ADR Ruling 2
            # mandates.
            from . import pointer_path, read_pointer

            try:
                pointer = read_pointer(self.aeat_local_storage_root)
            except (OSError, ValueError) as exc:
                pointer_file = pointer_path(self.aeat_local_storage_root)
                _LOGGER.debug(
                    "Invalid active-profile pointer at %s; refusing root storage fallback",
                    pointer_file,
                    exc_info=True,
                )
                raise ActiveProfilePointerError(path=pointer_file) from exc
            if pointer is not None:
                bucket_id = pointer.bucket_id.strip()
        if not bucket_id:
            fallback_db_path = self.aeat_local_storage_root / "aeat.db"
            object.__setattr__(
                self,
                "aeat_database_url",
                f"sqlite:///{fallback_db_path.as_posix()}",
            )
            return self
        bucket_db_path = self.aeat_local_storage_root / "buckets" / bucket_id / "db" / "aeat.db"
        object.__setattr__(
            self,
            "aeat_database_url",
            f"sqlite:///{bucket_db_path.as_posix()}",
        )
        return self

    @model_validator(mode="after")
    def _resolve_token_dir_under_storage_root(self) -> Settings:
        """Root ``aeat_token_dir`` under ``aeat_local_storage_root``.

        When the field is not explicitly supplied (the production
        default), this validator computes
        ``<aeat_local_storage_root>/tokens`` so that auth token and
        lock files live inside the one state root that
        ``AEAT_LOCAL_STORAGE_ROOT`` scopes — making the isolation
        contract tests and the persona harness rely on actually true.

        An explicit ``AEAT_TOKEN_DIR`` env var (or a value supplied via
        an ``override_settings`` block in tests) registers the field in
        ``model_fields_set`` and wins: the validator only computes the
        derived path when the field was left at its placeholder
        default.

        ``mode="after"`` guarantees ``aeat_local_storage_root`` is
        already populated when this runs.
        """
        if "aeat_token_dir" in self.model_fields_set:
            return self
        object.__setattr__(
            self,
            "aeat_token_dir",
            self.aeat_local_storage_root / "tokens",
        )
        return self

    @model_validator(mode="after")
    def _resolve_log_dir_under_storage_root(self) -> Settings:
        """Root ``aeat_log_dir`` under ``aeat_local_storage_root``.

        When the field is not explicitly supplied (the production
        default of ``None``), this validator computes
        ``<aeat_local_storage_root>/logs`` so the diagnostic log lives
        inside the one state root that ``AEAT_LOCAL_STORAGE_ROOT``
        scopes — consistent with the token directory. A system-wide
        ``~/.config/aeat/logs/aeat.log`` mixes every workspace's (and
        every test run's) records into a single file; rooting the log
        under the storage root keeps each workspace's diagnostics
        isolated.

        An explicit ``AEAT_LOG_DIR`` env var (or a value supplied via
        an ``override_settings`` block in tests) registers the field in
        ``model_fields_set`` and wins: the validator only computes the
        derived path when the field was left at its ``None`` default.

        ``mode="after"`` guarantees ``aeat_local_storage_root`` is
        already populated when this runs.
        """
        if "aeat_log_dir" in self.model_fields_set:
            return self
        object.__setattr__(
            self,
            "aeat_log_dir",
            self.aeat_local_storage_root / "logs",
        )
        return self

    @field_validator(
        "aeat_certificate_path",
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
            raise CoreValidationError("aeat_status_detail_url_template must contain '{expediente_id}'")
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
            raise CoreValidationError("AEAT_CLAVE_MOVIL_DNI_FECHA must be YYYY-MM-DD (e.g. 2030-01-01)")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise CoreValidationError("AEAT_CLAVE_MOVIL_DNI_FECHA must be a valid YYYY-MM-DD date") from exc
        return value

    @field_validator("aeat_clave_sede_access_url_template")
    @classmethod
    def _clave_sede_access_url_template_has_target(cls, value: str) -> str:
        """Reject templates that omit the ``{target}`` placeholder."""
        if "{target}" not in value:
            raise CoreValidationError(
                "aeat_clave_sede_access_url_template must contain '{target}' for the URL-encoded post-auth path",
            )
        return value

    @classmethod
    def env_var_names(cls) -> set[str]:
        """Return the set of environment variable names this model reads."""
        return {name.upper() for name in cls.model_fields}

    @staticmethod
    def external_constants() -> ExternalConstants:
        """Return the parsed external-constants registry.

        Bridges :mod:`aeat.core.external_constants` to the settings facade
        so callers reach third-party hostnames, AEAT service paths, OAuth
        scopes, and LLM endpoints through a single accessor.

        Returns:
            The process-wide cached :class:`ExternalConstants` instance.
        """
        from .external_constants import load_external_constants

        return load_external_constants()

    @field_validator(
        "aeat_token_dir",
        "aeat_usage_ratios_path",
        "aeat_financial_txs_dir",
        "aeat_invoices_dir",
        "aeat_attachments_dir",
        "aeat_purchase_invoice_evidence_dir",
        "aeat_ledgers_dir",
        "aeat_local_storage_root",
        "aeat_log_dir",
        "aeat_storage_backup_dir",
        "aeat_secret_store_dir",
        "aeat_blob_store_dir",
        "aeat_audit_dir",
        "aeat_registry_parity_store_dir",
        "aeat_manuals_root",
        "aeat_normatives_root",
        "aeat_iva_catalogue_root",
        "aeat_certificate_path",
        "aeat_llm_cache_dir",
        "aeat_llm_usage_dir",
        "aeat_submissions_dir",
        "aeat_submission_browser_trace_dir",
        "aeat_inbox_dir",
        "aeat_inbox_pdf_dir",
        "aeat_workflow_runs_dir",
        "aeat_drafts_dir",
        "aeat_runs_dir",
        "aeat_status_cache_dir",
        "aeat_status_browser_trace_dir",
        "aeat_justificantes_dir",
        "aeat_filing_history_dir",
        "aeat_wallet_diagnostic_dump_dir",
        mode="after",
    )
    @classmethod
    def _normalize_repo_relative_paths(cls, value: Path | None) -> Path | None:
        """Anchor repo-relative path settings to ``PROJECT_ROOT``."""
        return normalize_project_relative_path(value)


_settings_override: contextvars.ContextVar[Settings | None] = contextvars.ContextVar(
    "_settings_override",
    default=None,
)


def classify_storage_route(settings: Settings | None = None) -> StorageRouteClassification:
    """Classify the effective primary SQL route and return a :class:`StorageRouteClassification`."""
    return classify_storage_route_for_settings(settings or load_settings())


def settings_for_active_profile_bucket(bucket_id: str, source: Settings | None = None) -> Settings:
    """Return a :class:`Settings` instance routed to ``bucket_id``'s active-profile database."""
    return settings_for_bucket_route(bucket_id, source or load_settings())


def load_settings() -> Settings:
    """Return the effective :class:`Settings` instance."""
    override = _settings_override.get()
    if override is not None:
        return override
    return Settings()


@contextmanager
def override_settings(**overrides: object) -> Iterator[Settings]:
    """Override one or more :class:`Settings` fields for the with-block."""
    current = load_settings()
    # ``model_copy(update=)`` skips validators in Pydantic v2; route the
    # merged dict through ``model_validate`` so a malformed override
    # fails fast at entry, before the ContextVar is set.
    merged = current.model_dump()
    route_overrides = {"aeat_active_profile", "aeat_local_storage_root"}
    if (
        "aeat_database_url" not in overrides
        and "aeat_database_url" not in current.model_fields_set
        and route_overrides.intersection(overrides)
    ):
        merged.pop("aeat_database_url", None)
    merged.update(overrides)
    new_settings = Settings.model_validate(merged)
    # ``model_validate`` marks every key in the merged dict as set,
    # losing the distinction between "operator set this explicitly"
    # and "default flowed through unchanged". Restore the proper
    # fields_set: the union of what the source instance already had
    # explicitly set plus the override keys themselves.
    explicit_fields = current.model_fields_set | set(overrides.keys())
    object.__setattr__(new_settings, "__pydantic_fields_set__", explicit_fields)
    # The output-language cache keys an override block by ``id(override)``; a
    # GC'd block's Settings address can be reused by the next block, so the
    # cache must be invalidated at both boundaries or a stale language leaks
    # across blocks. Lazy import: ``i18n._render`` imports this module.
    from .i18n._render import clear_output_language_cache

    token = _settings_override.set(new_settings)
    clear_output_language_cache()
    try:
        yield new_settings
    finally:
        _settings_override.reset(token)
        clear_output_language_cache()
