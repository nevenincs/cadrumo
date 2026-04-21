"""AEAT live status reader (#43, extended in #227).

Read-only driver that authenticates against AEAT *Sede Electrónica*,
navigates to the user's status pages, and returns strict pydantic v2
records for the rest of the project to consume.

Since #227, :class:`StatusReader` also exposes
``fetch_filing_detail(modelo, period)``, the load-bearing read
surface for retroactive amendments (closes Kent audit wall 23). The
reader structurally conforms to both :class:`ExpedienteSource` and
:class:`FilingDetailFetcher` Protocols declared in
:mod:`aeat.history._protocols`, so callers can plug the reader
straight into :class:`aeat.history.HistoryFetcher` without adapters.

Public API:

- :class:`StatusReader` — the async driver.
- Record types: :class:`Expediente`, :class:`Notificacion`,
  :class:`Devolucion`, :class:`BorradorIrpf`, :class:`DatosFiscales`,
  :class:`Payor`, :class:`CalendarioEntry`.
- Enums: :class:`AeatStatusKind`, :class:`PayorKind`.
- Errors: :class:`StatusReaderError`, :class:`StatusAuthError`,
  :class:`StatusParseError`, :class:`StatusNotFoundError`.
- Protocol stub: :class:`CertificateBackend`.
- Cache: :class:`StatusCache`.

Callers outside this subpackage MUST import from ``aeat.status``
only — the leading-underscore modules are internal and may change
without notice.
"""

from __future__ import annotations

from ._cache import StatusCache
from ._errors import (
    StatusAuthError,
    StatusNotFoundError,
    StatusParseError,
    StatusReaderError,
)
from ._models import (
    AeatStatusKind,
    BorradorIrpf,
    CalendarioEntry,
    DatosFiscales,
    Devolucion,
    Expediente,
    Notificacion,
    Payor,
    PayorKind,
)
from ._protocols import BrowserSessionLike, CertificateBackend
from ._reader import StatusReader
from ._site_health import (
    SiteHealthAlert,
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from ._site_health_parsers import (
    evaluate_response,
    parse_mantenimiento_banner,
    parse_rate_limit_response,
    parse_waf_challenge,
)

# NOTE: ``SiteHealthAlert.stage`` is a forward reference to
# ``aeat.workflow.WorkflowStage``. Callers who need to instantiate
# ``SiteHealthAlert`` must import ``aeat.workflow`` at least once
# first; that import rebuilds the model in
# ``aeat.workflow.__init__``. The cycle cannot be broken eagerly
# here without re-introducing a partial-import ImportError.


__all__ = [
    "AeatStatusKind",
    "BorradorIrpf",
    "BrowserSessionLike",
    "CalendarioEntry",
    "CertificateBackend",
    "DatosFiscales",
    "Devolucion",
    "Expediente",
    "Notificacion",
    "Payor",
    "PayorKind",
    "SiteHealthAlert",
    "SiteHealthEvidence",
    "SiteHealthState",
    "SiteHealthStatus",
    "StatusAuthError",
    "StatusCache",
    "StatusNotFoundError",
    "StatusParseError",
    "StatusReader",
    "StatusReaderError",
    "evaluate_response",
    "parse_mantenimiento_banner",
    "parse_rate_limit_response",
    "parse_waf_challenge",
]
