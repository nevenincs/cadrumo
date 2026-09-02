"""Strict records describing workbook plans produced from registry snapshots.

Every record is a frozen pydantic v2 model with `extra="forbid"` so that
schema drift surfaces as validation failures at the moment the engine
assembles the plan rather than as silent payload divergence at the
renderer boundary. The records are intentionally narrow: the engine produces
them, the Google apply adapter and offline XLSX materializer consume them, and
the pull/parity adapters compare incoming workbook cell values back against the
same plan.

A1 addressing
-------------

Workbook cell addresses are expressed by the `SheetCellAddress` record
which carries the human-readable A1 string plus the structured tab
name, row index, and column index. Row and column indices are 1-based
to match Sheets/openpyxl convention. The `a1` string is recomputed from the
tab + row + column at construction time, so callers never hand-roll
A1 strings — they always go through this record.

See Also:
    :class:`cadrumo.domain.calculations.registry.RegistrySnapshot`
        Registry snapshot compiled into these records by the engine.
    :class:`SheetEvidenceFacet`
        Evidence facet carried by the plan and rendered by both workbook
        export paths.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, model_validator

from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.identity import ContentDigest, TransactionId
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.parsing import IsoCurrencyCode
from ....core.period import Period
from ....core.time.clock import now as _utc_now
from ....core.time.utc import validate_utc_aware
from ....domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    ModeloId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ....domain.calculations.registry.schema import DecimalValue as _RegistryDecimalValue
from ....domain.calculations.registry.schema_base import (
    CasillaSignConstraint,
    CasillaSignConstraintValue,
)
from .errors import CalcSheetsRecordError
from .theme import WORKBOOK_FONT_FAMILY, StyleRole

# `DecimalValue` is the registry's annotated `Decimal` with a
# BeforeValidator that coerces int / str inputs through `Decimal(...)`.
# That coercion is appropriate inside registry TOML loading but
# breaks `Decimal | str | bool | None` unions where the validator
# would eagerly try to parse a label string as a Decimal. The
# engine therefore uses plain `Decimal` for fields that mix value
# types, and the imported `_RegistryDecimalValue` only where the
# field is unambiguously a Decimal.
DecimalValue = _RegistryDecimalValue


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
    EVIDENCIA = "Evidencia"
    GUIDE = "Guía"


_A1_COLUMN = re.compile(r"^[A-Z]{1,3}$")


def column_index_to_letters(column: int) -> str:
    """Translate a 1-based column index to an A1 column letter string.

    Converts a positive integer column index (1-based, matching Google
    Sheets' convention) to the corresponding letter sequence used in A1
    notation: 1 → ``"A"``, 26 → ``"Z"``, 27 → ``"AA"``, 702 → ``"ZZ"``.

    Args:
        column: 1-based column index; must be ≥ 1.

    Returns:
        Upper-case letter string, e.g. ``"A"``, ``"B"``, ``"AA"``.

    Raises:
        ``CalcSheetsRecordError``: if ``column`` is less than 1.
    """
    if column < 1:
        raise CalcSheetsRecordError(
            "column index must be 1-based and positive",
            translated_message="application.storage.calc_sheets.records.errors.invalid_column_index",
        )
    letters: list[str] = []
    cursor = column
    while cursor:
        cursor, remainder = divmod(cursor - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def column_letters_to_index(letters: str) -> int:
    """Translate an A1 column letter string to a 1-based column index.

    Inverse of ``column_index_to_letters``. Accepts one to three upper-case
    ASCII letters: ``"A"`` → 1, ``"Z"`` → 26, ``"AA"`` → 27.

    Args:
        letters: Upper-case column identifier matching ``^[A-Z]{1,3}$``.

    Returns:
        1-based integer column index.

    Raises:
        ``CalcSheetsRecordError``: if ``letters`` does not match the expected
            pattern.
    """
    if not _A1_COLUMN.match(letters):
        raise CalcSheetsRecordError(
            "invalid Sheets column letters",
            context={"letters_length": len(letters)},
            translated_message="application.storage.calc_sheets.records.errors.invalid_column_letters",
        )
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
        letters = column_index_to_letters(self.column)
        expected = f"{letters}{self.row}"
        if self.a1 != expected:
            raise CalcSheetsRecordError(
                "sheet cell A1 address does not match row and column",
                context={"row": self.row, "column": self.column},
                translated_message="application.storage.calc_sheets.records.errors.address_mismatch",
            )
        return self

    @classmethod
    def at(cls, tab: TabName, row: int, column: int) -> SheetCellAddress:
        """Construct a ``SheetCellAddress`` from tab, row, and column indices.

        Derives the ``a1`` string automatically so callers never hand-roll A1
        notation.

        Args:
            tab: ``TabName`` enum member identifying the workbook tab.
            row: 1-based row index.
            column: 1-based column index.

        Returns:
            :class:`SheetCellAddress`: A validated ``SheetCellAddress`` instance.
        """
        letters = column_index_to_letters(column)
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
    casilla_id: CasillaId | None = None
    parameter: ParameterId | None = None
    role: Literal["operator_input", "parameter_value", "label", "metadata"]


class SheetRoundingRule(StrEnum):
    """How a computed sheet value is rounded before it is written.

    Distinct from the casilla data-type vocabulary, which also carries ``money`` and
    ``integer``: that one says what a value IS, this one says how it is rounded. A
    ratio is a data type and never a rounding rule, and ``integer-ceiling`` is a
    rounding rule and never a data type.
    """

    MONEY = "money"
    INTEGER = "integer"
    INTEGER_CEILING = "integer-ceiling"
    NONE = "none"


SheetRoundingRuleValue = Literal[
    SheetRoundingRule.MONEY,
    SheetRoundingRule.INTEGER,
    SheetRoundingRule.INTEGER_CEILING,
    SheetRoundingRule.NONE,
]
"""The same rule for a strict record field."""


class SheetFormulaCell(BaseModel):
    """A computed cell whose value comes from a Sheets formula.

    The formula string is exactly what is sent to the Sheets API,
    minus the leading "=" sign (the apply adapter prepends it). It
    must already be A1-resolved.
    """

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    formula: str = Field(min_length=1)
    casilla_id: CasillaId
    rounding_scale: int | None = Field(default=None, ge=0, le=12)
    rounding_rule: SheetRoundingRuleValue
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
    sign: CasillaSignConstraintValue = CasillaSignConstraint.ANY
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    casilla_id: CasillaId


class SheetRowSetColumn(BaseModel):
    """One column of a `SheetRowSet`, mapping a binding id to a header cell."""

    model_config = _STRICT_FROZEN

    binding: BindingId
    header_address: SheetCellAddress
    header_label: str = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)


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
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


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
            raise CalcSheetsRecordError(
                "range end row must be on or after start row",
                context={"range_kind": "protected"},
                translated_message="application.storage.calc_sheets.records.errors.range_malformed",
            )
        if self.end_column < self.start_column:
            raise CalcSheetsRecordError(
                "range end column must be on or after start column",
                context={"range_kind": "protected"},
                translated_message="application.storage.calc_sheets.records.errors.range_malformed",
            )
        return self


class SheetNumberFormat(BaseModel):
    """Display-format directive for a numeric workbook cell."""

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    casilla_id: CasillaId
    data_type: Literal["money", "integer", "percentage"]
    pattern: str = Field(min_length=1)


class SheetSectionHeader(BaseModel):
    """Section-header styling directive for a section's first label cell.

    Marks the column-A cell where a casilla section first appears so both
    transports render it as a bold section header — the official AEAT workbooks
    group casillas under bold section banners for operator orientation.
    """

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    text: str = Field(min_length=1)


class SheetAnchor(BaseModel):
    """An explicit labelled start / final anchor on the calculation flow.

    ``start`` marks the opening of the operator-input region (Entradas); ``final``
    marks the filing result (resultado / cuota) on Cálculos. Rendered as a
    labelled cell in both transports so the inputs→resultado flow is
    unambiguously oriented, mirroring the published workbook layout.
    """

    model_config = _STRICT_FROZEN

    address: SheetCellAddress
    kind: Literal["start", "final"]
    label: str = Field(min_length=1)


class SheetStyledRange(BaseModel):
    """A contiguous range tagged with a presentation role.

    The engine emits one styled range per role-region (the header band, each
    section banner, the operator-input column, the computed column, the result
    cell, wrapped body columns). Both transports resolve ``role`` to a concrete
    fill / font / alignment through the shared ``theme`` palette, so the offline
    xls and online Sheets render the same look from the same declaration. Later
    ranges win on overlap, so a narrow accent range (e.g. ``result``) may be
    emitted after the broad column range it refines.
    """

    model_config = _STRICT_FROZEN

    tab: TabName
    start_row: int = Field(ge=1)
    end_row: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_column: int = Field(ge=1)
    role: StyleRole
    wrap: bool = False

    @model_validator(mode="after")
    def _range_well_formed(self) -> SheetStyledRange:
        if self.end_row < self.start_row:
            raise CalcSheetsRecordError(
                "range end row must be on or after start row",
                context={"range_kind": "styled"},
                translated_message="application.storage.calc_sheets.records.errors.range_malformed",
            )
        if self.end_column < self.start_column:
            raise CalcSheetsRecordError(
                "range end column must be on or after start column",
                context={"range_kind": "styled"},
                translated_message="application.storage.calc_sheets.records.errors.range_malformed",
            )
        return self


class SheetColumnWidth(BaseModel):
    """A per-tab column width in approximate character units.

    The offline renderer applies it as an openpyxl ``column_dimensions`` width;
    the online renderer converts it to a pixel size (``~7 px`` per character)
    for ``updateDimensionProperties``. Sized so concept labels and legal-ref
    columns read without clipping.
    """

    model_config = _STRICT_FROZEN

    tab: TabName
    column: int = Field(ge=1)
    width: int = Field(ge=1, le=255)


class SheetFrozenView(BaseModel):
    """Per-tab frozen header rows / leading columns.

    Freezes the column-title row (and, where useful, the leading label columns)
    so the header stays visible while an operator scrolls a long modelo.
    """

    model_config = _STRICT_FROZEN

    tab: TabName
    frozen_rows: int = Field(ge=0, default=0)
    frozen_columns: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def _at_least_one(self) -> SheetFrozenView:
        if self.frozen_rows == 0 and self.frozen_columns == 0:
            raise CalcSheetsRecordError(
                "a frozen view must freeze at least one row or column",
                translated_message="application.storage.calc_sheets.records.errors.frozen_view_empty",
            )
        return self


class SheetAutoFilter(BaseModel):
    """A per-tab basic-filter range over the header row plus its data rows.

    Lets the operator sort / filter the tab by section or concept. Offline maps
    it to ``worksheet.auto_filter.ref``; online to ``setBasicFilter``.
    """

    model_config = _STRICT_FROZEN

    tab: TabName
    start_row: int = Field(ge=1)
    end_row: int = Field(ge=1)
    start_column: int = Field(ge=1)
    end_column: int = Field(ge=1)

    @model_validator(mode="after")
    def _range_well_formed(self) -> SheetAutoFilter:
        if self.end_row < self.start_row:
            raise CalcSheetsRecordError(
                "range end row must be on or after start row",
                context={"range_kind": "auto_filter"},
                translated_message="application.storage.calc_sheets.records.errors.range_malformed",
            )
        if self.end_column < self.start_column:
            raise CalcSheetsRecordError(
                "range end column must be on or after start column",
                context={"range_kind": "auto_filter"},
                translated_message="application.storage.calc_sheets.records.errors.range_malformed",
            )
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
    display_number: str
    casilla_label: str
    formula_id: FormulaId | None = None
    rounding_rule: SheetRoundingRuleValue
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    target_address: SheetCellAddress


class SheetEvidenceContributorRow(BaseModel):
    """One ledger contributor rendered into the workbook evidence surface."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    transaction_id: TransactionId
    amount: Decimal
    currency: IsoCurrencyCode
    # Euro projection of a foreign-currency contributor, mirroring the domain
    # evidence row. The casilla this row explains is denominated in euro, so an
    # evidence surface showing only the native amount cannot be reconciled
    # against it; both are rendered. Absent for a euro contributor, where the
    # native amount already is the euro amount.
    fx_rate: Decimal | None = None
    value_in_eur: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    counterparty: str | None = None
    attachment_ids: tuple[str, ...] = ()
    document_link_ids: tuple[str, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class SheetEvidenceManualEntry(BaseModel):
    """One non-ledger fact basis entry rendered into the evidence surface."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    note: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class SheetEvidenceFacet(BaseModel):
    """Evidence rows attached to a workbook export plan.

    Contributor rows carry ledger-derived transaction facts by casilla; manual
    entries carry non-ledger fact basis values. The offline serializer writes
    this facet to both the Evidencia worksheet and the adjacent JSON sidecar.
    """

    model_config = _STRICT_FROZEN

    snapshot_fingerprint: ContentDigest | None = None
    contributor_rows: tuple[SheetEvidenceContributorRow, ...] = ()
    manual_entries: tuple[SheetEvidenceManualEntry, ...] = ()


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
                raise CalcSheetsRecordError(
                    "tariff table shape is invalid",
                    context={"data_type": self.data_type, "reason": "missing_bracket_rows"},
                    translated_message="application.storage.calc_sheets.records.errors.tariff_shape_invalid",
                )
            if self.scalar_value is not None:
                raise CalcSheetsRecordError(
                    "tariff table shape is invalid",
                    context={"data_type": self.data_type, "reason": "unexpected_scalar_value"},
                    translated_message="application.storage.calc_sheets.records.errors.tariff_shape_invalid",
                )
        else:
            if self.scalar_value is None:
                raise CalcSheetsRecordError(
                    "tariff table shape is invalid",
                    context={"data_type": self.data_type, "reason": "missing_scalar_value"},
                    translated_message="application.storage.calc_sheets.records.errors.tariff_shape_invalid",
                )
            if self.bracket_rows:
                raise CalcSheetsRecordError(
                    "tariff table shape is invalid",
                    context={"data_type": self.data_type, "reason": "unexpected_bracket_rows"},
                    translated_message="application.storage.calc_sheets.records.errors.tariff_shape_invalid",
                )
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

    casilla_id: CasillaId
    value: Decimal | str | bool | None = None


class OperatorInputs(BaseModel):
    """Caller-supplied seed values for the `Entradas` tab."""

    model_config = _STRICT_FROZEN

    values: tuple[OperatorInput, ...] = ()

    def by_casilla_id(self) -> Mapping[CasillaId, OperatorInput]:
        """Return a ``CasillaId`` -> ``OperatorInput`` lookup mapping.

        Returns:
            Mapping[CasillaId, :class:`OperatorInput`]: A ``Mapping`` keyed by canonical casilla.id. Later
            duplicates overwrite earlier ones; the registry enforces
            uniqueness so duplicates are not expected in practice.
        """
        return {item.casilla_id: item for item in self.values}


class SheetRelationProvenance(StrEnum):
    """Where a spreadsheet relation cell's value came from.

    Deliberately coarser than :class:`ObservationSourceKind`, which splits the AEAT
    origins three ways for filing-grade evidence. This vocabulary answers a narrower
    question the workbook actually renders -- did the operator type it, did a local
    filing supply it, or did it come off AEAT -- and the two share the
    ``operator_manual`` token without being the same set. They must not be unified:
    collapsing them would let a sheet claim a filing-grade AEAT origin it never
    established.
    """

    LOCAL_FILING = "local_filing"
    """Derived from a filing this installation holds locally."""

    AEAT_LIVE = "aeat_live"
    """Observed from AEAT, without distinguishing which AEAT surface supplied it."""

    OPERATOR_MANUAL = "operator_manual"
    """Typed by the operator, carrying no external evidence of its own."""


SheetRelationProvenanceValue = Literal[
    SheetRelationProvenance.LOCAL_FILING,
    SheetRelationProvenance.AEAT_LIVE,
    SheetRelationProvenance.OPERATOR_MANUAL,
]
"""The same vocabulary for a strict record or CLI payload field.

A bare enum under strict validation refuses the plain token a serialised row carries,
so those fields take this literal over the members above rather than restating them.
"""


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
    The `source_*` and ref fields mirror the registry relation so the
    scalar workbook value remains joinable back to its official source
    modelo, source casilla, and legal grounding.
    """

    model_config = _STRICT_FROZEN

    relation: RelationId
    value: Decimal | None = None
    #: The registry's declared dependency treatment for this carry, empty when the
    #: revision declares none. A ``factual_evidence`` carry is a fact to reconcile
    #: against rather than a figure that settles the return, and a consumer must be
    #: able to tell it from a ``direct_annual_settlement`` one. Carried here rather
    #: than gated here: the value is NOT withheld, because a taxpayer is entitled to
    #: a suffered retención and dropping it silently is an over-declaration. Empty
    #: means the revision declared no treatment, which is not the same as any
    #: particular one and must never be read as one.
    dependency_treatment: str = ""
    provenance: SheetRelationProvenanceValue = SheetRelationProvenance.OPERATOR_MANUAL
    source_modelo: ModeloId | None = None
    source_filing_year: FilingYear | None = None
    source_periods: tuple[str, ...] = ()
    source_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    resolved_at: datetime | None = None
    note: str | None = None


class RelationValues(BaseModel):
    """Caller-supplied relation aggregations for the `Tarifas` tab."""

    model_config = _STRICT_FROZEN

    values: tuple[RelationValue, ...] = ()

    def by_relation(self) -> Mapping[RelationId, RelationValue]:
        """Return a ``RelationId`` → ``RelationValue`` lookup mapping.

        Returns:
            Mapping[RelationId, :class:`RelationValue`]: A ``Mapping`` keyed by relation id
            for fast lookup when the engine resolves cross-revision formula references.
        """
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
    filing_year: FilingYear
    period: Period
    engine_version: str = Field(min_length=1)
    registry_sha: str = Field(min_length=8, max_length=64, pattern=r"^[0-9a-f]+$")
    exported_at: datetime

    @model_validator(mode="after")
    def _exported_at_is_utc(self) -> SheetExportMetadata:
        validate_utc_aware(self.exported_at)
        return self

    @model_validator(mode="after")
    def _period_year_matches_metadata(self) -> SheetExportMetadata:
        if self.period.filing_year != self.filing_year:
            raise ValueError(
                f"metadata filing_year {self.filing_year} does not match period year {self.period.filing_year}",
            )
        return self

    @field_serializer("period", mode="plain")
    def _serialize_period(self, value: Period) -> dict[str, object]:
        return {"filing_year": value.filing_year, "code": value.code}


class SheetExportPlan(BaseModel):
    """Complete description of the workbook every renderer will write.

    The plan is the shared contract between the registry-backed engine, Google
    Sheets apply adapter, offline XLSX materializer, pull adapter, and parity
    harness. It includes calculation cells, protected ranges, display facets,
    registry metadata, relation provenance, row sets, and workbook evidence.
    """

    model_config = _STRICT_FROZEN

    metadata: SheetExportMetadata
    value_cells: tuple[SheetValueCell, ...] = ()
    formula_cells: tuple[SheetFormulaCell, ...] = ()
    tariffs: tuple[SheetTariffTable, ...] = ()
    provenance: tuple[SheetProvenanceRow, ...] = ()
    protected_ranges: tuple[SheetProtectedRange, ...] = ()
    number_formats: tuple[SheetNumberFormat, ...] = ()
    section_headers: tuple[SheetSectionHeader, ...] = ()
    anchors: tuple[SheetAnchor, ...] = ()
    cell_constraints: tuple[SheetCellConstraint, ...] = ()
    row_sets: tuple[SheetRowSet, ...] = ()
    relation_provenance: RelationValues | None = None
    evidence: SheetEvidenceFacet = Field(default_factory=SheetEvidenceFacet)
    font_family: str = Field(default=WORKBOOK_FONT_FAMILY, min_length=1)
    styled_ranges: tuple[SheetStyledRange, ...] = ()
    column_widths: tuple[SheetColumnWidth, ...] = ()
    frozen_views: tuple[SheetFrozenView, ...] = ()
    auto_filters: tuple[SheetAutoFilter, ...] = ()
    guide: SheetGuideContent

    @model_validator(mode="after")
    def _writable_cells_are_unique(self) -> SheetExportPlan:
        seen: set[tuple[TabName, int, int]] = set()
        duplicate_count = 0
        for address in self.all_addresses():
            key = (address.tab, address.row, address.column)
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
        if duplicate_count:
            raise CalcSheetsRecordError(
                "sheet export plan writes more than one payload to the same cell address",
                context={"duplicate_count": duplicate_count},
                translated_message="application.storage.calc_sheets.records.errors.duplicate_write_address",
            )
        return self

    def all_addresses(self) -> tuple[SheetCellAddress, ...]:
        """Return every cell address referenced by value or formula cells.

        Useful for collision detection and for building the full write list
        before sending requests to the Sheets API.

        Returns:
            tuple[:class:`SheetCellAddress`, ...]: objects from ``value_cells``
            followed by those from ``formula_cells``, in declaration order.
        """
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
    "SheetAnchor",
    "SheetAutoFilter",
    "SheetCellAddress",
    "SheetCellConstraint",
    "SheetColumnWidth",
    "SheetEvidenceContributorRow",
    "SheetEvidenceFacet",
    "SheetEvidenceManualEntry",
    "SheetExportMetadata",
    "SheetExportPlan",
    "SheetFormulaCell",
    "SheetFrozenView",
    "SheetGuideContent",
    "SheetNumberFormat",
    "SheetProtectedRange",
    "SheetProvenanceRow",
    "SheetRowSet",
    "SheetRowSetColumn",
    "SheetSectionHeader",
    "SheetStyledRange",
    "SheetTariffTable",
    "SheetTariffTableRow",
    "SheetValueCell",
    "TabName",
    "_utc_now",
    "column_index_to_letters",
    "column_letters_to_index",
]
