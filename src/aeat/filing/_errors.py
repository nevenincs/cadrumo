"""Domain errors for the :mod:`aeat.filing` subpackage.

Every exception inherits from :class:`aeat.errors.AeatError` so
callers can catch the project-wide base.
"""

from __future__ import annotations

from ..errors import AeatError


class FilingDraftError(AeatError):
    """Base class for every error raised inside :mod:`aeat.filing`."""


class FilingBuilderError(FilingDraftError):
    """Raised when builder selection or execution fails."""


class FilingValidationError(FilingDraftError):
    """Raised when validation surfaces a blocking finding.

    The validator itself never raises; this error is reserved for
    callers that opt into ``fail_on_warning`` and want a hard fail.
    """


class FilingComputationError(FilingDraftError):
    """Raised when a builder cannot evaluate a formula casilla."""


class FilingAmendmentError(FilingDraftError):
    """Base class for every amendment-related filing error."""


class FilingAmendmentValidationError(FilingAmendmentError):
    """Raised when an amendment violates legal or shape invariants."""
