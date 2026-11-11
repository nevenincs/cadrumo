"""Closed code domains stated by the value table of a field's referenced note.

Some ``Contenido`` cells hold nothing but note pointers, and the note they name
is a ``Valor | Descripción`` table: the codes the slot may carry, each with its
meaning. The numeric derivation cannot read that table from the pointer, so
without a reviewed reading it emits an open unscaled integer and the export
schema accepts any digit the codec can write.

A declaration here records one such reading. It is pinned the way its sibling
families are: one file by SHA-256, one sheet by name, one field by its source
cell, one exact published pointer, and the note by ordinal, cell and the exact
text read from each row of its table. Three properties keep it self-limiting:

* A reissued design carries another digest. Its declarations then refuse
  instead of travelling, so nobody's stale reading reaches a new file.
* The domain is the table's own value column. The declaration carries no
  second list that could disagree with the rows it quotes.
* Every value must fill the slot the design declares, through the same width
  check the printed enumerations pass.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .export_field_note_references import split_official_note_references

__all__ = [
    "NoteGovernedEnumerationDeclaration",
    "NoteValueTableRow",
    "note_governed_enumeration_for",
    "note_governed_enumerations_for",
]

_CELL_PATTERN: Final = r"^[A-Z]+[1-9][0-9]*$"


class NoteValueTableRow(BaseModel):
    """One row of a note's ``Valor | Descripción`` table, as read from its cells."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    value_cell: str = Field(pattern=_CELL_PATTERN)
    value: str = Field(pattern=r"^(0|[1-9][0-9]*)$")
    """The code exactly as the value column prints it, zero-canonical."""
    description_cell: str = Field(pattern=_CELL_PATTERN)
    description: str = Field(min_length=1)
    """The description cell's text exactly as read, leading spaces included."""


class NoteGovernedEnumerationDeclaration(BaseModel):
    """One pointer-only numeric field whose named note tabulates its codes."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    source_cell: str = Field(pattern=_CELL_PATTERN)
    published_pointer: str = Field(min_length=1)
    """The ``Contenido`` cell exactly as published, whitespace-normalised."""
    note_ordinal: int = Field(gt=0)
    """The note among the pointer's references whose table states the codes."""
    note_cell: str = Field(pattern=_CELL_PATTERN)
    note_statement: str = Field(min_length=1)
    """The note's heading cell exactly as read."""
    value_table: tuple[NoteValueTableRow, ...] = Field(min_length=2)
    evidence: str = Field(min_length=1)

    @property
    def allowed_values(self) -> tuple[str, ...]:
        """Return the closed domain, which is the table's value column in order."""
        return tuple(row.value for row in self.value_table)

    @model_validator(mode="after")
    def _require_a_pointer_to_a_tabulated_note(self) -> NoteGovernedEnumerationDeclaration:
        stem, references = split_official_note_references(" ".join(self.published_pointer.split()))
        if stem or self.note_ordinal not in references:
            raise ValueError("the published pointer must consist of note references that name the tabulated note")
        if not self.note_statement.strip().startswith(f"Nota {self.note_ordinal}"):
            raise ValueError("the note statement must be the heading of the note the ordinal names")
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("a note value table must not repeat a code")
        return self


_M303_PRORRATA_OPTION_EVIDENCE: Final = (
    "DP30301 fields 17 and 18, at positions 115 and 116, are one-position Num slots. They hold the "
    "'Opción por la aplicación de la prorrata especial (art. 103.Dos.1º LIVA)' and the 'Revocación de la "
    "opción' of that regime. Their Contenido cell reads only 'Nota 6. Nota 5'. Nota 6 is defined on the "
    "same sheet as a Valor | Descripción table with exactly two rows: 1, 'SI para el último periodo (12 y "
    "4T)', and 2, 'Blanco para periodos distintos del último (12 y 4T), y NO para el último periodo (12 y "
    "4T)'. Value 2 therefore covers both the period in which the option is not asked and a NO in the last "
    'period. Nota 5 adds a foral-only rule that every field it marks takes "2" NO. That value is already '
    "in the table, so it narrows a value rather than widening the domain. The neighbouring fields 14, 15, "
    "16 and 19 print the same Sí and No codes in their own cells, and the generator closes them to 1 and "
    "2. Without this reading the two pointer fields keep an open integer domain, and the export accepts "
    "a code the design never defines."
)

