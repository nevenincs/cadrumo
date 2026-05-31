"""Read-only filing submission helpers.

AEAT remote submission and write-shaped portal walks are permanently
forbidden. This adapter package exposes only the export-boundary
preflight contracts and live-submit refusal error.

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.adapters.outbound.aeat.export` (the package root);
the underscored submodules are implementation detail.

Domain lifecycle types live in :mod:`aeat.domain.submission`.
"""

from __future__ import annotations

from ._errors import AeatExportFormatError, ExportError

__all__ = [
    "AeatExportFormatError",
    "ExportError",
]
