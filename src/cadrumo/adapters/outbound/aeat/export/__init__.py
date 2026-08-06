"""Public outbound export boundary for AEAT fichero-BOE helpers.

This package root is the supported adapter import point for errors raised
while serialising registry-backed filing layouts, plus the fixed-width
record-encoding primitives a cross-package caller needs to render a
non-registry-driven fichero-BOE record body (the Modelo 145 local
communication record is the one such caller today).

AEAT remote submission and write-shaped portal walks are permanently
forbidden. The local submission lifecycle is owned by
:mod:`domain.submission`, including
:class:`domain.submission.SubmissionEngine`,
:class:`domain.submission.Preflight`, and
:class:`domain.submission.SubmissionPreflightError`. Any live-write
attempt is refused at the core access gate by
:class:`core.access_gate.LiveSubmitForbiddenError`.

Public API discipline: callers outside this subpackage must import only
from :mod:`adapters.outbound.aeat.export` (the package root); the
underscored submodules, including :mod:`._formats`, are implementation
detail.

See Also:
    :mod:`adapters.outbound.aeat.export._formats`
        Internal fixed-width fichero-BOE encoding primitives, re-exported
        here for cross-package callers.
    :mod:`domain.submission`
        Canonical local-only submission lifecycle and preflight engine.
    :mod:`core.access_gate`
        Core live-read gate and permanent live-write refusal policy.
"""

from __future__ import annotations

from ._errors import AeatExportFormatError, ExportError
from ._formats import (
    FicheroBoeEncoding,
    FieldKind,
    Justification,
    RecordFieldSpec,
    SignedMode,
    record_field,
    render_record_body,
)
from ._registry_record_renderer import RegistryFixedWidthRecordRenderer

__all__ = [
    "AeatExportFormatError",
    "ExportError",
    "FicheroBoeEncoding",
    "FieldKind",
    "Justification",
    "RecordFieldSpec",
    "RegistryFixedWidthRecordRenderer",
    "SignedMode",
    "record_field",
    "render_record_body",
]
