"""Walk a declared form layout once, classify every box it places and account for each placement.

This walk decides everything about a layout's boxes that the filing facts rest
on: which casilla each block shows and which block only repeats one shown
elsewhere, which value the design fixes, whether each page applies, what a
page that does not apply still asks, and what a table of records holds. It
refuses a layout that places a casilla twice, off the form or not at all. The
form's presentation walk takes every one of these answers from here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ...domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormCellKind,
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from .work_form_answers import answer_facts
from .work_form_counts import count_work_form_fields
from .work_form_errors import ModeloWorkFormLayoutError
from .work_form_facts import (
    ModeloFormDetailFacts,
    ModeloFormFieldFacts,
    ModeloFormPageFacts,
    ModeloFormRecordBlock,
    asking_no_value,
)
from .work_form_field_projection import (
    binding_facts,
    casilla_facts,
    design_constant_facts,
    facts_casilla_id,
    project_casilla_field,
)
from .work_form_field_vocabulary import ModeloFormCasillaAddressV1
from .work_form_models import ModeloFormField
from .work_form_rates import page_applies_for_values, read_design_value
from .work_form_records import saved_form_records

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.ids import BindingId
    from .work_form_context import WorkFormContext

type ModeloFormBlockPosition = tuple[str, str, str]
"""Where a block sits: its page, its section and its own id."""


class LayoutFactsWalker:
    """Classify a declared layout's boxes page by page while accounting for every placement."""

    def __init__(self, layout: FormLayoutDefinition, context: WorkFormContext) -> None:
        """Prepare placement indexes and an empty account of the casillas met on pages."""
        self.layout = layout
        self.context = context
        self.placements: dict[str, FormPlacementDefinition] = {item.casilla_id: item for item in layout.placements}
        self.seen: set[str] = set()
        # Boxes met only as a repeating group's column: their own field may still follow on a later section.
        self.columned: set[str] = set()
        self.positions: dict[str, set[tuple[str, str]]] = {}
        self.section_position: tuple[str, str] = ("", "")
        self.alias_blocks: set[ModeloFormBlockPosition] = set()
        self.records: list[ModeloFormRecordBlock] = []

    def casilla(
        self, casilla_id: str, *, design_constant: str | None = None, literal_decimals: int | None = None
    ) -> ModeloFormFieldFacts:
        """Classify one placed casilla; a box whose value the official design fixes holds the design's figure.

        Its value is the design's literal read at the export field's declared
        scale. A literal whose scale the registry does not declare is fixed
        without a number: neither the literal's raw digits nor the engine's own
        figure for the box is what the filed fichero carries.
        """
        if casilla_id in self.seen:
            raise ModeloWorkFormLayoutError(
                f"the layout places casilla {casilla_id!r} more than once",
                translated_message="application.modelo.errors.work_form_layout_casilla_repeated",
                context={"casilla_id": casilla_id},
            )
        placement = self.placements.get(casilla_id)
        if placement is None or placement.kind is not FormPlacementKind.ON_FORM:
            raise ModeloWorkFormLayoutError(
                f"casilla {casilla_id!r} sits on a page without an on-form placement",
                translated_message="application.modelo.errors.work_form_layout_casilla_off_form",
                context={"casilla_id": casilla_id},
            )
        self.seen.add(casilla_id)
        self.positions.setdefault(casilla_id, set()).add(self.section_position)
        facts = casilla_facts(casilla_id, self.context, placement)
        if design_constant is None:
            return facts
        fixed = read_design_value(
            design_constant,
            literal_decimals if literal_decimals is not None else self.context.export_decimals(casilla_id),
        )
        return design_constant_facts(facts, fixed, recorded=self.context.filed)

    def page(self, page: FormPageDefinition) -> ModeloFormPageFacts:
        """Classify one declared page's boxes, decide whether it applies, and what it still asks if it does not."""
        first_record = len(self.records)
        fields = tuple(field for section in page.sections for field in self.section(page.id, section))
        has_records = any(record.rows for record in self.records[first_record:])
        applies = page_applies_for_values(page, self.context, fields, has_records=has_records)
        if applies is False:
            fields = tuple(asking_no_value(field) for field in fields)
        return ModeloFormPageFacts(
            id=page.id,
            applies=applies,
            counts=count_work_form_fields(fields, filed=self.context.filed),
            fields=fields,
        )

    def section(self, page_id: str, section: FormSectionDefinition) -> tuple[ModeloFormFieldFacts, ...]:
        """Classify one section's boxes in their declared order."""
        self.section_position = (page_id, section.id)
        return tuple(field for block in section.blocks for field in self.block(block))

    def block(
        self,
        block: FormFieldBlock
        | FormGridBlock
        | FormRepeatingGroupBlock
        | FormBindingInputsBlock
        | FormContextFieldBlock,
    ) -> tuple[ModeloFormFieldFacts, ...]:
        """Classify the boxes one declared block shows; a context field or a table of records shows none."""
        if isinstance(block, FormContextFieldBlock):
            return ()
        if isinstance(block, FormFieldBlock):
            return self._field_block(block)
        if isinstance(block, FormGridBlock):
            cells = (
                self.cell(cell.kind, cell.casilla_id, cell.binding_id, cell.literal, cell.literal_decimals)
                for row in block.rows
                for cell in row.cells
            )
            return tuple(field for field in cells if field is not None)
        if isinstance(block, FormRepeatingGroupBlock):
            self.repeating(block)
            return ()
        return tuple(binding_facts(binding_id, self.context) for binding_id in block.binding_ids)

    def _field_block(self, block: FormFieldBlock) -> tuple[ModeloFormFieldFacts, ...]:
        if block.casilla_id is not None and block.casilla_id in self.columned:
            self.columned.discard(block.casilla_id)
            self.seen.discard(block.casilla_id)
        if block.casilla_id is not None and block.casilla_id in self.seen:
            self.alias(block)
            return ()
        if block.casilla_id is None:
            return (binding_facts(str(block.binding_id), self.context),)
        return (
            self.casilla(
                block.casilla_id, design_constant=block.design_constant, literal_decimals=block.literal_decimals
            ),
        )

    def alias(self, block: FormFieldBlock) -> None:
        """Account for a declared repeat of a box shown elsewhere, which creates no other address."""
        casilla_id = str(block.casilla_id)
        placement = self.placements[casilla_id]
        declared = {(alias.page_id, alias.section_id) for alias in placement.aliases}
        visited = self.positions.setdefault(casilla_id, set())
        if self.section_position not in declared or self.section_position in visited:
            raise ModeloWorkFormLayoutError(
                f"the layout places casilla {casilla_id!r} more than once",
                translated_message="application.modelo.errors.work_form_layout_casilla_repeated",
                context={"casilla_id": casilla_id},
            )
        visited.add(self.section_position)
        self.alias_blocks.add((*self.section_position, block.id))

    def cell(
        self,
        kind: FormCellKind,
        casilla_id: CasillaId | None,
        binding_id: BindingId | None,
        literal: str | None,
        literal_decimals: int | None = None,
    ) -> ModeloFormFieldFacts | None:
        """Classify one grid cell's box, from its declared casilla, binding or design literal; ``None`` for text."""
        if kind is FormCellKind.CASILLA and casilla_id is not None:
            return self.casilla(casilla_id)
        if kind is FormCellKind.BINDING_INPUT and binding_id is not None:
            return binding_facts(binding_id, self.context)
        if kind is FormCellKind.DESIGN_CONSTANT and casilla_id is not None:
            return self.casilla(casilla_id, design_constant=literal, literal_decimals=literal_decimals)
        return None

    def repeating(self, block: FormRepeatingGroupBlock) -> None:
        """Account for a table of records' visible columns and read the rows it saved."""
        column_casillas = tuple(column.casilla_id for column in block.columns)
        for casilla_id in column_casillas:
            if casilla_id is not None and casilla_id not in self.seen:
                placement = self.placements.get(casilla_id)
                if placement is not None and placement.kind is FormPlacementKind.ON_FORM:
                    self.seen.add(casilla_id)
                    self.columned.add(casilla_id)
        rows_known, rows = saved_form_records(
            snapshot=self.context.snapshot,
            revision=self.context.revision,
            block=block,
            column_casillas=column_casillas,
        )
        self.records.append(
            ModeloFormRecordBlock(
                position=(*self.section_position, block.id),
                rows_known=rows_known,
                rows=rows,
                column_casilla_ids=column_casillas,
            )
        )


