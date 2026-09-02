"""Typed records exchanged by the Google Sheets calculation pull adapter."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, TypedDict

from pydantic import BaseModel, Field, NonNegativeInt

from ....application.storage.calc_sheets.records import (
    OperatorInput,
    SheetExportMetadata,
    SheetRelationProvenanceValue,
)
from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.period import Period
from ....core.time.utc import coerce_utc_aware
from ....domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    ModeloId,
    RelationId,
    RevisionId,
    SourceRefId,
)


class ValueRange(TypedDict, total=False):
    """A single batch-get value-range entry from the Sheets API.

    Cell values are ``object``: the API returns whichever JSON scalar the cell
    holds, and callers must narrow before use. Every key is optional because
    Sheets omits an empty range's ``values`` rather than sending an empty list.
    """

    range: str
    majorDimension: str
    values: list[list[object]]


class OperatorEdit(BaseModel):
    """One operator-edited cell value."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    display_number: str
    label: str
    value: Decimal | str | bool | None = None

    def to_operator_input(self) -> OperatorInput:
        """Project onto the canonical :class:`OperatorInput` shape."""
        return OperatorInput(casilla_id=self.casilla_id, value=self.value)


class BindingEdit(BaseModel):
    """One operator-edited binding cell value (numeric or enum)."""

    model_config = _STRICT_FROZEN

    binding: BindingId
    value: Decimal | str | None = None


class RelationEdit(BaseModel):
    """One pre-resolved cross-revision relation value mirrored in Tarifas."""

    model_config = _STRICT_FROZEN

    relation: RelationId
    value: Decimal | None = None
    provenance: SheetRelationProvenanceValue | None = None
    source_modelo: ModeloId | None = None
    source_filing_year: FilingYear | None = None
    source_periods: tuple[str, ...] = ()
    source_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    resolved_at: datetime | None = None


def relation_edit_payload(edit: RelationEdit) -> dict[str, object]:
    """Project one relation edit into its operator-facing payload row."""
    return {
        "relation": edit.relation,
        "value": str(edit.value) if edit.value is not None else None,
        "provenance": edit.provenance,
        "source_modelo": edit.source_modelo,
        "source_filing_year": edit.source_filing_year,
        "source_periods": list(edit.source_periods),
        "source_casilla_ids": list(edit.source_casilla_ids),
        "legal_refs": list(edit.legal_refs),
        "source_refs": list(edit.source_refs),
        "resolved_at": edit.resolved_at.isoformat() if edit.resolved_at is not None else None,
    }


class RowSetCellEdit(BaseModel):
    """One operator-edited cell from a Detalle tab row-set."""

    model_config = _STRICT_FROZEN

    binding: BindingId
    row_index: int = Field(ge=1)
    value: Decimal | str | None = None


class RowSetEdit(BaseModel):
    """All operator-supplied detail rows for one row-set grouping."""

    model_config = _STRICT_FROZEN

    grouping: str = Field(min_length=1)
    cells: tuple[RowSetCellEdit, ...] = ()


class PullMetadata(BaseModel):
    """Workbook identity metadata recovered from developer metadata."""

    model_config = _STRICT_FROZEN

    modelo_id: str
    revision_id: RevisionId
    filing_year: int
    period: str
    engine_version: str
    registry_sha: str
    exported_at: str | None = None

    def to_sheet_export_metadata(self) -> SheetExportMetadata | None:
        """Project onto a strict :class:`SheetExportMetadata` when stamped."""
        if not self.exported_at:
            return None
        try:
            exported_at = coerce_utc_aware(datetime.fromisoformat(self.exported_at))
        except ValueError:
            return None
        return SheetExportMetadata(
            modelo_id=self.modelo_id,
            revision_id=self.revision_id,
            filing_year=self.filing_year,
            period=Period.from_year_and_code(self.filing_year, self.period),
            engine_version=self.engine_version,
            registry_sha=self.registry_sha,
            exported_at=exported_at,
        )


class MetadataMatchState(StrEnum):
    """Registry-SHA and stamp alignment result for a pulled workbook."""

    MATCHES = "matches"
    STALE = "stale"
    MISSING = "missing"


class PullResult(BaseModel):
    """Outcome of one Google Sheets pull cycle."""

    model_config = _STRICT_FROZEN

    spreadsheet_id: str
    operator_edits: tuple[OperatorEdit, ...]
    binding_edits: tuple[BindingEdit, ...]
    relation_edits: tuple[RelationEdit, ...]
    row_set_edits: tuple[RowSetEdit, ...] = ()
    metadata: PullMetadata
    metadata_match: MetadataMatchState
    cells_read: NonNegativeInt


class PullCoverageDiscrepancy(BaseModel):
    """One coverage delta between an export plan and pulled workbook records."""

    model_config = _STRICT_FROZEN

    kind: Literal[
        "metadata_mismatch",
        "row_set_missing",
        "row_set_extra",
        "binding_count_mismatch",
        "relation_count_mismatch",
    ]
    detail: str = Field(min_length=1)
    expected: str = ""
    observed: str = ""
