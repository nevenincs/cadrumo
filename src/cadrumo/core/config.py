"""Central settings facade for Cadrumo.

The :class:`Settings` model is the environment authority for Cadrumo
configuration: operators and tests override fields here, and downstream code
obtains the effective model through :func:`load_settings` or
:func:`override_settings`. Runtime-tunable Cadrumo settings stay in this schema,
while AEAT and Sede route and selector defaults come from
:mod:`core.external_constants` through the default factories below.

The storage boundary exposed here is also deliberate. Database URL derivation,
active-profile bucket routing, and route classification are surfaced through
:class:`StorageRouteClassification`, :func:`classify_storage_route`, and
:func:`settings_for_active_profile_bucket` so write guards do not re-parse SQL
URLs or active-profile pointers independently.
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, override

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from . import config_live_tests as _live_test_config
from .auth_provider import AuthProviderKind as _AuthProviderKind
from .config_integration_fields import (
    FORMER_PRODUCT_GOOGLE_DRIVE_VAULT_FOLDER_NAME,  # noqa: F401 - public re-export for storage adapters
)
from .config_llm_fields import CadrumoLlmSettings
from .config_state_root import (
    FORMER_PRODUCT_DATABASE_FILENAME,  # noqa: F401 - public re-export for storage adapters
    default_storage_root,
    refuse_former_product_database,
)
from .config_storage_route import classify_storage_route_for_settings, settings_for_bucket_route
from .config_support import (
    AEAT_CERTIFICATE_PROTECTED_ORIGIN,  # noqa: F401 - public certificate route authority
    AEAT_CERTIFICATE_PROTECTED_PATH,  # noqa: F401 - public certificate route authority
    AEAT_CERTIFICATE_PROTECTED_URL,  # noqa: F401 - public certificate route authority
    JustificanteParserBackendSetting,
    LLMProvider,  # noqa: F401 - public re-export from cadrumo.core.config
    SecretStoreBackend,
    StorageRouteClassification,
    StorageRouteKind,  # noqa: F401 - public re-export from cadrumo.core.config
    TuiAppearance,
    assert_canonical_protected_resource,  # noqa: F401 - public certificate route authority
    coerce_output_language_setting,
    unwrap_optional_secret,  # noqa: F401 - public re-export from cadrumo.core.config
)
from .config_support import default_aeat_sede_origin as _default_aeat_sede_origin
from .config_support import default_aeat_sede_origin_with_slash as _default_aeat_sede_origin_with_slash
from .config_support import (
    default_clave_permanente_sede_access_url_template as _default_clave_permanente_sede_access_url_template,
)
from .config_support import default_clave_sede_access_url_template as _default_clave_sede_access_url_template
from .config_support import default_sede_expedientes_path as _default_sede_expedientes_path
from .config_support import default_status_detail_url_template as _default_status_detail_url_template
from .config_support import default_status_notificaciones_path as _default_status_notificaciones_path
from .errors.hierarchy import ActiveProfilePointerError, CoreValidationError
from .external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from .paths import normalize_project_relative_path
from .resources import bundled_path
from .telemetry import TelemetryTier

if TYPE_CHECKING:
    from .bucket_pointer import BucketPointer
    from .external_constants import ExternalConstants


_LOGGER = logging.getLogger(__name__)


# Project root: four levels up from src/cadrumo/core/config.py
# (file → core/ → cadrumo/ → src/ → REPO_ROOT).
DEV_TEST_DATABASE_PASSWORD = "aeat-dev-test-database-password"
"""Shared development/test password for database-backed secure-storage tests."""
DEV_TEST_DATABASE_PASSWORD_ENV_VAR = "CADRUMO_DEV_TEST_DATABASE_PASSWORD"
"""Environment variable backing :attr:`Settings.cadrumo_dev_test_database_password`."""
LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD = _live_test_config.LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD
LIVE_READ_TEST_OPT_IN_ENV_VAR = _live_test_config.LIVE_READ_TEST_OPT_IN_ENV_VAR
LIVE_READ_TEST_OPT_IN_VALUE = _live_test_config.LIVE_READ_TEST_OPT_IN_VALUE
LIVE_READ_TEST_GOOGLE_OPT_IN_SETTINGS_FIELD = _live_test_config.LIVE_READ_TEST_GOOGLE_OPT_IN_SETTINGS_FIELD
LIVE_READ_TEST_GOOGLE_OPT_IN_ENV_VAR = _live_test_config.LIVE_READ_TEST_GOOGLE_OPT_IN_ENV_VAR

_NON_ENVIRONMENT_SELECTION_NAMES: Final[frozenset[str]] = frozenset({"CADRUMO_ACTIVE_PROFILE"})
"""Settings names that no environment source may populate.

Profile SELECTION is not an environment concern. ``CADRUMO_ACTIVE_PROFILE``
was a development override that operators adopted as the operating
mechanism, which made a shell variable outrank the on-disk pointer and left
``logout`` unable to clear a selection the application boundary could not
unset. Selection now has exactly two writers: the ``active-profile`` pointer
file, and the in-process override channel that ``--profile`` and
:func:`override_settings` use.

