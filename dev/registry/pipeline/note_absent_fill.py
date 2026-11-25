"""How a design's general notes state an unused numeric slot prints.

A numeric slot's blank fill is its zero padding unless the design says otherwise.
A reading identifies the note and the source bytes together, so it applies only
to the exact workbook whose notes were reviewed.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import ZERO_PADDED_EXPORT_DATA_TYPES

from .export_fragment_provenance import ExportFieldDerivation
from .record_design_intermediate import RecordDesignIntermediateSource


class NoteAbsentFillDeclaration(BaseModel):
    """One design whose general notes state the fill of its unused numeric slots."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    note_cells: tuple[str, ...] = Field(min_length=1)
    note_statements: tuple[str, ...] = Field(min_length=1)
    fill: Literal["spaces"]


NOTE_ABSENT_FILLS: Final[dict[str, NoteAbsentFillDeclaration]] = {
    "aeat-dr-369-2021": NoteAbsentFillDeclaration(
        source_ref="aeat-dr-369-2021",
        source_sha256="b59ade58821e8e0988a1aa4e2a7f52c97b21375fc0a6720d76ca0601a7c8b1a3",
        sheet="T3690 Estruc. gral",
        note_cells=("A36", "A37"),
        note_statements=(
            "6. En general los campos que no tengan información se rellenarán las posiciones con espacios en "
            "blanco. En particular en los campo numéricos (Num) sin información se rellenarán también con "
            "espacios en blanco y nunca con ceros. ",
            "7. En los grupos de datos referidos a una misma entidad (prestación de servicios, entrega de "
            "bienes, corrección...), si se quieren dejar vacíos TODOS los campos deberán rellenarse con blancos. "
            'Por ejemplo, aunque el "Tipo de IVA" esté especificado que tenga los valores [R,S], si el bloque '
            "lleva los demás campos vacíos, dicho campo deberá contener blancos. Lo mismo aplica a los valores "
            "numéricos.",
        ),
        fill="spaces",
    ),
}


def note_absent_fill_for(source: RecordDesignIntermediateSource) -> NoteAbsentFillDeclaration | None:
    """Return the reading only when it matches the parser-read source identity."""
    declaration = NOTE_ABSENT_FILLS.get(str(source.source_ref))
    if declaration is not None and declaration.source_sha256 != source.source_sha256:
        raise RegistryValidationError("absent-fill note is not pinned to the parser-read source SHA-256")
    return declaration


def with_note_absent_fill(
    derivation: ExportFieldDerivation,
    declaration: NoteAbsentFillDeclaration | None,
) -> ExportFieldDerivation:
    """Carry the design's stated fill onto a numeric slot that holds a value."""
    field = derivation.field
    if (
        declaration is None
        or field.data_type not in ZERO_PADDED_EXPORT_DATA_TYPES
        or field.kind.value in {"literal", "filler"}
    ):
        return derivation
    return derivation.model_copy(update={"field": field.model_copy(update={"absent_fill": declaration.fill})})
