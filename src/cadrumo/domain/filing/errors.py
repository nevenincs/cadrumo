"""Domain errors for the :mod:`domain.filing` subpackage.

Every exception inherits from :class:`~core.errors.CadrumoError` so
callers can catch the project-wide base.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError, CoreValidationError


class ModeloDraftError(CadrumoError):
    """Base class for every error raised inside :mod:`domain.filing`."""


class ModeloBuilderError(ModeloDraftError):
    """Raised when builder selection or execution fails."""


class FilingValidationError(ModeloDraftError, CoreValidationError):
    """Raised when a filing record is invalid.

    Two distinct callers raise it. :class:`ModeloValidator` never raises on its
    own — findings are returned — so this error is what a caller opting into
    ``fail_on_warning`` gets for a blocking finding on an otherwise well-formed
    draft. The schema models also raise it from their cross-field validators for
    a record that is structurally malformed: a provenance kind contradicting its
    own value, an identity that is not its own content address, or two identity
    axes naming different taxpayers. Inheriting :class:`ValueError` (via
    :class:`~core.errors.CoreValidationError`) means pydantic surfaces the second
    kind as a :class:`pydantic.ValidationError` at the model boundary.
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
