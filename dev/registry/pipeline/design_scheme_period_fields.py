"""Which design rows print the scheme period a registered filing period already carries.

A special-regime period such as a quarter or a month is one typed filing period,
while its design spreads it over an exercise, a period-type and a period row. A
reading identifies those rows and the source bytes together, so it applies only
to the exact workbook whose page was reviewed.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .export_fragment_provenance import ExportFieldDerivation
from .record_design_intermediate import RecordDesignIntermediateSource


class DesignSchemePeriodFieldsDeclaration(BaseModel):
    """One design page whose period rows are spelled by the scheme period being filed."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ordinal_part_by_sheet: dict[str, Literal["quarter_ordinal", "month_ordinal"]] = Field(min_length=1)
    filing_year_description: str = Field(min_length=1)
    period_type_description: str = Field(min_length=1)
    ordinal_description: str = Field(min_length=1)


DESIGN_SCHEME_PERIOD_FIELDS: Final[dict[str, DesignSchemePeriodFieldsDeclaration]] = {
    "aeat-dr-369-2021": DesignSchemePeriodFieldsDeclaration(
        source_ref="aeat-dr-369-2021",
        source_sha256="b59ade58821e8e0988a1aa4e2a7f52c97b21375fc0a6720d76ca0601a7c8b1a3",
        ordinal_part_by_sheet={
            "T36901 Ext": "quarter_ordinal",
            "T36904 Un": "quarter_ordinal",
            "T36910 Imp": "month_ordinal",
        },
        filing_year_description="2. Ejercicio y período. Ejercicio",
        period_type_description="2. Ejercicio y período. Tipo de periodo",
        ordinal_description="2. Ejercicio y período. Periodo",
    ),
}

#: The whole printed content of a row holding one constant letter, as ``"T"``.
_CONSTANT_CONTENT: Final = re.compile(r'"(?P<constant>[A-Z])"')


def design_scheme_period_fields_for(
    source: RecordDesignIntermediateSource,
) -> DesignSchemePeriodFieldsDeclaration | None:
    """Return the reading only when it matches the parser-read source identity."""
    declaration = DESIGN_SCHEME_PERIOD_FIELDS.get(str(source.source_ref))
    if declaration is not None and declaration.source_sha256 != source.source_sha256:
        raise RegistryValidationError("scheme-period reading is not pinned to the parser-read source SHA-256")
    return declaration


def with_scheme_period_part(
    derivation: ExportFieldDerivation,
    declaration: DesignSchemePeriodFieldsDeclaration | None,
) -> ExportFieldDerivation:
    """Carry onto a reviewed period row which part of the scheme period it prints."""
    parser_field = derivation.parser_field
    if declaration is None or parser_field.sheet not in declaration.ordinal_part_by_sheet:
        return derivation
    description = parser_field.normalized_description
    if description == declaration.filing_year_description:
        update: dict[str, str] = {"scheme_period_part": "filing_year"}
    elif description == declaration.ordinal_description:
        update = {"scheme_period_part": declaration.ordinal_part_by_sheet[parser_field.sheet]}
    elif description == declaration.period_type_description:
        update = {"scheme_period_part": "period_type", "scheme_period_type": _printed_constant(parser_field.content)}
    else:
        return derivation
    return derivation.model_copy(update={"field": derivation.field.model_copy(update=update)})


def _printed_constant(content: str | None) -> str:
    match = _CONSTANT_CONTENT.fullmatch((content or "").strip())
    if match is None:
        raise RegistryValidationError(f"scheme period-type row prints no single constant: {content!r}")
    constant = match.group("constant")
    if not isinstance(constant, str):
        raise RegistryValidationError("the reviewed regex must capture its constant as text")
    return constant
