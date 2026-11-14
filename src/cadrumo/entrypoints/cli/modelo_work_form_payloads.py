"""Typed JSON payload for ``aeat app modelo work form``: a declaration's saved repeating records.

The records are the repeating blocks of the served declaration form, the same
projection the workbench and the window show, carried with their row identity,
the casilla each column shows and the typed wire value of each cell.

This module uses :class:`OutputSchema`, the declared output contract.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class WorkFormRecordColumn(OutputSchema):
    """One column of a record block, as the form serves it."""

    key: str
    heading: str
    #: The casilla the column shows; ``None`` for a column no casilla owns.
    casilla_id: str | None = None
    data_type: str


class WorkFormRecordValue(OutputSchema):
    """One cell of a record that holds a value; a cell the form serves empty is not listed."""

    column_key: str
    casilla_id: str | None = None
    #: The wire scalar kind: ``string``, ``integer``, ``boolean``, ``decimal`` or ``date``.
    kind: str
    #: The typed wire value, written exactly as the form serves it.
    value: str
    #: The value as the table shows it in the form's language; ``None`` when the form words none.
    value_text: str | None = None


class WorkFormRecord(OutputSchema):
    """One saved record of a block, identified by its row index."""

    index: int
    values: list[WorkFormRecordValue]


class WorkFormRecordBlock(OutputSchema):
    """One repeating block of the form and its saved records.

    ``rows_known`` is ``False`` when the form cannot read the records from their
    source; ``records`` is then empty and ``rows_unknown_words`` says so, so an
    unknown block is never read as a block with no records.
    """

    block_id: str
    page_id: str
    section_id: str
    columns: list[WorkFormRecordColumn]
    min_rows: int
    max_rows: int | None = None
    rows_known: bool
    rows_unknown_words: str | None = None
    records: list[WorkFormRecord]


class WorkFormResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work form``."""

    bucket_id: BucketId
    work_unit_id: str
    modelo: str
    filing_year: int
    period: str
    registry_revision_id: str
    #: The calculation the records come from; ``None`` before the declaration is calculated.
    calculation_revision_id: str | None = None
    blocks: list[WorkFormRecordBlock]


__all__ = [
    "WorkFormRecord",
    "WorkFormRecordBlock",
    "WorkFormRecordColumn",
    "WorkFormRecordValue",
    "WorkFormResult",
]
