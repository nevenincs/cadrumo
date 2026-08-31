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
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from functools import cached_property, lru_cache
from importlib.resources import files  # nosemgrep
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors.hierarchy import CoreValidationError
from .modelo import Modelo
from .models import STRICT_FROZEN_CONFIG

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


class AeatDomains(_Frozen):
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


class AeatSedePaths(_Frozen):
    """Relative path templates against configured AEAT origins.

    These values are route fragments and templates only; consumers choose the
    correct origin from :class:`AeatDomains` or an overrideable
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
    deudas_consulta: str
    #: The *pagar todas mis deudas* launcher. Declared NOT to be navigated but
    #: to be refused: it shares the ``/wlpl/SRVO-JDIT/`` application prefix with
    #: :attr:`deudas_consulta`, so the deudas read guard must allow-list the
    #: consulta ENDPOINT rather than that shared prefix. Naming it here keeps
    #: the refusal case anchored to an observed route instead of a guess.
    deudas_pagar_todas: str


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
        if isinstance(value, list):
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
    idp_host_marker: str = Field(min_length=1)
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
        if isinstance(value, list):
            return tuple(value)
        return value


class AeatHelpPages(_Frozen):
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


class AeatOracles(_Frozen):
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
        if isinstance(value, list):
            return tuple(value)
        return value


class AeatPortalPaths(_Frozen):
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

    domains: AeatDomains
    sede_paths: AeatSedePaths
    clave_movil: AeatClaveMovilSurface
    clave_permanente: AeatClavePermanenteSurface
    # ANY-RETURN-RATIONALE-PRE303-RAW-STAGING:
    # Raw TOML parse staging slot; cached_property converts to typed
    # AeatPre303Surface boundary model.
    pre303_raw: dict[str, Any] = Field(default_factory=dict, alias="pre303")
    help_pages: AeatHelpPages
    notifications_query: AeatNotificationsQuery
    oracles: AeatOracles
    live_safety: AeatLiveSafety
    portal_paths: AeatPortalPaths

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


class GoogleOAuthScopes(_Frozen):
    """OAuth scope strings the Google integration requests."""

    openid: str
    email: str
    drive_file: str
    spreadsheets: str


class GoogleServices(_Frozen):
    """Google-hosted service surfaces."""

    oauth_scopes: GoogleOAuthScopes


class OnlineServicesSection(_Frozen):
    """Aggregates non-AEAT online service constants."""

    google: GoogleServices


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

#: ISO-8859-1 encoding string as accepted by the fichero-BOE wire layer.
#:
#: Identical in coverage to :data:`LATIN_1_ENCODING` at runtime; the literal
#: type preserves the exact public registry-codec spelling for static callers.
ISO_8859_1_ENCODING: Final[Literal["iso-8859-1"]] = "iso-8859-1"

#: UTF-8 character encoding used for all text file I/O in the application layer.
UTF_8_ENCODING: Final[str] = "utf-8"

#: Allowed wire encodings for fichero-BOE payloads.
#:
#: Windows-1252 is a superset of ISO-8859-1 that adds characters in the
#: 0x80-0x9F range; AEAT treats them as equivalent for fichero-BOE
#: purposes.  ISO-8859-15 adds the Euro symbol at 0xA4 plus minor deltas.
BOE_ENCODING_CHOICES: Final[tuple[str, ...]] = ("cp1252", "iso-8859-1", "iso-8859-15")

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

#: Modelo 347 declaration floor per counterparty. Binding provision: RD 1065/2007
#: art. 33.1 ("operaciones que en su conjunto … hayan superado la cifra de 3.005,06
#: euros"), which fixes the figure; art. 31.1 only defines the general obligation.
#: Counterparties whose annual operations total at most this amount are NOT declarable.
M347_THRESHOLD_EUR: Final[Decimal] = Decimal("3005.06")

#: Modelo 347 clave C declaration floor per beneficiary. Binding provisions:
#: RD 1065/2007 art. 32.c ("300,51 euros durante el mismo periodo, cuando...
#: realicen la función de cobro por cuenta de terceros de honorarios
#: profesionales o de derechos derivados de la propiedad intelectual,
#: industrial o de autor") and art. 33.4 (same figure, framed as the
#: declaration threshold rather than the exclusion floor). Applies ONLY to
#: :attr:`~core.ThirdPartyDeclarationRole.THIRD_PARTY_FEE_COLLECTOR` rows,
#: alongside -- never instead of -- ``M347_THRESHOLD_EUR``: the same
#: counterparty can carry both ordinary and clave-C operations in the same
#: year, and each is judged against its own floor.
M347_CLAVE_C_THRESHOLD_EUR: Final[Decimal] = Decimal("300.51")

#: IVA regularización de deducciones por bienes de inversión — regulatory constants
#: (LIVA arts. 107-109, Ley 37/1992, BOE-A-1992-28740), re-read verbatim from the
#: bundled consolidated corpus ``corpus/normatives/html/ley-37-1992-art-107.html``
#: and ``-art-109.html`` per ``aeat-calculation-grounding``.
#:
#: Art. 107.Uno: movable capital goods regularise over the "cuatro años naturales
#: siguientes" to acquisition; art. 107.Tres: "terrenos o edificaciones" over the
#: "nueve años naturales siguientes". These are the count of FOLLOWING years in the
#: regularisation window (the acquisition year itself is the year the deduction was
#: made).
IVA_BIEN_INVERSION_MUEBLE_VENTANA_ANOS: Final[int] = 4
IVA_BIEN_INVERSION_INMUEBLE_VENTANA_ANOS: Final[int] = 9

#: Art. 107.Uno: the regularisation is practised only "cuando … exista una diferencia
#: superior a diez puntos" between the definitive deduction percentage of the year and
#: the one that prevailed in the acquisition year. The gate is STRICT (> 10 points);
#: a difference of exactly 10 points does not trigger a regularisation. Binding
#: provision: Art. 107.Uno LIVA (Ley 37/1992).
IVA_BIEN_INVERSION_REGULARIZACION_UMBRAL_PUNTOS: Final[Decimal] = Decimal("10")

#: Art. 109.3.º: "La diferencia positiva o negativa se dividirá por cinco o, tratándose
#: de terrenos o edificaciones, por diez". The per-year regularisation quotient divides
#: the deduction difference by 5 for movable goods and 10 for land/buildings. Binding
#: provision: Art. 109.3.º LIVA (Ley 37/1992).
IVA_BIEN_INVERSION_MUEBLE_DIVISOR: Final[Decimal] = Decimal("5")
IVA_BIEN_INVERSION_INMUEBLE_DIVISOR: Final[Decimal] = Decimal("10")

#: Art. 108.Dos.5.º bienes-de-escaso-valor exclusion: a good "cuyo valor de adquisición
#: sea inferior a quinientas mil pesetas" is NOT a bien de inversión. The consolidated
#: corpus still states the figure in pesetas; 500.000 ptas is the historic amount whose
#: euro equivalent is 3.005,06 € (the same figure the Modelo 347 floor carries). A good
#: whose acquisition value is at or above this threshold may qualify; below it is
#: excluded. Binding provision: Art. 108.Dos.5.º LIVA (Ley 37/1992).
IVA_BIEN_ESCASO_VALOR_UMBRAL_EUR: Final[Decimal] = Decimal("3005.06")

#: IAE art. 82.1.c net-turnover exemption ceiling for Modelo 840 threshold
#: continuity. Binding provision: TRLRHL RDL 2/2004 art. 82.1.c ("importe
#: neto de la cifra de negocios inferior a 1.000.000 de euros"). The gate is
#: STRICTLY BELOW this amount; an INCN equal to 1,000,000.00 EUR is not within
#: the turnover-based exemption.
MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR: Final[Decimal] = Decimal("1000000.00")

#: Art. 7.p) LIRPF (Ley 35/2006, BOE-A-2006-20764) annual exemption cap for
#: foreign-work income of maritime and other qualifying workers.
#: The exempt amount is the lesser of the proportional daily salary for
#: qualifying days and this ceiling.  Binding provision: Art. 7.p) LIRPF.
ART_7P_EXEMPTION_CAP_EUR: Final[Decimal] = Decimal("60100")

#: Art. 96.3 LIRPF (Ley 35/2006) secondary-pagador trigger amount. When work
#: income comes from more than one pagador, the reduced filing-exemption limit
#: (see ``WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR``) applies only
#: when the aggregate income from the 2nd and subsequent pagadores STRICTLY
#: exceeds this amount; at or below it the general 22.000 € limit is retained
#: (Art. 96.3.a.1.º). Binding provision: Art. 96.3 LIRPF (Ley 35/2006). This
#: trigger is year-stable and has not been revalued.
MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR: Final[Decimal] = Decimal("1500")

#: Art. 96.2.a) LIRPF (Ley 35/2006) GENERAL filing-exemption ceiling for
#: rendimientos íntegros del trabajo. A natural person whose work income does not
#: exceed this amount (single pagador, or multiple pagadores with the 2nd-and-
#: subsequent aggregate at or below 1.500 €) is NOT obliged to file Modelo 100 on
#: account of work income. Binding provision: Art. 96.2.a) LIRPF (Ley 35/2006).
#: This ceiling is year-stable.
WORK_INCOME_GENERAL_DECLARATION_LIMIT_EUR: Final[Decimal] = Decimal("22000")

#: Art. 96.3 LIRPF (Ley 35/2006) REDUCED filing-exemption ceiling for
#: rendimientos íntegros del trabajo, keyed by filing year (the year the income
#: was obtained). The general 22.000 € ceiling drops to this reduced amount when
#: work income comes from more than one pagador AND the 2nd-and-subsequent
#: aggregate exceeds ``MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR`` (1.500 €).
#: The amount is DATED: 2019-2022 use 14.000 € (Art. 96.3 LIRPF base value,
#: post-Ley 26/2014); 2023 uses 15.000 € (Ley 31/2022 PGE-2023,
#: BOE-A-2022-22128, art. 96.3 modification); 2024-2026 use 15.876 €
#: (RD-Ley 4/2024, BOE-A-2024-13066, art. 96.3 modification, confirmed by
#: the bundled consolidated LIRPF art-96 corpus).
#: Binding provision: Art. 96.3 LIRPF (Ley 35/2006), as modified per year above.
#: A filing year beyond the latest tabulated entry resolves to the latest known
#: amount (forward-compatible) until a new law revalues it.
WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR: Final[Mapping[int, Decimal]] = MappingProxyType(
    {
        2019: Decimal("14000"),
        2020: Decimal("14000"),
        2021: Decimal("14000"),
        2022: Decimal("14000"),
        2023: Decimal("15000"),
        2024: Decimal("15876"),
        2025: Decimal("15876"),
        2026: Decimal("15876"),
    },
)

#: Art. 40.3 LIS (Ley 27/2014, BOE-A-2014-12328) INCN threshold that makes the
#: base-imponible pago-fraccionado modality MANDATORY for Modelo 202. A taxpayer
#: whose importe neto de la cifra de negocios in the 12 months prior to the start of
#: the relevant período impositivo exceeded this amount must use the art. 40.3
#: modality; below it, the art. 40.2 (cuota) modality is optional. Binding
#: provision: Ley 27/2014 art. 40.3 (modalidad obligatoria por cifra de negocios).
MODELO_202_ART_40_3_INCN_THRESHOLD_EUR: Final[Decimal] = Decimal("6000000")

#: Art. 20 LIRPF (Ley 35/2006) rendimiento-neto-del-trabajo ceiling above which the
#: reducción por obtención de rendimientos del trabajo is zero. The reduction is a
#: piecewise-linear function of the rendimiento neto del trabajo (RNT) that decays to
#: zero at this ceiling: for RNT strictly below it the general reduction is positive;
#: at or above it the reduction is nil. Used by the Modelo 100 art. 20 advisory to flag
#: a possibly-unapplied reduction (RNT inside the band but the general-reduction casilla
#: zero) — a ``no-silent-under-declaration`` safeguard. The DATED per-ejercicio schedule
#: is authoritative in the registry; this is the current (2024-2025) ceiling raised by
#: RDL 4/2024. Binding provision: Ley 35/2006 art. 20, schedule per RDL 4/2024 art. 3.1
#: (BOE-A-2024-12944).
MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR: Final[Decimal] = Decimal("19747.50")

#: Art. 52.1 LIRPF (Ley 35/2006) individual-contribution sub-limit for the
#: reducción por aportaciones y contribuciones a sistemas de previsión social.
#: The joint reducción (casilla 0468) is capped at the lesser of 30% of net
#: yields and EUR 10.000, but a taxpayer whose aportaciones are PURELY
#: individual — no plan-de-empleo worker contribution (casilla 0426) and no
#: contribución empresarial (casilla 0427) backing the EUR 8.500 increment —
#: is bound by the lower EUR 1.500 general limit; the EUR 8.500 increment
#: "siempre que tal incremento provenga de contribuciones empresariales, o de
#: aportaciones del trabajador al mismo instrumento de previsión social".
#: Used by the Modelo 100 art. 52 advisory to flag a possible over-reduction
#: (a granted reducción above this sub-limit with no employer-linked backing),
#: pending the full individual/employer contribution-split compute. Binding
#: provision: Ley 35/2006 art. 52.1.
MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR: Final[Decimal] = Decimal("1500")

#: Default IVA general-rate percentage for input/pre-fill purposes.
#: This is the LIVA art. 90 Uno general rate (Ley 37/1992, BOE-A-1992-28740)
#: currently in force for Spain (ES).
#: The DATED authoritative percentage lives in ``registry/aeat/iva/rates.toml``
#: and is resolved via :func:`domain.iva.lookup_rate`; this constant is
#: bound to that registry authority by a gate test so it cannot silently drift.
DEFAULT_IVA_GENERAL_RATE_PCT: Final[Decimal] = Decimal("21.00")

#: Modelos belonging to the *retenciones* aggregation family (withholding/retention filings).
#: Covers: M111 (labour income), M115 (leases), M123 (capital yields), M180 (lease annual),
#: M190 (labour annual summary), M193 (capital yields annual summary).
RETENCIONES_MODELOS: Final[tuple[Modelo, ...]] = (
    Modelo.M111,
    Modelo.M115,
    Modelo.M123,
    Modelo.M180,
    Modelo.M190,
    Modelo.M193,
)

#: Modelos belonging to the *counterpart* aggregation family (third-party declaration filings).
#: Covers: M347 (annual operations with third parties), M349 (intra-EU operations summary).
COUNTERPART_MODELOS: Final[tuple[Modelo, ...]] = (Modelo.M347, Modelo.M349)

#: Modelos belonging to the *foreign assets* aggregation family (overseas-asset declaration).
#: Covers: M720 (assets and rights abroad declaration per Ley 7/2012).
FOREIGN_ASSET_MODELOS: Final[tuple[Modelo, ...]] = (Modelo.M720,)

#: Modelos belonging to the *IVA regime* gating group (value-added tax periodic filings).
#: Covers: M303 (quarterly/monthly IVA self-assessment), M390 (IVA annual summary).
IVA_REGIME_MODELOS: Final[tuple[Modelo, ...]] = (Modelo.M303, Modelo.M390)

#: REBECA 50% exemption of qualifying maritime navigation income.
#: Applies to crew of REBECA-registered vessels and scheduled Canary Islands routes.
#: Binding provision: Ley 19/1994 art. 75.1 (BOE-A-1994-15794) fixes the 50 por 100
#: renta exenta; art. 73 establishes REBECA eligibility. Catalogue: ley-19-1994:art-75.
REBECA_MARITIME_EXEMPTION_FRACTION: Final[Decimal] = Decimal("0.50")

#: 3% amortización de inmuebles arrendados; rate fixed by RD 439/2007 (RIRPF) art. 14.2.a
#: ("3 por 100 sobre el mayor de coste de adquisición o valor catastral, excluido el suelo").
#: Deductibility base: Ley 35/2006 art. 23 (capital inmobiliario gastos deducibles).
AMORTIZACION_INMUEBLE_RATE: Final[Decimal] = Decimal("0.03")

#: Art. 81 LIRPF (Ley 35/2006, BOE-A-2006-20764) monthly accrual per hijo menor de tres años.
#: Proration of the €1,200 annual cap; casilla 0611 carries integer euros only.
DEDUCCION_MATERNIDAD_MENSUAL_EUR: Final[int] = 100

#: Art. 81 LIRPF (Ley 35/2006, BOE-A-2006-20764) annual cap per hijo menor de tres años.
#: The deducción accrues at €100/month and is capped at this amount per hijo; casilla 0611.
DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR: Final[int] = 1200

#: Art. 81.1 LIRPF one-off increment for the calendar month in which a madre not
#: registered with the Seguridad Social (or a mutualidad) at the birth completes the
#: 30-day minimum contribution period the article requires for the post-birth alta
#: route ("estén dadas de alta en el régimen correspondiente de la Seguridad Social o
#: Mutualidad con un período mínimo, en este último caso, de 30 días cotizados"). The
#: bundled Manual Práctico de Renta 2023 worked example ("Alta en la Seguridad Social
#: con posterioridad al nacimiento y 30 días cotizados en el mes de mayo") reproduces the
#: arithmetic verbatim: the completion month counts once at the ordinary monthly rate
#: AND once again at this increment — ``[(8 meses x 100 euros) + (1 mes x 150)] = 950``.
DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR: Final[int] = 150

#: The per-hijo annual cap while the Art. 81.1 post-birth alta increment applies:
#: DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR raised by
#: DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR. Matches the "Límite de la
#: deducción por hijo (1.350 euros)" the Manual Práctico de Renta 2023 worked example
#: states for both children it covers.
DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR: Final[int] = 1350

#: First filing year the post-birth alta route (and its 150 euro increment) reaches.
#: Before it, Art. 81 LIRPF granted the deducción only to a madre already registered
#: with the Seguridad Social or a mutualidad "en el momento del nacimiento" (Manual
#: Práctico de Renta 2021, "Normativa: Arts. 81 Ley IRPF y 60 Reglamento" — the manual's
#: own beneficiary test names no post-birth alta at all). The Manual Práctico de Renta
#: 2023 worked example states the extension in terms: "a partir del 1 de enero de 2023
#: se han ampliado los supuestos que dan derecho a ésta". Filing years before this take
#: no increment and keep the ordinary DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR cap.
DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR: Final[int] = 2023

#: Art. 81.1 LIRPF: the first filing year in which the deducción por maternidad is NO
#: LONGER capped at the mother's Social Security cotizaciones. Until 2022 the deducción
#: was limited to the "cotizaciones y cuotas totales a la Seguridad Social y mutualidades
#: devengadas en cada período impositivo", stated in the Manual Práctico de Renta 2020 and
#: 2022; the Manual Práctico de Renta 2024 records the removal in terms — "desaparece esta
#: limitación del importe de la deducción a las cotizaciones devengadas en el período
#: impositivo … el nuevo régimen resulta aplicable desde el 1 de enero de 2023".
#:
#: Shares a value with the alta-posterior gate above and is deliberately NOT merged with
#: it: two independent rules that happen to change in the same reform. Collapsing them
#: would silently move one if the other were ever corrected.
DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR: Final[int] = 2023

#: Art. 58.1 LIRPF (Ley 35/2006, BOE-A-2006-20764) ordinary mínimo-por-descendientes
#: age ceiling: a descendant qualifies for the ordinary mínimo while younger than 25
#: (exclusive) at year end, unless disabled (which removes the age limit).
MINIMO_DESCENDIENTE_MAX_AGE: Final[int] = 25

#: Art. 58.2 LIRPF (Ley 35/2006, BOE-A-2006-20764) bajo-3-años supplement age ceiling:
#: "Cuando el descendiente sea menor de tres años, el mínimo … se aumentará". The
#: additional mínimo applies to a descendant younger than 3 (exclusive) at year end.
MINIMO_MENOR_TRES_MAX_AGE: Final[int] = 3

#: Art. 61.4ª LIRPF (Ley 35/2006, BOE-A-2006-20764) custodia compartida prorrata
#: factor: under the normas comunes, when two contribuyentes have the right to the
#: same mínimo "su importe se prorrateará entre ellos por partes iguales" — a 50 %
#: split between the two custodial parents.
CUSTODIA_COMPARTIDA_PRORRATA_FACTOR: Final[Decimal] = Decimal("0.5")

#: Art. 81.1 LIRPF (Ley 35/2006, BOE-A-2006-20764) adopción/acogimiento window for the
#: deducción por maternidad: the limb runs "durante los tres años siguientes a la fecha
#: de la inscripción en el Registro Civil". Counted in YEARS from a date, unlike the
#: Art. 58.2 window below, which counts whole tax PERIODS from the entry period — two
#: rules that read alike and are not, so they stay separate constants.
ART_81_1_ENTRY_WINDOW_YEARS: Final[int] = 3

#: Madrid DL 1/2010 art. 4 deducción por nacimiento o adopción applicability window,
#: expressed as the count of periods FOLLOWING the entry period. The deducción applies
#: in the period of nacimiento/adopción and in each of the two following, i.e. a
#: three-period window keyed on the entry year. Grounded in the bundled AEAT Renta 2025
#: manual, parte 2 (deducciones autonómicas), "Ámbito temporal de aplicación de la
#: deducción". Autonómico rather than estatal, so it is the likelier of the two to move.
NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS: Final[int] = 2

#: LIRPF Disposición Transitoria 12ª (Ley 35/2006, BOE-A-2006-20764) reducción rate:
#: 40 % reducción on the part of a plan-de-pensiones capital rescate attributable to
#: contributions made on or before 31-12-2006.
DT12_RESCATE_REDUCCION_RATE: Final[Decimal] = Decimal("0.40")

#: LIRPF DT 12ª apartado 3 (added by Ley 26/2014 art. 1.85, BOE-A-2014-12327)
#: time-window boundaries, each quoted from the bundled consolidated LIRPF at
#: ``corpus/normatives/html/ley-35-2006.html#dtduodecima``. The régimen
#: transitorio -- and so the 40 % reducción above -- reaches only prestaciones
#: percibidas inside a window measured from the contingencia year.
#:
#: These are boundaries fixed once by the 2014 amendment, not figures the law
#: re-sets per filing year, so they are leaf constants rather than registry
#: parameters: year-versioning an invariant value would duplicate it across
#: every revision to vary nothing.
#:
#: General rule, contingencia 2015 onwards: percibida "en el ejercicio en el que
#: acaezca la contingencia correspondiente, o en los dos ejercicios siguientes".
DT12_GENERAL_WINDOW_FOLLOWING_YEARS: Final[int] = 2

#: Contingencia "acaecidas en los ejercicios 2011 a 2014": percibida "hasta la
#: finalización del octavo ejercicio siguiente a aquel en el que acaeció la
#: contingencia correspondiente".
DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR: Final[int] = 2011
DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR: Final[int] = 2014
DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS: Final[int] = 8

#: Contingencia "acaecidas en los ejercicios 2010 o anteriores": percibida
#: "hasta el 31 de diciembre de 2018".
DT12_CLIFF_LAST_YEAR: Final[int] = 2018

#: Ley 44/2015 art. 14.1 (BOE-A-2015-11071) SAL/SLL reserva especial dotación rate:
#: 10 % of net profit endowed each year ("se dotará con el diez por ciento del
#: beneficio líquido de cada ejercicio").
SAL_RESERVA_DOTACION_RATE: Final[Decimal] = Decimal("0.10")

#: Ley 44/2015 art. 14.1 (BOE-A-2015-11071) SAL/SLL reserva especial accumulation cap
#: multiple: the reserve accrues until it exceeds twice the share capital ("hasta que
#: alcance al menos una cifra superior al doble del capital social").
SAL_RESERVA_CAPITAL_MULTIPLE: Final[Decimal] = Decimal("2")

#: LIVA art. 103.Dos.2.º as redrafted by Ley 28/2014 art. 1.26 (BOE-A-2014-12329),
#: in force from 01-01-2015: the prorrata especial regime is mandatory "cuando el
#: montante total de las cuotas deducibles en un año natural por aplicación de la
#: regla de prorrata general exceda en un 10 por ciento o más del que resultaría
#: por aplicación de la regla de prorrata especial". The margin is INCLUSIVE ("o
#: más" reaches it), so the regime switches at
#: ``deduction_general >= deduction_especial * 1.10``.
PRORRATA_ESPECIAL_MANDATORY_MULTIPLE_FROM_2015: Final[Decimal] = Decimal("1.10")

#: LIVA art. 103.Dos.2.º in its ORIGINAL redaction (Ley 37/1992, BOE-A-1992-28740,
#: in force 01-01-1993 to 31-12-2014): "Cuando el montante total de las cuotas
#: deducibles en un año natural por aplicación de la regla de prorrata general
#: exceda en un 20 por 100 del que resultaría por aplicación de la regla de
#: prorrata especial". Twenty percent, and with no "o más", so the margin must be
#: passed rather than merely reached:
#: ``deduction_general > deduction_especial * 1.20``.
PRORRATA_ESPECIAL_MANDATORY_MULTIPLE_UNTIL_2014: Final[Decimal] = Decimal("1.20")

#: First filing year governed by the Ley 28/2014 (BOE-A-2014-12329) redaction of
#: LIVA art. 103.Dos.2.º. The bundled consolidated corpus records the amendment
#: verbatim ("Se modifica el apartado 2.2º por el art. 1.26 de la Ley 28/2014, de
#: 27 de noviembre") and dates it "en vigor a partir del 01/01/2015", and the Ley
#: 28/2014 preamble states the change as "disminuir del 20 al 10 por ciento la
#: diferencia admisible". Filing years at or above this take the ten-percent
#: inclusive margin; earlier years take the original twenty-percent exclusive one.
PRORRATA_ESPECIAL_MANDATORY_LEY_28_2014_FIRST_YEAR: Final[int] = 2015

#: LIVA art. 9.1.c (Ley 37/1992, BOE-A-1992-28740) sectoral-separation threshold:
#: régimen de sectores diferenciados is mandatory when the spread between the highest
#: and lowest general prorrata across sectors exceeds fifty percentage points.
PRORRATA_SECTORAL_SEPARATION_SPREAD_PP: Final[Decimal] = Decimal("50")

#: Ley 39/2015 art. 43.2 (BOE-A-2015-10565) rechazo-tácito window for an electronic
#: notification: "se entenderá rechazada cuando hayan transcurrido diez días naturales
#: desde la puesta a disposición de la notificación sin que se acceda a su contenido".
#: Días NATURALES, not hábiles — weekends, holidays and August count, so a
#: días-hábiles reading would compute a later lapse date than the law allows and
#: understate urgency to the taxpayer. The clock runs from the puesta a disposición,
#: never from access. The provision is enrolled in the legal catalogue as
#: ``ley-39-2015:art-43.2``, and the quoted clause above is that entry's own
#: corpus text rather than a restatement of it.
DEHU_RECHAZO_TACITO_DIAS_NATURALES: Final[int] = 10


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
