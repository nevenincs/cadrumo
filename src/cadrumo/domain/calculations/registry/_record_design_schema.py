"""Record-design parser output models."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from ._schema import RegistryModel

__all__ = [
    "RecordDesignField",
    "RecordDesignRelativeSuffixMarker",
    "RecordDesignSheet",
    "RecordDesignVariableBodyMarker",
    "RecordDesignVariableEnvelope",
    "RecordDesignVariableTotalMarker",
]


class RecordDesignField(RegistryModel):
    """One fixed-width field described by an AEAT record-design sheet."""

    sheet: str
    row: int
    ordinal: int
    offset: int
    length: int
    type_code: str
    complementary: str | None = None
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignVariableBodyMarker(RegistryModel):
    """Official marker that opens a variable-length composed body."""

    sheet: str
    row: int = Field(gt=0)
    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: Literal["Variable"]
    type_code: str
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignRelativeSuffixMarker(RegistryModel):
    """Official closing suffix positioned relative to a variable body."""

    sheet: str
    row: int = Field(gt=0)
    ordinal: int = Field(gt=0)
    offset: Literal["***"]
    length: int = Field(gt=0)
    type_code: str
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignVariableTotalMarker(RegistryModel):
    """Official declaration that the composed record has variable total length."""

    sheet: str
    row: int = Field(gt=0)
    label: Literal["total"]
    length: Literal["Variable"]


class RecordDesignVariableEnvelope(RegistryModel):
    """Variable composition wrapper, distinct from a fixed-width record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    prefix_fields: tuple[RecordDesignField, ...] = Field(min_length=1)
    prefix_extent: int = Field(gt=0)
    body: RecordDesignVariableBodyMarker
    closing_suffix: RecordDesignRelativeSuffixMarker
    variable_total: RecordDesignVariableTotalMarker


class RecordDesignSheet(RegistryModel):
    """Parsed field rows and declared total length for one workbook sheet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[RecordDesignField, ...]
    total_positions: int | None = None
    variable_envelope: RecordDesignVariableEnvelope | None = None
