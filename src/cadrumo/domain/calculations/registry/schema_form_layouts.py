"""Declared form layout of one modelo revision: pages, sections, blocks and placements.

A revision's casillas carry no page, row or column: their section path is the
wrong grain for a printed form and their declaration order is uncorrelated with
it. The official record design and the Renta dictionary do state that
structure, so a development-time generator reads them and declares it here, one
layout per revision, compiled and published with the revision it describes.
The runtime joins this declaration with live values; it never derives layout.

The family is total over the revision. Every casilla has exactly one
:class:`FormPlacementDefinition`: on the form (with its official box number and
any other official position it also appears at), a working figure the
application computes and the official form does not print, or unplaced with a
closed reason. Nothing is dropped silently, and an edit always addresses a
casilla or binding by id, never a position, so a grouping mistake can mislead
the eye but cannot misfile a value.

Headings are declared twice on purpose. ``heading_key`` names the catalogue
entry a reviewer translates; ``official_heading`` quotes the design's own
Spanish words verbatim, as provenance and as the disclosed fallback when no
translation exists. Neither is ever produced by humanising a technical token.

Page conditions are a closed set of structural facts the registry already
declares (an optional export record, a record gated on a positive casilla, a
period-restricted record). Prose notes in a design are not parsed into
conditions: an undeclared condition stays ``always``.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BeforeValidator, Field, model_validator

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.identity.aeat_box import AeatBoxNumber
from .errors import RegistryValidationError
from .ids import BindingId, RecordId, RevisionId, SourceRefId
from .schema_base import RegistryModel, coerce_enum_member

__all__ = [
    "FORM_LAYOUT_GENERATOR_VERSION",
    "FormAliasPosition",
    "FormBindingInputsBlock",
    "FormBlockDefinition",
    "FormCell",
    "FormCellKind",
    "FormDesignSource",
    "FormFieldBlock",
    "FormGridBlock",
    "FormGridColumn",
    "FormGridRow",
    "FormLayoutDefinition",
    "FormLayoutReview",
    "FormLayoutReviewState",
    "FormLayoutSeedSource",
    "FormPageCondition",
    "FormPageDefinition",
    "FormPlacementDefinition",
    "FormPlacementKind",
    "FormRepeatingColumn",
    "FormRepeatingGroupBlock",
    "FormRepeatingRowSource",
    "FormSectionDefinition",
    "FormUnplacedReason",
]

#: Version of the generator contract a layout was produced under. Part of the
#: generator's drift check, so a generator change that alters output is visible
#: as stale layouts rather than as a silent reshuffle.
FORM_LAYOUT_GENERATOR_VERSION: Final[int] = 1

_NODE_ID_RE: Final[str] = r"^[a-z0-9][a-z0-9_-]*$"
_HEADING_KEY_RE: Final[str] = r"^[a-z0-9][a-z0-9_]*(\.[a-z0-9][a-z0-9_-]*)+$"
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")

type FormNodeId = Annotated[str, Field(min_length=1, max_length=96, pattern=_NODE_ID_RE)]
"""A page, section, block, row or column id, stable within its layout."""

type FormHeadingKey = Annotated[str, Field(min_length=3, max_length=200, pattern=_HEADING_KEY_RE)]
"""A catalogue key naming a heading; the catalogue may not yet translate it."""

type OfficialHeading = Annotated[str, Field(min_length=1, max_length=400)]
"""The official design's own Spanish words, quoted verbatim."""


class FormLayoutSeedSource(StrEnum):
    """The official anchor family the layout's order and grouping were seeded from."""

    #: Fixed-width export offsets joined to the record design's descriptions.
    EXPORT_RECORD_DESIGN = "export_record_design"
    #: The Renta dictionary line order and its XML schema element tree.
    XML_DICTIONARY = "xml_dictionary"
    #: The design's printed ``[NN]`` box numbers, without export offsets.
    DESIGN_BOX_NUMBER = "design_box_number"
    #: Numeric casilla numbers only; no official heading is available.
    CASILLA_NUMBER = "casilla_number"
    #: A reviewer declared the structure.
    AUTHORED = "authored"


