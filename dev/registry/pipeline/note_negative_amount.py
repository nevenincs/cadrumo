"""How a design's general notes state a negative amount is written.

A design whose type column reads as unsigned can still say, in its notes and worked
examples, that the slot takes a negative. Only the amounts the reading names change:
every other slot keeps the shape its own row derives. A reading identifies the notes
and the source bytes together, so it applies only to the workbook that was reviewed.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportSignPosition

from .export_fragment_provenance import ExportFieldDerivation
from .record_design_intermediate import RecordDesignIntermediateSource


class NoteNegativeAmountDeclaration(BaseModel):
    """One design whose notes write a negative in the amounts named by ``amount_label``."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    note_cells: tuple[str, ...] = Field(min_length=1)
    note_statements: tuple[str, ...] = Field(min_length=1)
    amount_label: str = Field(min_length=1)
    sign_position: ExportSignPosition


_NOTE_NEGATIVE_AMOUNTS: Final[dict[str, NoteNegativeAmountDeclaration]] = {
    "aeat-dr-369-2021": NoteNegativeAmountDeclaration(
        source_ref="aeat-dr-369-2021",
        source_sha256="b59ade58821e8e0988a1aa4e2a7f52c97b21375fc0a6720d76ca0601a7c8b1a3",
        sheet="T3690 Estruc. gral",
        note_cells=("A33", "A34"),
        note_statements=(
            "3. Los campos numéricos (Num) sólo admiten números más el carácter de signo negativo '-'.",
            "4. Los campos numéricos (Num) admiten números tanto positivos como negativos. Los datos numéricos "
            "negativos llevarán un caracter '-' inmediatamente delante de los números.",
            "-0000000000001537' (El dato es -15,37",
        ),
        # The form's own settlement lists "correcciones negativas apdo. 4"; no other amount of the design goes below zero.
        amount_label="Cuota IVA corregida",
        sign_position=ExportSignPosition.MINUS_DISPLACES_DIGIT,
    ),
}


def note_negative_amount_for(source: RecordDesignIntermediateSource) -> NoteNegativeAmountDeclaration | None:
    """Return the reading only when it matches the parser-read source identity."""
    declaration = _NOTE_NEGATIVE_AMOUNTS.get(str(source.source_ref))
    if declaration is not None and declaration.source_sha256 != source.source_sha256:
        raise RegistryValidationError("negative-amount note is not pinned to the parser-read source SHA-256")
    return declaration


def with_note_negative_amount(
    derivation: ExportFieldDerivation,
    declaration: NoteNegativeAmountDeclaration | None,
) -> ExportFieldDerivation:
    """Give the amounts the notes name the design's signed shape, at the money scale they already print."""
    if declaration is None or declaration.amount_label not in (derivation.parser_field.description or ""):
        return derivation
    field = derivation.field
    if field.data_type != "decimal" or field.decimals != 2:
        raise RegistryValidationError(f"export field {field.id!r} is named by a sign note but is not a 2-decimal amount")
    return derivation.model_copy(
        update={
            "field": field.model_copy(
                update={
                    "data_type": "money",
                    "decimals": None,
                    "signed": True,
                    "sign_position": declaration.sign_position,
                }
            )
        }
    )
