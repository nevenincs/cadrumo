"""External constants registry loaded from `external_constants.toml`.

Centralises third-party hostnames, AEAT service paths, OAuth scopes, and
remote API endpoints. The TOML file sits beside this module and is parsed
once per process via :func:`load_external_constants`. Every section is
modelled as a frozen, strict pydantic v2 model so callers see typed,
immutable values and any drift between the TOML and the schema fails fast
at import time.
"""

from __future__ import annotations

import tomllib
from functools import cached_property, lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .errors import CoreValidationError


class _Frozen(BaseModel):
    """Strict, frozen base for external-constant submodels."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


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
    census_g313_launcher: str
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
    iva_wallet_empty_page_tokens: tuple[str, ...] = Field(min_length=1)
    representation_own_name_selector: str = Field(min_length=1)
    representation_own_name_label_selector: str = Field(min_length=1)
    representation_representative_selector: str = Field(min_length=1)
    representation_submit_selector: str = Field(min_length=1)
    alert_modal_selector: str = Field(min_length=1)
    alert_continue_button_text: str = Field(min_length=1)
    wallet_form_selector: str = Field(min_length=1)
    wallet_execute_submit_selector: str = Field(min_length=1)
    official_access_auth_methods: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "iva_wallet_header_tokens",
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
    pre303_raw: dict[str, Any] = Field(default_factory=dict, alias="pre303")
    help_pages: AeatHelpPages
    oracles: AeatOracles
    live_safety: AeatLiveSafety

    @cached_property
    def pre303(self) -> AeatPre303Surface:
        """Return the strict-validated Pre303 / IVA-wallet surface.

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
                suggestion="aeat config repair",
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


@lru_cache(maxsize=1)
def load_external_constants(path: Path | None = None) -> ExternalConstants:
    """Return the parsed external-constants registry.

    Cached per-process; the first call reads and validates
    ``external_constants.toml`` from the package directory via
    ``importlib.resources`` so the resolution path is identical
    under editable installs and built wheels.
    """

    if path is not None:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    else:
        payload = tomllib.loads(
            files(__package__).joinpath("external_constants.toml").read_text(encoding="utf-8")
        )
    return ExternalConstants.model_validate(payload)
