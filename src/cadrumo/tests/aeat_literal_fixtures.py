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

# ── Sede/www6 URLs test modules previously owned inline ──────────────────────
#
# Assembled from ``_AEAT.domains`` rather than spelled out, so a domain change
# moves them with the constants instead of leaving nine test modules pinned to
# a host the product no longer uses.
SEDE_ROOT_URL_FIXTURE = f"{_AEAT.domains.sede}/"
IVA_WALLET_SOURCE_URL_FIXTURE = f"{_AEAT.domains.sede}/wallet"
COTEJO_VERIFICATION_URL_FIXTURE = f"{_AEAT.domains.sede}/cotejo/A1B2C3D4E5F6G7H8"
#: Base of the published Diseno de Registro tree. Catalogue tests assert the
#: DOCUMENT route AEAT records for a design, so only the tail belongs to them;
#: the host and the static_files/Sede prefix move with the constants here.
RECORD_DESIGN_ROUTE_BASE_FIXTURE = f"{_AEAT.domains.sede}/static_files/Sede/Disenyo_registro"
NOTIFICATION_DETALLE_SEDE_PATH_FIXTURE = "/wlpl/GNNO-JDIT/DetalleSede"
#: Notification paths the same-host guard must REFUSE: a comparecencia surface
#: that is mutation-shaped, and an acknowledge surface reached by redirect.
#: Both are canaries -- the guard proving it rejects them is the whole point.
NOTIFICATION_COMPARECER_PATH_CANARY = "/wlpl/GNNO-JDIT/comparecer"
NOTIFICATION_ACKNOWLEDGE_PATH_CANARY = "/wlpl/GNNO-JDIT/acknowledge"
NOTIFICATION_DETALLE_SEDE_URL_FIXTURE = f"{_AEAT.domains.www6}{NOTIFICATION_DETALLE_SEDE_PATH_FIXTURE}"

#: Redaction canaries: a Sede URL carrying a secret in its query string, which
#: the envelope funnel must strip. The secret is the point, so these stay
#: whole-URL rather than being assembled at each call site.
REDACTION_SESSION_QUERY_URL_CANARY = f"{_AEAT.domains.sede}/path?session=secret"
REDACTION_TOKEN_QUERY_URL_CANARY = f"{_AEAT.domains.sede}/private?token=correct-horse"