The FIELD survives -- only its environment source is severed -- because the
in-process channel is how ``--profile`` and tests scope a selection. The
sanctioned environment surface is ``CADRUMO_SECRET_PASSPHRASE``: secrets,
never selection.
"""


def _without_severed_names(env_vars: Mapping[str, str | None]) -> dict[str, str | None]:
    """Drop the names no environment source may populate."""
    return {name: value for name, value in env_vars.items() if name.upper() not in _NON_ENVIRONMENT_SELECTION_NAMES}


class _CadrumoEnvSettingsSource(EnvSettingsSource):
    """Ignore severed names in the process environment."""

    @override
    def __call__(self) -> dict[str, Any]:
        original_env_vars = self.env_vars
        self.env_vars = _without_severed_names(original_env_vars)
        try:
            return super().__call__()
        finally:
            self.env_vars = original_env_vars


class Settings(CadrumoLlmSettings):
    """Application settings populated from process environment variables.

    Field names map directly to env var names (uppercased). For example,
    ``aeat_base_url`` reads ``AEAT_BASE_URL``. There is no ``.env`` file
    support: the process environment is the sole external override channel,
    alongside the in-process ``init_settings`` source that ``--profile`` and
    :func:`override_settings` write through. The model is declarative: it
    carries operator choices, timeouts, storage roots, live-read opt-ins, and
    provider selectors, but does not open secret stores, build outbound
    providers, or execute AEAT browser flows.

    Validators keep derived paths coherent with ``cadrumo_local_storage_root`` and
    derive ``cadrumo_database_url`` from either an explicit field, the active
    profile, or the cold root fallback. Tests and CLI scopes should prefer
    :func:`override_settings` over process-wide environment mutation whenever
    they are not explicitly testing environment parsing.
    """

    model_config = SettingsConfigDict(
        env_ignore_empty=True,
    )

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Sever forbidden names from the process environment; no dotenv source.

        There is no ``.env`` support: production configuration comes from the
        process environment only. ``env_settings`` is replaced by a filtering
        subclass so a severed name (see :data:`_NON_ENVIRONMENT_SELECTION_NAMES`)
        cannot reach the model from the process environment.
        ``dotenv_settings`` is accepted because ``pydantic_settings`` always
        constructs it, but it is never returned: no source reads a dotenv
        file. ``init_settings`` is deliberately untouched: it is the
        in-process channel ``--profile`` and :func:`override_settings` write
        through.
        """
        del dotenv_settings
        assert isinstance(env_settings, EnvSettingsSource)
        filtered_env_settings = _CadrumoEnvSettingsSource(
            settings_cls,
            case_sensitive=env_settings.case_sensitive,
            env_prefix=env_settings.env_prefix,
            env_nested_delimiter=env_settings.env_nested_delimiter,
            env_nested_max_split=env_settings.env_nested_max_split,
            env_ignore_empty=env_settings.env_ignore_empty,
            env_parse_none_str=env_settings.env_parse_none_str,
            env_parse_enums=env_settings.env_parse_enums,
        )
        return init_settings, filtered_env_settings, file_secret_settings

    # ── Token Storage ───────────────────────────────────────────────────────
    cadrumo_token_dir: Path = Field(
        default=Path("tokens"),
        description=(
            "Directory for cached authentication token and lock files. The "
            "the relative default here is a placeholder: when the field "
            "is not explicitly set, the model validator roots it at "
            "``<cadrumo_local_storage_root>/tokens`` so every profile store, "
            "token and lock files included, lives under one state root. An "
            "explicit ``CADRUMO_TOKEN_DIR`` override wins over the derived "
            "default."
        ),
    )

    # ── AEAT ────────────────────────────────────────────────────────────────
    aeat_base_url: str = Field(
        default_factory=_default_aeat_sede_origin,
        description="AEAT sede electrónica base URL",
    )
    cadrumo_log_level: str = Field(
        default="",
        description="Optional default CLI log level override: quiet, default, verbose, or debug",
    )
    cadrumo_tui_appearance: TuiAppearance = Field(
        default=TuiAppearance.AUTO,
        description=(
            "Appearance for the full-screen terminal surfaces. "
            "auto = follow the host terminal. light = the warm-paper appearance. "
            "dark = the low-light appearance."
        ),
    )
    # ── Multilingual i18n ───────────────────────────────────────────────────
    cadrumo_output_language: Annotated[
        OutputLanguage | None,
        BeforeValidator(coerce_output_language_setting),
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
    cadrumo_authoritative_language_project_docs: str = Field(
        default="en",
        description="Authoritative language for internal code and documentation",
    )
    cadrumo_fallback_languages: str = Field(
        default="es,en",
        description=("Comma-separated fallback chain consulted when the target language is missing."),
    )

    # ── Storage ─────────────────────────────────────────────────────────────
    cadrumo_database_url: str = Field(
        default="",
        description=(
            "SQLAlchemy URL for the primary persistence backend. When empty, "
            "the model validator resolves the URL through the active-profile "
            "precedence chain to "
            "``sqlite:///<cadrumo_local_storage_root>/buckets/<bucket-id>/db/cadrumo.db``; "
            "with no active profile it derives a root-level fallback at "
            "``sqlite:///<cadrumo_local_storage_root>/cadrumo.db`` so the URL is "
            "never empty when the storage root is set. Tests that need a "
            "deterministic location supply this field explicitly; production "
            "reads the computed value."
        ),
    )
    cadrumo_secret_store_backend: SecretStoreBackend = Field(
        default=SecretStoreBackend.AUTO,
        description=(
            "Whether at-rest material is protected by real custody. "
            "auto = the profile's own password custody, which is the only "
            "secured route and needs no further configuration. "
            "unsecured = testing-only mode with a published deterministic "
            "key; requires cadrumo_allow_unencrypted=true and refuses real NIFs."
        ),
    )
    # Typed as ``str`` (not ``bool``) to preserve the strict-"1"-only
    # kill-switch semantic. Pydantic's bool coercion would widen the
    # opt-in surface to accept "true"/"yes"/"on" — a softer gate than
    # the safety-critical "no confidentiality" surface allows. The
    # consumer in master_key checks ``settings.cadrumo_allow_unencrypted
    # == "1"`` rather than truth-testing.
    cadrumo_allow_unencrypted: str = Field(
        default="",
        description=(
            "Hostile-named opt-out gate for the unsecured backend. Must be "
            "set to the literal '1' (env var: CADRUMO_ALLOW_UNENCRYPTED=1) to "
            "use cadrumo_secret_store_backend=unsecured. The unsecured backend "
            "is intended for testing / educational / throwaway scenarios "
            "only and provides ZERO confidentiality. The substrate refuses "
            "to load an operator profile that carries a real NIF/NIE/CIF "
            "while running in unsecured mode."
        ),
    )
    cadrumo_secret_store_dir: Path = Field(
        default=Path("secrets"),
        description="Directory for the encrypted secret-store master-key file and ciphertext records",
    )
    cadrumo_dev_test_database_password: SecretStr = Field(
        default=SecretStr(DEV_TEST_DATABASE_PASSWORD),
        description="Development/test-only password used by secure-storage subprocess tests.",
    )
    cadrumo_blob_store_dir: Path = Field(
        default=Path("blobs"),
        description="Directory containing the encrypted blob store (content-addressed, classification-aware)",
    )
    cadrumo_live_state_dir: Path = Field(
        default=Path("live-state"),
        description="Directory for live AEAT state and remote-state evidence",
    )

    # ── Outbound storage provider ───────────────────────────────────────────
    cadrumo_storage_provider_kind: str = Field(
        default="local_filesystem",
        description=(
            "Backend for `cadrumo.adapters.outbound.storage`. "
            "Accepted values: local_filesystem (default), google_drive, in_memory. "
            "google_drive additionally requires cadrumo_google_drive_root_folder_id "
            "and a per-profile registered OAuth client + token via `aeat config google`."
        ),
    )
    cadrumo_local_storage_root: Path = Field(
        default_factory=default_storage_root,
        description=(
            "Root directory for the LocalFileSystemProvider backend. Each namespace "
            "becomes a subdirectory; each object is a `<hmac_prefix_8>--<label>.bin` file "
            "paired with a `.meta.json` sidecar. The default is the platform user-data "
            "directory (`%LOCALAPPDATA%/cadrumo/storage`, `$XDG_DATA_HOME/cadrumo/storage` "
            "or `~/Library/Application Support/cadrumo/storage`) in every run mode, so the "
            "encrypted store never lands inside a virtualenv or uv cache. A source checkout "
            "does not redirect it: a developer who wants the tree inside their checkout "
            "sets this variable, and that explicit override wins over the derived default."
        ),
    )
    cadrumo_google_drive_root_folder_id: str | None = Field(
        default=None,
        description=(
            "Drive folder ID under which `cadrumo-vault/` is created and used. "
            "Required when cadrumo_storage_provider_kind=google_drive. Operator obtains "
            "this from the Cloud Console / Drive web UI; the app creates `cadrumo-vault/` "
            "lazily on first probe."
        ),
    )

    cadrumo_profile_kdf_measure_calibration: bool = Field(
        default=True,
        description=(
            "Whether profile-custody KDF calibration MEASURES the parameter grid on this host. "
            "True (the default, and the only production posture) samples real supervised "
            "derivations to pick the strongest grid point that still lands inside the operator "
            "latency band. False skips the measurement loop and adopts the fixed fallback point "
            "the calibrator already falls back to when the grid cannot be measured in time. "
            "This changes only whether the host is MEASURED, never how strongly a profile is "
            "wrapped: the fallback point is stronger than the measured band's floor, and the "
            "derivation itself is the same real Argon2id through the same supervised worker."
        ),
    )

    # ── Live tests ──────────────────────────────────────────────────────────
    # Typed as ``str`` to preserve the strict literal-"1" opt-in predicate.
    cadrumo_live_tests_enabled: str = Field(
        default="",
        description="Opt-in flag (set to '1') to run @pytest.mark.aeat_live tests against real external services",
    )
    cadrumo_live_tests_google: str = Field(
        default="",
        description=(
            "Opt-in flag (set to '1') to run @pytest.mark.aeat_live Google "
            "(OAuth / Drive) tests against real Google services"
        ),
    )

    @property
    def live_tests_enabled(self) -> bool:
        """Whether the pytest live-read opt-in is enabled.

        This is a strict ``"1"`` predicate for test selection only; production
        live-read access gates consume their own policy and capability checks.
        """
        return _live_test_config.strict_live_test_opt_in(self.cadrumo_live_tests_enabled)

    @property
    def live_tests_google_enabled(self) -> bool:
        """Whether the Google live-test opt-in is enabled.

        Google OAuth / Drive tests use the same strict ``"1"`` predicate as the
        general live-read opt-in and remain separate from production provider
        construction.
        """
        return _live_test_config.strict_live_test_opt_in(self.cadrumo_live_tests_google)

    # ── Replay IPC ──────────────────────────────────────────────────────────
    # Set by ``cadrumo.core.observability.replay.replay_run`` on the parent
    # process before it re-enters the CLI, then read by ``run_context`` in
    # the child invocation so the persisted trace can label its
    # ``replay_of`` field with the original run id. Subprocess IPC writes
    # still go through ``os.environ[REPLAY_ACTIVE_ENV_VAR] = run_id``
    # (Settings is read-only and ``Settings()`` is re-instantiated by
    # ``load_settings()`` on each call, so the write is visible to the
    # next read).
    cadrumo_replay_active: str = Field(
        default="",
        description="Subprocess-IPC marker carrying the original run_id when a CLI invocation is a replay re-entry",
    )

    # ── TTY / colour ────────────────────────────────────────────────────────
    cadrumo_force_color: bool = Field(
        default=False,
        description=(
            "Force ANSI colour output even when stdout is not a TTY. "
            "Operators set this when piping Cadrumo output through a terminal "
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
    cadrumo_cli_reveal_identifiers: bool = Field(
        default=False,
        description=(
            "Reveal raw profile and bucket identifiers in CLI success output "
            "instead of the paste-safe ``<profile-id>`` / ``<bucket-id>`` "
            "placeholders. Default off keeps the centralised-output-redaction "
            "policy (profile/bucket UUIDs are redacted so diagnostics are safe "
            "to paste into shared notes). A multi-client gestor who must "
            "disambiguate which bucket a command addressed sets "
            "``CADRUMO_CLI_REVEAL_IDENTIFIERS=1`` to opt out. This only un-redacts "
            "the opaque profile/bucket UUIDs; NIF/NIE/CIF tax identities, "
            "bearer tokens, URLs, and secure-object keys stay redacted "
            "unconditionally."
        ),
    )

    # ── Diagnostic logging ──────────────────────────────────────────────────
    cadrumo_log_dir: Path | None = Field(
        default=None,
        description=(
            "Diagnostic-log root directory. The ``None`` default here is a "
            "placeholder: when the field is not explicitly set, the model "
            "validator roots it at ``<cadrumo_local_storage_root>/logs`` so the "
            "diagnostic log lives under the one state root that "
            "``CADRUMO_LOCAL_STORAGE_ROOT`` scopes, isolating each workspace's "
            "log. An explicit ``CADRUMO_LOG_DIR`` override wins over the "
            "derived default."
        ),
    )

    # ── Master-key passphrase (live-write security perimeter) ───────────────
    cadrumo_secret_passphrase: SecretStr | None = Field(
        default=None,
        description=(
            "Passphrase that derives the encrypted-secret-store master key. "
            "With the default of None, the master-key loader refuses operation on None or "
            "empty values to preserve fail-closed behaviour. The environment name "
            "CADRUMO_SECRET_PASSPHRASE belongs to the separately governed "
            "programmatic substrate; CLI secret input uses explicit stdin or "
            "descriptor channels and does not fall back to this setting."
        ),
    )

    # ── Manuals corpus (cadrumo.domain.manuals) ───────────────────────────────────────
    aeat_manuals_root: Path = Field(
        default_factory=lambda: bundled_path("corpus", "manuals"),
        description="Root directory for the structured AEAT Manual práctico corpus",
    )
    cadrumo_manuals_review_required: bool = Field(
        default=True,
        description=(
            "When True, manual corpus verification rejects any Manual/Section/Rule record "
            "missing definition-review metadata; when False the rejection is downgraded to a warning"
        ),
    )
    aeat_normatives_root: Path = Field(
        default_factory=lambda: bundled_path("corpus", "normatives"),
        description="Root directory for the bundled legal normatives corpus",
    )

    # ── IVA catalogue (cadrumo.domain.iva) ──────────────────────────────────
    cadrumo_iva_catalogue_file: Path = Field(
        default_factory=lambda: bundled_path("registry", "aeat", "iva", "catalogues.toml"),
        description="The hand-reviewed IVA taxonomy catalogue file",
    )

    # ── Registry corpus-text validation cache ───────────────────────────────
    cadrumo_corpus_text_cache_dir: Path = Field(
        default=Path("cache") / "corpus-text",
        description=(
            "Directory for the registry corpus source-text validation cache "
            "(normalised text keyed by content fingerprint)"
        ),
    )
    cadrumo_corpus_search_cache_dir: Path = Field(
        default=Path("cache") / "corpus-search",
        description=(
            "Directory for the corpus-search lexical index (a SQLite database "
            "stemmed from the bundled corpus on first search, and current "
            "thereafter because that corpus is static)"
        ),
    )
    cadrumo_validation_verdict_cache_dir: Path = Field(
        default=Path("cache") / "registry-verdict",
        description=(
            "Directory for the persistent registry-validation verdict cache "
            "(a fingerprint-keyed proof that validate_registry ran green, so a "
            "matching immutable tree skips runtime re-validation)"
        ),
    )

    # ── Browser Automation ──────────────────────────────────────────────────
    cadrumo_browser_channel: str = Field(
        default="chrome",
        description="Playwright browser channel to use (e.g., 'chrome', 'chromium', 'msedge')",
    )
    cadrumo_browser_headless: bool = Field(
        default=True,
        description="Run browser in headless mode",
    )
    cadrumo_wallet_diagnostic_dump_dir: Path | None = Field(
        default=None,
        description=(
            "Opt-in diagnostic capture directory for the IVA compensation "
            "wallet (cartera) read. The ``None`` default disables capture and "
            "is the only production posture: with it unset the wallet read "
            "path is byte-for-byte unchanged. When set via "
            "``CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`` the read writes one redacted "
            "structural-shape summary per captured page and frame (URL "
            "without query, heading/table/form/input counts, form action "
            "paths, input identifiers, and a content hash) to this directory "
            "so AEAT DOM drift on the cartera surface can be diagnosed "
            "offline. It never writes raw HTML, frame HTML, screenshots, "
            "input values, or wallet amounts, so the capture carries no live "
            "taxpayer figures; it is written only to this operator-chosen "
            "directory and must never be committed or reused as a fixture "
            "without sanitisation."
        ),
    )
    cadrumo_wallet_diagnostic_retention_days: int = Field(
        default=30,
        ge=1,
        description=(
            "Retention window in days for wallet diagnostic dump files; when the "
            "opt-in dump directory is configured, dump files older than this are pruned"
        ),
    )
    cadrumo_active_profile: str | None = Field(
        default=None,
        description=(
            "In-process override for the active operator profile, written by "
            "the --profile flag and by override_settings in tests. When set, "
            "wins over the <cadrumo-root>/active-profile pointer file in the "
            "active-profile precedence chain. No environment variable "
            "populates this field: profile selection belongs to the pointer "
            "file, which 'aeat config login' writes. The pointer file is the "
            "canonical default."
        ),
    )
    cadrumo_proxy_url: str = Field(
        default="",
        description="Proxy URL (e.g., 'http://proxy.example.com:8080')",
    )
    cadrumo_proxy_username: str = Field(
        default="",
        description="Username for proxy authentication",
    )
    cadrumo_proxy_password_secret: SecretStr | None = Field(
        default=None,
        description="Password for proxy authentication",
    )
    cadrumo_proxy_bypass: str = Field(
        default="",
        description="Comma-separated list of domains to bypass the proxy",
    )
    cadrumo_rate_limit_delay_seconds: float = Field(
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
    cadrumo_certificate_path: Path | None = Field(
        default=None,
        description="Filesystem path to the operator's PKCS#12 (.p12/.pfx) bundle",
    )
    cadrumo_certificate_password_secret: SecretStr | None = Field(
        default=None,
        description="PKCS#12 passphrase (env only, never logged or persisted)",
    )
    cadrumo_certificate_friendly_name: str | None = Field(
        default=None,
        description="Optional human-readable label for the certificate",
    )
    cadrumo_auth_timeout_ms: int = Field(
        default=30_000,
        ge=1,
        description="Playwright navigation timeout for protected AEAT authentication in milliseconds",
    )
    cadrumo_strict_security: bool = Field(
        default=False,
        description="Raise instead of warn when AEAT credential artifact permission hardening fails",
    )
    cadrumo_cert_warn_days: int = Field(
        default=60,
        gt=0,
        description=(
            "Warning threshold (days) for the certificate pre-expiry gate: "
            "certificates with <= this many days remaining are surfaced as WARN"
        ),
    )
    cadrumo_cert_critical_days: int = Field(
        default=14,
        gt=0,
        description=(
            "Critical threshold (days) for the certificate pre-expiry gate: "
            "certificates with <= this many days remaining are CRITICAL and "
            "must be renewed before authenticated AEAT work continues"
        ),
    )

    # ── AEAT auth provider default ──────────────────────────────────────────
    cadrumo_auth_provider: _AuthProviderKind | None = Field(
        default=None,
        description=(
            "Default auth provider for `aeat config auth status` / `test` when "
            "--provider is omitted. When None, the CLI auto-selects the "
            "first configured provider from the canonical registry order."
        ),
    )

    # ── Cl@ve Móvil ─────────────────────────────────────────────────────────
    cadrumo_clave_movil_dni_nie: SecretStr | None = Field(
        default=None,
        description=(
            "Taxpayer DNI/NIE for `aeat config auth configure --provider clave_movil`. "
            "Used to stamp the persisted session with the operator's "
            "identity and to pre-fill the non-QR fallback form. AEAT-regulated "
            "personal identifier under Spanish tax law; typed as SecretStr to "
            "prevent leakage through repr / model_dump / ValidationError."
        ),
    )
    cadrumo_clave_movil_dni_fecha: str | None = Field(
        default=None,
        description=(
            "DNI validity / expiry date (YYYY-MM-DD) used by the "
            "non-QR Cl@ve Móvil fallback form. Applies when the "
            "configured identity is a DNI."
        ),
    )
    cadrumo_clave_movil_nie_soporte: SecretStr | None = Field(
        default=None,
        description=(
            "NIE support number (número de soporte) used by the "
            "non-QR Cl@ve Móvil fallback form. Applies when the "
            "configured identity is a NIE. AEAT-regulated personal "
            "identifier; typed as SecretStr to prevent leakage."
        ),
    )
    cadrumo_clave_prefer_non_qr: bool = Field(
        default=False,
        description=(
            "When true, the Cl@ve Móvil provider uses the non-QR fallback "
            "(DNI/NIE + contraste) rather than the QR code. This still "
            "requires operator-mediated completion in Cl@ve."
        ),
    )
    cadrumo_clave_movil_timeout_ms: int = Field(
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
            "AEAT Sede path for 'Mis expedientes'; the default post-auth "
            "target used by Cl@ve Móvil login and the expedientes reader."
        ),
    )

    # ── Cl@ve Permanente ────────────────────────────────────────────────────
    cadrumo_clave_permanente_dni_nie: SecretStr | None = Field(
        default=None,
        description=(
            "Taxpayer DNI/NIE for `aeat config auth configure "
            "--provider clave_permanente`. Used as the Cl@ve IdP login "
            "username and to stamp the persisted session with the "
            "operator's identity. AEAT-regulated personal identifier "
            "under Spanish tax law; typed as SecretStr to prevent "
            "leakage through repr / model_dump / ValidationError."
        ),
    )
    cadrumo_clave_permanente_password: SecretStr | None = Field(
        default=None,
        description=(
            "Cl@ve Permanente password for the DNI/NIE + password login "
            "form. Same treatment as the certificate passphrase: env var "
            "only, never stored in a committed env file, never logged."
        ),
    )
    cadrumo_clave_permanente_timeout_ms: int = Field(
        default=60_000,
        ge=15_000,
        le=120_000,
        description=(
            "Maximum time (milliseconds) the Cl@ve Permanente provider "
            "waits for the AEAT/Cl@ve IdP login form round-trip to "
            "complete before aborting. Routine Cl@ve Permanente login is "
            "headless-automatable (DNI/NIE + password, no SMS), so this "
            "window is shorter than the human-in-the-loop Cl@ve Móvil "
            "timeout."
        ),
    )
    aeat_clave_permanente_sede_access_url_template: str = Field(
        default_factory=_default_clave_permanente_sede_access_url_template,
        description=(
            "URL template for AEAT's auth-method selector page used by "
            "the Cl@ve Permanente login flow. `{target}` is replaced with "
            "the URL-encoded target path. The default template is "
            "sourced from the external constants registry."
        ),
    )

    # ── Off-host evidence reading: opt-in consent posture ───────────────────
    # The two flags a cloud read of a taxpayer's document must clear before the
    # per-invocation acknowledgement is even consulted. Both default to the
    # refusing value, so a deployment that configures nothing at all cannot
    # transmit evidence: the permitted flag is False and no acknowledgement can
    # rescue a gestor deployment. They are settings rather than a runtime
    # argument because the posture is a property of the DEPLOYMENT -- an
    # operator's per-call acknowledgement narrows it and can never widen it
    # (sensitive-financial-data-secure-storage-only).
    cadrumo_evidence_cloud_upload_permitted: bool = Field(
        default=False,
        description=(
            "Whether this deployment permits reading taxpayer evidence at an off-host model at all. "
            "Default off: every evidence read stays on the host. When True, an explicit per-invocation "
            "operator acknowledgement is still required for each read, and gestor deployments stay barred."
        ),
    )
    cadrumo_evidence_gestor_mode: bool = Field(
        default=False,
        description=(
            "Gestor/professional deployment flag for evidence reading. When True, an off-host evidence "
            "read is categorically refused regardless of cadrumo_evidence_cloud_upload_permitted or any "
            "per-invocation acknowledgement."
        ),
    )

    # ── Remote telemetry: opt-in consent posture ────────────────────────────
    # Default and only-acceptable-for-serious-use posture is fully local: every
    # existing local telemetry primitive is
    # written to encrypted secure storage or a local JSONL file and never
    # contacts a network endpoint. Remote telemetry is a deliberate, narrow,
    # opt-in exception. It shares the evidence gate's shape above -- gestor bar
    # first and absolutely, then the deployment opt-in, then the per-invocation
    # acknowledgement -- so the codebase's off-host consent postures stay
    # uniform and comparable, with the tier as this posture's only extra axis.
    cadrumo_telemetry_opt_in: bool = Field(
        default=False,
        description=(
            "Whether this deployment permits transmitting remote telemetry at all. Default off: all "
            "telemetry stays local. When True, a per-invocation operator consent acknowledgement is "
            "still required for each emit, and cadrumo_telemetry_tier must not be 'off'."
        ),
    )
    cadrumo_telemetry_tier: TelemetryTier = Field(
        default=TelemetryTier.OFF,
        description=(
            "Remote telemetry tier: 'off' (no remote emission regardless of opt-in), 'crash_only' "
            "(error/outcome counters only), or 'full' (counters plus timing percentiles). Only "
            "remote_allowed=True metric keys are ever eligible for transmission at any tier."
        ),
    )
    cadrumo_telemetry_gestor_mode: bool = Field(
        default=False,
        description=(
            "Gestor/professional deployment flag. When True, remote telemetry emission is "
            "categorically refused regardless of cadrumo_telemetry_opt_in, cadrumo_telemetry_tier, or "
            "per-invocation consent."
        ),
    )
    cadrumo_telemetry_endpoint: str | None = Field(
        default=None,
        description=(
            "Remote telemetry collector URL, consumed by HttpTelemetrySink when "
            "a call site opts into real transmission. Unset means no dial target."
        ),
    )

    # ── Filing-deadline engine ──────────────────────────────────────────────
    cadrumo_deadline_due_soon_days: int = Field(
        default=14,
        description=(
            "Days before an obligation's closes_on date that flag ObligationStatus.DUE_SOON in the deadline engine"
        ),
    )

    # ── Submission engine ───────────────────────────────────────────────────
    cadrumo_submissions_dir: Path = Field(
        default=Path("submissions"),
        description="Directory where ModeloPresentado JSON audit records are persisted",
    )

    # ── Notifications inbox ─────────────────────────────────────────────────
    cadrumo_inbox_alert_lead_days: int = Field(
        default=7,
        description=(
            "Lead window (days) for notification deadline reporting: surface CRITICAL/HIGH "
            "notifications whose appeal_deadline falls within the next N days"
        ),
    )

    # ── Workflow engine ─────────────────────────────────────────────────────
    cadrumo_workflow_runs_dir: Path = Field(
        default=Path("workflow-runs"),
        description="Directory where WorkflowResult JSON audit records are persisted",
    )
    # ── Filing draft engine ─────────────────────────────────────────────────
    cadrumo_drafts_dir: Path = Field(
        default=Path("drafts"),
        description="Directory where filing drafts are written as JSON files",
    )
    cadrumo_draft_fail_on_warning: bool = Field(
        default=False,
        description=(
            "If true, build_draft raises FilingValidationError when any WARNING- or ERROR-severity finding is produced"
        ),
    )
    cadrumo_m210_engine_live: bool = Field(
        default=False,
        description=(
            "Gate the M210 IRNR engine, which currently covers only TRLIRNR Art. 25 "
            "letters a, b, and f. When False (default) `aeat app modelo "
            "work create --modelo 210` emits the Path-B refusal stub. When True "
            "the stub guard is skipped and the engine path runs (irnr_resolve_tipo_gravamen "
            "dispatch + representante-fiscal predicate + cuota composition)."
        ),
    )

    # ── Status reader ───────────────────────────────────────────────────────
    aeat_status_detail_url_template: str = Field(
        default_factory=_default_status_detail_url_template,
        description=(
            "URL path template for an expediente detail page. "
            "Must contain '{expediente_id}'. Override only when AEAT changes "
            "the corresponding route."
        ),
    )
    aeat_status_notificaciones_path: str = Field(
        default_factory=_default_status_notificaciones_path,
        description=(
            "URL path for the 'Mis notificaciones' listing page. "
            "Joined against aeat_base_url. Override only when AEAT changes "
            "the corresponding route."
        ),
    )

    # ── Observability ──────────────────────────────────────────────────────
    cadrumo_runs_dir: Path = Field(
        default=Path("runs"),
        description=(
            "Directory where run traces and JSONL event logs are persisted "
            "(one subdirectory per run_id, containing trace.json + events.jsonl)"
        ),
    )
    cadrumo_runs_retention_days: int = Field(
        default=30,
        ge=1,
        description="Retention window in days for per-run trace directories; older run directories are pruned",
    )
    cadrumo_runs_max_total_bytes: int = Field(
        default=256 * 1024 * 1024,
        ge=1,
        description="Trace-store byte cap; after age pruning, remove oldest runs but always retain the newest",
    )
    # ── Justificante parser ─────────────────────────────────────────────────
    cadrumo_justificantes_dir: Path = Field(
        default=Path("justificantes"),
        description="Directory where parsed justificante PDFs and metadata are stored",
    )
    cadrumo_filed_declarations_dir: Path = Field(
        default=Path("filed-declarations"),
        description=(
            "Directory for filed-declaration observations captured from AEAT. "
            "Derived under cadrumo_local_storage_root unless explicitly set."
        ),
    )
    cadrumo_iva_compensation_history_dir: Path = Field(
        default=Path("live") / "iva-compensation-history",
        description=(
            "Directory for Modelo 303 compensation-history capture reports. "
            "Derived under cadrumo_local_storage_root unless explicitly set."
        ),
    )
    cadrumo_iva_read_evidence_dir: Path = Field(
        default=Path("live") / "iva-read-evidence",
        description=(
            "Directory for IVA remote-state read-evidence reports. "
            "Derived under cadrumo_local_storage_root unless explicitly set."
        ),
    )
    cadrumo_justificante_parser_backend: JustificanteParserBackendSetting = Field(
        default=JustificanteParserBackendSetting.PDFPLUMBER,
        description="Parser backend for `cadrumo.adapters.inbound.justificante`",
    )

    # ── Filing history ──────────────────────────────────────────────────────
    cadrumo_filing_history_dir: Path = Field(
        default=Path("filing-history"),
        description="Directory where the persisted ModeloHistory JSON file lives",
    )
    cadrumo_filing_history_cache_ttl_s: int = Field(
        default=900,
        description="TTL in seconds for per-expediente filing-history cache entries (default 15 min)",
    )
    cadrumo_filing_history_archive_html: bool = Field(
        default=False,
        description="If true, archive fetched detail-page HTML under <cadrumo_filing_history_dir>/pages/",
    )

    # ── Introspection ───────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_live_iva_timeout_hierarchy(self) -> Settings:
        if self.cadrumo_live_iva_declaration_capture_timeout_ms >= self.cadrumo_live_iva_surface_timeout_ms:
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "capture_timeout_ms": self.cadrumo_live_iva_declaration_capture_timeout_ms,
                    "surface_timeout_ms": self.cadrumo_live_iva_surface_timeout_ms,
                    "capture_below_surface": False,
                },
            )
        return self

    @model_validator(mode="after")
    def _resolve_database_url_for_active_profile(self) -> Settings:
        """Resolve ``cadrumo_database_url`` through the active-profile chain.

        When the field is left empty (the production default), this
        validator computes the per-bucket SQLite URL at
        ``sqlite:///<cadrumo_local_storage_root>/buckets/<bucket-id>/db/cadrumo.db``.
        Tests that pass an explicit URL bypass the resolution — the
        validator only fires the computation when the field is empty.

        Active-profile resolution honours the operator-facing
        precedence chain:

        1. ``self.cadrumo_active_profile`` (the in-process override the
           ``--profile`` flag and ``override_settings`` write; no
           environment variable reaches it).
        2. ``<cadrumo_local_storage_root>/active-profile`` plaintext
           pointer file written by ``profile create`` / ``config
           login``.

        When neither rung resolves, the field derives a root-level
        fallback at ``sqlite:///<cadrumo_local_storage_root>/cadrumo.db`` so
        the two storage settings stay coherent: setting
        ``CADRUMO_LOCAL_STORAGE_ROOT`` alone never leaves
        ``cadrumo_database_url`` empty. Cold-start commands still refuse
        before touching this fallback database — every profile-scoped
        path checks for an active profile first — so the fallback
        database is a placeholder that real per-profile data never
        lands in.
        """
        if self.cadrumo_database_url:
            return self
        bucket_id = (self.cadrumo_active_profile or "").strip()
        if not bucket_id:
            # Delegate to the canonical pointer-file reader rather
            # than re-implementing the TOML parse inline. The reader
            # uses strict pydantic validation; this preserves the
            # one-resolver invariant for the active-profile pointer.
            #
            # Reached through the owning submodule, never the ``cadrumo.core``
            # facade. Both helpers are served by the package's PEP 562
            # ``__getattr__``, which is defined near the END of
            # ``core/__init__``; any module imported EARLIER in that file that
            # reaches this validator therefore asks a half-built package for an
            # attribute whose accessor does not exist yet, and the whole package
            # becomes unimportable. Naming the submodule keeps this resolvable
            # no matter how early the caller sits.
            from .bucket_pointer import pointer_path, read_pointer

            try:
                captured = _settings_pointer_observation.get()
                pointer = (
                    captured[1]
                    if captured is not None and captured[0] == self.cadrumo_local_storage_root
                    else read_pointer(self.cadrumo_local_storage_root)
                )
            except (OSError, ValueError) as exc:
                pointer_file = pointer_path(self.cadrumo_local_storage_root)
                _LOGGER.debug(
                    "Invalid active-profile pointer at %s; refusing root storage fallback",
                    pointer_file,
                    exc_info=True,
                )
                raise ActiveProfilePointerError(path=pointer_file) from exc
            if pointer.bucket_id is not None:
                bucket_id = pointer.bucket_id.strip()
        from .storage_taxonomy import StorageCategory, bucket_scoped_storage_path, storage_path

        if not bucket_id:
            refuse_former_product_database(self.cadrumo_local_storage_root)
            fallback_db_path = storage_path(StorageCategory.ROOT_FALLBACK_DATABASE, settings=self)
            object.__setattr__(
                self,
                "cadrumo_database_url",
                f"sqlite:///{fallback_db_path.as_posix()}",
            )
            return self
        refuse_former_product_database(self.cadrumo_local_storage_root, bucket_id=bucket_id)
        # The layout comes from the one core storage authority. This fallback
        # used to re-type it, unpinned against the code that actually
        # provisions a bucket, so a rename would have routed the cold-start
        # database at a directory nothing else agreed on.
        bucket_db_path = bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE_FILE, bucket_id, settings=self)
        object.__setattr__(
            self,
            "cadrumo_database_url",
            f"sqlite:///{bucket_db_path.as_posix()}",
        )
        return self

    @model_validator(mode="after")
    def _resolve_output_dirs_under_storage_root(self) -> Settings:
        """Root every derived output directory under ``cadrumo_local_storage_root``.

        Auth tokens, the diagnostic log, the encrypted-store substrate (secret,
        blob, audit), the append-only telemetry logs, the regenerable caches,
        and the durable generated-output directories all default to a subpath
        under the one state root that ``CADRUMO_LOCAL_STORAGE_ROOT`` scopes, per
        the core storage taxonomy. That root is the platform
        user-data location in every run mode, never inside a virtualenv or uv
        cache — the hazard a checkout-relative ``var/...`` default carries on
        an installed distribution. A developer who wants the tree inside their
        checkout sets ``CADRUMO_LOCAL_STORAGE_ROOT``.

        An explicit per-field env override (``CADRUMO_TOKEN_DIR``,
        ``CADRUMO_RUNS_DIR``, …) or a value supplied via an ``override_settings``
        block registers the field in ``model_fields_set`` and wins: the
        validator only computes the derived path when the field was left at its
        placeholder default. The validator only computes paths; provider
        factories and custody loaders decide how those directories are opened.

        Which fields those are, and what subpath each takes, is not decided
        here: the typed declaration is iterated directly so this validator
        cannot drift from it by carrying a table of its own. Members whose
        field is a deliberate opt-in override are excluded by the declaration
        rather than by a special case here -- deriving a default into one would
        silently retire the branch that selects on the field being unset.

        ``mode="after"`` guarantees ``cadrumo_local_storage_root`` is already
        populated when this runs.
        """
        from .storage_taxonomy import ROOT_DERIVED_STORAGE_LOCATIONS

        for location in ROOT_DERIVED_STORAGE_LOCATIONS:
            field_name = location.settings_field
            if field_name is None or field_name in self.model_fields_set:
                continue
            object.__setattr__(self, field_name, self.cadrumo_local_storage_root / location.relative_path())
        return self

    @field_validator(
        "cadrumo_certificate_path",
        mode="before",
    )
    @classmethod
    def _empty_optional_paths_are_none(cls, value: object) -> object:
        """Treat blank env vars for optional path fields as unset."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "cadrumo_certificate_password_secret",
        "cadrumo_llm_anthropic_api_key",
        "cadrumo_llm_openai_api_key",
        "cadrumo_llm_gemini_api_key",
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
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "setting": "aeat_status_detail_url_template",
                    "required_placeholder": "{expediente_id}",
                    "placeholder_present": False,
                },
            )
        return value

    @field_validator(
        "cadrumo_clave_movil_dni_nie",
        "cadrumo_clave_movil_dni_fecha",
        "cadrumo_clave_movil_nie_soporte",
        "cadrumo_clave_permanente_dni_nie",
        "cadrumo_clave_permanente_password",
        mode="before",
    )
    @classmethod
    def _empty_optional_clave_fields_are_none(cls, value: object) -> object:
        """Treat blank env vars for optional Cl@ve identity/password fields as unset."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("cadrumo_clave_movil_dni_fecha")
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
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "env_var": "CADRUMO_CLAVE_MOVIL_DNI_FECHA",
                    "required_format": "YYYY-MM-DD",
                    "canonical_form": False,
                },
            )
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "env_var": "CADRUMO_CLAVE_MOVIL_DNI_FECHA",
                    "required_format": "YYYY-MM-DD",
                    "resolvable_date": False,
                },
            ) from exc
        return value

    @field_validator(
        "aeat_clave_sede_access_url_template",
        "aeat_clave_permanente_sede_access_url_template",
    )
    @classmethod
    def _clave_sede_access_url_template_has_target(cls, value: str) -> str:
        """Reject templates that omit the ``{target}`` placeholder."""
        if "{target}" not in value:
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "required_placeholder": "{target}",
                    "placeholder_present": False,
                    "placeholder_purpose": "url_encoded_post_auth_path",
                },
            )
        return value

    @classmethod
    def env_var_names(cls) -> set[str]:
        """Return the set of environment variable names this model reads.

        Severed names are excluded: a field whose environment source has
        been cut is still a field, but no environment variable reaches it,
        so listing it here would document a control that does nothing.
        """
        return {name.upper() for name in cls.model_fields} - _NON_ENVIRONMENT_SELECTION_NAMES

    @staticmethod
    def external_constants() -> ExternalConstants:
        """Return the parsed external-constants registry.

        Bridges :mod:`core.external_constants` to the settings facade
        so callers reach third-party hostnames, AEAT service paths, OAuth
        scopes, and LLM endpoints through a single accessor.

        Returns:
            The process-wide cached :class:`ExternalConstants` instance.
        """
        from .external_constants import load_external_constants

        return load_external_constants()

    @field_validator(
        "cadrumo_token_dir",
        "cadrumo_usage_ratios_path",
        "cadrumo_financial_txs_dir",
        "cadrumo_invoices_dir",
        "cadrumo_attachments_dir",
        "cadrumo_local_storage_root",
        "cadrumo_log_dir",
        "cadrumo_secret_store_dir",
        "cadrumo_blob_store_dir",
        "cadrumo_live_state_dir",
        "cadrumo_registry_disk_cache_dir",
        "aeat_manuals_root",
        "aeat_normatives_root",
        "cadrumo_iva_catalogue_file",
        "cadrumo_corpus_text_cache_dir",
        "cadrumo_corpus_search_cache_dir",
        "cadrumo_validation_verdict_cache_dir",
        "cadrumo_certificate_path",
        "cadrumo_llm_cache_dir",
        "cadrumo_llm_usage_dir",
        "cadrumo_llm_run_telemetry_dir",
        "cadrumo_submissions_dir",
        "cadrumo_workflow_runs_dir",
        "cadrumo_drafts_dir",
        "cadrumo_runs_dir",
        "cadrumo_justificantes_dir",
        "cadrumo_filing_history_dir",
        "cadrumo_wallet_diagnostic_dump_dir",
        "cadrumo_filed_declarations_dir",
        "cadrumo_iva_compensation_history_dir",
        "cadrumo_iva_read_evidence_dir",
        mode="after",
    )
    @classmethod
    def _normalize_repo_relative_paths(cls, value: Path | None) -> Path | None:
        """Anchor repo-relative path settings to the application data root."""
        return normalize_project_relative_path(value)


