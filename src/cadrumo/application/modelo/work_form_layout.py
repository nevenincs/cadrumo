"""Walk the declared form layout and account for its placements."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormCellKind,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from .work_form_counts import count_work_form_fields
from .work_form_errors import ModeloWorkFormLayoutError
from .work_form_field_projection import project_binding_field, project_casilla_field
from .work_form_localization import localized_heading, localized_text
from .work_form_models import (
    ModeloFormBindingInputsBlock,
    ModeloFormBlock,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormRepeatingBlock,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    section_fields,
)
from .work_form_rates import (
    page_applies_for_values,
    read_design_value,
    with_grounded_grid_rates,
    with_printed_row_rates,
)
from .work_form_records import saved_form_records
from .work_form_sources import FIXED_BY_THE_FORM


class LayoutWalker:
    """Turn a declared layout into form pages while accounting for every placement."""

    def __init__(self, layout: FormLayoutDefinition, context: WorkFormContext) -> None:
        """Prepare placement indexes and an empty set of casillas encountered on pages."""
        self.layout = layout
        self.context = context
        self.placements: dict[str, FormPlacementDefinition] = {str(item.casilla_id): item for item in layout.placements}
        self.aliases: dict[str, tuple[str, ...]] = {
            str(item.casilla_id): tuple(alias.official_ref or alias.page_id for alias in item.aliases)
            for item in layout.placements
        }
        self.seen: set[str] = set()

    def casilla(
        self, casilla_id: str, *, design_constant: str | None = None, literal_decimals: int | None = None
    ) -> ModeloFormField:
        """Show one placed casilla; a box whose value the official design fixes is never editable.

        Its value is the design's literal read at the export field's declared
        scale. A literal whose scale the registry does not declare is shown as
        fixed without a number: neither the literal's raw digits nor the
        engine's own figure for the box is what the filed fichero carries.
        """
        if casilla_id in self.seen:
            raise ModeloWorkFormLayoutError(f"the layout places casilla {casilla_id!r} more than once")
        placement = self.placements.get(casilla_id)
        if placement is None or placement.kind is not FormPlacementKind.ON_FORM:
            raise ModeloWorkFormLayoutError(f"casilla {casilla_id!r} sits on a page without an on-form placement")
        self.seen.add(casilla_id)
        field = project_casilla_field(casilla_id, self.context, placement, self.aliases.get(casilla_id, ()))
        if design_constant is None:
            return field
        fixed = read_design_value(
            design_constant,
            literal_decimals if literal_decimals is not None else self.context.export_decimals(casilla_id),
        )
        return field.model_copy(
            update={
                "editability": ModeloFormEditability.DESIGN_CONSTANT,
                "not_writable_reason": None,
                "origin": ModeloFormOrigin.INFORMATIONAL,
                "unattributed": False,
                "value": fixed,
                "source": FIXED_BY_THE_FORM,
            }
        )

    def page(self, page: FormPageDefinition) -> ModeloFormPage:
        """Project one declared page and derive applicability from its fields and saved rows."""
        language = self.context.language
        sections = tuple(self.section(page.id, section) for section in page.sections)
        return ModeloFormPage(
            id=page.id,
            heading=localized_heading(page.heading_key, page.official_heading, page.official_ref or page.id, language),
            official_ref=page.official_ref,
            condition=page.condition,
            applies=page_applies_for_values(page, self.context, sections),
            sections=sections,
            counts=count_work_form_fields(
                (field for section in sections for field in section_fields(section)), filed=self.context.filed
            ),
        )

    def section(self, page_id: str, section: FormSectionDefinition) -> ModeloFormSection:
        """Project one section's blocks and counts in their declared order."""
        blocks = tuple(self.block(block) for block in section.blocks)
        form_section = ModeloFormSection(
            id=f"{page_id}.{section.id}",
            heading=localized_heading(section.heading_key, section.official_heading, section.id, self.context.language),
            official_heading=section.official_heading,
            blocks=blocks,
            counts=count_work_form_fields((), filed=self.context.filed),
        )
        return form_section.model_copy(
            update={"counts": count_work_form_fields(section_fields(form_section), filed=self.context.filed)}
        )

    def block(
        self, block: FormFieldBlock | FormGridBlock | FormRepeatingGroupBlock | FormBindingInputsBlock
    ) -> ModeloFormBlock:
        """Project one declared field, grid, repeating group, or binding-input block."""
        language = self.context.language
        if isinstance(block, FormFieldBlock):
            field = (
                self.casilla(
                    str(block.casilla_id),
                    design_constant=block.design_constant,
                    literal_decimals=block.literal_decimals,
                )
                if block.casilla_id is not None
                else project_binding_field(str(block.binding_id), self.context)
            )
            return ModeloFormFieldBlock(id=block.id, field=field)
        if isinstance(block, FormGridBlock):
            columns = tuple(
                ModeloFormGridColumn(
                    key=column.key,
                    heading=localized_heading(column.heading_key, column.official_heading, column.key, language),
                )
                for column in block.columns
            )
            rows = tuple(
                ModeloFormGridRow(
                    key=row.key,
                    heading=localized_heading(row.heading_key, row.official_heading, row.key, language),
                    cells=with_grounded_grid_rates(
                        tuple(
                            self.cell(cell.kind, cell.casilla_id, cell.binding_id, cell.literal, cell.literal_decimals)
                            for cell in row.cells
                        ),
                        self.context,
                    ),
                )
                for row in block.rows
            )
            return ModeloFormGridBlock(id=block.id, columns=columns, rows=with_printed_row_rates(rows))
        if isinstance(block, FormRepeatingGroupBlock):
            return self.repeating(block)
        return ModeloFormBindingInputsBlock(
            id=block.id,
            fields=tuple(project_binding_field(str(binding_id), self.context) for binding_id in block.binding_ids),
        )

    def cell(
        self,
        kind: FormCellKind,
        casilla_id: CasillaId | None,
        binding_id: BindingId | None,
        literal: str | None,
        literal_decimals: int | None = None,
    ) -> ModeloFormGridCell:
        """Project one grid cell from its declared casilla, binding, or design literal."""
        if kind is FormCellKind.CASILLA and casilla_id is not None:
            return ModeloFormGridCell(kind=kind, field=self.casilla(str(casilla_id)))
        if kind is FormCellKind.BINDING_INPUT and binding_id is not None:
            return ModeloFormGridCell(kind=kind, field=project_binding_field(str(binding_id), self.context))
        if kind is FormCellKind.DESIGN_CONSTANT and casilla_id is not None:
            return ModeloFormGridCell(
                kind=kind,
                field=self.casilla(str(casilla_id), design_constant=literal, literal_decimals=literal_decimals),
                literal=literal,
            )
        return ModeloFormGridCell(kind=kind, literal=literal)

    def repeating(self, block: FormRepeatingGroupBlock) -> ModeloFormRepeatingBlock:
        """Project a repeating record and account for its saved rows and visible columns."""
        columns = tuple(
            ModeloFormGridColumn(key=column.key, heading=self.repeating_heading(column)) for column in block.columns
        )
        column_casillas = tuple(
            None if column.casilla_id is None else str(column.casilla_id) for column in block.columns
        )
        self._remember_placed_columns(column_casillas)
        data_types = self._column_data_types(column_casillas)
        rows_known, rows = saved_form_records(
            snapshot=self.context.snapshot,
            revision=self.context.revision,
            block=block,
            column_casillas=column_casillas,
        )
        return ModeloFormRepeatingBlock(
            id=block.id,
            columns=columns,
            column_casilla_ids=column_casillas,
            column_data_types=data_types,
            min_rows=block.min_rows,
            max_rows=block.max_rows,
            rows_known=rows_known,
            rows=rows,
        )

    def _remember_placed_columns(self, column_casillas: tuple[str | None, ...]) -> None:
        for casilla_id in column_casillas:
            if casilla_id is not None and casilla_id not in self.seen:
                placement = self.placements.get(casilla_id)
                if placement is not None and placement.kind is FormPlacementKind.ON_FORM:
                    self.seen.add(casilla_id)

    def _column_data_types(self, column_casillas: tuple[str | None, ...]) -> tuple[str, ...]:
        return tuple(
            "text"
            if casilla_id is None or casilla_id not in self.context.rows
            else str(self.context.rows[casilla_id].data_type)
            for casilla_id in column_casillas
        )

    def repeating_heading(self, column: FormRepeatingColumn) -> ModeloFormText:
        """A repeating column's heading; one the design does not name reads as the label of the box it shows."""
        language = self.context.language
        heading = localized_heading(column.heading_key, column.official_heading, column.key, language)
        if heading.disclosure is not ModeloFormTextDisclosure.TECHNICAL or column.casilla_id is None:
            return heading
        casilla = self.context.casillas.get(str(column.casilla_id))
        label = None if casilla is None else localized_text(casilla.localization_keys, language)
        return heading if label is None else label
