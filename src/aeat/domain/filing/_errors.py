"""Domain errors for the :mod:`aeat.domain.filing` subpackage.

Every exception inherits from :class:`aeat.core.errors.AeatError` so
callers can catch the project-wide base.
"""

from __future__ import annotations

from ...core.errors import AeatError, CoreValidationError


class ModeloDraftError(AeatError):
    """Base class for every error raised inside :mod:`aeat.domain.filing`."""


class ModeloBuilderError(ModeloDraftError):
    """Raised when builder selection or execution fails."""


class FilingValidationError(ModeloDraftError, CoreValidationError):
    """Raised when validation surfaces a blocking finding.

    The validator itself never raises; this error is reserved for
    callers that opt into ``fail_on_warning`` and want a hard fail.
    """


class ModeloComputationError(ModeloDraftError):
    """Raised when a builder cannot evaluate a formula casilla."""


class ModeloAmendmentError(ModeloDraftError):
    """Base class for every amendment-related filing error."""


class ModeloAmendmentValidationError(ModeloAmendmentError):
    """Raised when an amendment violates legal or shape invariants."""


class ModeloImportError(ModeloDraftError):
    """Raised when importing a filing from a justificante PDF fails."""


class FilingExportError(ModeloDraftError):
    """Raised when exporting a draft to an AEAT wire format fails."""


class FilingExportValidationError(FilingExportError, ValueError):
    """Raised on invalid export field values or layouts. Inherits from ValueError for Pydantic."""
