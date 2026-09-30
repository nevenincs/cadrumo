"""A small synthetic editor form and reader for driving the workbench screen.

Two official pages and the calculation details: a first page with a finished
section and an official grid, a second page with a box that needs the filer,
and one working figure. Values are synthetic. The reader counts its calls so a
test can prove the screen read off the event loop exactly as often as it should.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ......application.modelo.calculation_report import CalculationReportRowRole
from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1, ModeloHelpFormulaV1
from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormCounts,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
)
from ......application.modelo.work_review import ModeloWorkProgress
from ......core.casilla_id import CasillaId
from ......core.external_constants import OutputLanguage
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.schema_form_layouts import FormCellKind, FormPageCondition
from ..ports import (
    WorkbenchChange,
    WorkbenchLoadV1,
    WorkbenchParsed,
    WorkbenchParseOutcome,
    WorkbenchRefused,
)

if TYPE_CHECKING:
    from ....operations.controller import OperationController


def _text(text: str) -> ModeloFormText:
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.LOCALIZED)


def form_field(
    box: str,
    label: str,
    origin: ModeloFormOrigin,
    value: Decimal | None = None,
    *,
    editability: ModeloFormEditability = ModeloFormEditability.EDITABLE_VALUE,
    role: CalculationReportRowRole | None = None,
    help_text: str | None = None,
) -> ModeloFormField:
    """Build one synthetic money field addressed by its box number."""
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=box),
        box=box,
        label=_text(label),
        help=help_text,
        data_type="money",
        value=value,
        origin=origin,
        editability=editability,
        required=origin is ModeloFormOrigin.NEEDS_INPUT,
        role=role,
    )


def _counts(fields: list[ModeloFormField]) -> ModeloFormCounts:
    def count(origin: ModeloFormOrigin) -> int:
        return sum(1 for item in fields if item.origin is origin)

    return ModeloFormCounts(
        total=len(fields),
        needs_input=count(ModeloFormOrigin.NEEDS_INPUT),
        entered=count(ModeloFormOrigin.ENTERED),
        imported=count(ModeloFormOrigin.IMPORTED),
        calculated=count(ModeloFormOrigin.CALCULATED),
        overridden=count(ModeloFormOrigin.OVERRIDES_SOURCE),
        default_to_confirm=count(ModeloFormOrigin.DEFAULT_TO_CONFIRM),
        not_applicable=count(ModeloFormOrigin.NOT_APPLICABLE),
        blocked=sum(1 for item in fields if item.blockers),
    )


def _section(section_id: str, heading: str, fields: list[ModeloFormField]) -> ModeloFormSection:
    blocks = tuple(ModeloFormFieldBlock(id=f"f{item.box}", field=item) for item in fields)
    return ModeloFormSection(
        id=section_id, heading=_text(heading), official_heading=None, blocks=blocks, counts=_counts(fields)
    )


def synthetic_form(*, calculated: bool = True, needs_input: bool = True) -> ModeloWorkForm:
    """Build the fixture form: two official pages and the calculation details."""
    income = form_field(
        "01",
        "Ingresos computables",
        ModeloFormOrigin.IMPORTED,
        Decimal("24000.00"),
        editability=ModeloFormEditability.LOCKED_SOURCE,
    )
    expenses = form_field(
        "02",
        "Gastos deducibles",
        ModeloFormOrigin.IMPORTED,
        Decimal("9500.00"),
        editability=ModeloFormEditability.LOCKED_SOURCE,
    )
    net = form_field(
        "03",
        "Rendimiento neto",
        ModeloFormOrigin.CALCULATED,
        Decimal("14500.00"),
        editability=ModeloFormEditability.CALCULATED,
    )
    base = form_field("07", "Base imponible", ModeloFormOrigin.ENTERED, Decimal("1000.00"))
    quota = form_field(
        "09", "Cuota", ModeloFormOrigin.CALCULATED, Decimal("210.00"), editability=ModeloFormEditability.CALCULATED
    )
    withholding = form_field(
        "06",
        "Retenciones e ingresos a cuenta",
        ModeloFormOrigin.NEEDS_INPUT if needs_input else ModeloFormOrigin.ENTERED,
        None if needs_input else Decimal("300.00"),
        help_text="Retenciones soportadas en el trimestre.",
    )
    result = form_field(
        "19",
        "Resultado de la autoliquidación",
        ModeloFormOrigin.CALCULATED,
        Decimal("1300.00"),
        editability=ModeloFormEditability.CALCULATED,
        role=CalculationReportRowRole.RESULT,
    )
    working = form_field(
        "99",
        "Saldo negativo trasladable",
        ModeloFormOrigin.CALCULATED,
        Decimal("0"),
        editability=ModeloFormEditability.CALCULATED,
    )
    grid = ModeloFormGridBlock(
        id="grid",
        columns=(
            ModeloFormGridColumn(key="base", heading=_text("Base imponible")),
            ModeloFormGridColumn(key="tipo", heading=_text("Tipo %")),
            ModeloFormGridColumn(key="cuota", heading=_text("Cuota")),
        ),
        rows=(
            ModeloFormGridRow(
                key="r21",
                heading=_text("Régimen general 21 %"),
                cells=(
                    ModeloFormGridCell(kind=FormCellKind.CASILLA, field=base),
                    ModeloFormGridCell(kind=FormCellKind.DESIGN_CONSTANT, literal="21,00"),
                    ModeloFormGridCell(kind=FormCellKind.CASILLA, field=quota),
                ),
            ),
        ),
    )
    first_section = _section("p1.s1", "I. Actividades económicas", [income, expenses, net])
    grid_section = ModeloFormSection(
        id="p1.s2", heading=_text("IVA devengado"), official_heading=None, blocks=(grid,), counts=_counts([base, quota])
    )
    second_section = _section("p2.s1", "III. Total liquidación", [withholding, result])
    pages = (
        ModeloFormPage(
            id="p1",
            heading=_text("Liquidación"),
            official_ref="DR13001",
            condition=FormPageCondition.ALWAYS,
            applies=True,
            sections=(first_section, grid_section),
            counts=_counts([income, expenses, net, base, quota]),
        ),
        ModeloFormPage(
            id="p2",
            heading=_text("Resultado"),
            official_ref="DR13002",
            condition=FormPageCondition.ALWAYS,
            applies=True,
            sections=(second_section,),
            counts=_counts([withholding, result]),
        ),
    )
    every = [income, expenses, net, base, quota, withholding, result, working]
    return ModeloWorkForm(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        registry_revision_id="2019-y-siguientes",
        work_unit_id="a" * 64,
        calculation_revision_id=("b" * 64) if calculated else None,
        language=OutputLanguage.ES,
        layout_provenance=ModeloFormLayoutProvenance.GENERATED,
        pages=pages,
        working_figures=(working,),
        result_addresses=("19",),
        counts=_counts(every),
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        operator_entries_known=True,
        edit_admitted=True,
    )


@dataclass
class FakeReader:
    """Answers the workbench's reads from a fixed form and counts them."""

    form: ModeloWorkForm = field(default_factory=synthetic_form)
    verified: bool = False
    filed: bool = False
    loads: int = 0
    cards: list[str] = field(default_factory=list)

    def load(self, language: OutputLanguage) -> WorkbenchLoadV1:
        """Return the fixed form."""
        self.loads += 1
        return WorkbenchLoadV1(form=self.form, verified=self.verified, filed=self.filed)

    def help_card(self, casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        """Return a card whose formula names the casilla, and record the request."""
        self.cards.append(str(casilla_id))
        return ModeloCasillaHelpCardV1(
            casilla_id=casilla_id,
            formula=ModeloHelpFormulaV1(text=f"[{casilla_id}] = [01] − [02]", complete=True),
            quotes=(),
            legal_basis=(),
            constraints=(),
            origins=(),
            feeds=(),
        )


@dataclass
class FakeActions:
    """Parses Spanish decimals and records every operation the workbench asks for.

    Operations raise instead of opening a supervised operation, so a test proves
    what the workbench submitted and that a failure leaves the staged changes in
    place.
    """

    applied: list[tuple[WorkbenchChange, ...]] = field(default_factory=list)
    requested: list[str] = field(default_factory=list)

    def parse(self, field: ModeloFormField, lexeme: str, language: OutputLanguage) -> WorkbenchParseOutcome:
        """Read a Spanish decimal, or refuse with a fix-it sentence."""
        try:
            value = Decimal(lexeme.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return WorkbenchRefused(message="Escribe un importe, por ejemplo 1.234,56.")
        return WorkbenchParsed(value=value, display=f"{value:.2f}".replace(".", ",") + "\u00a0\u20ac")

    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationController:
        """Record the submitted changes, then fail as an unavailable service would."""
        self.applied.append(changes)
        raise RuntimeError("no operation service in this test")

    async def calculate(self) -> OperationController:
        """Record a calculate request."""
        self.requested.append("calculate")
        raise RuntimeError("no operation service in this test")

    async def verify(self) -> OperationController:
        """Record a verify request."""
        self.requested.append("verify")
        raise RuntimeError("no operation service in this test")

    async def file(self) -> OperationController:
        """Record a file request."""
        self.requested.append("file")
        raise RuntimeError("no operation service in this test")


__all__ = ["FakeActions", "FakeReader", "form_field", "synthetic_form"]
