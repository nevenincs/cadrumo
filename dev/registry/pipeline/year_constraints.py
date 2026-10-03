"""Source-pinned lower bounds stated on four-digit filing-year slots."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .record_design_intermediate import RecordDesignIntermediateSource


class BoundedYearDeclaration(BaseModel):
    """A complete reviewed reading of one official year constraint."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    source_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    published_statement: str = Field(min_length=1)
    minimum_year: int = Field(ge=1000, le=9999)

    @model_validator(mode="after")
    def _require_exact_lower_bound(self) -> BoundedYearDeclaration:
        if self.published_statement != f">= {self.minimum_year}":
            raise ValueError("year constraint must state one exact inclusive lower bound")
        return self


_YEAR_CONSTRAINTS = {
    "aeat-dr-216-2024": BoundedYearDeclaration(
        source_ref="aeat-dr-216-2024",
        source_sha256="ebee21da4709d6cd63e42cbd82d8c0592252ce2157c93ac1df9833f1ea42cbf0",
        sheet="Pág. 1",
        source_cell="A14",
        published_statement=">= 2024",
        minimum_year=2024,
    ),
}


def year_constraints_for(source: RecordDesignIntermediateSource) -> tuple[BoundedYearDeclaration, ...]:
    """Resolve the constraints of the exact parser-read source, refusing stale pins."""
    declaration = _YEAR_CONSTRAINTS.get(str(source.source_ref))
    if declaration is None:
        return ()
    if declaration.source_sha256 != source.source_sha256:
        raise RegistryValidationError("year constraint is not pinned to the parser-read source SHA-256")
    return (declaration,)


def bounded_year_for(
    *,
    source_ref: str,
    source_sha256: str,
    sheet: str,
    source_cell: str | None,
    published_statement: str | None,
) -> BoundedYearDeclaration | None:
    """Resolve only the exact declared source, field and constraint."""
    declaration = _YEAR_CONSTRAINTS.get(source_ref)
    if declaration is None:
        return None
    if declaration.source_sha256 != source_sha256:
        raise RegistryValidationError("year constraint is not pinned to the parser-read source SHA-256")
    if (sheet, source_cell) != (declaration.sheet, declaration.source_cell):
        return None
    if published_statement != declaration.published_statement:
        raise RegistryValidationError("official year constraint differs from its complete source-pinned reading")
    return declaration
