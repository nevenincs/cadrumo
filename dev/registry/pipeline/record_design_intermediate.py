"""The parser-read record design as its consumers outside this package see it.

Which official binary a design epoch was read from, in what format, and what
each field's exact anchor within it is: that is the shape every consumer of the
generator's intermediate representation addresses, and it is a shared contract
rather than an implementation detail of the loader that builds it. The
eligibility question publishes both types in its own public signature, the
declaration validators check a declaration's pin against the source, and the
analysis screens read fields straight off a parsed design -- so the contract has
a public defining module of its own rather than living inside the private loader
module.

Assembling one of these remains private: ``_record_design_ir`` selects the
official binary through the registry catalogue, runs the shipped parser, and
composes the sheets, envelopes and whole-design aggregate around these records.
A caller wanting a parsed design asks that loader; a caller merely holding one
of its fields or its source needs only this module.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.ids import SourceRefId

__all__ = [
    "RecordDesignIntermediateField",
    "RecordDesignIntermediateSource",
    "RecordDesignWorkbookFormat",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RecordDesignWorkbookFormat(StrEnum):
    """Exact official binary formats the shipped parser supports."""

    PDF = "pdf"
    XLS = "xls"
    XLSM = "xlsm"
    XLSX = "xlsx"


class RecordDesignIntermediateSource(_StrictModel):
    """Verified official binary authority for one parsed design epoch."""

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workbook_format: RecordDesignWorkbookFormat
    design_epoch: str = Field(min_length=1)


class RecordDesignIntermediateField(_StrictModel):
    """One parser-derived field with its exact official source anchor."""

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    #: The ordinal AEAT printed, verbatim -- a str because it is a printed LABEL
    #: (``14bis``), never an arithmetic value. Mirrors
    #: :attr:`domain.calculations.registry.RecordDesignField.ordinal`, which this
    #: field is a straight 1:1 projection of.
    ordinal: str | None = None
    offset: int = Field(gt=0)
    length: int = Field(gt=0)
    aeat_type: str = Field(min_length=1)
    normalized_description: str = Field(min_length=1)
    validation: str | None = None
    content: str | None = None
