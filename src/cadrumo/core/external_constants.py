"""External constants registry loaded from ``external_constants.toml``.

Centralises third-party hostnames, AEAT service paths, OAuth scopes, and
remote API endpoints. The TOML file sits beside this module and is parsed
once per process via :func:`load_external_constants`. Every section is
modelled as a frozen, strict pydantic v2 model so callers see typed,
immutable values and any drift between the TOML and the schema fails fast
at import time.

This is a read-only remote-mirror registry for public, externally defined
constants. Runtime-tunable values such as timeouts, storage roots, and operator
choices belong in :class:`core.config.Settings`; profile data, tokens,
passphrases, bucket ids, and SQL routes do not belong here. Loading the registry
only reads packaged TOML (or an explicit audit/test path) and never opens
storage, writes files, or contacts remote providers.

The typed root is :class:`ExternalConstants`, with AEAT-specific subsections
grouped under :class:`AeatSection`; callers normally reach it through
:meth:`core.config.Settings.external_constants`. The volatile Pre303 and
IVA-wallet browser surface remains lazily validated as :class:`AeatPre303Surface`
so selector churn does not poison unrelated configuration reads.
"""

from __future__ import annotations

import re
import tomllib
from enum import StrEnum
from functools import cached_property, lru_cache
from importlib.resources import files  # nosemgrep
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors.hierarchy import CoreValidationError
from .models import STRICT_FROZEN_CONFIG
from .type_guards import is_object_list

#: ISO 4217 currency code for the Euro, used as the functional currency throughout AEAT.
DEFAULT_CURRENCY: Final[str] = "EUR"

#: Standard binary MIME type for opaque byte-stream payloads (Drive uploads, blob store, fichero).
BINARY_MIME_TYPE: Final[str] = "application/octet-stream"

#: IANA-registered MIME type for JSON document payloads.
JSON_MIME_TYPE: Final[str] = "application/json"

#: IANA-registered MIME type for comma-separated value exports.
CSV_MIME_TYPE: Final[str] = "text/csv"

#: MIME type for newline-delimited JSON export streams.
JSONL_MIME_TYPE: Final[str] = "application/x-ndjson"

#: MIME type for Office Open XML spreadsheet workbooks.
XLSX_MIME_TYPE: Final[str] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

#: Sentinel written to ``classified_by`` when the operator provides a classification directly
#: (no rule engine involved).  The field also accepts ``"rule:<id>"`` payloads; this named
#: constant prevents the literal from drifting across the application and domain layers.
CLASSIFIED_BY_MANUAL: Final[str] = "manual"

#: Sentinel written to ``classified_by`` when the classification was produced automatically
#: by the rule engine with no operator override.
CLASSIFIED_BY_AUTO: Final[str] = "auto"


class _Frozen(BaseModel):
    """Strict, frozen base for external-constant submodels.

    Unknown TOML keys are rejected and parsed instances are immutable, so a
    newly added external value must be represented in the schema before
    production code can consume it.
    """

    model_config = STRICT_FROZEN_CONFIG


class AeatDomainSection(_Frozen):
    """AEAT and related government hostnames.

    Hostnames are registry data, not executable literals in live drivers.
    Callers combine these origins with path sections below instead of
    re-declaring Sede, Cl@ve, BOE, or numbered AEAT subdomain strings.
    """

    host_suffix: str = Field(min_length=1)
    sede: str = Field(min_length=1)
    www1: str = Field(min_length=1)
    www2: str = Field(min_length=1)
    www3: str = Field(min_length=1)
    www6: str = Field(min_length=1)
    www12: str = Field(min_length=1)
    aeat_gob: str = Field(min_length=1)
    legacy_host_suffix: str = Field(min_length=1)
    legacy_www: str = Field(min_length=1)
    clave: str = Field(min_length=1)
    boe: str = Field(min_length=1)


class AeatSedePathSection(_Frozen):
    """Relative path templates against configured AEAT origins.

    These values are route fragments and templates only; consumers choose the
    correct origin from :class:`AeatDomainSection` or an overrideable
    :class:`core.config.Settings` field before building a full URL.
    """

    auth_gate_4033: str
    expedientes_resumen: str
    declarations_listing: str
    cotejo_query: str
    cotejo_document: str
    notifications_summary: str
    notifications_query: str
    notifications_detail: str
    certificate_selector: str
    r210_simulator_open_ajax: str
    borrador_100_detail_template: str
    declaracion_consult: str
    clave_movil_login: str
    expediente_detail_template: str
    irpf_expediente_detail_year_prefix: str
    irpf_expediente_detail_year_suffix: str
    notificaciones: str
    iva_compensation_wallet: str
    censal_datos: str


