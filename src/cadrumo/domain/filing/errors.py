"""Domain errors for the :mod:`domain.filing` subpackage.

Every exception inherits from :class:`~core.errors.hierarchy.CadrumoError` so
callers can catch the project-wide base.
"""

from __future__ import annotations

from typing import ClassVar

from ...core.errors.hierarchy import CadrumoError, CoreValidationError, TerminalPreconditionErrorMixin
from ...core.text_fold import code_point_label


class ModeloDraftError(TerminalPreconditionErrorMixin[object], CadrumoError):
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
    """Raised when exporting a draft to an AEAT wire format fails.

    A refusal may carry the typed verdict that says whether the filer's data,
    the filer's decision or nothing the filer does can put it right. The domain
    holds the verdict opaquely; the application builds it.
    """


class FilingExportValidationError(FilingExportError):
    """Raised on invalid export field values or layouts.

    Its canonical registered ancestry is :class:`FilingExportError`; any
    Pydantic export validator translates this registered failure to
    ``ValueError`` at its narrow boundary.
    """


class FilingExportIntegrityError(FilingExportError):
    """Raised when the export design the application carries contradicts itself or the code that renders it.

    Every check behind it compares the application's own record design, registry
    layout or computed result, never a value the filer supplied, so no change to
    the filer's data repairs it.
    """


class FilingExportDesignIntegrityError(FilingExportIntegrityError, FilingExportValidationError):
    """Raised on an invalid export field value or layout that is the application's own fault.

    It is both an export integrity defect and an export validation failure, so a
    handler that catches :class:`FilingExportValidationError` still catches it.
    """


class FilingExportProfileFactMissingError(FilingExportValidationError):
    """Raised when the export needs a fact about the filer that the profile does not state.

    The fact is the filer's to state, so the refusal carries the door that
    names the action putting it right. Nothing is written until it is stated.
    """


class FilingExportCasillaValueRefusedError(FilingExportValidationError):
    """Raised when the value of one box the filer states cannot be written as the design places it.

    ``casilla_id`` is the box whose value puts it right; the served words say
    why. Nothing is written until that box is stated again.
    """

    def __init__(
        self,
        *,
        casilla_id: str,
        translated_message: str,
        context: dict[str, object],
        precondition_verdict: object | None = None,
    ) -> None:
        """Construct the refusal for the box ``casilla_id``."""
        self.casilla_id: str = casilla_id
        super().__init__(
            f"box {casilla_id!r} holds a value the export cannot write",
            context={**context, "casilla_id": casilla_id},
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )


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
        precondition_verdict: object | None = None,
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
            precondition_verdict=precondition_verdict,
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
            precondition_verdict=self.terminal_precondition_verdict,
        )


class FilingExportRequiredRecordAbsentError(FilingExportValidationError):
    """Raised when the layout requires a record this return has no occurrence of.

    The official design cannot be written without that record, so a return
    with nothing to state in it has nothing to file in this format.
    """

    def __init__(self, *, export_record_id: str, precondition_verdict: object | None = None) -> None:
        """Record which required record has no occurrence."""
        self.export_record_id: str = export_record_id
        super().__init__(
            f"required export record {export_record_id!r} has no applicable occurrence",
            context={"export_record_id": export_record_id},
            precondition_verdict=precondition_verdict,
        )


class FilingExportFieldUnrenderableError(FilingExportValidationError):
    """Raised when the record design and a value disagree so that the field cannot be written.

    An integer slot given a fractional amount is the example. The export
    refuses instead of rounding or cutting, and names the field, its casilla
    when it has one, its data type and the codec's reason. No change to the
    filer's data repairs it: the fault is in the design the application
    carries.
    """

    def __init__(
        self,
        *,
        field_id: str,
        casilla_id: str | None,
        data_type: str,
        reason: str,
        precondition_verdict: object | None = None,
    ) -> None:
        """Construct the refusal for one field."""
        self.field_id: str = field_id
        self.casilla_id: str | None = casilla_id
        self.data_type: str = data_type
        self.reason: str = reason
        context: dict[str, object] = {"field_id": field_id, "data_type": data_type, "reason": reason}
        if casilla_id is not None:
            context["casilla_id"] = casilla_id
        super().__init__(
            f"export field {field_id!r} cannot be rendered from its value",
            context=context,
            precondition_verdict=precondition_verdict,
        )


