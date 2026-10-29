"""Scalar source and cell rendering for form workbooks."""

from __future__ import annotations

from ....domain.calculations.registry.schema_form_layouts import (
    FormFieldBlock,
    FormFieldChoice,
)
from ...export.review_form_data import ReviewSavedForm
from .errors import CalcSheetsEngineError
from .form_cell_builder import FormCellBuilder, saved_cell_value
from .records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetFormulaCell,
    SheetReviewMetadata,
    SheetRoundingRule,
    SheetRowHeight,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole


class FormScalarBuilder[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    FormCellBuilder[M]
):
    """Render the corresponding declared form phase."""

    def _choice_value(
        self,
        source: SheetValueCell | SheetFormulaCell | None,
        choice: FormFieldChoice,
        domain: tuple[str, ...],
        casilla_id: str,
    ) -> None:
        if source is None:
            self.text("Sin dato", 10)
        elif self.saved_form is not None and isinstance(source, SheetValueCell):
            self.text("Sin dato" if source.value is None else "X" if source.value == choice.value else "", 10)
        else:
            reference = source.address.qualified()
            literal = choice.value.replace('"', '""')
            allowed = ",".join(f'EXACT({reference},"{value.replace(chr(34), chr(34) * 2)}")' for value in domain)
            self.formulas.append(
                SheetFormulaCell(
                    address=SheetCellAddress.at(TabName.FORM, self.row, 10),
                    formula=(
                        f'IF(ISBLANK({reference}),"Sin dato",IF(NOT(OR({allowed})),"Valor no válido",'
                        f'IF(EXACT({reference},"{literal}"),"X","")))'
                    ),
                    casilla_id=casilla_id,
                    rounding_rule=SheetRoundingRule.NONE,
                )
            )

    def _choice_domain(self, block: FormFieldBlock) -> tuple[str, ...]:
        casilla = next(c for c in self.registry_revision.casillas if c.id == block.casilla_id)
        domain = casilla.constraints.enum if casilla.constraints is not None else None
        if casilla.data_type.value != "text" or domain is None or any(c.value not in domain for c in block.choices):
            raise CalcSheetsEngineError("form choices require values in the casilla's closed text domain")
        return domain

    def choices(self, block: FormFieldBlock) -> None:
        """Show mutually exclusive marks from one source, preserving unknown values."""
        if block.casilla_id is None:
            raise CalcSheetsEngineError("form choices require a casilla")
        domain = self._choice_domain(block)
        source = self.sources.get(block.casilla_id)
        for choice in block.choices:
            self.text(self.localized(choice.heading_key) or choice.official_heading or "Opción")
            self.span(2, 8, StyleRole.FORM_LABEL)
            self._choice_value(source, choice, domain, block.casilla_id)
            self.span(10, 12, StyleRole.FORM_COMPUTED, boxed=True)
            self.row += 1

    def field(self, casilla_id: str, *, constant: str | None = None, decimals: int | None = None) -> None:
        """Render or initialize this form component."""
        self.text(self.casilla_label(casilla_id))
        self.span(2, 8, StyleRole.FORM_LABEL)
        self.text(self.placements[casilla_id].box_number or "", 9)
        self.span(9, 9, StyleRole.CASILLA, boxed=True)
        self.value(casilla_id, 10, 12, constant=constant, decimals=decimals)
        self.heights.append(
            SheetRowHeight(
                tab=TabName.FORM,
                row=self.row,
                height_pixels=max(30, 18 * (1 + len(self.casilla_label(casilla_id)) // 65)),
            )
        )
        self.row += 1

    def binding(self, binding_id: str) -> None:
        """Render or initialize this form component."""
        if binding_id not in {b.id for b in self.registry_revision.bindings}:
            raise CalcSheetsEngineError("form references an unknown binding")
        address = self.binding_addresses.get(binding_id)
        if address is None:
            owners = [c for c in self.registry_revision.casillas if c.binding == binding_id]
            if len(owners) == 1:
                self.field(owners[0].id)
                return
            raise CalcSheetsEngineError("form binding has no unambiguous human-labelled source cell")
        label_address = SheetCellAddress.at(address.tab, address.row, 3)
        label_cell = self.address_sources[label_address.qualified()]
        if not isinstance(label_cell, SheetValueCell) or not isinstance(label_cell.value, str):
            raise CalcSheetsEngineError("form binding source has no human label")
        self.text(label_cell.value)
        self.span(2, 8, StyleRole.FORM_LABEL)
        self.binding_value(binding_id, 9, 12)
        self.row += 1

    def _saved_binding_value(self, saved_form: ReviewSavedForm, binding_id: str, column: int, end: int) -> None:
        bindings = {item.id: item.value for item in saved_form.bindings}
        value = bindings.get(binding_id)
        if value is None:
            owners = [casilla.id for casilla in self.casillas.values() if casilla.binding == binding_id]
            source = self.sources.get(owners[0]) if len(owners) == 1 else None
            value = source.value if isinstance(source, SheetValueCell) else None
        self.text(saved_cell_value(value) if value is not None else "Sin dato", column)
        self.span(column, end, StyleRole.FORM_COMPUTED, boxed=True)

    def _binding_source(self, binding_id: str) -> tuple[SheetCellAddress, SheetValueCell | SheetFormulaCell]:
        address = self.binding_addresses.get(binding_id)
        if address is None:
            owners = [casilla for casilla in self.casillas.values() if casilla.binding == binding_id]
            if len(owners) != 1 or owners[0].id not in self.sources:
                raise CalcSheetsEngineError("form binding has no unambiguous source cell")
            address = self.sources[owners[0].id].address
        source = self.address_sources.get(address.qualified())
        if source is None:
            raise CalcSheetsEngineError("form binding source cell is missing")
        return address, source

    def _binding_guard(self, source: SheetValueCell | SheetFormulaCell, address: SheetCellAddress) -> tuple[str, str]:
        leaves = self.input_leaves(source, frozenset())
        guards = ",".join(f"ISBLANK({leaf})" for leaf in sorted(leaves))
        reference = address.qualified()
        guard = f"OR({guards})" if len(leaves) > 1 else guards or f"ISBLANK({reference})"
        if isinstance(source, SheetFormulaCell) and source.missing_input_condition is not None:
            guard = source.missing_input_condition
        return reference, guard

    def binding_value(self, binding_id: str, column: int, end: int, *, readonly: bool = False) -> None:
        """Link a declared binding to its existing value without inventing a zero."""
        if binding_id not in {binding.id for binding in self.registry_revision.bindings}:
            raise CalcSheetsEngineError("form references an unknown binding")
        if self.saved_form is not None:
            self._saved_binding_value(self.saved_form, binding_id, column, end)
            return
        address, source = self._binding_source(binding_id)
        reference, guard = self._binding_guard(source, address)
        target = SheetCellAddress.at(TabName.FORM, self.row, column)
        self.formulas.append(
            SheetFormulaCell(
                address=target,
                formula=f'IF({guard},"Sin dato",{reference})',
                casilla_id=None,
                rounding_rule=SheetRoundingRule.NONE,
            )
        )
        self.span(column, end, StyleRole.FORM_COMPUTED if readonly else StyleRole.FORM_INPUT, boxed=True)
        for directive in self.plan.number_formats:
            if directive.address == address:
                self.formats.append(directive.model_copy(update={"address": target}))