class AeatClaveMovilSurface(_Frozen):
    """Externally-defined Cl@ve Móvil page identifiers and shape markers."""

    selector_access_url_template: str = Field(min_length=1)
    selector_access_path_marker: str = Field(min_length=1)
    dialogo_representacion_path_marker: str = Field(min_length=1)
    dialogo_representacion_path: str = Field(min_length=1)
    obtener_clave_movil_path_marker: str = Field(min_length=1)
    obtener_clave_movil_qr_path_marker: str = Field(min_length=1)
    cancelar_clave_movil_path_marker: str = Field(min_length=1)
    obtener_clave_movil_qr_path: str = Field(min_length=1)
    obtener_clave_movil_non_qr_path: str = Field(min_length=1)
    autentica_dni_nie_contraste_path: str = Field(min_length=1)
    cancelar_clave_movil_path: str = Field(min_length=1)
    obtener_clave_movil_browser_global: str = Field(min_length=1)
    authorize_button_selector: str = Field(min_length=1)
    non_qr_link_selector: str = Field(min_length=1)
    nif_input_selector: str = Field(min_length=1)
    dni_fecha_input_selector: str = Field(min_length=1)
    dni_fecha_visible_selector: str = Field(min_length=1)
    nie_soporte_input_selector: str = Field(min_length=1)
    nie_soporte_visible_selector: str = Field(min_length=1)
    continue_button_selector: str = Field(min_length=1)
    continue_button_visible_selector: str = Field(min_length=1)
    verification_code_selector: str = Field(min_length=1)
    wait_text_markers: tuple[str, ...] = Field(min_length=1)
    pending_petition_text_markers: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "wait_text_markers",
        "pending_petition_text_markers",
        mode="before",
    )
    @classmethod
    def _markers_from_toml_arrays(cls, value: object) -> object:
        if is_object_list(value):
            return tuple(value)
        return value


class AeatClavePermanenteSurface(_Frozen):
    """Externally-defined Cl@ve Permanente selector-page and IdP form markers.

    Cl@ve Permanente reuses the same AEAT auth-method selector page as Cl@ve
    Movil (:attr:`selector_access_url_template`); the Cl@ve IdP itself then
    renders a DNI/NIE + password form rather than the QR/push screen. These
    IdP form selectors and error markers are the least stable part of this
    surface — they track the Cl@ve frontend, not an AEAT-published contract —
    and may need redesign if the Cl@ve frontend changes shape.
    """

    selector_access_url_template: str = Field(min_length=1)
    selector_access_path_marker: str = Field(min_length=1)
    username_input_selector: str = Field(min_length=1)
    password_input_selector: str = Field(min_length=1)
    submit_button_selector: str = Field(min_length=1)
    elevation_sms_marker: str = Field(min_length=1)
    invalid_credentials_marker: str = Field(min_length=1)
    account_locked_marker: str = Field(min_length=1)
    password_expired_marker: str = Field(min_length=1)


