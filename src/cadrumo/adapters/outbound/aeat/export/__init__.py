"""Public outbound boundary for registry-backed AEAT fichero-BOE rendering.

AEAT remote submission and write-shaped portal walks are permanently
forbidden. The local submission lifecycle is owned by
:mod:`domain.submission`, including
:class:`domain.submission.SubmissionEngine`,
:class:`domain.submission.Preflight`, and
:class:`domain.submission.SubmissionPreflightError`. Any live-write
attempt is refused at the core access gate by
:class:`core.access_gate.LiveSubmitForbiddenError`.

Public API discipline: callers outside this subpackage import the renderer
and translated adapter errors from this package root. Fixed-width value
semantics are owned by :mod:`domain.calculations.registry`.

See Also:
    :mod:`domain.submission`
        Canonical local-only submission lifecycle and preflight engine.
    :mod:`core.access_gate`
        Core live-read gate and permanent live-write refusal policy.
"""

from __future__ import annotations

from ._registry_record_renderer import RegistryFixedWidthRecordRenderer
from .errors import AeatExportFormatError, ExportError

__all__ = [
    "AeatExportFormatError",
    "ExportError",
    "RegistryFixedWidthRecordRenderer",
]