def walk_layout_facts(
    layout: FormLayoutDefinition, context: WorkFormContext
) -> tuple[LayoutFactsWalker, tuple[ModeloFormPageFacts, ...], ModeloFormDetailFacts]:
    """Classify every box a usable layout places: its pages', its working figures', its unplaced and its answers.

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.
    """
    walk = LayoutFactsWalker(layout, context)
    pages = tuple(walk.page(page) for page in layout.pages)
    working, unplaced = _other_placements(layout, context, walk)
    _ensure_layout_is_total(context, walk, (*working, *unplaced))
    laid_out = (*(field for page in pages for field in page.fields), *working, *unplaced)
    details = ModeloFormDetailFacts(
        working_figures=working, unplaced=unplaced, answers=answer_facts(layout, context, laid_out)
    )
    return walk, pages, details


def _other_placements(
    layout: FormLayoutDefinition, context: WorkFormContext, walk: LayoutFactsWalker
) -> tuple[tuple[ModeloFormFieldFacts, ...], tuple[ModeloFormFieldFacts, ...]]:
    working: list[ModeloFormFieldFacts] = []
    unplaced: list[ModeloFormFieldFacts] = []
    for placement in layout.placements:
        casilla_id = placement.casilla_id
        if placement.kind is FormPlacementKind.WORKING_FIGURE:
            working.append(casilla_facts(casilla_id, context, placement))
        elif placement.kind is FormPlacementKind.UNPLACED:
            unplaced.append(casilla_facts(casilla_id, context, placement))
        elif casilla_id not in walk.seen:
            raise ModeloWorkFormLayoutError(
                f"casilla {casilla_id!r} is placed on the form but no page shows it",
                translated_message="application.modelo.errors.work_form_layout_casilla_not_shown",
                context={"casilla_id": str(casilla_id)},
            )
    return tuple(working), tuple(unplaced)