#: The row of each 303 workbook's ``Nota 6:`` heading on DP30301. The value
#: table follows it after one ``Valor | Descripción`` header row.
_M303_NOTE_6_HEADING_ROWS: Final[dict[tuple[str, str], int]] = {
    ("aeat-dr-303-2022", "6648f6b319579e49cd5bfdaae69e7451db75767e7f19da0b90383b25b79b3f60"): 113,
    ("aeat-dr-303-2023", "72e463cb29984f535c9f56917d788ff0641965f116aeab47da5f76a59eecfbe4"): 122,
    ("aeat-dr-303-2024-early", "8b1f74b58b9293e60f9ea6fa3cc352a35ca3fe7d09a6705f122585e7f7da65b9"): 122,
    ("aeat-dr-303-2024-late", "2095dd633413f4aed28053bc88402461d80865f454156c01ebc4a2ab68cb76a8"): 129,
    ("aeat-dr-303-2025", "6c3d7eeb714e0deb52f91d7e8dbadeb83f16c1d32d25f9e871756f3ddf0117e6"): 129,
    ("aeat-dr-303-2026", "0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b"): 130,
}


def _m303_prorrata_option_pair(
    source_ref: str, source_sha256: str, heading_row: int
) -> tuple[NoteGovernedEnumerationDeclaration, ...]:
    """Declare fields 17 and 18 of one workbook against its own Nota 6 cells."""
    first_value_row = heading_row + 2
    value_table = (
        NoteValueTableRow(
            value_cell=f"A{first_value_row}",
            value="1",
            description_cell=f"B{first_value_row}",
            description="  SI para el último periodo (12 y 4T)",
        ),
        NoteValueTableRow(
            value_cell=f"A{first_value_row + 1}",
            value="2",
            description_cell=f"B{first_value_row + 1}",
            description=(
                "  Blanco para periodos distintos del último (12 y 4T), y NO para el último periodo (12 y 4T)"
            ),
        ),
    )
    return tuple(
        NoteGovernedEnumerationDeclaration(
            source_ref=source_ref,
            source_sha256=source_sha256,
            sheet="DP30301",
            source_cell=source_cell,
            published_pointer="Nota 6. Nota 5",
            note_ordinal=6,
            note_cell=f"A{heading_row}",
            note_statement="Nota 6: ",
            value_table=value_table,
            evidence=_M303_PRORRATA_OPTION_EVIDENCE,
        )
        for source_cell in ("A22", "A23")
    )


_NOTE_GOVERNED_ENUMERATIONS_BY_REF: Final[dict[str, tuple[NoteGovernedEnumerationDeclaration, ...]]] = {
    source_ref: _m303_prorrata_option_pair(source_ref, source_sha256, heading_row)
    for (source_ref, source_sha256), heading_row in _M303_NOTE_6_HEADING_ROWS.items()
}


def note_governed_enumerations_for(
    source_ref: str, source_sha256: str
) -> tuple[NoteGovernedEnumerationDeclaration, ...]:
    """Return one design's readings, refusing any pinned to other bytes.

    Callers pass the identity of the source the parser read, so a declaration
    pinned to a superseded digest stops the generation rather than applying.
    """
    declarations = _NOTE_GOVERNED_ENUMERATIONS_BY_REF.get(source_ref, ())
    seen: set[tuple[str, str]] = set()
    for declaration in declarations:
        if declaration.source_ref != source_ref or declaration.source_sha256 != source_sha256:
            raise RegistryValidationError(
                f"note-governed enumeration for {declaration.source_ref!r} is not pinned to the parser-read SHA-256",
            )
        key = (declaration.sheet, declaration.source_cell)
        if key in seen:
            raise RegistryValidationError(
                f"duplicate note-governed enumeration for {source_ref!r} cell {declaration.sheet}!"
                f"{declaration.source_cell}",
            )
        seen.add(key)
    return declarations


def note_governed_enumeration_for(
    declarations: tuple[NoteGovernedEnumerationDeclaration, ...],
    *,
    sheet: str,
    source_cell: str | None,
    published_pointer: str,
) -> NoteGovernedEnumerationDeclaration | None:
    """Return the reading for this exact field and pointer, or ``None``.

    The pointer must match exactly as well as the cell. A reissued cell that
    points at another note set therefore keeps the open reading until somebody
    reads the new note.
    """
    for declaration in declarations:
        if (
            declaration.sheet == sheet
            and declaration.source_cell == source_cell
            and declaration.published_pointer == published_pointer
        ):
            return declaration
    return None
