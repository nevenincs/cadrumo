"""External constants registry loaded from ``external_constants.toml``.

Centralises third-party hostnames, AEAT service paths, OAuth scopes, and
remote API endpoints. The TOML file sits beside this module and is parsed
once per process via :func:`load_external_constants`. Every section is
modelled as a frozen, strict pydantic v2 model so callers see typed,
immutable values and any drift between the TOML and the schema fails fast
at import time.

The typed root is :class:`ExternalConstants`, with AEAT-specific subsections
grouped under :class:`AeatSection`; callers normally reach it through
:meth:`~aeat.core.config.Settings.external_constants`. The volatile Pre303 and
IVA-wallet browser surface remains lazily validated as :class:`AeatPre303Surface`
so selector churn does not poison unrelated configuration reads.
"""

from __future__ import annotations

import re
import tomllib
from decimal import Decimal
from enum import StrEnum
from functools import cached_property, lru_cache
from importlib.resources import files  # nosemgrep
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..core import STRICT_FROZEN_CONFIG
from . import Modelo
from .errors import CoreValidationError

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
    """Strict, frozen base for external-constant submodels."""

    model_config = STRICT_FROZEN_CONFIG


class AeatDomains(_Frozen):
    """AEAT and related government hostnames."""

    host_suffix: str = Field(min_length=1)
    sede: str = Field(min_length=1)
    www1: str = Field(min_length=1)
    www2: str = Field(min_length=1)
    www3: str = Field(min_length=1)
    www6: str = Field(min_length=1)
    www12: str = Field(min_length=1)
    aeat_gob: str = Field(min_length=1)
    legacy_www: str = Field(min_length=1)
    clave: str = Field(min_length=1)
    boe: str = Field(min_length=1)


class AeatSedePaths(_Frozen):
    """Relative path templates against the sede / www6 origins."""

    auth_gate_4033: str
    expedientes_resumen: str
    declarations_listing: str
    cotejo_query: str
    cotejo_document: str
    notifications_summary: str
    notifications_query: str
    certificate_selector: str
    censo_g313_launcher: str
    r210_simulator_open_ajax: str
    borrador_100_detail_template: str
    declaracion_consult: str
    clave_movil_login: str
    expediente_detail_template: str
    irpf_expediente_detail_year_prefix: str
    irpf_expediente_detail_year_suffix: str
    notificaciones: str
    iva_compensation_wallet: str


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


class AeatOracles(_Frozen):
    """Absolute URLs of AEAT parity oracles."""

    nif_iva_verification: str
    groi_check: str
    renta_web_open_app_template: str
    groi_auth_unlock_descriptor: str
    nif_iva_auth_locked_descriptor: str


