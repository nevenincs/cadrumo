"""AEAT live status reader (#43).

Read-only driver that authenticates against AEAT *Sede Electrónica*,
navigates to the user's status pages, and returns strict pydantic v2
records for the rest of the project to consume.

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
    "StatusAuthError",
    "StatusCache",
    "StatusNotFoundError",
    "StatusParseError",
    "StatusReader",
    "StatusReaderError",
]
