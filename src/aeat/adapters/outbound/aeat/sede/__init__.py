"""Read-only driver for the authenticated AEAT sede electrónica.

This subpackage models the authenticated AEAT surface through typed
read-only records, URL templates, selectors, and parser outputs.

Public API::

    from aeat.adapters.outbound.aeat.sede import (
        # Records
        Declaracion,
        Expediente,
        FiledDeclaracionArtefact,
        FiledDeclaracionObservation,
        JustificanteRef,
        NotificationsSnapshot,
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

from ._censo_live import (
    G313_LAUNCHER_URL,
    censo_fact_set_to_mapping,
    fetch_g313_censo,
)
from ._declarations import (
    Declaracion,
    DeclaracionesRegisterSession,
    capture_declaration,
    capture_filed_declaration_observation,
    capture_previous_filing_observations,
    capture_relation_source_observations,
    open_declarations_register,
    registry_observation_from_filed_declaration,
    resolve_previous_filing_bindings_from_filed_declarations,
    resolve_relation_values_from_filed_declarations,
    shared_playwright,
    walk_declarations_register,
)
from ._declarations_observations import observed_casillas_from_submitted_file
from ._errors import (
    ExpedienteNotFoundError,
    JustificanteFetchError,
    SedeError,
    SedeFailureMode,
    SedeNavigationError,
    SedeParseError,
)
from ._iva_compensation_wallet import (
    IVA_COMPENSATION_WALLET_URL,
    PRE303_PRESENTATION_SERVICE_URL,
    fetch_iva_compensation_wallet,
    parse_iva_compensation_wallet_html,
)
from ._notifications import (
    NotificationsSnapshot,
    RemoteNotification,
    fetch_notifications_query,
    fetch_notifications_summary,
    parse_notifications_query,
    parse_notifications_summary,
)
from ._observation_store import FiledDeclaracionObservationStore
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
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
    JustificanteRef,
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
    "G313_LAUNCHER_URL",
    "IVA_COMPENSATION_WALLET_URL",
    "PRE303_PRESENTATION_SERVICE_URL",
    "Declaracion",
    "DeclaracionesRegisterSession",
    "Expediente",
    "ExpedienteNotFoundError",
    "FiledDeclaracionArtefact",
    "FiledDeclaracionObservation",
    "FiledDeclaracionObservationStore",
    "IvaCompensationWalletObservation",
    "IvaCompensationWalletRow",
    "JustificanteFetchError",
    "JustificanteRef",
    "NotificationsSnapshot",
    "ObservedCasillaValue",
    "RemoteNotification",
    "RentaWebOpenSedeDriver",
    "SedeCapture",
    "SedeError",
    "SedeFailureMode",
    "SedeNavigationError",
    "SedeParseError",
    "capture_declaration",
    "capture_filed_declaration_observation",
    "capture_justificante",
    "capture_previous_filing_observations",
    "capture_relation_source_observations",
    "censo_fact_set_to_mapping",
    "collect_renta_web_open_observation",
    "extract_renta_web_open_summary_value",
    "fetch_g313_censo",
    "fetch_iva_compensation_wallet",
    "fetch_notifications_query",
    "fetch_notifications_summary",
    "find_expediente",
    "observed_casillas_from_submitted_file",
    "open_declarations_register",
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
