"""A small synthetic editor form and reader for driving the workbench screen.

Two official pages and the calculation details: a first page with a finished
section and an official grid, a second page with a box that needs the filer,
and one working figure. Income and expenses come from the ledger; the
withholding box is fed by two registers, one of which has produced nothing yet.
Values are synthetic. The reader counts its calls so a
test can prove the screen read off the event loop exactly as often as it should.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ......application.modelo.calculation_report import CalculationReportRowRole
from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1, ModeloHelpFormulaV1
from ......application.modelo.source_policy import source_policy
from ......application.modelo.work_form_models import (
    ModeloFormBinding,
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
from ......application.modelo.work_form_service import ModeloWorkFormLoadV1
from ......application.modelo.work_review import ModeloWorkProgress
from ......core.aggregation import BindingSourceKind
from ......core.casilla_id import CasillaId
from ......core.errors.hierarchy import CadrumoError
from ......core.external_constants import OutputLanguage
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.schema_form_layouts import FormCellKind, FormPageCondition
from ...m303_evidence import OrdinaryM303FilingEvidenceSubmission
from ..header import ResultView, StatusLine
from ..ports import (
    WorkbenchCalculationEvidence,
    WorkbenchChange,
    WorkbenchExportOffer,
    WorkbenchExportRequest,
    WorkbenchParsed,
    WorkbenchParseOutcome,
    WorkbenchPreflight,
    WorkbenchRefused,
)

if TYPE_CHECKING:
    from ......application.modelo.operation_definitions import ModeloExportPublicResultV2
    from ......application.operations.frontend_projection import OperationPublicProjectionV1
    from ....operations.controller import OperationController


def _text(text: str) -> ModeloFormText:
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.LOCALIZED)


def fed_by(binding_id: str, kind: BindingSourceKind, *, resolved: bool = True) -> ModeloFormBinding:
    """Build one synthetic binding with the product's real policy for its source kind."""
    return ModeloFormBinding(binding_id=binding_id, policy=source_policy(kind), resolved=resolved)


def form_field(
    box: str,
    label: str,
    origin: ModeloFormOrigin,
    value: Decimal | None = None,
    *,
    editability: ModeloFormEditability = ModeloFormEditability.EDITABLE_VALUE,
    role: CalculationReportRowRole | None = None,
    help_text: str | None = None,
    bindings: tuple[ModeloFormBinding, ...] = (),
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
        bindings=bindings,
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
        bindings=(fed_by("m130.ingresos", BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION),),
    )
    expenses = form_field(
        "02",
        "Gastos deducibles",
        ModeloFormOrigin.IMPORTED,
        Decimal("9500.00"),
        editability=ModeloFormEditability.LOCKED_SOURCE,
        bindings=(fed_by("m130.gastos", BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION),),
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
        bindings=(
            fed_by("m130.retenciones", BindingSourceKind.RETENCIONES_AGGREGATION, resolved=False),
            fed_by("m130.retencion_registro", BindingSourceKind.WITHHOLDING),
        ),
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
    refusal: str | None = None

    def load(self, language: OutputLanguage) -> ModeloWorkFormLoadV1:
        """Return the fixed form."""
        self.loads += 1
        return ModeloWorkFormLoadV1(form=self.form, verified=self.verified, filed=self.filed)

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

    def edit_refusal(self) -> str | None:
        """Why editing is unavailable, as the test set it."""
        return self.refusal


def status_line_of(text: str) -> StatusLine:
    """The header's result line saying ``text``, with no chip, as a dialog repeats it."""
    return StatusLine(ResultView(text=text, short_text=text, stale=None, failed=False, help=()), chips=())


@dataclass
class FakeActions:
    """Parses Spanish decimals and records every operation the workbench asks for.

    Operations raise instead of opening a supervised operation, so a test proves
    what the workbench submitted and that a failure leaves the staged changes in
    place.
    """

    applied: list[tuple[WorkbenchChange, ...]] = field(default_factory=list)
    requested: list[str] = field(default_factory=list)
    evidence: WorkbenchCalculationEvidence | None = None
    evidence_given: list[OrdinaryM303FilingEvidenceSubmission | None] = field(default_factory=list)
    exports: list[WorkbenchExportRequest] = field(default_factory=list)
    asks_elections: bool = False
    refusal: CadrumoError | None = None
    preflight_answer: WorkbenchPreflight = field(default_factory=WorkbenchPreflight)
    checked: list[tuple[WorkbenchChange, ...]] = field(default_factory=list)
    refreshed: int = 0

    def parse(self, field: ModeloFormField, lexeme: str, language: OutputLanguage) -> WorkbenchParseOutcome:
        """Read a Spanish decimal, or refuse with a fix-it sentence."""
        try:
            value = Decimal(lexeme.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return WorkbenchRefused(message="Escribe un importe, por ejemplo 1.234,56.")
        return WorkbenchParsed(value=value, display=f"{value:.2f}".replace(".", ",") + "\u00a0\u20ac")

    async def preflight(self, changes: tuple[WorkbenchChange, ...]) -> WorkbenchPreflight:
        """Record the checked changes and answer what the test set."""
        self.checked.append(changes)
        return self.preflight_answer

    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationController:
        """Record the submitted changes, then fail as an unavailable service would."""
        self.applied.append(changes)
        raise RuntimeError("no operation service in this test")

    def take_apply_prerequisite(self) -> None:
        """The fake failed service has no private calculation prerequisite."""
        return None

    def calculation_evidence(self) -> WorkbenchCalculationEvidence | None:
        """Return the evidence the next calculation asks for, as the test set it."""
        return self.evidence

    async def calculate(self, m303_evidence: OrdinaryM303FilingEvidenceSubmission | None = None) -> OperationController:
        """Record a calculate request and the evidence it carried; refuse as the test asks."""
        self.requested.append("calculate")
        self.evidence_given.append(m303_evidence)
        if self.refusal is not None:
            raise self.refusal
        raise RuntimeError("no operation service in this test")

    async def verify(self) -> OperationController:
        """Record a verify request."""
        self.requested.append("verify")
        raise RuntimeError("no operation service in this test")

    async def file(self) -> OperationController:
        """Record a file request."""
        self.requested.append("file")
        raise RuntimeError("no operation service in this test")

    def export_offer(self) -> WorkbenchExportOffer:
        """Offer the filing file, and the payment elections when the test asks for them."""
        return WorkbenchExportOffer(artefacts=(ModeloExportArtefact.FICHERO_BOE,), asks_elections=self.asks_elections)

    async def export(self, request: WorkbenchExportRequest) -> OperationController:
        """Record an export request."""
        self.exports.append(request)
        raise RuntimeError("no operation service in this test")

    async def export_result(self, projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV2 | None:
        """No export ever settles in these tests."""
        return None

    def refresh_product(self) -> None:
        """Count the product refreshes asked for."""
        self.refreshed += 1


__all__ = ["FakeActions", "FakeReader", "form_field", "synthetic_form"]
