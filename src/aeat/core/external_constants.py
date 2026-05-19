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
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Frozen(BaseModel):
    """Strict, frozen base for external-constant submodels."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class AeatDomains(_Frozen):
    """AEAT and related government hostnames."""

    sede: str = Field(min_length=1)
    www1: str = Field(min_length=1)
    www2: str = Field(min_length=1)
    www6: str = Field(min_length=1)
    clave: str = Field(min_length=1)
    boe: str = Field(min_length=1)


class AeatSedePaths(_Frozen):
    """Relative path templates against the sede / www6 origins."""

    expedientes_resumen: str
    declarations_listing: str
    cotejo_query: str
    cotejo_document: str
    notifications_summary: str
    notifications_query: str
    certificate_selector: str
    expediente_detail_template: str
    notificaciones: str
    iva_compensation_wallet: str


class AeatClaveMovilSurface(_Frozen):
    """Externally-defined Cl@ve Móvil page identifiers and shape markers."""

    selector_access_url_template: str = Field(min_length=1)
    selector_access_path_marker: str = Field(min_length=1)
    dialogo_representacion_path_marker: str = Field(min_length=1)
    obtener_clave_movil_path_marker: str = Field(min_length=1)
    obtener_clave_movil_qr_path_marker: str = Field(min_length=1)
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

    @field_validator("wait_text_markers", "pending_petition_text_markers", mode="before")
    @classmethod
    def _markers_from_toml_arrays(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value


class AeatHelpPages(_Frozen):
    """Static help/landing pages rooted under the sede origin."""

    csv_verification: str
    renta_web_open_landing: str
    nif_iva_landing: str


class AeatOracles(_Frozen):
    """Absolute URLs of AEAT parity oracles."""

    nif_iva_verification: str
    groi_check: str
    renta_web_open_app_template: str


class AeatSection(_Frozen):
    """Aggregates every AEAT-flavoured constant subsection."""

    domains: AeatDomains
    sede_paths: AeatSedePaths
    clave_movil: AeatClaveMovilSurface
    help_pages: AeatHelpPages
    oracles: AeatOracles


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