class AeatPre303Surface(_Frozen):
    """Externally-defined Pre303 and IVA compensation wallet surface markers."""

    presentation_service_path: str = Field(min_length=1)
    access_help_path: str = Field(min_length=1)
    faq_general_path: str = Field(min_length=1)
    faq_specific_path: str = Field(min_length=1)
    functionalities_path: str = Field(min_length=1)
    procedures_path: str = Field(min_length=1)
    iva_wallet_header_tokens: tuple[str, ...] = Field(min_length=1)
    iva_wallet_total_label_tokens: tuple[str, ...] = Field(min_length=1)
    iva_wallet_empty_page_tokens: tuple[str, ...] = Field(min_length=1)
    representation_own_name_selector: str = Field(min_length=1)
    representation_own_name_label_selector: str = Field(min_length=1)
    representation_representative_selector: str = Field(min_length=1)
    representation_submit_selector: str = Field(min_length=1)
    representation_own_name_action_label: str = Field(min_length=1)
    wallet_discovered_entrypoint_action_label: str = Field(min_length=1)
    wallet_execute_read_action_label: str = Field(min_length=1)
    alert_modal_selector: str = Field(min_length=1)
    alert_continue_button_text: str = Field(min_length=1)
    wallet_form_selector: str = Field(min_length=1)
    wallet_execute_submit_selector: str = Field(min_length=1)
    tipo_actuacion_own_name_link_selector: str = Field(min_length=1)
    wallet_ejercicio_input_selector: str = Field(min_length=1)
    wallet_periodo_input_selector: str = Field(min_length=1)
    official_access_auth_methods: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "iva_wallet_header_tokens",
        "iva_wallet_total_label_tokens",
        "iva_wallet_empty_page_tokens",
        "official_access_auth_methods",
        mode="before",
    )
    @classmethod
    def _tuples_from_toml_arrays(cls, value: object) -> object:
        if is_object_list(value):
            return tuple(value)
        return value


class AeatHelpPageSection(_Frozen):
    """Static help/landing pages rooted under the sede origin."""

    csv_verification: str
    renta_web_open_landing: str
    nif_iva_landing: str
    manual_practicos_root: str


class AeatNotificationsQuery(_Frozen):
    """Filter parameters driving AEAT's notifications search surface.

    The surface defaults its date range to a single month. Reading it without
    supplying a range therefore answers "what arrived this month", which is not
    the question the notifications register is asked.

    Attributes:
        lookback_years: How far back the search window reaches from today.
        date_format: ``strftime`` pattern AEAT accepts for the filter dates.
        tipo_consulta_all: Filter value selecting every notification kind.
        leida_all: Filter value selecting both read and unread rows.
        detail_view_action: Action token returning the notification PDF.
    """

    lookback_years: int = Field(ge=1, le=50)
    date_format: str
    tipo_consulta_all: str
    leida_all: str
    detail_view_action: str


class AeatOracleSection(_Frozen):
    """Absolute URLs of AEAT parity oracles."""

    nif_iva_verification: str
    groi_check: str
    renta_web_open_app_template: str
    groi_auth_unlock_descriptor: str
    nif_iva_auth_locked_descriptor: str


class AeatLiveSafety(_Frozen):
    """Centralized allow-list labels for audited live AEAT browser actions.

    The patterns identify reviewed action categories for live-surface guards.
    They do not authorize a write by themselves; command policy, capability
    checks, and live-write gates remain responsible for deciding whether an
    operation may run.
    """

    auth_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    wallet_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    declarations_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    consult_oracle_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    renta_web_open_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    censal_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    censal_forbidden_landing_markers: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator(
        "auth_browser_action_patterns",
        "wallet_browser_action_patterns",
        "declarations_browser_action_patterns",
        "consult_oracle_browser_action_patterns",
        "renta_web_open_browser_action_patterns",
        "censal_browser_action_patterns",
        "censal_forbidden_landing_markers",
        mode="before",
    )
    @classmethod
    def _tuples_from_toml_arrays(cls, value: object) -> object:
        if is_object_list(value):
            return tuple(value)
        return value


class AeatPortalPathSection(_Frozen):
    """Centralized AEAT portal catalogue paths keyed by :class:`Portal` id.

    Portal entries resolve their route fragments from this registry so the
    catalogue can describe AEAT surfaces without carrying host or path source
    literals in each entry module.
    """

    filing_censo_path_regex: str = Field(min_length=1)
    filing_censo_path_description: str = Field(min_length=1)
    paths: dict[str, str] = Field(min_length=1)

    @field_validator("filing_censo_path_regex")
    @classmethod
    def _filing_censo_path_regex_is_valid(cls, value: str) -> str:
        re.compile(value)
        return value

    @field_validator("paths")
    @classmethod
    def _paths_are_relative_urls(cls, value: dict[str, str]) -> dict[str, str]:
        for key, path in value.items():
            if not key.strip():
                raise ValueError("portal path keys must not be blank")
            if not path.startswith("/"):
                raise ValueError(f"portal path for {key!r} must start with '/'")
        return value


