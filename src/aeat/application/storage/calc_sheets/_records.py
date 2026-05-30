"""Strict records describing a Google Sheets workbook produced from a
registry snapshot.

Every record is a frozen pydantic v2 model with `extra="forbid"` so that
schema drift surfaces as validation failures at the moment the engine
assembles the plan rather than as silent payload divergence at the
Sheets API. The records are intentionally narrow: the engine produces
them, the apply adapter consumes them, and the pull adapter compares
incoming Sheet cell values back against them.

A1 addressing
-------------

Sheets cell addresses are expressed by the `SheetCellAddress` record
which carries the human-readable A1 string plus the structured tab
name, row index, and column index. Row and column indices are 1-based
to match Sheets' convention. The `a1` string is recomputed from the
tab + row + column at construction time, so callers never hand-roll
A1 strings — they always go through this record.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ....core.time import _now as _utc_now
from ....core.time._utc import _validate_utc_aware
from ....domain.calculations.registry._ids import (
    BindingId,
    CasillaId,
    FormulaId,
    ParameterId,
    RelationId,
    RevisionId,
)
from ....domain.calculations.registry._schema import DecimalValue as _RegistryDecimalValue

# `DecimalValue` is the registry's annotated `Decimal` with a
# BeforeValidator that coerces int / str inputs through `Decimal(...)`.
# That coercion is appropriate inside registry TOML loading but
# breaks `Decimal | str | bool | None` unions where the validator
# would eagerly try to parse a label string as a Decimal. The
# engine therefore uses plain `Decimal` for fields that mix value
# types, and the imported `_RegistryDecimalValue` only where the
# field is unambiguously a Decimal.
DecimalValue = _RegistryDecimalValue


_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class TabName(StrEnum):
    """The tabs the engine emits in every workbook.

    The set is fixed so that the pull adapter and the parity oracle
    have a stable layout to anchor against. New layers (for example a
    future "Pagos" tab for ingreso/devolución timings) are added by
    extending this enumeration; freeform tab names are rejected.
    """

    ENTRADAS = "Entradas"
    CALCULOS = "Cálculos"
    PROVENANCE = "Procedencia"
    TARIFFS = "Tarifas"
    DETALLE = "Detalle"
    GUIDE = "Guía"


_A1_COLUMN = re.compile(r"^[A-Z]{1,3}$")


def _column_index_to_letters(column: int) -> str:
    """Translate a 1-based column index to A, B, ..., Z, AA, AB, ..."""

    if column < 1:
        raise ValueError("column index must be 1-based and positive")
    letters: list[str] = []
    cursor = column
    while cursor:
        cursor, remainder = divmod(cursor - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _column_letters_to_index(letters: str) -> int:
    if not _A1_COLUMN.match(letters):
        raise ValueError(f"invalid Sheets column letters: {letters!r}")
    cursor = 0
    for char in letters:
        cursor = cursor * 26 + (ord(char) - ord("A") + 1)
    return cursor


class SheetCellAddress(BaseModel):
    """A single Sheets cell address, expressed as tab + row + column."""

    model_config = _STRICT_FROZEN

    tab: TabName
    row: int = Field(ge=1)
    column: int = Field(ge=1)
    a1: str = Field(min_length=2)

    @model_validator(mode="after")
    def _a1_matches_row_column(self) -> SheetCellAddress:
        letters = _column_index_to_letters(self.column)
        expected = f"{letters}{self.row}"
        if self.a1 != expected:
            raise ValueError(
                f"a1 {self.a1!r} does not match row={self.row} column={self.column} (expected {expected!r})"
            )
        return self

    @classmethod
    def at(cls, tab: TabName, row: int, column: int) -> SheetCellAddress:
        letters = _column_index_to_letters(column)
        return cls(tab=tab, row=row, column=column, a1=f"{letters}{row}")

    def qualified(self) -> str:
        """Return the cross-tab A1 reference (`'Tab Name'!A1`)."""

        # Sheets A1 syntax single-quotes the sheet name and escapes
        # inner apostrophes by doubling them. The tab enum values do
        # not contain apostrophes today, but the escape is applied
        # unconditionally so a future tab rename cannot break syntax.
        safe = self.tab.value.replace("'", "''")
        return f"'{safe}'!{self.a1}"


class SheetValueCell(BaseModel):
    """A literal value the engine writes verbatim to a cell.

    Used for operator-input cells (with `value=None` indicating "blank,
    awaiting operator entry"), for parameter mirror cells, and for the
    structural section/header labels.
    """

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    value: Decimal | str | bool | None = None
    note: str | None = None
    casilla: CasillaId | None = None
    parameter: ParameterId | None = None
    role: Literal["operator_input", "parameter_value", "label", "metadata"]


class SheetFormulaCell(BaseModel):
    """A computed cell whose value comes from a Sheets formula.

    The formula string is exactly what is sent to the Sheets API,
    minus the leading "=" sign (the apply adapter prepends it). It
    must already be A1-resolved.
    """

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    formula: str = Field(min_length=1)
    casilla: CasillaId
    rounding_scale: int | None = Field(default=None, ge=0, le=12)
    rounding_rule: Literal["money", "integer", "none"]
    note: str | None = None


class SheetCellConstraint(BaseModel):
    """A declarative value constraint surfaced to one Sheets cell.

    Mirrors the registry's `CasillaConstraints` record into a Sheets
    `setDataValidation` rule. The apply adapter renders this as a
    `condition` block on the target cell so an operator who types an
    out-of-range value sees Sheets's own validation banner reject it
    in the workbook UI.

    The constraint also propagates to the cell's `note` so the
    operator sees the legal grounding ("LIRPF art. 56 — non-negative")
    even before they attempt invalid input.
    """

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    sign: Literal["any", "non_negative", "non_positive"] = "any"
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    legal_refs: tuple[str, ...] = Field(min_length=1)
    casilla: CasillaId


class SheetRowSetColumn(BaseModel):
    """One column of a `SheetRowSet`, mapping a binding id to a header cell."""

    model_config = _STRICT_FROZEN

    binding: BindingId
    header_address: SheetCellAddress
    header_label: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = ()


class SheetRowSet(BaseModel):
    """A repeating-row data block in the `Detalle` tab.

    Mirrors the registry's row-producer binding pattern (bindings
    declared with `aggregation = { op = "rows", grouping = "..." }`).
    Each row in the workbook represents one operator-supplied detail
    record (e.g., one perceptor on modelo 190, one VIES counterparty
    on modelo 349, one foreign asset on modelo 720). Columns are
    declared per row-producing binding sharing the same `grouping`.

    The engine emits a header row carrying `header_label` for each
    column. Operators add row data freely below; the apply adapter
    leaves the data area unprotected. The pull adapter reads the
    operator-supplied rows back into structured `RowSetEdit` records
    keyed by binding id.

    `legal_refs` and `source_refs` ground the row-set against AEAT's
    diseño-de-registro authority that mandates the per-record
    fields.
    """

    model_config = _STRICT_FROZEN

    grouping: str = Field(min_length=1)
    tab: TabName
    header_row: int = Field(ge=1)
    first_data_row: int = Field(ge=2)
    columns: tuple[SheetRowSetColumn, ...] = Field(min_length=1)
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class SheetProtectedRange(BaseModel):
    """A contiguous range the apply adapter marks read-only.

    `Cálculos`, `Procedencia`, and `Tarifas` are always fully
    protected. The pull adapter inspects these to decide which cells
    operators are allowed to mutate.
    """

    model_config = _STRICT_FROZEN

    tab: TabName
    start_row: int = Field(ge=1)
    end_row: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_column: int = Field(ge=1)
    description: str

    @model_validator(mode="after")
    def _range_well_formed(self) -> SheetProtectedRange:
        if self.end_row < self.start_row:
            raise ValueError("end_row must be on or after start_row")
        if self.end_column < self.start_column:
            raise ValueError("end_column must be on or after start_column")
        return self


class SheetProvenanceRow(BaseModel):
    """One row of the `Procedencia` audit tab.

    Each computed casilla emits a row recording the formula id, the
    rounding rule, the legal references, and the workbook cell that
    holds the value. Operators reading the workbook can audit every
    figure back to a registry source.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    casilla_number: str
    casilla_label: str
    formula_id: FormulaId | None = None
    rounding_rule: Literal["money", "integer", "none"]
    legal_refs: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)
    target_address: SheetCellAddress


