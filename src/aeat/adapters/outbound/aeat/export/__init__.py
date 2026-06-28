"""Public outbound export boundary for AEAT fichero-BOE helpers.

This package root is the supported adapter import point for errors raised
while serialising registry-backed filing layouts. It currently re-exports
:class:`AeatExportFormatError` and :class:`ExportError`; fixed-width
primitives and record layouts remain internal implementation details.

AEAT remote submission and write-shaped portal walks are permanently
forbidden. The local submission lifecycle is owned by
:mod:`aeat.domain.submission`, including
:class:`~aeat.domain.submission.SubmissionEngine`,
:class:`~aeat.domain.submission.Preflight`, and
:class:`~aeat.domain.submission.SubmissionPreflightError`. Any live-write
attempt is refused at the core access gate by
:class:`~aeat.core.access_gate.LiveSubmitForbiddenError`.

Public API discipline: callers outside this subpackage must import only
from :mod:`aeat.adapters.outbound.aeat.export` (the package root); the
underscored submodules are implementation detail.

See Also:
    :mod:`aeat.adapters.outbound.aeat.export._formats`
        Internal fixed-width fichero-BOE encoding primitives used by
        registry-backed export definitions.
    :mod:`aeat.domain.submission`
        Canonical local-only submission lifecycle and preflight engine.
    :mod:`aeat.core.access_gate`
        Core live-read gate and permanent live-write refusal policy.
"""

from __future__ import annotations

from ._errors import AeatExportFormatError, ExportError

__all__ = [
    "AeatExportFormatError",
    "ExportError",
]
