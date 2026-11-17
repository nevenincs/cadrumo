"""Present the declared form layout's pages from the form's classified summary of them."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from ...core.casilla_id import CasillaId
from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.export_semantics import ExportDraftAttribute
from ...domain.calculations.registry.form_context import form_context_choice, resolve_form_context_field
from ...domain.calculations.registry.form_projection_fields import resolve_form_projection_fields
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.modelo_localization import form_heading_edition_locale_key
from ...domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormCellKind,
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from .work_form_context_values import form_context_value
from .work_form_counts import count_work_form_fields
from .work_form_facts import ModeloFormFieldFacts, ModeloFormPageFacts, ModeloWorkFormSummary
from .work_form_field_projection import (
    binding_facts,
    casilla_facts,
    casilla_label,
    project_binding_field,
    project_casilla_field,
)
from .work_form_field_vocabulary import (
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormText,
    ModeloFormTextDisclosure,
    address_key,
)
from .work_form_layout_facts import placement_aliases
from .work_form_localization import localized_casilla_label, localized_heading
from .work_form_models import (
    ModeloFormBindingInputsBlock,
    ModeloFormBlock,
    ModeloFormContextFieldBlock,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormPage,
    ModeloFormRepeatingBlock,
    ModeloFormSection,
    section_fields,
)
from .work_form_rates import with_grounded_grid_rates, with_printed_row_rates, with_row_rate_bases
from .work_form_wording import context_value_text


class LayoutWalker:
    """Present a declared layout's pages from the form's classified summary of them.

    Every decision about a box -- which casilla a block shows, which block only
    repeats one, its value and where it stands, whether its page applies -- is
    the summary's (:func:`~.work_form_layout_facts.walk_layout_facts`); this
    walk adds the words, the controls and the layout's own structure.
    """

    def __init__(
        self,
        layout: FormLayoutDefinition,
        context: WorkFormContext,
        summary: ModeloWorkFormSummary,
        *,
        producer_values: Mapping[FilingProducerKey, ModeloFormScalar] | None = None,
        profile_binding_values: Mapping[BindingId, ModeloFormScalar] | None = None,
    ) -> None:
        """Index the summary's pages and boxes for the walk."""
        self.layout = layout
        self.context = context
        self.summary = summary
        self.producer_values = producer_values
        self.profile_binding_values = profile_binding_values
        self.placements: dict[str, FormPlacementDefinition] = {item.casilla_id: item for item in layout.placements}
        self.aliases: dict[str, tuple[str, ...]] = {
            item.casilla_id: placement_aliases(item) for item in layout.placements
        }
        self.pages: dict[str, ModeloFormPageFacts] = {page.id: page for page in summary.pages}
        self.facts: dict[tuple[str, tuple[str, str]], ModeloFormFieldFacts] = {
            (page.id, address_key(field.address)): field for page in summary.pages for field in page.fields
        }
        self.records = iter(summary.records)
        self.section_position: tuple[str, str] = ("", "")

    def casilla(self, casilla_id: str) -> ModeloFormField:
        """Show one placed casilla as the summary classified it on this page."""
        facts = self.facts[(self.section_position[0], ("casilla", casilla_id))]
        return project_casilla_field(
            facts, self.context, self.placements.get(casilla_id), self.aliases.get(casilla_id, ())
        )

    def binding(self, binding_id: str) -> ModeloFormField:
        """Show one binding input as the summary classified it on this page."""
        return project_binding_field(self.facts[(self.section_position[0], ("binding", binding_id))], self.context)

    def page(self, page: FormPageDefinition) -> ModeloFormPage:
        """Present one declared page with the applicability and counts the summary decided for it."""
        language = self.context.language
        facts = self.pages[page.id]
        applies = facts.applies
        sections = tuple(
            section.model_copy(update={"applies": section_applies(section, page_applies=applies)})
            for section in (self.section(page.id, part) for part in page.sections)
        )
        return ModeloFormPage(
            id=page.id,
            heading=localized_heading(
                page.heading_key,
                page.official_heading,
                page.official_ref or page.id,
                language,
                edition_key=self._edition_key(page.heading_key),
            ),
            official_ref=page.official_ref,
            condition=page.condition,
            applies=applies,
            sections=sections,
            counts=facts.counts,
        )

    def section(self, page_id: str, section: FormSectionDefinition) -> ModeloFormSection:
        """Project one section's blocks and counts in their declared order."""
        self.section_position = (page_id, section.id)
        blocks = tuple(self.block(block) for block in section.blocks)
        form_section = ModeloFormSection(
            id=f"{page_id}.{section.id}",
            heading=localized_heading(
                section.heading_key,
                section.official_heading,
                section.id,
                self.context.language,
                edition_key=self._edition_key(section.heading_key),
            ),
            official_heading=section.official_heading,
            blocks=blocks,
            counts=count_work_form_fields((), filed=self.context.filed),
            applies=None,
        )
        return form_section.model_copy(
            update={"counts": count_work_form_fields(section_fields(form_section), filed=self.context.filed)}
        )

    def _edition_key(self, heading_key: str) -> str | None:
        return form_heading_edition_locale_key(str(self.context.review.modelo), self.layout.revision_id, heading_key)

    def block(
        self,
        block: FormFieldBlock
        | FormGridBlock
        | FormRepeatingGroupBlock
        | FormBindingInputsBlock
        | FormContextFieldBlock,
    ) -> ModeloFormBlock:
        """Project one declared field, grid, repeating group, or binding-input block."""
        if isinstance(block, FormContextFieldBlock):
            return self._context_block(block)
        if isinstance(block, FormFieldBlock):
            return self._field_block(block)
        if isinstance(block, FormGridBlock):
            return self._grid_block(block)
        if isinstance(block, FormRepeatingGroupBlock):
            return self.repeating(block)
        return ModeloFormBindingInputsBlock(
            id=block.id, fields=tuple(self.binding(binding_id) for binding_id in block.binding_ids)
        )

    def _context_block(self, block: FormContextFieldBlock) -> ModeloFormContextFieldBlock:
        language = self.context.language
        owner = resolve_form_context_field(self.context.snapshot.revision, block)
        label = localized_heading(block.heading_key, block.official_heading, "Dato del formulario", language)
        value = (
            self._binding_context_value(owner.binding)
            if owner.binding is not None
            else form_context_value(
                self.context.snapshot,
                block,
                producer_values=self.producer_values,
                revision=self.context.revision,
            )
        )
        choice = form_context_choice(block, value)
        if choice is not None:
            value = localized_heading(choice.heading_key, choice.official_heading, "Opción", language).text
        period = self.context.snapshot.filing_period
        shows_period = (
            owner.binding is None
            and owner.draft_attribute is ExportDraftAttribute.PERIOD_CODE
            and value is not None
            and choice is None
        )
        return ModeloFormContextFieldBlock(
            id=block.id,
            label=label,
            box_number=block.box_number,
            value=value,
            value_text=context_value_text(value, language, period=period if shows_period else None),
        )

    def _binding_context_value(self, binding_id: BindingId) -> ModeloFormScalar:
        """Keep every saved answer; otherwise use the caller's admitted profile context."""
        revision = self.context.revision
        if (
            (revision is None or binding_id not in revision.binding_overrides)
            and self.profile_binding_values is not None
            and binding_id in self.profile_binding_values
        ):
            return self.profile_binding_values[binding_id]
        return binding_facts(binding_id, self.context).value

    def _field_block(self, block: FormFieldBlock) -> ModeloFormBlock:
        if (*self.section_position, block.id) in self.summary.alias_blocks:
            return self.alias(block)
        field = self.casilla(block.casilla_id) if block.casilla_id is not None else self.binding(str(block.binding_id))
        # Both parts are validated: the id by the hydrated layout, the field as it was built. Validating
        # the block would only run the field's own checks again on the same frozen field.
        return ModeloFormFieldBlock.model_construct(id=block.id, field=field)

    def _grid_block(self, block: FormGridBlock) -> ModeloFormGridBlock:
        language = self.context.language
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
                    tuple(self.cell(cell.kind, cell.casilla_id, cell.binding_id, cell.literal) for cell in row.cells),
                    self.context,
                ),
            )
            for row in block.rows
        )
        return ModeloFormGridBlock(
            id=block.id, columns=columns, rows=with_row_rate_bases(columns, with_printed_row_rates(rows))
        )

    def alias(self, block: FormFieldBlock) -> ModeloFormContextFieldBlock:
        """Show a declared repeat of a box shown elsewhere, with its label and value and no address of its own."""
        casilla_id = str(block.casilla_id)
        facts = casilla_facts(casilla_id, self.context, self.placements[casilla_id])
        return ModeloFormContextFieldBlock(
            id=block.id, label=casilla_label(self.context.casillas[casilla_id], self.context), value=facts.value
        )

    def cell(
        self,
        kind: FormCellKind,
        casilla_id: CasillaId | None,
        binding_id: BindingId | None,
        literal: str | None,
    ) -> ModeloFormGridCell:
        """Project one grid cell from its declared casilla, binding, or design literal."""
        if kind is FormCellKind.CASILLA and casilla_id is not None:
            return ModeloFormGridCell(kind=kind, field=self.casilla(casilla_id))
        if kind is FormCellKind.BINDING_INPUT and binding_id is not None:
            return ModeloFormGridCell(kind=kind, field=self.binding(binding_id))
        if kind is FormCellKind.DESIGN_CONSTANT and casilla_id is not None:
            return ModeloFormGridCell(kind=kind, field=self.casilla(casilla_id), literal=literal)
        return ModeloFormGridCell(kind=kind, literal=literal)

    def repeating(self, block: FormRepeatingGroupBlock) -> ModeloFormRepeatingBlock:
        """Project a repeating record and account for its saved rows and visible columns."""
        columns = tuple(
            ModeloFormGridColumn(key=column.key, heading=self.repeating_heading(column)) for column in block.columns
        )
        column_casillas = tuple(column.casilla_id for column in block.columns)
        record = next(self.records)
        if record.position != (*self.section_position, block.id):
            raise ValueError("the form's tables of records are presented in the order the summary read them")
        data_types = self._column_data_types(column_casillas)
        if any(column.export_field_id is not None for column in block.columns):
            data_types = tuple(
                str(field.data_type) for field in resolve_form_projection_fields(self.context.snapshot.revision, block)
            )
        return ModeloFormRepeatingBlock(
            id=block.id,
            columns=columns,
            column_casilla_ids=column_casillas,
            column_data_types=data_types,
            min_rows=block.min_rows,
            max_rows=block.max_rows,
            rows_known=record.rows_known,
            rows=record.rows,
        )

    def _column_data_types(self, column_casillas: tuple[str | None, ...]) -> tuple[str, ...]:
        return tuple(
            "text"
            if casilla_id is None or casilla_id not in self.context.rows
            else self.context.rows[casilla_id].data_type
            for casilla_id in column_casillas
        )

    def repeating_heading(self, column: FormRepeatingColumn) -> ModeloFormText:
        """A repeating column's heading; one the design does not name reads as the label of the box it shows."""
        language = self.context.language
        heading = localized_heading(column.heading_key, column.official_heading, column.key, language)
        if heading.disclosure is not ModeloFormTextDisclosure.TECHNICAL or column.casilla_id is None:
            return heading
        casilla = self.context.casillas.get(column.casilla_id)
        label = (
            None
            if casilla is None
            else localized_casilla_label(casilla, language, ejercicio=self.context.review.period.filing_year)
        )
        return heading if label is None else label


def section_applies(section: ModeloFormSection, *, page_applies: bool | None) -> bool | None:
    """Whether a section applies: not on a page that does not, nor when every box on it is proven not to apply.

    Otherwise the section answers as its page does, so a page that may not
    apply leaves its sections undecided too.
    """
    if page_applies is False:
        return False
    fields = section_fields(section)
    if fields and all(field.origin is ModeloFormOrigin.NOT_APPLICABLE for field in fields):
        return False
    return page_applies