_settings_override: contextvars.ContextVar[Settings | None] = contextvars.ContextVar(
    "_settings_override",
    default=None,
)
_settings_pointer_observation: contextvars.ContextVar[tuple[Path, BucketPointer] | None] = contextvars.ContextVar(
    "_settings_pointer_observation",
    default=None,
)


def classify_storage_route(settings: Settings | None = None) -> StorageRouteClassification:
    """Classify the effective primary SQL route.

    The returned :class:`StorageRouteClassification` distinguishes explicit
    database URLs, active-profile bucket databases, and cold root-fallback
    SQLite routes. Application write guards consume this facade instead of
    re-parsing ``cadrumo_database_url`` or duplicating active-profile pointer
    rules.
    """
    return classify_storage_route_for_settings(settings or load_settings())


def settings_for_active_profile_bucket(bucket_id: str, source: Settings | None = None) -> Settings:
    """Return settings routed to ``bucket_id``'s active-profile database.

    Non-route fields are preserved from ``source`` (or :func:`load_settings`),
    while ``cadrumo_database_url`` is re-derived through the same validators used
    by normal settings construction. Explicit database URLs are refused by the
    lower-level route helper because they already define the storage authority.

    Returns:
        A :class:`Settings` instance whose database route targets ``bucket_id``.
    """
    return settings_for_bucket_route(bucket_id, source or load_settings())