AEAT_LEGACY_APEX_CANARY = "aeat.es"
AEAT_LEGACY_SEDE_CANARY = f"sede.{AEAT_LEGACY_APEX_CANARY}"
CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED = _AEAT.clave_movil.obtener_clave_movil_browser_global
UNKNOWN_AEAT_SUBDOMAIN_CANARY = f"www9.{_AEAT.domains.host_suffix}"
#: A host ENDING in the AEAT apex as a substring rather than as a domain
#: suffix. Any guard that admits it is doing a substring match where it meant
#: a suffix match, which an attacker-registered domain satisfies trivially.
AEAT_SUFFIX_LOOKALIKE_HOST_CANARY = f"{_AEAT.domains.host_suffix}.evil.test"
UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY = "/wlpl/unsafe-state-surface"
UNKNOWN_AEAT_STATE_SURFACE_URL_CANARY = (
    f"https://{UNKNOWN_AEAT_SUBDOMAIN_CANARY}{UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY}"
)
PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE = "/Sede/procedimientoini/"
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
# Real AEAT write surfaces independently corroborating a specific
# AEAT_WRITE_FORBIDDEN_VERB_TOKENS entry, beyond the TGVI/PRET family above.
# Each path is a genuine AEAT-published surface, not a synthetic canary shape:
# ``RealizarPresentacionLotes`` is the batch-presentation endpoint named while
# closing a write-verb substring-match gap in the adjacent-domain dedup pass;
# the cancellation path is this project's own deployed Clave Movil
# configuration (``core/external_constants.toml``); the payment path is quoted
# verbatim from the bundled AEAT Manual Practico de Sociedades 2024 PDF. Most
# tokens in AEAT_WRITE_FORBIDDEN_VERB_TOKENS have NO comparable witness today.
WRITE_VERB_WITNESS_PRESENTACION_PATH_CANARY = "/wlpl/OVPT-NTGV/RealizarPresentacionLotes"
WRITE_VERB_WITNESS_CANCELAR_PATH_CANARY = _AEAT.clave_movil.cancelar_clave_movil_path
WRITE_VERB_WITNESS_PAGAR_PATH_CANARY = (
    "/Sede/deudas-apremios-embargos-subastas/pagar-aplazar-consultar/pagos-transferencias-especial-extranjero.html"
)
AEAT_WRITE_VERB_TOKEN_WITNESS_PATH_CANARIES = (
    WRITE_VERB_WITNESS_PRESENTACION_PATH_CANARY,
    WRITE_VERB_WITNESS_CANCELAR_PATH_CANARY,
    WRITE_VERB_WITNESS_PAGAR_PATH_CANARY,
)
# The censal consulta page reaches these three write surfaces through its own
# buttons and links. They are declared here so the censal reader's no-write
# proof can assert the landing guard refuses the paths that genuinely exist.
# None of them contains the token ``MOD036``, which is why the guard keys on
# the landing path instead.
CENSAL_MODIF_DOMICILIO_FISCAL_PATH_CANARY = "/wlpl/BUGC-JDIT/ModifDomiDual"
CENSAL_MODIF_DOMICILIO_NOTIF_PATH_CANARY = "/wlpl/BUGC-JDIT/ModifDomiNotif"
CENSAL_M036_FILING_TOOL_PATH_CANARY = "/wlpl/BU36-ASIS/M036/index.zul"
CENSAL_WRITE_SURFACE_PATH_CANARIES = (
    CENSAL_MODIF_DOMICILIO_FISCAL_PATH_CANARY,
    CENSAL_MODIF_DOMICILIO_NOTIF_PATH_CANARY,
    CENSAL_M036_FILING_TOOL_PATH_CANARY,
)
# The debts-consulta landing shapes the deudas read guard must refuse.
#
# These are SHAPED, not observed: each stands for a KIND of landing rather than
# a path anyone captured. They are declared here so the guard's proof can name
# the landings that would cost a taxpayer money without any test module owning
# an AEAT route literal of its own.
#
# They keep their job now that the real consulta HAS been observed (see the
# ``*_OBSERVED_PATH_FIXTURE`` values below). The allow-list carries exactly one
# endpoint, so every shape here is a route the guard must still refuse, and the
# read-shaped pair is the sharper case: a plausible consulta path that is not
# THE consulta path must not be admitted by a loose prefix match.
#
# The canonical write-verb token scan catches literal "pagar", so the first two
# payment shapes would be refused by policy alone -- but "PagoParcial",
# "SolicitarAplazamiento" and "AplazamientoFraccionamiento" carry no token the
# scan knows, and the allow-list is the only thing that refuses them.
DEUDAS_CONSULTA_PATH_SHAPE_CANARY = "/wlpl/DEUD-DEUD/ConsultarDeudas"
DEUDAS_DETALLE_PATH_SHAPE_CANARY = "/wlpl/DEUD-DEUD/DetalleDeuda"
DEUDAS_PAGAR_TODAS_PATH_SHAPE_CANARY = "/wlpl/DEUD-DEUD/PagarTodasDeudas"
DEUDAS_PAGAR_ALGUNAS_PATH_SHAPE_CANARY = "/wlpl/DEUD-DEUD/PagarAlgunasDeudas"
DEUDAS_PAGO_PARCIAL_PATH_SHAPE_CANARY = "/wlpl/DEUD-DEUD/PagoParcial"
DEUDAS_APLAZAMIENTO_PATH_SHAPE_CANARY = "/wlpl/RECA-JDIT/SolicitarAplazamiento"
DEUDAS_FRACCIONAMIENTO_PATH_SHAPE_CANARY = "/wlpl/RECA-JDIT/AplazamientoFraccionamiento"
DEUDAS_PAYMENT_SURFACE_PATH_SHAPE_CANARIES = (
    DEUDAS_PAGAR_TODAS_PATH_SHAPE_CANARY,
    DEUDAS_PAGAR_ALGUNAS_PATH_SHAPE_CANARY,
    DEUDAS_PAGO_PARCIAL_PATH_SHAPE_CANARY,
    DEUDAS_APLAZAMIENTO_PATH_SHAPE_CANARY,
    DEUDAS_FRACCIONAMIENTO_PATH_SHAPE_CANARY,
)
DEUDAS_READ_SURFACE_PATH_SHAPE_CANARIES = (
    DEUDAS_CONSULTA_PATH_SHAPE_CANARY,
    DEUDAS_DETALLE_PATH_SHAPE_CANARY,
)
DEUDAS_OFF_HOST_LANDING_CANARY = "https://deudas-lookalike.example.com/ConsultarDeudas"
#: The consulta endpoint OBSERVED on the live sede under an authenticated
#: session, as distinct from the invented ``*_SHAPE_CANARY`` paths above, which
#: stay plausible-but-wrong routes the guard must keep refusing.
DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE = "/wlpl/SRVO-JDIT/ConsultaDdas"
#: *Pagar todas mis deudas*, observed on the SAME ``/wlpl/SRVO-JDIT/``
#: application as the consulta. The single most important refusal case on this
#: surface: an allow-list written against the shared application prefix rather
#: than the consulta endpoint would admit it.
DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE = "/wlpl/SRVO-JDIT/PagarTodas"
#: Payment and aplazamiento launchers observed beside the consulta. AEAT serves
#: these from three different numbered hosts; the paths are what the guard sees.
DEUDAS_OBSERVED_PAYMENT_SURFACE_PATH_FIXTURES = (
    DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE,
    "/wlpl/OVPP-PAGO/LiquidacionesTPV",
    "/wlpl/OVPP-PAGO/LiquidacionesCuenta",
    "/wlpl/OVCT-CXEW/DialogoRepresentacion",
)
ACCESO_DR_DETAIL_PATH_FIXTURE = "/wlpl/DASR-CORE/AccesoDR2023RVlt"
KATA_COTEJO_ID_PATH_FIXTURE = "/wlpl/KATA-APLI/cotejo/CotejoIdSv"
KATA_COTEJO_DOC_ID_PATH_FIXTURE = "/wlpl/KATA-APLI/cotejo/CotejoDocIdSv"
AEAT_HOST_WITH_USERINFO_AUTHORITY_CANARY = "ignored@sede.agenciatributaria.gob.es"
AEAT_HOST_WITH_PORT_AUTHORITY_CANARY = "sede.agenciatributaria.gob.es:443"
AEAT_HOST_WITH_INVALID_PORT_AUTHORITY_CANARY = "sede.agenciatributaria.gob.es:not-a-port"
AEAT_NON_HOST_AUTHORITY_CANARIES = (
    AEAT_HOST_WITH_USERINFO_AUTHORITY_CANARY,
    AEAT_HOST_WITH_PORT_AUTHORITY_CANARY,
    AEAT_HOST_WITH_INVALID_PORT_AUTHORITY_CANARY,
)
#: A host trailing the real AEAT apex as a substring rather than a suffix, in
#: the opposite arrangement from ``AEAT_SUFFIX_LOOKALIKE_HOST_CANARY`` above
#: (apex-then-lookalike-tail rather than lookalike-then-apex-tail).
AEAT_APEX_EVIL_SUFFIX_URL_CANARY = "https://agenciatributaria.gob.es.evil.test/phish"
#: A host merely prefixed onto the real AEAT apex, no dot boundary.
AEAT_APEX_NOT_PREFIX_URL_CANARY = "https://not-agenciatributaria.gob.es/x"
AEAT_NONCANONICAL_HTTP_MANUAL_URL_CANARY = "http://sede.agenciatributaria.gob.es/manual.pdf"
CITATION_MANUAL_PDF_URL_FIXTURE = "https://sede.agenciatributaria.gob.es/manual.pdf"
#: A host merely ENDING in the official apex as a substring, used to prove a
#: category-citation origin check anchors suffix matching on a dot boundary.
CITATION_SEDE_LOOKALIKE_HOST_URL_CANARY = "https://evil-agenciatributaria.gob.es/a"
CITATION_SEDE_HTTP_DOWNGRADE_URL_CANARY = "http://sede.agenciatributaria.gob.es/a"
CITATION_SEDE_AYUDA_URL_FIXTURE = "https://sede.agenciatributaria.gob.es/Sede/ayuda.html"
CITATION_APEX_URL_FIXTURE = "https://agenciatributaria.gob.es/apex"
CITATION_SEDE_BARE_HOST_FIXTURE = "sede.agenciatributaria.gob.es"
JUSTIFICANTE_FILING_TARGET_VERIFY_URL_FIXTURE = "https://www.agenciatributaria.gob.es/verify"
BORRADOR_PAYLOAD_WWW2_ORIGIN_FIXTURE = "https://www2.agenciatributaria.gob.es/"
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
LANDED_ORIGIN_CARTERA_CUOTAS_PATH_FIXTURE = "/wlpl/DAI3-RUTI/CarteraCuotas"
RENTA_REGIMEN_CITATION_URL_FIXTURE = "https://sede.agenciatributaria.gob.es/regimen"
RENTA_DEDUCIBILIDAD_CITATION_URL_FIXTURE = "https://sede.agenciatributaria.gob.es/renta"
AUTH_DIAGNOSTIC_SEDE_URL_FIXTURE = "sede.agenciatributaria.gob.es/auth"
#: Sibling-application-path comparison canaries for
#: ``_same_aeat_application_path`` (the ``wlpl``/``inwinvoc`` root pairing
#: shape, not a specific captured AEAT landing).
INWINVOC_LANDING_PATH_CANARY = "/wlpl/inwinvoc/es.aeat.dit.adu.eeca.catalogo.vis.VisorCatalogo"
INWINVOC_SIBLING_PATH_CANARY = "/wlpl/inwinvoc/other/page"
OTHERAPP_LANDING_PATH_CANARY = "/wlpl/otherapp/page"
INWINVOC_TARGET_PATH_CANARY = "/wlpl/inwinvoc/page"
WLPL_INWINVOC_TWO_SEGMENT_PATH_CANARY = "/wlpl/inwinvoc"
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
    if not isinstance(value, str):
        raise AssertionError(f"configured AEAT origin {origin!r} is not a string")
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
    "ACCESO_DR_DETAIL_PATH_FIXTURE",
    "AEAT_APEX_EVIL_SUFFIX_URL_CANARY",
    "AEAT_APEX_NOT_PREFIX_URL_CANARY",
    "AEAT_HOST_SUFFIX_EXPECTED",
    "AEAT_HOST_WITH_INVALID_PORT_AUTHORITY_CANARY",
    "AEAT_HOST_WITH_PORT_AUTHORITY_CANARY",
    "AEAT_HOST_WITH_USERINFO_AUTHORITY_CANARY",
    "AEAT_LEGACY_APEX_CANARY",
    "AEAT_LEGACY_SEDE_CANARY",
    "AEAT_LITERAL_SCAN_TOKENS",
    "AEAT_NONCANONICAL_HTTP_MANUAL_URL_CANARY",
    "AEAT_NON_HOST_AUTHORITY_CANARIES",
    "AEAT_WRITE_VERB_TOKEN_WITNESS_PATH_CANARIES",
    "AUTH_DIAGNOSTIC_PATH_FIXTURE",
    "BORRADOR_PAYLOAD_WWW2_ORIGIN_FIXTURE",
    "BORRADOR_STORAGE_PATH_FIXTURE",
    "CENSAL_M036_FILING_TOOL_PATH_CANARY",
    "CENSAL_MODIF_DOMICILIO_FISCAL_PATH_CANARY",
    "CENSAL_MODIF_DOMICILIO_NOTIF_PATH_CANARY",
    "CENSAL_WRITE_SURFACE_PATH_CANARIES",
    "CITATION_APEX_URL_FIXTURE",
    "CITATION_MANUAL_PDF_URL_FIXTURE",
    "CITATION_SEDE_AYUDA_URL_FIXTURE",
    "CITATION_SEDE_BARE_HOST_FIXTURE",
    "CITATION_SEDE_HTTP_DOWNGRADE_URL_CANARY",
    "CITATION_SEDE_LOOKALIKE_HOST_URL_CANARY",
    "CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED",
    "DEUDAS_APLAZAMIENTO_PATH_SHAPE_CANARY",
    "DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE",
    "DEUDAS_CONSULTA_PATH_SHAPE_CANARY",
    "DEUDAS_DETALLE_PATH_SHAPE_CANARY",
    "DEUDAS_FRACCIONAMIENTO_PATH_SHAPE_CANARY",
    "DEUDAS_OBSERVED_PAYMENT_SURFACE_PATH_FIXTURES",
    "DEUDAS_OFF_HOST_LANDING_CANARY",
    "DEUDAS_PAGAR_ALGUNAS_PATH_SHAPE_CANARY",
    "DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE",
    "DEUDAS_PAGAR_TODAS_PATH_SHAPE_CANARY",
    "DEUDAS_PAGO_PARCIAL_PATH_SHAPE_CANARY",
    "DEUDAS_PAYMENT_SURFACE_PATH_SHAPE_CANARIES",
    "DEUDAS_READ_SURFACE_PATH_SHAPE_CANARIES",
    "FILED_ARTEFACT_PATH_FIXTURE",
    "INWINVOC_LANDING_PATH_CANARY",
    "INWINVOC_SIBLING_PATH_CANARY",
    "INWINVOC_TARGET_PATH_CANARY",
    "JUSTIFICANTE_AYUDA_PATH_FIXTURE",
    "JUSTIFICANTE_COTEJO_PATH_PREFIX_FIXTURE",
    "JUSTIFICANTE_FILING_TARGET_VERIFY_URL_FIXTURE",
    "JUSTIFICANTE_VERIFY_PATH_FIXTURE",
    "JUSTIFICANTE_WLPL_COTEJO_PATH_PREFIX_FIXTURE",
    "KATA_COTEJO_DOC_ID_PATH_FIXTURE",
    "KATA_COTEJO_ID_PATH_FIXTURE",
    "LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE",
    "LIVE_PARITY_PRET_CHECK_PATH_FIXTURE",
    "LIVE_PARITY_STATE_CREATING_PATH_CANARIES",
    "LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE",
    "LIVE_PARITY_SUBMIT_PATH_CANARY",
    "OTHERAPP_LANDING_PATH_CANARY",
    "PDF_100_PATH_FIXTURE",
    "PDF_FORM_PATH_FIXTURE",
    "PDF_MODELO_130_2024_PATH_FIXTURE",
    "PORTAL_CENSO_NON_GCODE_PATH_CANARY",
    "PORTAL_LITERAL_SCAN_TOKENS",
    "PORTAL_NON_GCODE_PATH_CANARY",
    "PORTAL_RETIRED_PATH_CANARY",
    "PORTAL_RETIRED_WITH_NOTES_PATH_CANARY",
    "PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE",
    "PUBLIC_OPEN_SIMULATOR_PATH_FIXTURE",
    "RECORD_DESIGN_ROUTE_BASE_FIXTURE",
    "REDACTION_INTERNAL_PATH_CANARY",
    "REDACTION_SECRET_WLPL_PATH_CANARY",
    "REMOTE_GUARD_LITERAL_SCAN_TOKENS",
    "STATIC_DESIGN_REGISTER_PATH_FIXTURE",
    "UNCLASSIFIED_MUTATING_READ_POST_PATH_CANARY",
    "UNCLASSIFIED_WWW2_READ_PATH_CANARY",
    "UNKNOWN_AEAT_STATE_SURFACE_URL_CANARY",
    "WLPL_INWINVOC_TWO_SEGMENT_PATH_CANARY",
    "WRITE_VERB_WITNESS_CANCELAR_PATH_CANARY",
    "WRITE_VERB_WITNESS_PAGAR_PATH_CANARY",
    "WRITE_VERB_WITNESS_PRESENTACION_PATH_CANARY",
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
