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


class FilingExportValueOverflowError(FilingExportValidationError):
    """Raised when a value is wider than its slot in the official record design.

    The export refuses instead of truncating, and names the slot: its field,
    its one-based positions and width, and once the record is known the
    design's record type. ``rendered`` is the text that did not fit; it is
    kept off the context so only a boundary that chooses to show it does.
    """

    def __init__(
        self,
        *,
        field_id: str,
        first_position: int | None,
        field_length: int,
        rendered: str,
        data_type: str,
        record_type: str | None = None,
    ) -> None:
        """Construct the refusal for one slot, optionally already placed in its record."""
        self.field_id: str = field_id
        self.first_position: int | None = first_position
        self.field_length: int = field_length
        self.rendered: str = rendered
        self.data_type: str = data_type
        self.record_type: str | None = record_type
        super().__init__(
            f"export field {field_id!r} cannot render its fixed-width value",
            context={"field_id": field_id, "field_length": field_length, "value_length": len(rendered)},
        )

    def in_record(self, record_type: str) -> FilingExportValueOverflowError:
        """The same refusal placed in the record design ``record_type``."""
        return FilingExportValueOverflowError(
            field_id=self.field_id,
            first_position=self.first_position,
            field_length=self.field_length,
            rendered=self.rendered,
            data_type=self.data_type,
            record_type=record_type,
        )


class FilingExportRequiredRecordAbsentError(FilingExportValidationError):
    """Raised when the layout requires a record this return has no occurrence of.

    The official design cannot be written without that record, so a return
    with nothing to state in it has nothing to file in this format.
    """

    def __init__(self, *, export_record_id: str) -> None:
        """Record which required record has no occurrence."""
        self.export_record_id: str = export_record_id
        super().__init__(
            f"required export record {export_record_id!r} has no applicable occurrence",
            context={"export_record_id": export_record_id},
        )