def _active_profile_pointer_observation() -> tuple[Path, BucketPointer]:
    """Identify the current active-profile pointer through its native coordinate.

    Settings construction is not a pure function of the environment: when
    ``cadrumo_database_url`` is unset, the post-validator below reads the
    ``active-profile`` pointer file and derives the bucket's database route
    from it. That makes the pointer a construction INPUT, and it moves
    whenever ``config login``/``logout`` writes it — inside a live process,
    for a long-running interactive or external session.

    Holding one settings instance across such a switch would keep serving the
    previous profile's database route, so the canonical durable transition
    coordinate is folded into the cache key. A fresh root observes the initial
    absent coordinate zero; a later clear is a distinct persisted tombstone.

    The root is read straight from the environment: that read is deliberately
    independent of the settings model it guards, because it has to answer
    "which pointer would the next construction see" BEFORE any settings exist
    to ask.
    """
    import os

    configured_root = os.environ.get("CADRUMO_LOCAL_STORAGE_ROOT")
    root = normalize_project_relative_path(Path(configured_root)) if configured_root else default_storage_root()
    assert root is not None
    try:
        from .bucket_pointer import read_pointer

        pointer = read_pointer(root)
    except (OSError, ValueError):
        raise
    return (root, pointer)


@lru_cache(maxsize=8)
def _constructed_settings(
    root: Path,
    selection: Literal["absent", "selected"],
    bucket_id: str | None,
    transition_revision: int,
) -> Settings:
    """Build the settings for one active-profile pointer state and hold them.

    Construction is expensive out of proportion to what it produces: the model
    validates 92 fields and resolves 28 configured paths, and on Windows each
    of those resolutions is a filesystem round trip. Measured on a developer
    machine it costs roughly 300 ms, and :func:`load_settings` is called from
    over two hundred production sites — around ten times for a single profile
    field edit, which is how a keystroke came to cost seconds.

    The transition coordinate arguments are not read; they are the cache key.
    Keying on the pointer keeps
    the hold from outliving a bucket switch, which is what the profile-bucket
    lifecycle requires of any cache that could otherwise strand a stale route.
    A handful of entries is enough for the few profiles one process touches.

    Tests that exercise environment parsing construct :class:`Settings`
    directly and so never reach this cache; tests that need different values
    use :func:`override_settings`, which is consulted ahead of it.
    """
    from .bucket_pointer import BucketPointer

    pointer = BucketPointer(
        selection=selection,
        bucket_id=bucket_id,
        transition_revision=transition_revision,
        schema_version=2,
    )
    token = _settings_pointer_observation.set((root, pointer))
    try:
        return Settings()
    finally:
        _settings_pointer_observation.reset(token)