class AeatLiveSafety(_Frozen):
    """Centralized allow-list labels for audited live AEAT browser actions."""

    auth_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    wallet_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    declarations_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    csv_verify_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    consult_oracle_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)
    renta_web_open_browser_action_patterns: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator(
        "auth_browser_action_patterns",
        "wallet_browser_action_patterns",
        "declarations_browser_action_patterns",
        "csv_verify_browser_action_patterns",
        "consult_oracle_browser_action_patterns",
        "renta_web_open_browser_action_patterns",
        mode="before",
    )
    @classmethod
    def _tuples_from_toml_arrays(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value


class AeatPortalPaths(_Frozen):
    """Centralized AEAT portal catalogue paths keyed by :class:`Portal` id."""

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
    construction, since :class:`~aeat.core.config.Settings` resolves
    AEAT-URL defaults through :func:`load_external_constants` — the raw
    ``[aeat.pre303]`` mapping is kept untyped and validated lazily into a
    strict :class:`AeatPre303Surface` only on first access via the
    :attr:`pre303` property. A missing or malformed pre303 block thus
    never raises while parsing the registry; it surfaces as a clean
    :class:`~aeat.core.errors.CoreValidationError` to the wallet /
    representation flows that actually consume it, and leaves
    selector-free commands (``config profile status``, ``modelo list``,
    …) entirely unaffected.
    """

    domains: AeatDomains
    sede_paths: AeatSedePaths
    clave_movil: AeatClaveMovilSurface
    # ANY-RETURN-RATIONALE-PRE303-RAW-STAGING:
    # Raw TOML parse staging slot; cached_property converts to typed
    # AeatPre303Surface boundary model.
    pre303_raw: dict[str, Any] = Field(default_factory=dict, alias="pre303")
    help_pages: AeatHelpPages
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
        in a :class:`~aeat.core.errors.CoreValidationError` carrying an
        operator-facing recovery hint.
        """
        try:
            return AeatPre303Surface.model_validate(self.pre303_raw)
        except ValidationError as exc:
            raise CoreValidationError(
                "The AEAT Pre303 / IVA-wallet surface section of "
                "external_constants.toml is missing or malformed. This "
                "section configures AEAT web-scraping selectors; only "
                "commands that read the IVA compensation wallet or the "
                "Pre303 portal need it.",
                context={
                    "section": "aeat.pre303",
                    "validation_error": str(exc),
                },
                suggestion="aeat config repair --help",
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
    """Top-level registry model mirroring the TOML root."""

    aeat: AeatSection
    online_services: OnlineServicesSection


#: IANA-registered MIME type for PDF document payloads.
PDF_MIME_TYPE: Final[str] = "application/pdf"

#: PDF file-extension string (lower-case, dot-prefixed).
PDF_EXTENSION: Final[str] = ".pdf"

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
#: Identical in coverage to :data:`LATIN_1_ENCODING` at runtime; declared as a
#: typed ``Literal["iso-8859-1"]`` so callers that pass it to a
#: :data:`~aeat.adapters.outbound.aeat.export._formats._record_spec.FicheroBoeEncoding`
#: parameter satisfy the static type checker without a cast.
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

#: Environment variable name used to override the CLI output language at runtime.
OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANGUAGE"

#: POSIX / Windows environment variable that Rich uses to determine console column width.
COLUMNS_ENV_VAR: Final[str] = "COLUMNS"


class OutputLanguage(StrEnum):
    """Closed enumeration of CLI / API output language BCP-47 tags.

    The four members match the locale catalogues committed under
    ``src/aeat/locales/``. Adding a new operator-facing language
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

#: Modelo 720 declaration floor per asset class (``bloque``). Binding provision: RD 1065/2007
#: arts. 42 bis/ter/quater (added by RD 1558/2012) under LGT DA 18ª — each block
#: (cuentas / valores-seguros / inmuebles) carries an independent 50.000 € umbral.
#: An asset class is declarable iff its total valuation strictly exceeds this amount.
MODELO_720_REPORTING_THRESHOLD_EUR: Final[Decimal] = Decimal("50000.00")

#: Art. 7.p) LIRPF (Ley 35/2006, BOE-A-2006-20764) annual exemption cap for
#: foreign-work income of maritime and other qualifying workers.
#: The exempt amount is the lesser of the proportional daily salary for
#: qualifying days and this ceiling.  Binding provision: Art. 7.p) LIRPF.
ART_7P_EXEMPTION_CAP_EUR: Final[Decimal] = Decimal("60100")

#: Art. 96.3 LIRPF (Ley 35/2006) secondary-pagador filing floor.
#: A natural person whose rendimientos del trabajo originate from more than one
#: pagador must file Modelo 100 when aggregate income from the 2nd and subsequent
#: pagadores exceeds this amount.  Binding provision: Art. 96.3 LIRPF (Ley 35/2006).
MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR: Final[Decimal] = Decimal("1500")

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

#: Default IVA general-rate percentage for input/pre-fill purposes.
#: This is the LIVA art. 90 Uno general rate (Ley 37/1992, BOE-A-1992-28740)
#: currently in force for Spain (ES).
#: The DATED authoritative percentage lives in ``registry/aeat/iva/rates.toml``
#: and is resolved via :func:`aeat.domain.iva.lookup_rate`; this constant is
#: bound to that registry authority by a gate test so it cannot silently drift.
DEFAULT_IVA_GENERAL_RATE_PCT: Final[Decimal] = Decimal("21.00")

#: Secure-object namespace slug for Cl@ve Móvil auth diagnostics.
#: Used by the auth diagnostics service and the persistence namespace registry.
CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE: Final[str] = "aeat.outbound.aeat.auth.clave_movil.diagnostics"

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

#: Art. 81 LIRPF (Ley 35/2006, BOE-A-2006-20764) incremento por gastos de custodia en
#: guardería o centro de educación infantil autorizado, per hijo menor de tres años cap.
#: Capped at the lesser of real gastos, this amount × hijos_menores_3, and SS cotizaciones;
#: casilla 0613.  Note: this is Art. 81 LIRPF (deducción maternidad supplemento), NOT Art. 81
#: bis (familia numerosa / discapacidad).
INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR: Final[int] = 1000

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

#: LIRPF Disposición Transitoria 12ª (Ley 35/2006, BOE-A-2006-20764) reducción rate:
#: 40 % reducción on the part of a plan-de-pensiones capital rescate attributable to
#: contributions made on or before 31-12-2006.
DT12_RESCATE_REDUCCION_RATE: Final[Decimal] = Decimal("0.40")

#: Ley 44/2015 art. 14.1 (BOE-A-2015-11071) SAL/SLL reserva especial dotación rate:
#: 10 % of net profit endowed each year ("se dotará con el diez por ciento del
#: beneficio líquido de cada ejercicio").
SAL_RESERVA_DOTACION_RATE: Final[Decimal] = Decimal("0.10")

#: Ley 44/2015 art. 14.1 (BOE-A-2015-11071) SAL/SLL reserva especial accumulation cap
#: multiple: the reserve accrues until it exceeds twice the share capital ("hasta que
#: alcance al menos una cifra superior al doble del capital social").
SAL_RESERVA_CAPITAL_MULTIPLE: Final[Decimal] = Decimal("2")

#: LIVA art. 103.Dos (Ley 37/1992, BOE-A-1992-28740) prorrata especial mandatory
#: multiple: the especial regime is mandatory when the general-regime deduction
#: exceeds the especial-regime deduction by more than ten percent — i.e. when
#: ``deduction_general > deduction_especial * 1.10``.
PRORRATA_ESPECIAL_MANDATORY_MULTIPLE: Final[Decimal] = Decimal("1.10")

#: LIVA art. 9.1.c (Ley 37/1992, BOE-A-1992-28740) sectoral-separation threshold:
#: régimen de sectores diferenciados is mandatory when the spread between the highest
#: and lowest general prorrata across sectors exceeds fifty percentage points.
PRORRATA_SECTORAL_SEPARATION_SPREAD_PP: Final[Decimal] = Decimal("50")


@lru_cache(maxsize=1)
def load_external_constants(path: Path | None = None) -> ExternalConstants:
    """Return the parsed external-constants registry.

    Cached per-process; the first call reads and validates
    ``external_constants.toml`` from the package directory via
    ``importlib.resources`` so the resolution path is identical
    under editable installs and built wheels.

    Returns:
        The process-wide cached :class:`ExternalConstants` instance.
    """
    if path is not None:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    else:
        payload = tomllib.loads(files(__package__).joinpath("external_constants.toml").read_text(encoding="utf-8"))
    return ExternalConstants.model_validate(payload)
