"""Errors raised by :func:`serialize_tabular_rows` and tabular export models.

:class:`ExportFormatError` rejects unsupported
:class:`ExportSerializationFormat` values, while :class:`ExportFieldError`
carries :class:`TabularExportResult` field and payload invariant failures
through the typed error registry.
"""

from __future__ import annotations

from ...core.errors import CoreError, CoreValidationError


class ExportFormatError(CoreError):
    """Raised when an unsupported export serialization format is requested.

    The tabular export pipeline is closed over the declared
    :class:`~aeat.application.export._tabular.ExportSerializationFormat`
    enum members.  Requesting any value outside that set violates the
    pipeline contract and is surfaced as this error rather than a bare
    :class:`ValueError`.
    """


class ExportFieldError(CoreValidationError):
    """Raised when a field validation invariant is violated during tabular export.

    Field-level invariants (non-empty names, no duplicates, no unknown
    keys) are enforced before serialization.  Each violation raises this
    error instead of a bare :class:`ValueError` so the failure propagates
    through the typed error registry and produces a structured envelope.
    """