class FormLayoutReviewState(StrEnum):
    """Whether a person has reviewed the declaration."""

    #: Generator output: shipped and editable with a visible disclosure.
    GENERATED = "generated"
    #: Promoted by a named reviewer on a date.
    REVIEWED = "reviewed"


class FormPageCondition(StrEnum):
    """The closed set of structurally declared page conditions."""

    ALWAYS = "always"
    #: The page's export record is optional.
    OPTIONAL_RECORD = "optional_record"
    #: The page's export record is emitted only when a casilla is positive.
    REQUIRES_POSITIVE_CASILLA = "requires_positive_casilla"
    #: The page applies only in the named periods.
    PERIOD_RESTRICTED = "period_restricted"


class FormPlacementKind(StrEnum):
    """Where a casilla sits in the layout."""

    #: At its official position on a page.
    ON_FORM = "on_form"
    #: An application figure the official form does not print, shown under calculation details.
    WORKING_FIGURE = "working_figure"
    #: Declared without a position, with a closed reason.
    UNPLACED = "unplaced"


class FormUnplacedReason(StrEnum):
    """Why a casilla has no position on the form."""

    NO_OFFICIAL_ANCHOR = "no_official_anchor"
    AMBIGUOUS_ANCHOR = "ambiguous_anchor"
    ANCHOR_CONFLICTS_WITH_SECTION = "anchor_conflicts_with_section"
    PENDING_REVIEW = "pending_review"


class FormCellKind(StrEnum):
    """What one grid cell holds."""

    CASILLA = "casilla"
    BINDING_INPUT = "binding_input"
    #: A value the official design fixes; the edit surface never offers it.
    DESIGN_CONSTANT = "design_constant"
    #: The paper form has no box at this row and column.
    BLANK = "blank"


class FormRepeatingRowSource(StrEnum):
    """The declared row set a repeating group ranges over."""

    ROW_SET_BINDING = "row_set_binding"
    EXPORT_RECORD = "export_record"


FormLayoutSeedSourceField = Annotated[FormLayoutSeedSource, BeforeValidator(coerce_enum_member(FormLayoutSeedSource))]
FormLayoutReviewStateField = Annotated[
    FormLayoutReviewState, BeforeValidator(coerce_enum_member(FormLayoutReviewState))
]
FormPageConditionField = Annotated[FormPageCondition, BeforeValidator(coerce_enum_member(FormPageCondition))]
FormPlacementKindField = Annotated[FormPlacementKind, BeforeValidator(coerce_enum_member(FormPlacementKind))]
FormUnplacedReasonField = Annotated[FormUnplacedReason, BeforeValidator(coerce_enum_member(FormUnplacedReason))]
FormCellKindField = Annotated[FormCellKind, BeforeValidator(coerce_enum_member(FormCellKind))]
FormRepeatingRowSourceField = Annotated[
    FormRepeatingRowSource, BeforeValidator(coerce_enum_member(FormRepeatingRowSource))
]


def _require_unique(owner: str, kind: str, values: tuple[str, ...]) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise RegistryValidationError(f"{owner} declares duplicate {kind} {duplicates!r}")


class FormLayoutReview(RegistryModel):
    """The review state of one layout, with the reviewer bound to a review claim."""

    state: FormLayoutReviewStateField = FormLayoutReviewState.GENERATED
    reviewer: str | None = Field(default=None, min_length=1, max_length=128)
    reviewed_at: date | None = None
    notes: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _bind_reviewer_to_review(self) -> FormLayoutReview:
        """Refuse a review claim without a reviewer and date, or a reviewer on generator output."""
        reviewed = self.state is FormLayoutReviewState.REVIEWED
        attributed = self.reviewer is not None and self.reviewed_at is not None
        if reviewed and not attributed:
            raise RegistryValidationError("a reviewed form layout names its reviewer and review date")
        if not reviewed and (self.reviewer is not None or self.reviewed_at is not None):
            raise RegistryValidationError("a generated form layout carries no reviewer or review date")
        return self


