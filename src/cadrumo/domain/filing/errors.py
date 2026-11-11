"""Domain errors for the :mod:`domain.filing` subpackage.

Every exception inherits from :class:`~core.errors.hierarchy.CadrumoError` so
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
    Its registered ancestry includes :class:`~core.errors.hierarchy.CoreValidationError`
    under the filing error family. Pydantic model validators translate the
    registered failure to ``ValueError`` at their narrow boundary, yielding a
    :class:`pydantic.ValidationError` for structurally malformed records.
    """


class ModeloComputationError(ModeloDraftError):
    """Raised when a builder cannot evaluate a formula casilla."""


class ModeloImportError(ModeloDraftError):
    """Raised when importing a filing from a justificante PDF fails."""


class FilingExportError(ModeloDraftError):
    """Raised when exporting a draft to an AEAT wire format fails."""


class FilingExportValidationError(FilingExportError):
    """Raised on invalid export field values or layouts.

    Its canonical registered ancestry is :class:`FilingExportError`; any
    Pydantic export validator translates this registered failure to
    ``ValueError`` at its narrow boundary.
    """


class FilingExportFieldOverflowError(FilingExportValidationError):
    """Refuses an export whose value is wider than its fixed-width field.

    An official design that asks for a complete value gives no truncation
    rule, so the export writes nothing rather than shorten it. The context
    names the record, the field and both widths, never the value, which can be
    a taxpayer's or a counterparty's private data.
    """

    def __init__(self, *, export_record_id: str, export_field_id: str, field_length: int, value_length: int) -> None:
        """Record where the value does not fit and by how much."""
        super().__init__(
            f"export record {export_record_id!r} field {export_field_id!r} needs {value_length} positions "
            f"but its fixed width is {field_length}",
            context={
                "export_record_id": export_record_id,
                "export_field_id": export_field_id,
                "field_length": field_length,
                "value_length": value_length,
            },
        )
        self.export_record_id = export_record_id
        self.export_field_id = export_field_id
        self.field_length = field_length
        self.value_length = value_length


class FilingExportRequiredRecordAbsentError(FilingExportValidationError):
    """Refuses an export whose layout requires a record this return has no occurrence of.

    The official design cannot be written without that record, so a return
    with nothing to state in it has nothing to file in this format.
    """

    def __init__(self, *, export_record_id: str) -> None:
        """Record which required record has no occurrence."""
        super().__init__(
            f"required export record {export_record_id!r} has no applicable occurrence",
            context={"export_record_id": export_record_id},
        )
        self.export_record_id = export_record_id


#: Export refusals the modelo export boundary shows as they are, since their
#: own code and context already tell the operator why nothing was written.
FILING_EXPORT_REFUSALS: tuple[type[FilingExportValidationError], ...] = (
    FilingExportFieldOverflowError,
    FilingExportRequiredRecordAbsentError,
)
