"""Adjudicated defects in an AEAT-published record design, pinned to one file.

An official record design is the authority the export generator compares every
literal field against byte-for-byte, and that comparison is the only check that
reads the source document rather than the project's transcription of it. It has
to stay exact. But a published workbook can contradict itself, and when it does
no reading of it satisfies both halves: the modelo 390 filing-year 2022 design
prints an eleven-character close constant into a slot the same cell declares as
twelve bytes wide, while its seven sibling pages each print twelve into twelve.

A declaration here records that adjudication as data rather than as a branch in
the parser or an exemption in a test. It is deliberately narrower than the thing
it unblocks: pinned to one file by digest, one cell by coordinate, and one exact
published string, and carrying the evidence that established the reading.

Two properties keep it self-limiting, and both are load-bearing rather than
incidental:

* Because the key includes the file's SHA-256, a reissued design carries a
  different digest, the declaration stops applying, and the generator refuses
  again until the new file is adjudicated on its own terms. The failure mode is
  a stale correction going dormant, never a stale correction being applied.
* Because the adjudicated literal is fed back through the SAME byte comparison
  and the SAME length check that follow it, the mechanism cannot express an
  arbitrary substitution. It can only resolve a contradiction in the direction
  the document's own surviving half supports -- a value that does not fill the
  slot the cell declares is refused exactly as it is today.

Source: ADR ``2026-08-31-aeat-export-fragment-generator-authority-source-defect-adjudication-adr``,
grounded in ``2026-08-31-aeat-export-fragment-generator-authority-m390-2022-page-7-constant-reference``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

if TYPE_CHECKING:
    from ._record_design_ir import RecordDesignIntermediateSource

__all__ = [
    "SourceDefectDeclaration",
    "adjudicated_literal_for",
    "validate_source_defect_declarations",
]


class SourceDefectDeclaration(BaseModel):
    """One adjudicated contradiction in one published record-design file.

    Every field is required. A declaration without its evidence is not a
    weaker declaration, it is an unreviewed one, and the whole point of
    declaring rather than branching is that the reasoning travels with the
    correction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    source_cell: str = Field(min_length=1)
    published_content: str = Field(min_length=1)
    """The cell's content exactly as the workbook publishes it, defect included."""
    adjudicated_literal: str = Field(min_length=1)
    """The literal the document's own surviving half supports."""
    evidence: str = Field(min_length=1)
    """How the reading was established, in terms a later reviewer can re-check."""


def validate_source_defect_declarations(
    declarations: tuple[SourceDefectDeclaration, ...],
    source: RecordDesignIntermediateSource,
) -> None:
    """Refuse a declaration set that is not pinned to the design being rendered.

    Mirrors the pinning discipline ``_validate_anomaly_exceptions`` applies to
    semantic-map anomalies, and for the same reason: a correction that is not
    tied to the exact bytes it was adjudicated against is a correction that can
    outlive its document.

    The SHA-256 is checked against the PARSER-READ source rather than any
    caller-supplied transport claim, so a declaration cannot be admitted by a
    profile that merely asserts the digest it wants.
    """
    seen: set[tuple[str, str, str]] = set()
    for declaration in declarations:
        key = (declaration.source_ref, declaration.sheet, declaration.source_cell)
        if key in seen:
            raise RegistryValidationError(
                f"duplicate source-defect declaration for {declaration.source_ref!r} "
                f"sheet {declaration.sheet!r} cell {declaration.source_cell!r}",
            )
        seen.add(key)
        if declaration.source_ref != source.source_ref:
            raise RegistryValidationError(
                f"source-defect declaration source {declaration.source_ref!r} does not match parser "
                f"intermediate source {source.source_ref!r}",
            )
        if declaration.source_sha256 != source.source_sha256:
            raise RegistryValidationError(
                f"source-defect declaration for {declaration.source_ref!r} is not pinned to the parser "
                "intermediate SHA-256",
            )


def adjudicated_literal_for(
    declarations: tuple[SourceDefectDeclaration, ...],
    *,
    sheet: str,
    source_cell: str,
    published_content: str,
) -> str | None:
    """Return the adjudicated literal for this cell, or ``None`` to refuse normally.

    The published content must match the declaration EXACTLY. Any other content
    means the file is not the one that was adjudicated -- a reissue, a different
    sheet revision, a parser change -- and the caller's refusal stands, which is
    the behaviour a reader should be able to assume when no declaration applies.
    """
    for declaration in declarations:
        if declaration.sheet != sheet or declaration.source_cell != source_cell:
            continue
        if declaration.published_content != published_content:
            return None
        return declaration.adjudicated_literal
    return None