class FormDesignSource(RegistryModel):
    """One official source file the generator read, pinned by content digest."""

    source_ref: SourceRefId
    sha256: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _digest_is_sha256(self) -> FormDesignSource:
        if _SHA256_RE.fullmatch(self.sha256) is None:
            raise RegistryValidationError(f"design source {self.source_ref!r} digest is not a lowercase SHA-256")
        return self


class FormCell(RegistryModel):
    """One grid cell: a casilla, a binding input, a design constant with its literal, or a blank.

    A design-constant cell may name the casilla printed at that box: the
    official design fixes the value the fichero carries there, so the box is
    shown with the design's literal and is never offered for editing.
    """

    kind: FormCellKindField
    casilla_id: CasillaId | None = None
    binding_id: BindingId | None = None
    literal: str | None = Field(default=None, min_length=1, max_length=64)
    literal_decimals: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _kind_owns_its_payload(self) -> FormCell:
        """Refuse a cell whose payload disagrees with its kind."""
        expected = {
            FormCellKind.CASILLA: ((True,), False),
            FormCellKind.BINDING_INPUT: ((False,), True),
            FormCellKind.DESIGN_CONSTANT: ((True, False), False),
            FormCellKind.BLANK: ((False,), False),
        }[self.kind]
        if (self.casilla_id is not None) not in expected[0] or (self.binding_id is not None) != expected[1]:
            raise RegistryValidationError(f"form cell of kind {self.kind.value!r} names the wrong address")
        if self.kind is FormCellKind.DESIGN_CONSTANT and self.literal is None:
            raise RegistryValidationError("a design-constant form cell must carry the design's literal")
        if self.kind is not FormCellKind.DESIGN_CONSTANT and self.literal is not None:
            raise RegistryValidationError(f"form cell of kind {self.kind.value!r} carries a literal")
        _validate_literal_scale(self.literal, self.literal_decimals)
        return self


def _validate_literal_scale(literal: str | None, decimals: int | None) -> None:
    """A numeric scale belongs only to an ASCII digit constant of sufficient width."""
    if decimals is not None and (
        literal is None or not literal.isascii() or not literal.isdigit() or decimals >= len(literal)
    ):
        raise RegistryValidationError("literal decimals require a numeric constant with an integer digit")


class FormGridColumn(RegistryModel):
    """One grid column, keyed into the shared column vocabulary where it matches."""

    key: FormNodeId
    heading_key: FormHeadingKey
    official_heading: OfficialHeading | None = None


class FormGridRow(RegistryModel):
    """One official printed row; ``cells`` align positionally with the grid's columns."""

    key: FormNodeId
    heading_key: FormHeadingKey
    official_heading: OfficialHeading | None = None
    cells: tuple[FormCell, ...] = Field(min_length=1)


class FormFieldBlock(RegistryModel):
    """One vertical label/value line addressing a casilla or a binding.

    ``design_constant`` carries the literal the official design fixes for the
    casilla's box; such a field is shown, never edited.
    """

    kind: Literal["field"] = "field"
    id: FormNodeId
    casilla_id: CasillaId | None = None
    binding_id: BindingId | None = None
    design_constant: str | None = Field(default=None, min_length=1, max_length=64)
    literal_decimals: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_address(self) -> FormFieldBlock:
        if (self.casilla_id is None) == (self.binding_id is None):
            raise RegistryValidationError(f"form field block {self.id!r} addresses exactly one casilla or binding")
        if self.design_constant is not None and self.casilla_id is None:
            raise RegistryValidationError(f"form field block {self.id!r} fixes a design constant on no casilla")
        _validate_literal_scale(self.design_constant, self.literal_decimals)
        return self


