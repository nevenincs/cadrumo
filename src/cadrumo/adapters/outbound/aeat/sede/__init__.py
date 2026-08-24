"""Read-only driver for the authenticated AEAT sede electrónica.

This subpackage models the authenticated AEAT surface through typed
read-only records, URL templates, selectors, and parser outputs.

Public API::

    from cadrumo.adapters.outbound.aeat.sede import (
        # Records
        Declaracion,
        Expediente,
        FiledDeclaracionArtefact,
        FiledDeclaracionObservation,
        JustificanteRef,
        NotificationsSnapshot,
        ObservedCasillaSkip,
        ObservedCasillaValue,
        RemoteNotification,
        SedeCapture,
        # Errors
        ExpedienteNotFoundError,
        JustificanteFetchError,
        SedeError,
        SedeNavigationError,
        SedeParseError,
        # Declaraciones-presentadas register surface
        capture_declaration,
        capture_filed_declaration_observation,
        walk_declarations_register,
        # Mis Expedientes (procedure-tree) surface
        capture_justificante,
        find_expediente,
        resolve_justificante_ref,
        walk_expedientes_tree,
        # Notifications / Comunicaciones surface
        assert_notification_content_readable,
        fetch_notification_document,
        fetch_notifications_query,
        fetch_notifications_summary,
        # Parsers (offline-testable)
        parse_expediente_detail,
        parse_notifications_query,
        parse_notifications_summary,
        parse_resumen_tree,
    )

The surface is structurally read-only: every boundary-crossing record
carries ``mode: Literal["read"]`` and public operations are limited to
navigation, download, parsing, and observation.

Navigation flow:

1. ``page.goto("/wlpl/TEWV-CORE/ResumenVlt")`` — Mis Expedientes
   renders a category tree (AEAT procedure categories, not modelo
   codes). Expedientes live at the leaves.
2. Tree nodes lazy-load on click of ``javascript:mostrarListado(...)``
   onclick handlers. Expanded leaves expose an ``<a>`` whose text is
   the expediente id and whose ``href`` is the per-filing-family
   endpoint (for IRPF: ``/wlpl/DASR-CORE/AccesoDR<YYYY>RVlt?exp=<id>``).
3. On the expediente detail page, the authoritative justificante
   (a PDF signed by AEAT) is reachable through the
   *Grabación de la declaración — Consulta / Copia* link at
   ``/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV=<csv>``.
4. The raw PDF body is served at
   ``/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=<csv>`` and must be
   fetched via :class:`APIRequestContext` — browser ``goto`` wraps
   the response in Chrome's PDF viewer shell.
"""

from __future__ import annotations

