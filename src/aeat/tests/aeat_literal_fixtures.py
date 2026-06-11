"""Declared AEAT host/path literals used only as test canaries.

Most AEAT/Sede URLs in tests should be assembled from
``Settings.external_constants()``. This module is the exception boundary
for literals whose purpose is to prove that guards reject unsafe,
unknown, or legacy-looking AEAT surfaces.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..core.config import Settings

_AEAT = Settings.external_constants().aeat

AEAT_HOST_SUFFIX_EXPECTED = _AEAT.domains.host_suffix
AEAT_LEGACY_APEX_CANARY = "aeat.es"
AEAT_LEGACY_SEDE_CANARY = f"sede.{AEAT_LEGACY_APEX_CANARY}"
CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED = _AEAT.clave_movil.obtener_clave_movil_browser_global
UNKNOWN_AEAT_SUBDOMAIN_CANARY = f"www9.{_AEAT.domains.host_suffix}"
UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY = "/wlpl/unsafe-state-surface"
UNKNOWN_AEAT_STATE_SURFACE_URL_CANARY = (
    f"https://{UNKNOWN_AEAT_SUBDOMAIN_CANARY}{UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY}"
)
PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE = "/Sede/procedimientoini/ZZ08.shtml"
STATIC_DESIGN_REGISTER_PATH_FIXTURE = "/Sede/ayuda/disenos-registro.html"
AUTH_DIAGNOSTIC_PATH_FIXTURE = "/auth"
BORRADOR_STORAGE_PATH_FIXTURE = "/borrador/100"
FILED_ARTEFACT_PATH_FIXTURE = "/file"
PDF_100_PATH_FIXTURE = "/100.pdf"
PDF_FORM_PATH_FIXTURE = "/form.pdf"
PDF_MODELO_130_2024_PATH_FIXTURE = "/modelo-130-2024.pdf"
LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE = "/wlpl/check"
LIVE_PARITY_PRET_CHECK_PATH_FIXTURE = "/wlpl/PRET/check"
LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE = "/wlpl/sim"
LIVE_PARITY_SUBMIT_PATH_CANARY = "/wlpl/submit"
LIVE_PARITY_STATE_CREATING_PATH_CANARIES = (
    "/wlpl/TGVI/online",
    "/wlpl/PRET/tgvionline/upload",
    "/wlpl/PRET/transmision-fichero",
    "/wlpl/PRET/transmitir",
)
JUSTIFICANTE_AYUDA_PATH_FIXTURE = "/ayuda"
JUSTIFICANTE_COTEJO_PATH_PREFIX_FIXTURE = "/Sede/cotejo/CSV="
JUSTIFICANTE_VERIFY_PATH_FIXTURE = "/verify"
JUSTIFICANTE_WLPL_COTEJO_PATH_PREFIX_FIXTURE = "/wlpl/SCEJ-MANT/cotejo/CSV/"
PORTAL_CENSO_NON_GCODE_PATH_CANARY = "/Sede/censal.html"
PORTAL_NON_GCODE_PATH_CANARY = "/Sede/something-else.html"
PORTAL_RETIRED_PATH_CANARY = "/Sede/retired-path.html"
PORTAL_RETIRED_WITH_NOTES_PATH_CANARY = "/Sede/retired.html"
REDACTION_INTERNAL_PATH_CANARY = "/internal/path?token=12345"
REDACTION_SECRET_WLPL_PATH_CANARY = "/wlpl/SECRET-PATH/Submit?session=ABCDEFGHIJ"  # noqa: S105 - path canary
UNCLASSIFIED_MUTATING_READ_POST_PATH_CANARY = "/wlpl/OTHER/MutatingPath"
UNCLASSIFIED_WWW2_READ_PATH_CANARY = "/wlpl/some/path"
AEAT_LITERAL_SCAN_TOKENS = (
    _AEAT.domains.host_suffix,
    "/wlpl/",
    "/Sede/",
    "static_files",
    _AEAT.clave_movil.selector_access_path_marker,
    "CarteraCuotas",
    "ConsultaIntracomunitarios",
    "ConsultaOperadorSedeGroiServlet",
    "www1 IXVI",
    "www2 GROI",
    _AEAT.clave_movil.obtener_clave_movil_browser_global,
)
PORTAL_LITERAL_SCAN_TOKENS = (
    _AEAT.domains.host_suffix,
    "agenciatributaria.es",
    "clave.gob.es",
    "/Sede/",
    "/wlpl/",
)
REMOTE_GUARD_LITERAL_SCAN_TOKENS = (
    _AEAT.domains.host_suffix,
    AEAT_LEGACY_APEX_CANARY,
    "/Sede/",
    "/wlpl/",
    "CarteraCuotas",
)


def aeat_host(origin: str) -> str:
    """Return a configured AEAT host name without a scheme."""
    value = getattr(_AEAT.domains, origin)
    host = urlparse(value).hostname
    if host is None:
        raise AssertionError(f"configured AEAT origin {origin!r} has no host")
    return host


def aeat_url(origin: str, path: str) -> str:
    """Return an absolute URL from a configured AEAT origin and path."""
    if not path.startswith("/"):
        raise AssertionError(f"AEAT fixture path must be absolute: {path!r}")
    return f"{getattr(_AEAT.domains, origin)}{path}"


def configured_path(section: str, name: str) -> str:
    """Return a configured AEAT path from ``external_constants``."""
    return str(getattr(getattr(_AEAT, section), name))


def configured_template_path(section: str, name: str, **kwargs: object) -> str:
    """Return a formatted configured AEAT path template."""
    return configured_path(section, name).format(**kwargs)


def manual_practicos_url(relative_path: str) -> str:
    """Return a manual-practicos URL rooted at the configured static manuals base."""
    return aeat_url("sede", f"{_AEAT.help_pages.manual_practicos_root}/{relative_path.lstrip('/')}")


def portal_path(key: str) -> str:
    """Return a configured portal catalogue path."""
    return _AEAT.portal_paths.paths[key]


def justificante_cotejo_url(csv: str) -> str:
    """Return a synthetic justificante cotejo URL for parser fixtures."""
    return aeat_url("sede", f"{JUSTIFICANTE_COTEJO_PATH_PREFIX_FIXTURE}{csv}")


def justificante_wlpl_cotejo_url(csv: str) -> str:
    """Return a synthetic legacy WLPL cotejo URL for parser fixtures."""
    return aeat_url("sede", f"{JUSTIFICANTE_WLPL_COTEJO_PATH_PREFIX_FIXTURE}{csv}")


def sede_pdf_url(path: str) -> str:
    """Return a synthetic Sede URL for persistence fixtures."""
    return aeat_url("sede", path)


__all__ = [
    "AEAT_HOST_SUFFIX_EXPECTED",
    "AEAT_LEGACY_APEX_CANARY",
    "AEAT_LEGACY_SEDE_CANARY",
    "AEAT_LITERAL_SCAN_TOKENS",
    "AUTH_DIAGNOSTIC_PATH_FIXTURE",
    "BORRADOR_STORAGE_PATH_FIXTURE",
    "CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED",
    "FILED_ARTEFACT_PATH_FIXTURE",
    "JUSTIFICANTE_AYUDA_PATH_FIXTURE",
    "JUSTIFICANTE_COTEJO_PATH_PREFIX_FIXTURE",
    "JUSTIFICANTE_VERIFY_PATH_FIXTURE",
    "JUSTIFICANTE_WLPL_COTEJO_PATH_PREFIX_FIXTURE",
    "LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE",
    "LIVE_PARITY_PRET_CHECK_PATH_FIXTURE",
    "LIVE_PARITY_STATE_CREATING_PATH_CANARIES",
    "LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE",
    "LIVE_PARITY_SUBMIT_PATH_CANARY",
    "PDF_100_PATH_FIXTURE",
    "PDF_FORM_PATH_FIXTURE",
    "PDF_MODELO_130_2024_PATH_FIXTURE",
    "PORTAL_CENSO_NON_GCODE_PATH_CANARY",
    "PORTAL_LITERAL_SCAN_TOKENS",
    "PORTAL_NON_GCODE_PATH_CANARY",
    "PORTAL_RETIRED_PATH_CANARY",
    "PORTAL_RETIRED_WITH_NOTES_PATH_CANARY",
    "PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE",
    "REDACTION_INTERNAL_PATH_CANARY",
    "REDACTION_SECRET_WLPL_PATH_CANARY",
    "REMOTE_GUARD_LITERAL_SCAN_TOKENS",
    "STATIC_DESIGN_REGISTER_PATH_FIXTURE",
    "UNCLASSIFIED_MUTATING_READ_POST_PATH_CANARY",
    "UNCLASSIFIED_WWW2_READ_PATH_CANARY",
    "UNKNOWN_AEAT_STATE_SURFACE_URL_CANARY",
    "aeat_host",
    "aeat_url",
    "configured_path",
    "configured_template_path",
    "justificante_cotejo_url",
    "justificante_wlpl_cotejo_url",
    "manual_practicos_url",
    "portal_path",
    "sede_pdf_url",
]
