"""Exact constants stated in an official field's referenced note.

A note pointer is no constant by itself. These readings identify the field,
the note and the source bytes together; they cannot choose among alternatives.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .record_design_intermediate import RecordDesignIntermediateSource


class NoteLiteralDeclaration(BaseModel):
    """One field whose exact referenced note states a single wire constant."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    source_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    published_pointer: str = Field(min_length=1)
    note_ordinal: int = Field(gt=0)
    note_source_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    note_statement: str = Field(min_length=1)
    literal: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_one_exact_constant(self) -> NoteLiteralDeclaration:
        statement = " ".join(self.note_statement.split())
        match = re.fullmatch(
            r"(?P<ordinal>[1-9][0-9]*)\. El tipo de declaración para la presentación "
            r"puede ser: (?P<literal>[A-Z]) \(ingreso\)\.?",
            statement,
        )
        if match is None:
            raise ValueError("literal note must state one exact constant without alternatives or conditions")
        if int(match.group("ordinal")) != self.note_ordinal or match.group("literal") != self.literal:
            raise ValueError("literal note ordinal or constant disagrees with its exact statement")
        if not self.evidence.strip():
            raise ValueError("literal note requires nonblank evidence")
        return self


_NOTE_LITERALS: dict[str, tuple[NoteLiteralDeclaration, ...]] = {
    "aeat-dr-122-2016": (
        NoteLiteralDeclaration(
            source_ref="aeat-dr-122-2016",
            source_sha256="2b7c2bb3472cde1faba997f777aa88290e707a3773a3dc88348f74caeee0a4c7",
            sheet="Pag. 1",
            source_cell="A11",
            published_pointer="Ver nota 1",
            note_ordinal=1,
            note_source_cell="A47",
            note_statement="1. El tipo de declaración para la presentación puede ser: I (ingreso)",
            literal="I",
            evidence=(
                "The hash-verified workbook's Pag. 1 row 11 declares one An position and points to note 1. "
                "Cell A47 defines that note with only I (ingreso), without another token or condition. "
                "The declaration retains both exact cells and the complete note rather than interpreting "
                "a note number as a constant. Encoding and full slot-width checks still apply."
            ),
        ),
    ),
}


def note_literals_for(source: RecordDesignIntermediateSource) -> tuple[NoteLiteralDeclaration, ...]:
    """Return readings only when they match the parser-read source identity."""
    declarations = _NOTE_LITERALS.get(str(source.source_ref), ())
    for declaration in declarations:
        if declaration.source_ref != str(source.source_ref) or declaration.source_sha256 != source.source_sha256:
            raise RegistryValidationError("literal note is not pinned to the parser-read source SHA-256")
    return declarations


def note_literal_for(
    declarations: tuple[NoteLiteralDeclaration, ...],
    *,
    sheet: str,
    source_cell: str | None,
    published_pointer: str,
    note_references: tuple[int, ...],
) -> str | None:
    """Resolve one exact pointer; leave every undeclared or ambiguous pointer refused."""
    matches = tuple(
        declaration
        for declaration in declarations
        if declaration.sheet == sheet
        and declaration.source_cell == source_cell
        and declaration.published_pointer == published_pointer
        and note_references == (declaration.note_ordinal,)
    )
    if len(matches) > 1:
        raise RegistryValidationError("literal note has multiple declarations for one exact field pointer")
    return matches[0].literal if matches else None