def reset_settings_cache() -> None:
    """Drop every held settings instance so the next load rebuilds.

    The pointer key already covers profile switches. This is for the rare
    caller that changes the process environment and needs it observed;
    prefer :func:`override_settings`, which scopes the change to a block and
    does not disturb the cache at all.
    """
    _constructed_settings.cache_clear()


def load_settings() -> Settings:
    """Return the effective :class:`Settings` instance.

    Context-local overrides installed by :func:`override_settings` win inside
    their block; otherwise this returns the process-wide settings built once by
    :func:`_constructed_settings`.
    """
    override = _settings_override.get()
    if override is not None:
        return override
    root, pointer = _active_profile_pointer_observation()
    return _constructed_settings(
        root,
        pointer.selection,
        pointer.bucket_id,
        pointer.transition_revision,
    )


@contextmanager
def override_settings(**overrides: object) -> Iterator[Settings]:
    """Override one or more :class:`Settings` fields for the with-block.

    Overrides are validated through normal model construction so derived route,
    token, log, and storage-substrate paths stay coherent. The helper preserves
    ``model_fields_set`` to keep the distinction between explicit operator
    settings and computed defaults visible to route classification.

    When the root itself is overridden, every derived field that the caller did
    not set and the source had not set explicitly is dropped from the merged
    dict so it re-derives under the NEW root. Without that, flattening through
    ``model_dump`` turns each previously-derived absolute path into an explicit
    value and the whole tree stays pinned to the old root -- a leak that does
    not fail any single test, because each one still reads a path that exists.
    The field set is taken from the taxonomy, so a member added there is
    covered here the moment it lands.
    """
    from .storage_taxonomy import ROOT_DERIVED_STORAGE_FIELDS

    current = load_settings()
    # ``model_copy(update=)`` skips validators in Pydantic v2; route the
    # merged dict through ``model_validate`` so a malformed override
    # fails fast at entry, before the ContextVar is set.
    merged = current.model_dump()
    route_overrides = {"cadrumo_active_profile", "cadrumo_local_storage_root"}
    if (
        "cadrumo_database_url" not in overrides
        and "cadrumo_database_url" not in current.model_fields_set
        and route_overrides.intersection(overrides)
    ):
        merged.pop("cadrumo_database_url", None)
    if "cadrumo_local_storage_root" in overrides:
        for derived_field in ROOT_DERIVED_STORAGE_FIELDS:
            if derived_field not in overrides and derived_field not in current.model_fields_set:
                merged.pop(derived_field, None)
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
    # across blocks. The one exception is a block opened by the language
    # resolution itself, which the invalidator recognises and skips -- see
    # ``clear_output_language_cache_for_settings_override``. Lazy import:
    # ``i18n._render`` imports this module.
    from .i18n import clear_output_language_cache_for_settings_override

    token = _settings_override.set(new_settings)
    clear_output_language_cache_for_settings_override()
    try:
        yield new_settings
    finally:
        _settings_override.reset(token)
        clear_output_language_cache_for_settings_override()