def _ensure_layout_is_total(
    context: WorkFormContext, walk: LayoutFactsWalker, details: tuple[ModeloFormFieldFacts, ...]
) -> None:
    placed = walk.seen | {
        field.address.casilla_id for field in details if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    missing = sorted(set(context.rows) - placed)
    if missing:
        raise ModeloWorkFormLayoutError(
            f"the layout gives no placement to casillas {missing[:10]!r}",
            translated_message="application.modelo.errors.work_form_layout_casillas_unplaced",
            context={"casillas": ", ".join(str(casilla_id) for casilla_id in missing[:10])},
        )


def layout_presenter(
    layout: FormLayoutDefinition, context: WorkFormContext
) -> Callable[[ModeloFormFieldFacts], ModeloFormField]:
    """Present a casilla of this layout as the form does: at its placement, naming where else a page repeats it."""
    placements = {item.casilla_id: item for item in layout.placements}

    def present(facts: ModeloFormFieldFacts) -> ModeloFormField:
        placement = placements.get(facts_casilla_id(facts))
        if placement is None or placement.kind is not FormPlacementKind.ON_FORM:
            return project_casilla_field(facts, context, placement)
        return project_casilla_field(facts, context, placement, placement_aliases(placement))

    return present


def placement_aliases(placement: FormPlacementDefinition) -> tuple[str, ...]:
    """Where else the form repeats a placed casilla: each repeat's official reference, else its page."""
    return tuple(alias.official_ref or alias.page_id for alias in placement.aliases)


__all__ = [
    "LayoutFactsWalker",
    "ModeloFormBlockPosition",
    "layout_presenter",
    "placement_aliases",
    "walk_layout_facts",
]