class SheetTariffTableRow(BaseModel):
    """One row of a parameter bracket table mirrored to the `Tarifas` tab."""

    model_config = _STRICT_FROZEN

    lower_bound: DecimalValue
    upper_bound: DecimalValue | None = None
    fixed_addition: DecimalValue
    marginal_rate: DecimalValue
    valid_from: date
    valid_to: date | None = None


class SheetTariffTable(BaseModel):
    """A parameter mirrored into the workbook as a lookup table.

    Two flavours are supported: scalar dated values and bracket tables
    (`bracket_table` parameters). The engine emits one of the two
    depending on the parameter's `data_type`.
    """

    model_config = _STRICT_FROZEN

    parameter: ParameterId
    label: str
    data_type: Literal["decimal", "money", "integer", "ratio", "bracket_table"]
    anchor: SheetCellAddress
    scalar_value: DecimalValue | None = None
    bracket_rows: tuple[SheetTariffTableRow, ...] = ()

    @model_validator(mode="after")
    def _shape_well_formed(self) -> SheetTariffTable:
        if self.data_type == "bracket_table":
            if not self.bracket_rows:
                raise ValueError("bracket_table tariff requires at least one row")
            if self.scalar_value is not None:
                raise ValueError("bracket_table tariff must not declare scalar_value")
        else:
            if self.scalar_value is None:
                raise ValueError(f"{self.data_type} tariff requires scalar_value")
            if self.bracket_rows:
                raise ValueError(f"{self.data_type} tariff must not declare bracket_rows")
        return self


class ParameterCell(BaseModel):
    """Pointer from a parameter id to its anchor cell in the `Tarifas` tab.

    The translator consults this mapping when an expression references
    a parameter, so that the emitted Sheets formula reads from the
    mirrored value instead of inlining a literal.
    """

    model_config = _STRICT_FROZEN

    parameter: ParameterId
    anchor: SheetCellAddress