class AeatSection(_Frozen):
    """Aggregates every AEAT-flavoured constant subsection.

    The ``pre303`` web-scraping surface (IVA-compensation-wallet routes,
    representation-gate selectors, parser markers) is the most volatile
    section of the registry: every value tracks the AEAT portal's HTML
    and may break on a portal redesign. To keep that volatility from
    poisoning the whole registry — and therefore every ``Settings()``
    construction, since :class:`core.config.Settings` resolves
    AEAT-URL defaults through :func:`load_external_constants` — the raw
    ``[aeat.pre303]`` mapping is kept untyped and validated lazily into a
    strict :class:`AeatPre303Surface` only on first access via the
    :attr:`pre303` property. A missing or malformed pre303 block thus
    never raises while parsing the registry; it surfaces as a clean
    :class:`core.errors.CoreValidationError` to the wallet /
    representation flows that actually consume it, and leaves
    selector-free commands (``config profile status``, ``modelo list``,
    …) entirely unaffected.
    """

    domains: AeatDomainSection
    sede_paths: AeatSedePathSection
    clave_movil: AeatClaveMovilSurface
    clave_permanente: AeatClavePermanenteSurface
    # ANY-RETURN-RATIONALE-PRE303-RAW-STAGING:
    # Raw TOML parse staging slot; cached_property converts to typed
    # AeatPre303Surface boundary model.
    pre303_raw: dict[str, Any] = Field(default_factory=dict, alias="pre303")
    help_pages: AeatHelpPageSection
    notifications_query: AeatNotificationsQuery
    oracles: AeatOracleSection
    live_safety: AeatLiveSafety
    portal_paths: AeatPortalPathSection

    @cached_property
    def pre303(self) -> AeatPre303Surface:
        """Return the strict-validated :class:`AeatPre303Surface` (Pre303 / IVA-wallet surface).

        Validation is deferred to first access so a malformed or absent
        ``[aeat.pre303]`` block cannot break registry parsing for the
        many CLI paths that never scrape the AEAT portal. When the block
        is broken the leaked :exc:`pydantic.ValidationError` is wrapped
        in a :class:`core.errors.CoreValidationError` carrying the section
        identity and the failing error's type as machine facts. The wrapper
        renders no prose and copies no validation message: the operator-facing
        text is the registered code's translation key, and the recovery is
        resolved downstream from the facts.
        """
        try:
            return AeatPre303Surface.model_validate(self.pre303_raw)
        except ValidationError as exc:
            raise CoreValidationError(
                translated_message=CoreValidationError.code.message_key,
                context={
                    "section": "aeat.pre303",
                    "valid": False,
                    "validation_error_type": type(exc).__name__,
                },
            ) from exc


class GoogleOAuthScopeSection(_Frozen):
    """OAuth scope strings the Google integration requests."""

    openid: str
    email: str
    drive_file: str
    spreadsheets: str


class GoogleServiceSection(_Frozen):
    """Google-hosted service surfaces."""

    oauth_scopes: GoogleOAuthScopeSection


class OnlineServicesSection(_Frozen):
    """Aggregates non-AEAT online service constants."""

    google: GoogleServiceSection


class ExternalConstants(_Frozen):
    """Top-level registry model mirroring the TOML root.

    The root intentionally separates AEAT-owned surfaces from other online
    services so call sites can depend on the narrow subsection they need while
    still sharing one typed registry load.
    """

    aeat: AeatSection
    online_services: OnlineServicesSection


#: IANA-registered MIME type for PDF document payloads.
PDF_MIME_TYPE: Final[str] = "application/pdf"

#: PDF file-extension string (lower-case, dot-prefixed).
PDF_EXTENSION: Final[str] = ".pdf"

#: IANA-registered MIME type for XML document payloads (RFC 7303 prefers this
#: over the discouraged ``text/xml``). Deliberately the GENERIC container type:
#: a structured e-invoice may be Facturae, EN16931 CII or UBL, and which one it
#: is can only be settled by probing the bytes. Storing a syntax-specific type
#: would restate as a declared fact the very claim the document-shape probe
#: exists to derive -- the mistake that once routed a ZUGFeRD invoice, whose
#: declared type said "PDF", down the prose-extraction path.
XML_MIME_TYPE: Final[str] = "application/xml"

#: Legacy binary Excel workbook file-extension string (lower-case, dot-prefixed).
XLS_EXTENSION: Final[Literal[".xls"]] = ".xls"

