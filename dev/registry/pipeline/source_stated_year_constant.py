"""Exact source readings for a four-digit ejercicio printed as `Constante`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .record_design_intermediate import RecordDesignIntermediateField


class SourceStatedYearConstant(BaseModel):
    """One hash-pinned year slot whose source wrapper defines EEEE as ejercicio."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str
    source_row: int
    source_cell: str
    published_content: str
    published_description: str
    reviewed_wrapper_statement: str


_M131_YEAR_CONSTANTS = {
    source_ref: SourceStatedYearConstant(
        source_ref=source_ref,
        source_sha256=sha256,
        sheet="Pág. 1",
        source_row=15,
        source_cell="A15",
        published_content="Constante",
        published_description="Devengo (2) - Ejercicio",
        reviewed_wrapper_statement=statement,
    )
    for source_ref, sha256, statement in (
        (
            "aeat-dr-131-2019-2023-v101",
            "2b36ae9d4712a94d3b0a798d813c9f560b29fdd2a00062b7d7b4ba9f72f970f3",
            "EEEE indica las cuatro cifras del ejercicio en curso",
        ),
        (
            "aeat-dr-131-2024",
            "83e40d7d4d64c3b2da570d5e70a650685de036277df3ce077b0569a2235aa06f",
            "EEEE indica las cuatro cifras del ejercicio de devengo",
        ),
        (
            "aeat-dr-131-2025",
            "df4c23a10d836c7d1b4ba16a7758e735c6ae113c5c6c01ff6c439692d0ad4935",
            "EEEE indica las cuatro cifras del ejercicio de devengo",
        ),
        (
            "aeat-dr-131-2026",
            "6d7704aa438c30dd538dbba471ac68f28d22e478bcd679ba8b49b2776a6c964a",
            "EEEE indica las cuatro cifras del ejercicio de devengo",
        ),
        (
            "aeat-dr-131-2026-late",
            "b394370ae16d303a3ed7e192ca34ba1ff49dbbbea49e4d2bbe220085cc53600f",
            "EEEE indica las cuatro cifras del ejercicio de devengo",
        ),
    )
}


def source_stated_year_constant_for(
    *,
    source_ref: str,
    source_sha256: str,
    field: RecordDesignIntermediateField,
) -> SourceStatedYearConstant | None:
    """Resolve an exact source and anchor, refusing a reissued or changed cell."""
    declaration = _M131_YEAR_CONSTANTS.get(source_ref)
    if declaration is None:
        return None
    if declaration.source_sha256 != source_sha256:
        raise RegistryValidationError("year constant reading is stale for its parser-read source SHA-256")
    if (field.sheet, field.source_row, field.source_cell) != (
        declaration.sheet,
        declaration.source_row,
        declaration.source_cell,
    ):
        return None
    if (field.content, field.normalized_description) != (
        declaration.published_content,
        declaration.published_description,
    ):
        raise RegistryValidationError("year constant cell no longer matches its exact reviewed source reading")
    return declaration
