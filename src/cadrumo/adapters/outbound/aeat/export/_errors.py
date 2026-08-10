"""Exception types for AEAT outbound export-format adapters.

The classes here cover fichero-BOE serialisation and layout failures in
the outbound export adapter. They are separate from the local submission
lifecycle errors in :mod:`domain.submission` and from the permanent
live-write refusal raised by :mod:`core.access_gate`.
"""

from __future__ import annotations

from .....core.errors import CadrumoError


class ExportError(CadrumoError):
    """Base class for outbound AEAT export-format adapter errors.

    Catch this root for failures emitted by registry-backed fichero-BOE
    serialisation helpers. Submission lifecycle failures remain under
    :class:`~domain.submission.SubmissionError`.
    """


class AeatExportFormatError(ExportError, ValueError):
    """Raised when a filing draft cannot be serialised to a concrete BOE format.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators and other standard library consumers that expect
    value-related failures.

    See Also:
        :mod:`domain.calculations.registry`
            Canonical fixed-width semantics translated by outbound adapters.
        :class:`~domain.submission.SubmissionPreflightError`
            Domain-level refusal raised before a local submission
            lifecycle transition is allowed.
    """