class FilingExportUnrepresentableCharacterError(FilingExportValidationError):
    """Raised when a text value holds a character its record design cannot write.

    The export refuses instead of dropping or replacing the character, and names
    the slot: its field, its one-based positions and width, the character, and
    once the record is known the design's record type. ``rendered`` is the text
    as the record's rule wrote it; it is kept off the context so only a boundary
    that chooses to show it does.
    """

    def __init__(
        self,
        *,
        field_id: str,
        first_position: int | None,
        field_length: int | None,
        character: str,
        rendered: str,
        record_type: str | None = None,
        precondition_verdict: object | None = None,
    ) -> None:
        """Construct the refusal for one slot, optionally already placed in its record."""
        self.field_id: str = field_id
        self.first_position: int | None = first_position
        self.field_length: int | None = field_length
        self.character: str = character
        self.rendered: str = rendered
        self.record_type: str | None = record_type
        super().__init__(
            f"export field {field_id!r} holds a character its record cannot write",
            context={"field_id": field_id, "code_point": code_point_label(character)},
            precondition_verdict=precondition_verdict,
        )

    def in_record(self, record_type: str) -> FilingExportUnrepresentableCharacterError:
        """The same refusal placed in the record design ``record_type``."""
        return FilingExportUnrepresentableCharacterError(
            field_id=self.field_id,
            first_position=self.first_position,
            field_length=self.field_length,
            character=self.character,
            rendered=self.rendered,
            record_type=record_type,
            precondition_verdict=self.terminal_precondition_verdict,
        )


class FilingExportDeclaredPartyNameError(FilingExportValidationError):
    """Refuses a party-name slot whose party has no filing name the record design can take.

    The design prescribes the slot's content from the party's own name parts and
    allows no shortening, so a name nobody stated, one the design cannot compose
    or one wider than the slot leaves nothing truthful to write. The context
    names where the slot is, a non-identifying handle of the party, both widths
    and the action that states the party's filing name; never the name or the
    party's tax identifier.
    """

    reason: ClassVar[str] = "unstated"

    def __init__(
        self,
        *,
        modelo: str,
        export_record_id: str,
        export_field_id: str,
        field_length: int,
        door_action_id: str,
        party_handle: str | None = None,
        row_index: int | None = None,
        composed_length: int | None = None,
        tax_identifier: str | None = None,
        country_code: str | None = None,
    ) -> None:
        """Record which slot refuses, for which party, and the action that remedies it.

        ``tax_identifier`` and ``country_code`` name the party for the door's
        own arguments; they are attributes only, never part of the context.
        """
        self.modelo = modelo
        self.tax_identifier = tax_identifier
        self.country_code = country_code
        self.export_record_id = export_record_id
        self.export_field_id = export_field_id
        self.field_length = field_length
        self.door_action_id = door_action_id
        self.party_handle = party_handle
        self.row_index = row_index
        self.composed_length = composed_length
        context: dict[str, object] = {
            "reason": self.reason,
            "modelo": modelo,
            "export_record_id": export_record_id,
            "export_field_id": export_field_id,
            "field_length": field_length,
            "door_action_id": door_action_id,
        }
        if party_handle is not None:
            context["party_handle"] = party_handle
        if row_index is not None:
            context["row_index"] = row_index
        if composed_length is not None:
            context["composed_length"] = composed_length
        super().__init__(
            f"export record {export_record_id!r} field {export_field_id!r} has no declared party name it can file "
            f"({self.reason})",
            context=context,
        )


class FilingExportDeclaredPartyNameMissingError(FilingExportDeclaredPartyNameError):
    """The party's filing name was never stated, so the slot would be left without its content."""

    reason: ClassVar[str] = "missing"


class FilingExportDeclaredPartyNameSingleSurnameError(FilingExportDeclaredPartyNameError):
    """The party is a natural person stated with one surname, which no design says how to compose."""

    reason: ClassVar[str] = "single_surname"


class FilingExportDeclaredPartyNameTooWideError(FilingExportDeclaredPartyNameError):
    """The composed name is wider than the slot and the operator stated no rendering that fits it."""

    reason: ClassVar[str] = "too_wide"