class OperatorInput(BaseModel):
    """One pre-populated operator-input value.

    Operator inputs are casilla values the caller already knows (for
    example from the ledger or from a previous filing). They are
    written as literal values into the `Entradas` tab; the operator
    is free to overwrite them in the workbook.
    """

    model_config = _STRICT_FROZEN

    casilla: CasillaId
    value: Decimal | str | bool | None = None


class OperatorInputs(BaseModel):
    """Caller-supplied seed values for the `Entradas` tab."""

    model_config = _STRICT_FROZEN

    values: tuple[OperatorInput, ...] = ()

    def by_casilla(self) -> Mapping[CasillaId, OperatorInput]:
        return {item.casilla: item for item in self.values}


class RelationValue(BaseModel):
    """One pre-resolved cross-revision relation value.

    Relations aggregate values from a different modelo's filings
    (typically rolling quarterly filings up into an annual summary).
    The local side resolves them through
    `resolve_relation_values_from_observations` and supplies the
    result here; the engine mirrors it as a scalar cell in `Tarifas`
    so the workbook's formulas can consume it.

    `provenance` carries the source tier the value came from:
    `local_filing` (operator's own prior filing in
    `SecureObjectRepository`), `aeat_live` (remote AEAT Sede
    justificante parse), `operator_manual` (operator entered the
    value into Sheets directly). The engine stamps the provenance
    on the workbook so the pull adapter can detect stale prefills.
    """

    model_config = _STRICT_FROZEN

    relation: RelationId
    value: Decimal | None = None
    provenance: Literal["local_filing", "aeat_live", "operator_manual"] = "operator_manual"
    source_filing_year: int | None = Field(default=None, ge=2000, le=2099)
    source_periods: tuple[str, ...] = ()
    resolved_at: datetime | None = None
    note: str | None = None


class RelationValues(BaseModel):
    """Caller-supplied relation aggregations for the `Tarifas` tab."""

    model_config = _STRICT_FROZEN

    values: tuple[RelationValue, ...] = ()

    def by_relation(self) -> Mapping[RelationId, RelationValue]:
        return {item.relation: item for item in self.values}


class SheetGuideContent(BaseModel):
    """Plain-text content for the `Guía` tab.

    The guide tab is the human-readable preamble: how to use the
    workbook, what each tab contains, and where to find the
    bidirectional sync command. Strings are caller-supplied (the CLI
    surface resolves them through `tr()` so locale parity holds).
    """

    model_config = _STRICT_FROZEN

    title: str = Field(min_length=1)
    paragraphs: tuple[str, ...] = Field(min_length=1)


class SheetExportMetadata(BaseModel):
    """Stamps the workbook with the registry + engine identities.

    Stored both in the workbook's developer metadata (so the pull
    adapter can validate compatibility before merging operator edits)
    and rendered as plain-text in the `Guía` tab so a human reader can
    see provenance at a glance.
    """

    model_config = _STRICT_FROZEN

    modelo_id: str = Field(min_length=1)
    revision_id: RevisionId
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=16)
    engine_version: str = Field(min_length=1)
    registry_sha: str = Field(min_length=8, max_length=64)
    exported_at: datetime

    @model_validator(mode="after")
    def _exported_at_is_utc(self) -> SheetExportMetadata:
        _validate_utc_aware(self.exported_at)
        return self


class SheetExportPlan(BaseModel):
    """Complete description of the workbook the apply adapter will write."""

    model_config = _STRICT_FROZEN

    metadata: SheetExportMetadata
    value_cells: tuple[SheetValueCell, ...] = ()
    formula_cells: tuple[SheetFormulaCell, ...] = ()
    tariffs: tuple[SheetTariffTable, ...] = ()
    provenance: tuple[SheetProvenanceRow, ...] = ()
    protected_ranges: tuple[SheetProtectedRange, ...] = ()
    cell_constraints: tuple[SheetCellConstraint, ...] = ()
    row_sets: tuple[SheetRowSet, ...] = ()
    relation_provenance: RelationValues | None = None
    guide: SheetGuideContent

    def all_addresses(self) -> tuple[SheetCellAddress, ...]:
        seen: list[SheetCellAddress] = []
        for cell in self.value_cells:
            seen.append(cell.address)
        for cell in self.formula_cells:
            seen.append(cell.address)
        return tuple(seen)


__all__ = [
    "OperatorInput",
    "OperatorInputs",
    "ParameterCell",
    "RelationValue",
    "RelationValues",
    "SheetCellAddress",
    "SheetCellConstraint",
    "SheetExportMetadata",
    "SheetExportPlan",
    "SheetFormulaCell",
    "SheetGuideContent",
    "SheetProtectedRange",
    "SheetProvenanceRow",
    "SheetRowSet",
    "SheetRowSetColumn",
    "SheetTariffTable",
    "SheetTariffTableRow",
    "SheetValueCell",
    "TabName",
    "_column_index_to_letters",
    "_column_letters_to_index",
    "_utc_now",
]
