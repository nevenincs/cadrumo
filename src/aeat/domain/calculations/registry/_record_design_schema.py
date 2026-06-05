"""Record-design parser output models."""

from __future__ import annotations

from pydantic import ConfigDict

from ._schema import RegistryModel

__all__ = ["RecordDesignField", "RecordDesignSheet"]


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


class RecordDesignSheet(RegistryModel):
    """Parsed field rows and declared total length for one workbook sheet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[RecordDesignField, ...]
    total_positions: int | None = None