#: Excel / Open-XML workbook file-extension string (lower-case, dot-prefixed).
XLSX_EXTENSION: Final[Literal[".xlsx"]] = ".xlsx"

#: Excel macro-enabled workbook file-extension string (lower-case, dot-prefixed).
XLSM_EXTENSION: Final[Literal[".xlsm"]] = ".xlsm"

#: Legacy ISO-8859-1 / Latin-1 encoding used by AEAT sede fixed-width response bodies.
LATIN_1_ENCODING: Final[str] = "latin-1"

#: UTF-8 character encoding used for all text file I/O in the application layer.
UTF_8_ENCODING: Final[str] = "utf-8"

CSV_ENCODING_FALLBACK_CHAIN: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1")

#: Provenance source identifier for facts entered interactively via the CLI.
PROVENANCE_SOURCE_MANUAL_CLI: Final[str] = "manual_cli"

#: Provenance source identifier for censal facts parsed from an
#: operator-supplied Certificado de Situación Censal (procedure G313)
#: artefact. A NON-OFFICIAL evidence tier: the artefact is operator-channel
#: input, never stamped AEAT-verified, so the overview calendar's
#: ``censo.enrolment_unverified`` posture is unaffected by facts carrying
#: this token.
PROVENANCE_SOURCE_CENSO_ARTEFACT: Final[str] = "censo_artefact_g313"

#: Reserved operator-visible bucket-label prefix identifying a sandbox profile.
#: A profile whose plaintext manifest label starts with this token is a sandbox:
#: an isolated, discardable bucket. Declared in the light core layer so the
#: state-free CLI surface (``aeat`` / ``--help`` / ``--version``) can check the
#: active bucket's sandbox status without importing the heavy
#: ``bucket_maintenance`` / ``workflow`` facades. ``bucket_maintenance._sandbox``
#: re-exports it as the canonical application-facing name.
SANDBOX_LABEL_PREFIX: Final[str] = "sandbox:"

#: Environment variable name used to override the CLI output language at runtime.
OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "CADRUMO_OUTPUT_LANGUAGE"


class OutputLanguage(StrEnum):
    """Closed enumeration of CLI / API output language BCP-47 tags.

    The four members match the locale catalogues committed under
    ``src/cadrumo/locales/``. Adding a new operator-facing language
    requires landing the catalogue first and then extending this
    enum so the loader-side gates remain in sync.
    """

    ES = "es"
    EN = "en"
    CA = "ca"
    HU = "hu"


#: BCP-47 language tag for the default CLI and API output language (Spanish).
DEFAULT_OUTPUT_LANGUAGE: Final[OutputLanguage] = OutputLanguage.ES

#: Ordered tuple of BCP-47 language tags supported by the CLI and API output layer.
#: Kept as ``tuple[str, ...]`` (not ``tuple[OutputLanguage, ...]``) so
#: ``click.Choice(SUPPORTED_OUTPUT_LANGUAGES)`` renders the operator-facing
#: lowercase tags (``[es|en|ca|hu]``) on parse failure rather than the enum
#: NAMES (``[ES|EN|CA|HU]``) that Click derives from StrEnum members. The
#: ``OutputLanguage`` enum stays the canonical closed-set authority above;
#: this constant is the str-typed projection used at the click.Choice
#: boundary.
SUPPORTED_OUTPUT_LANGUAGES: Final[tuple[str, ...]] = tuple(lang.value for lang in OutputLanguage)


@lru_cache(maxsize=1)
def load_external_constants(path: Path | None = None) -> ExternalConstants:
    """Return the parsed external-constants registry.

    Cached per-process; the first call reads and validates
    ``external_constants.toml`` from the package directory via
    ``importlib.resources`` so the resolution path is identical
    under editable installs and built wheels. Passing ``path`` is reserved for
    audits and tests that need to validate an alternate TOML payload against the
    same schema.

    Args:
        path: Optional TOML file to parse instead of the packaged registry.

    Returns:
        The process-wide cached :class:`ExternalConstants` instance.
    """
    if path is not None:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    else:
        payload = tomllib.loads(files(__package__).joinpath("external_constants.toml").read_text(encoding="utf-8"))
    return ExternalConstants.model_validate(payload)