class FormGridBlock(RegistryModel):
    """Official rows and columns, each cell positional against ``columns``."""

    kind: Literal["grid"] = "grid"
    id: FormNodeId
    columns: tuple[FormGridColumn, ...] = Field(min_length=2)
    rows: tuple[FormGridRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _rows_match_columns(self) -> FormGridBlock:
        """Refuse a row whose width differs from the column count, and duplicate keys."""
        owner = f"form grid {self.id!r}"
        _require_unique(owner, "column keys", tuple(column.key for column in self.columns))
        _require_unique(owner, "row keys", tuple(row.key for row in self.rows))
        width = len(self.columns)
        for row in self.rows:
            if len(row.cells) != width:
                raise RegistryValidationError(
                    f"{owner} row {row.key!r} has {len(row.cells)} cells for {width} columns",
                )
        return self


class FormRepeatingColumn(RegistryModel):
    """One column of a repeating group, optionally projecting a declared casilla."""

    key: FormNodeId
    heading_key: FormHeadingKey
    official_heading: OfficialHeading | None = None
    casilla_id: CasillaId | None = None


class FormRepeatingGroupBlock(RegistryModel):
    """Open detail rows over a row-set binding or a repeating export record; never flattened."""

    kind: Literal["repeating"] = "repeating"
    id: FormNodeId
    row_source: FormRepeatingRowSourceField
    binding_id: BindingId | None = None
    export_record_id: RecordId | None = None
    min_rows: int = Field(default=0, ge=0)
    max_rows: int | None = Field(default=None, ge=1)
    columns: tuple[FormRepeatingColumn, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _source_matches_kind(self) -> FormRepeatingGroupBlock:
        """Refuse a row source whose address disagrees with its declared kind."""
        owner = f"form repeating group {self.id!r}"
        by_binding = self.row_source is FormRepeatingRowSource.ROW_SET_BINDING
        if by_binding != (self.binding_id is not None) or by_binding == (self.export_record_id is not None):
            raise RegistryValidationError(f"{owner} row source {self.row_source.value!r} names the wrong address")
        if self.max_rows is not None and self.max_rows < self.min_rows:
            raise RegistryValidationError(f"{owner} declares max_rows below min_rows")
        _require_unique(owner, "column keys", tuple(column.key for column in self.columns))
        return self


class FormBindingInputsBlock(RegistryModel):
    """Manual-input bindings no casilla owns, presented as first-class fields."""

    kind: Literal["binding_inputs"] = "binding_inputs"
    id: FormNodeId
    binding_ids: tuple[BindingId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _unique_bindings(self) -> FormBindingInputsBlock:
        _require_unique(f"form binding-inputs block {self.id!r}", "bindings", self.binding_ids)
        return self


FormBlockDefinition = Annotated[
    FormFieldBlock | FormGridBlock | FormRepeatingGroupBlock | FormBindingInputsBlock,
    Field(discriminator="kind"),
]
"""Closed union of the blocks a section may hold, discriminated on ``kind``."""


class FormSectionDefinition(RegistryModel):
    """One apartado of a page with its heading and ordered blocks."""

    id: FormNodeId
    heading_key: FormHeadingKey
    official_heading: OfficialHeading | None = None
    blocks: tuple[FormBlockDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _unique_blocks(self) -> FormSectionDefinition:
        _require_unique(f"form section {self.id!r}", "block ids", tuple(block.id for block in self.blocks))
        return self


class FormPageDefinition(RegistryModel):
    """One official page with its structurally declared condition and ordered sections."""

    id: FormNodeId
    official_ref: str | None = Field(default=None, min_length=1, max_length=128)
    heading_key: FormHeadingKey
    official_heading: OfficialHeading | None = None
    condition: FormPageConditionField = FormPageCondition.ALWAYS
    condition_casilla_id: CasillaId | None = None
    condition_periods: tuple[str, ...] = ()
    sections: tuple[FormSectionDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _condition_carries_its_operand(self) -> FormPageDefinition:
        """Refuse a condition missing its operand, or an operand without its condition."""
        owner = f"form page {self.id!r}"
        gated = self.condition is FormPageCondition.REQUIRES_POSITIVE_CASILLA
        if gated != (self.condition_casilla_id is not None):
            raise RegistryValidationError(f"{owner} condition {self.condition.value!r} disagrees with its casilla")
        restricted = self.condition is FormPageCondition.PERIOD_RESTRICTED
        if restricted != bool(self.condition_periods):
            raise RegistryValidationError(f"{owner} condition {self.condition.value!r} disagrees with its periods")
        _require_unique(owner, "section ids", tuple(section.id for section in self.sections))
        return self


class FormAliasPosition(RegistryModel):
    """Another official position the same box also appears at; never editable twice."""

    page_id: FormNodeId
    section_id: FormNodeId
    official_ref: str | None = Field(default=None, min_length=1, max_length=128)


class FormPlacementDefinition(RegistryModel):
    """The one placement every casilla of the revision carries."""

    casilla_id: CasillaId
    kind: FormPlacementKindField
    unplaced_reason: FormUnplacedReasonField | None = None
    box_number: AeatBoxNumber | None = None
    aliases: tuple[FormAliasPosition, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _kind_owns_its_detail(self) -> FormPlacementDefinition:
        """Refuse a reason off the unplaced arm, or aliases off the on-form arm."""
        owner = f"form placement {self.casilla_id!r}"
        if (self.kind is FormPlacementKind.UNPLACED) != (self.unplaced_reason is not None):
            raise RegistryValidationError(f"{owner}: an unplaced reason belongs to, and only to, the unplaced arm")
        if self.aliases and self.kind is not FormPlacementKind.ON_FORM:
            raise RegistryValidationError(f"{owner}: only an on-form placement has alias positions")
        return self


class FormLayoutDefinition(RegistryModel):
    """The declared form layout of exactly one revision.

    ``source_state_digest`` is the digest of the revision facts the layout was
    generated from (its casillas, the bindings it places and the export
    structure it reads); a layout whose digest no longer matches its revision
    is stale and refused. ``design_sources`` pins the official files the
    headings were quoted from, and ``seed_source`` names the anchor family.

    The layout carries no ``legal_refs`` or ``source_refs`` of its own. It is
    derived presentation, and copying its revision's citations onto it would
    make every manifest reference look cited by an authored child.
    """

    id: FormNodeId
    revision_id: RevisionId
    seed_source: FormLayoutSeedSourceField
    review: FormLayoutReview = Field(default_factory=FormLayoutReview)
    generator_version: int = Field(ge=1)
    source_state_digest: str = Field(min_length=64, max_length=64)
    design_sources: tuple[FormDesignSource, ...] = ()
    pages: tuple[FormPageDefinition, ...] = ()
    placements: tuple[FormPlacementDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _layout_is_internally_consistent(self) -> FormLayoutDefinition:
        """Refuse duplicate ids, duplicate placements and dangling alias positions."""
        owner = f"form layout {self.id!r}"
        if _SHA256_RE.fullmatch(self.source_state_digest) is None:
            raise RegistryValidationError(f"{owner} source_state_digest is not a lowercase SHA-256")
        _require_unique(owner, "page ids", tuple(page.id for page in self.pages))
        _require_unique(owner, "placements for casillas", tuple(item.casilla_id for item in self.placements))
        _require_unique(owner, "design sources", tuple(item.source_ref for item in self.design_sources))
        sections = {(page.id, section.id) for page in self.pages for section in page.sections}
        for placement in self.placements:
            for alias in placement.aliases:
                if (alias.page_id, alias.section_id) not in sections:
                    raise RegistryValidationError(
                        f"{owner} placement {placement.casilla_id!r} aliases unknown section "
                        f"{alias.page_id!r}/{alias.section_id!r}",
                    )
        return self

    def casilla_sections(self) -> dict[str, tuple[str, str]]:
        """Return each casilla shown on the form mapped to its ``(page id, section id)``.

        Every casilla a block addresses -- a field, a grid cell (including a
        design-constant cell) or a repeating-group column -- is listed once, at
        the section that shows it; alias positions are not included.
        """
        found: dict[str, tuple[str, str]] = {}
        for page in self.pages:
            for section in page.sections:
                for block in section.blocks:
                    for casilla_id in _block_casilla_ids(block):
                        found.setdefault(casilla_id, (page.id, section.id))
        return found


def _block_casilla_ids(block: FormBlockDefinition) -> tuple[str, ...]:
    if isinstance(block, FormFieldBlock):
        return () if block.casilla_id is None else (block.casilla_id,)
    if isinstance(block, FormGridBlock):
        return tuple(cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None)
    if isinstance(block, FormRepeatingGroupBlock):
        return tuple(column.casilla_id for column in block.columns if column.casilla_id is not None)
    return ()
