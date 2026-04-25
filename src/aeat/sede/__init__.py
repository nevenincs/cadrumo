"""Read-only driver for the authenticated AEAT sede electrónica (#239).

This subpackage models the real post-auth AEAT surface as observed
live on 2026-04-24 against Kent's production sede. Every record shape,
URL template, and selector is derived from captured ground truth —
there is no speculative scaffolding.

Public API:

    from aeat.sede import (
        Expediente,
        JustificanteRef,
        SedeCapture,
        SedeError,
        capture_justificante,
        find_expediente,
        resolve_justificante_ref,
        walk_expedientes_tree,
    )

The surface is structurally read-only (Layer 1 of the five-layer
write-guard): every boundary-crossing record carries ``mode:
Literal["read"]`` and no public method name mentions submission,
amendment, or any mutating verb in English or Spanish.

Navigation flow, captured live:

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
   the response in Chrome's PDF viewer stub.
"""

from __future__ import annotations

from ._declarations import Declaration, walk_declarations_register
from ._errors import (
    ExpedienteNotFoundError,
    JustificanteFetchError,
    SedeError,
    SedeNavigationError,
    SedeParseError,
)
from ._notifications import (
    NotificationsSnapshot,
    RemoteNotification,
    fetch_notifications_query,
    fetch_notifications_summary,
    parse_notifications_query,
    parse_notifications_summary,
)
from ._parse import parse_expediente_detail, parse_resumen_tree
from ._schema import Expediente, JustificanteRef, SedeCapture
from ._walker import (
    capture_justificante,
    find_expediente,
    resolve_justificante_ref,
    walk_expedientes_tree,
)

__all__ = [
    "Declaration",
    "Expediente",
    "ExpedienteNotFoundError",
    "JustificanteFetchError",
    "JustificanteRef",
    "NotificationsSnapshot",
    "RemoteNotification",
    "SedeCapture",
    "SedeError",
    "SedeNavigationError",
    "SedeParseError",
    "capture_justificante",
    "fetch_notifications_query",
    "fetch_notifications_summary",
    "find_expediente",
    "parse_expediente_detail",
    "parse_notifications_query",
    "parse_notifications_summary",
    "parse_resumen_tree",
    "resolve_justificante_ref",
    "walk_declarations_register",
    "walk_expedientes_tree",
]
