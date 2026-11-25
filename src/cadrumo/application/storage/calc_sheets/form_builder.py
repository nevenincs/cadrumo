"""Compose complete declared form pages and checks."""

from __future__ import annotations

from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.schema_form_layouts import (
    FormBlockDefinition,
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutReviewState,
    FormPageCondition,
    FormPageDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from ....domain.calculations.registry.schema_verification import (
    ParsedVerificationPredicate,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)
from .errors import CalcSheetsEngineError
from .form_record_builder import FormRecordBuilder
from .records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetFormulaCell,
    SheetReviewMetadata,
    SheetRoundingRule,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole


class FormBuilder[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](FormRecordBuilder[M]):
    """Render the corresponding declared form phase."""

    def _choice_label(self, block: FormBlockDefinition, antecedent: str, literal: str, label: str) -> str:
        if isinstance(block, FormFieldBlock) and block.casilla_id == antecedent:
            for choice in block.choices:
                if choice.value == literal:
                    label = self.localized(choice.heading_key) or choice.official_heading or label
        return label

    def _conditional_label(self, antecedent: str, literal: str) -> str:
        label = self.casilla_label(antecedent)
        for page in self.layout.pages:
            for section in page.sections:
                for block in section.blocks:
                    label = self._choice_label(block, antecedent, literal, label)
        return label

    def _conditional_check_row(
        self,
        parsed: ParsedVerificationPredicate,
        antecedent: str,
        consequent: str,
        trigger: SheetValueCell | SheetFormulaCell,
        required: SheetValueCell | SheetFormulaCell,
    ) -> None:
        label = self._conditional_label(antecedent, parsed.literal)
        self.text(f"{label}: {self.casilla_label(consequent)}")
        self.span(2, 8, StyleRole.FORM_LABEL)
        source, target = trigger.address.qualified(), required.address.qualified()
        literal = parsed.literal.replace('"', '""')
        requirement = (
            f'IF(ISBLANK({target}),"Falta dato",IF(AND(ISNUMBER({target}),{target}=0),"Cero indicado","Debe ser cero"))'
            if parsed.operator is VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO
            else f'IF(AND(ISNUMBER({target}),{target}<>0),"Dato aportado","Falta dato")'
        )
        self.formulas.append(
            SheetFormulaCell(
                address=SheetCellAddress.at(TabName.FORM, self.row, 10),
                formula=(f'IF(ISBLANK({source}),"Sin dato",IF(EXACT({source},"{literal}"),{requirement},"No aplica"))'),
                casilla_id=None,
                rounding_rule=SheetRoundingRule.NONE,
            )
        )
        self.span(10, 12, StyleRole.FORM_COMPUTED, boxed=True)
        self.row += 1

    def conditional_checks(self) -> None:
        """Expose supported categorical requirements without claiming complete verification."""
        if self.saved_form is not None:
            return
        heading_shown = False
        for predicate in self.registry_revision.verification_predicates:
            parsed = parse_verification_predicate_expression(predicate.expression)
            if (
                predicate.finding_kind.value != "BLOCKING_RULE"
                or parsed is None
                or parsed.operator
                not in (
                    VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO,
                    VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO,
                )
            ):
                continue
            antecedent, consequent = parsed.casilla_ids
            trigger, required = self.sources.get(antecedent), self.sources.get(consequent)
            if trigger is None or required is None:
                raise CalcSheetsEngineError("conditional form check has no source cell")
            if not heading_shown:
                self.row += 1
                self.line("Comprobaciones parciales de los datos", StyleRole.FORM_SECTION)
                heading_shown = True
            self._conditional_check_row(parsed, antecedent, consequent, trigger, required)

    def _caption(self) -> str:
        if isinstance(self.plan.metadata, SheetReviewMetadata):
            return self.plan.metadata.title + " · copia de valores guardados; no válida para presentar"
        if isinstance(self.plan.metadata, SheetTemplatePreviewMetadata):
            return "EJEMPLO FICTICIO · ejercicio y período ilustrativos · no válido para presentar"
        if not isinstance(self.frame, Period):
            return tr("application.storage.calc_sheets.form.communication_caption", locale="es")
        if not self.registry_revision.formulas:
            return tr("application.storage.calc_sheets.form.reported_data_caption", locale="es")
        return "Escenario de cálculo · edite los datos en las hojas de origen"

    def _render_field_block(self, block: FormFieldBlock) -> None:
        if block.choices:
            self.choices(block)
        elif block.casilla_id is not None and block.casilla_id:
            self.field(block.casilla_id, constant=block.design_constant, decimals=block.literal_decimals)
        elif block.binding_id is not None and block.binding_id:
            self.binding(block.binding_id)

    def _render_block(self, block: FormBlockDefinition) -> None:
        if isinstance(block, FormFieldBlock):
            self._render_field_block(block)
        elif isinstance(block, FormGridBlock):
            self.grid(block)
        elif isinstance(block, FormRepeatingGroupBlock):
            self.repeating(block)
        elif isinstance(block, FormContextFieldBlock):
            self.context_field(block)
        else:
            for binding_id in block.binding_ids:
                self.binding(binding_id)

    def _render_section(self, section: FormSectionDefinition, index: int) -> None:
        self.line(
            self.localized(section.heading_key) or section.official_heading or f"Apartado {index}",
            StyleRole.FORM_SECTION,
        )
        for block in section.blocks:
            self._render_block(block)

    def _render_page(self, page: FormPageDefinition, index: int) -> None:
        if (
            page.condition is FormPageCondition.PERIOD_RESTRICTED
            and isinstance(self.frame, Period)
            and self.frame.code not in page.condition_periods
        ):
            return
        self.row += 1
        heading = self.localized(page.heading_key) or page.official_heading
        self.line(heading or f"Página {index}", StyleRole.TITLE)
        if page.condition is not FormPageCondition.ALWAYS:
            descriptions = {
                FormPageCondition.OPTIONAL_RECORD: "Página opcional; compruebe si corresponde.",
                FormPageCondition.REQUIRES_POSITIVE_CASILLA: (
                    "Página condicionada a una casilla positiva; compruebe su aplicación."
                ),
                FormPageCondition.PERIOD_RESTRICTED: "Página aplicable a los períodos: "
                + ", ".join(page.condition_periods),
            }
            self.line(descriptions[page.condition])
        for section_index, section in enumerate(page.sections, 1):
            self._render_section(section, section_index)

    def _render_unplaced(self) -> None:
        for kind, title in (
            (FormPlacementKind.WORKING_FIGURE, "Datos auxiliares del cálculo"),
            (FormPlacementKind.UNPLACED, "Datos pendientes de ubicación en el formulario"),
        ):
            placements = [
                p
                for p in self.layout.placements
                if p.kind is kind and p.workbook_exclusion is None and not self.casillas[p.casilla_id].internal_only
            ]
            if placements:
                self.row += 1
                self.line(title, StyleRole.FORM_SECTION)
                for placement in placements:
                    self.field(placement.casilla_id)

    def render(self) -> None:
        """Render or initialize this form component."""
        period_suffix = f" · {self.frame.code}" if isinstance(self.frame, Period) else ""
        self.line(f"Modelo {self.modelo_id} · {self.frame.filing_year}{period_suffix}", StyleRole.TITLE)
        self.line(self._caption())
        if self.layout.review.state is FormLayoutReviewState.GENERATED:
            self.line("Distribución generada desde el registro; pendiente de revisión visual del formulario oficial.")
        else:
            self.line("Distribución revisada. Documento de trabajo; no es un justificante de presentación.")
        for page_index, page in enumerate(self.layout.pages, 1):
            self._render_page(page, page_index)
        self._render_unplaced()
        self.conditional_checks()