from ._censal_datos import (
    censal_datos_url,
    fetch_censal_datos,
    forbidden_censal_landing_marker,
    is_forbidden_censal_landing,
    parse_censal_datos,
)
from ._declarations import (
    DeclaracionesRegisterSession,
    capture_declaration,
    capture_filed_declaration_observation,
    capture_previous_filing_observations,
    capture_relation_source_observations,
    discover_filed_declaration_availability,
    open_declarations_register,
    shared_playwright,
    walk_declarations_register,
)
from ._declarations_observations import (
    non_numeric_observed_casillas,
    observed_casillas_from_submitted_file,
    registry_observation_from_filed_declaration,
    resolve_previous_filing_bindings_from_filed_declarations,
    resolve_relation_values_from_filed_declarations,
)
from ._declarations_remote import extract_csv_from_url
from ._declarations_schema import Declaracion
from ._deudas import (
    DEUDAS_READ_SURFACE,
    Deuda,
    assert_deudas_landing,
    deudas_read_path_prefixes,
)
from ._errors import (
    BrowserAdapterTypeError,
    ExpedienteNotFoundError,
    JustificanteFetchError,
    SedeError,
    SedeFailureMode,
    SedeNavigationError,
    SedeParseError,
)
from ._groi_check import GroiSedeDriver
from ._iva_compensation_wallet import (
    IVA_COMPENSATION_WALLET_URL,
    PRE303_PRESENTATION_SERVICE_URL,
    fetch_iva_compensation_wallet,
    parse_iva_compensation_wallet_html,
)
from ._nif_iva_check import NifIvaCheckSedeDriver
from ._notifications import (
    NotificationDocument,
    NotificationsSnapshot,
    RemoteNotification,
    assert_notification_content_readable,
    fetch_notification_document,
    fetch_notifications_query,
    fetch_notifications_summary,
    parse_notifications_query,
    parse_notifications_summary,
)
from ._observation_store import (
    FiledDeclaracionObservationStore,
    filed_declaracion_observation_object_key,
    iva_compensation_wallet_observation_object_key,
)
from ._parse import parse_expediente_detail, parse_resumen_tree
from ._renta_web_open import (
    RentaWebOpenSedeDriver,
    collect_renta_web_open_observation,
    extract_renta_web_open_summary_value,
)
from ._schema import (
    Expediente,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclarationAvailability,
    FiledDeclarationAvailabilityReport,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
    JustificanteRef,
    ObservedCasillaSkip,
    ObservedCasillaValue,
    SedeCapture,
)
from ._walker import (
    capture_justificante,
    find_expediente,
    resolve_justificante_ref,
    walk_expedientes_tree,
)

__all__ = [
    "DEUDAS_READ_SURFACE",
    "IVA_COMPENSATION_WALLET_URL",
    "PRE303_PRESENTATION_SERVICE_URL",
    "BrowserAdapterTypeError",
    "Declaracion",
    "DeclaracionesRegisterSession",
    "Deuda",
    "Expediente",
    "ExpedienteNotFoundError",
    "FiledDeclaracionArtefact",
    "FiledDeclaracionObservation",
    "FiledDeclaracionObservationStore",
    "FiledDeclarationAvailability",
    "FiledDeclarationAvailabilityReport",
    "GroiSedeDriver",
    "IvaCompensationWalletObservation",
    "IvaCompensationWalletRow",
    "JustificanteFetchError",
    "JustificanteRef",
    "NifIvaCheckSedeDriver",
    "NotificationDocument",
    "NotificationsSnapshot",
    "ObservedCasillaSkip",
    "ObservedCasillaValue",
    "RemoteNotification",
    "RentaWebOpenSedeDriver",
    "SedeCapture",
    "SedeError",
    "SedeFailureMode",
    "SedeNavigationError",
    "SedeParseError",
    "assert_deudas_landing",
    "assert_notification_content_readable",
    "capture_declaration",
    "capture_filed_declaration_observation",
    "capture_justificante",
    "capture_previous_filing_observations",
    "capture_relation_source_observations",
    "censal_datos_url",
    "collect_renta_web_open_observation",
    "deudas_read_path_prefixes",
    "discover_filed_declaration_availability",
    "extract_csv_from_url",
    "extract_renta_web_open_summary_value",
    "fetch_censal_datos",
    "fetch_iva_compensation_wallet",
    "fetch_notification_document",
    "fetch_notifications_query",
    "fetch_notifications_summary",
    "filed_declaracion_observation_object_key",
    "find_expediente",
    "forbidden_censal_landing_marker",
    "is_forbidden_censal_landing",
    "iva_compensation_wallet_observation_object_key",
    "non_numeric_observed_casillas",
    "observed_casillas_from_submitted_file",
    "open_declarations_register",
    "parse_censal_datos",
    "parse_expediente_detail",
    "parse_iva_compensation_wallet_html",
    "parse_notifications_query",
    "parse_notifications_summary",
    "parse_resumen_tree",
    "registry_observation_from_filed_declaration",
    "resolve_justificante_ref",
    "resolve_previous_filing_bindings_from_filed_declarations",
    "resolve_relation_values_from_filed_declarations",
    "shared_playwright",
    "walk_declarations_register",
    "walk_expedientes_tree",
]
