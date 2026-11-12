"""A small synthetic editor form and reader for driving the workbench screen.

Two official pages and the calculation details: a first page with a finished
section and an official grid, a second page with a box that needs the filer,
and one working figure. Income and expenses come from the ledger; the
withholding box is fed by two registers, one of which has produced nothing yet.
Values are synthetic. The reader counts its calls so a
test can prove the screen read off the event loop exactly as often as it should.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ......application.modelo.calculation_report import CalculationReportRowRole
from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ......application.modelo.casilla_help_formula import ModeloHelpFormulaV1
from ......application.modelo.source_policy import source_policy
from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_declaration_facts import ModeloFormYearProjection
from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormBinding,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormStanding,
    ModeloFormText,
    ModeloFormTextDisclosure,
)
from ......application.modelo.work_form_models import (
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormLayoutProvenance,
    ModeloFormPage,
    ModeloFormSection,
    ModeloWorkForm,
)
from ......application.modelo.work_form_outline import form_outline
from ......application.modelo.work_form_service import ModeloWorkFormLoadV1, modelo_form_snapshot
from ......application.modelo.work_review import (
    ModeloWorkProgress,
    ModeloWorkReview,
    ModeloWorkReviewCasilla,
    build_modelo_work_review_casillas,
)
from ......core.aggregation import BindingSourceKind
from ......core.authority_grade import RegistryAuthorityGrade
from ......core.casilla_id import CasillaId
from ......core.errors.hierarchy import CadrumoError
from ......core.external_constants import OutputLanguage
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.schema import RegistrySnapshot
from ......domain.calculations.registry.schema_form_layouts import FormCellKind, FormPageCondition
from ......domain.calculations.registry.schema_references import TemporalProjectionDirection
from ......domain.modelos.calculation_revision import CalculationRevisionState
from ......domain.modelos.codes import ModeloCode
from ......domain.modelos.verification_report import ModeloVerificationFinding
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
    from ......application.modelo.export_projection import ModeloExportPublicResultV3
    from ......application.operations.frontend_projection import OperationPublicProjectionV1
    from ....operations.controller_port import OperationControllerPort


def form_text(text: str) -> ModeloFormText:
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
        label=form_text(label),
        help=help_text,
        data_type="money",
        value=value,
        origin=origin,
        editability=editability,
        required=origin is ModeloFormOrigin.NEEDS_INPUT,
        role=role,
        bindings=bindings,
    )


def form_counts(fields: list[ModeloFormField]) -> ModeloFormCounts:
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
        needs_you=sum(1 for item in fields if item.standing is ModeloFormStanding.NEEDS_YOU),
        could_not_calculate=count(ModeloFormOrigin.CALCULATION_FAILED),
    )


def form_section(section_id: str, heading: str, fields: list[ModeloFormField]) -> ModeloFormSection:
    blocks = tuple(ModeloFormFieldBlock(id=f"f{item.box}", field=item) for item in fields)
    return ModeloFormSection(
        id=section_id,
        heading=form_text(heading),
        official_heading=None,
        blocks=blocks,
        counts=form_counts(fields),
        applies=True,
    )


def registry_form_of(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    year: int,
    code: str,
    bucket_id: str,
    work_unit_id: str,
    findings: tuple[ModeloVerificationFinding, ...] = (),
    lifecycle_state: CalculationRevisionState | None = None,
    hold: Callable[[RegistrySnapshot, tuple[ModeloWorkReviewCasilla, ...]], tuple[ModeloWorkReviewCasilla, ...]]
    | None = None,
) -> ModeloWorkForm:
    """Build the form of one real published registry revision with no work calculated yet.

    ``hold`` may rewrite the review rows from the snapshot, so a caller can make chosen casillas hold a figure.
    """
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id=work_unit_id,
        calculation_revision_id=None,
        lifecycle_state=lifecycle_state,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=rows if hold is None else hold(snapshot, rows),
        findings=findings,
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def registry_form(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    year: int,
    code: str,
    findings: tuple[ModeloVerificationFinding, ...],
) -> ModeloWorkForm:
    """Build the form of one real published registry revision, carrying ``findings`` and no work yet."""
    return registry_form_of(
        operation,
        modelo=modelo,
        year=year,
        code=code,
        bucket_id="13000000-0000-4000-8000-000000000349",
        work_unit_id="e" * 64,
        findings=findings,
    )


def authored_year_projection(period: Period) -> ModeloFormYearProjection:
    """Return the projection of a synthetic form whose edition authors its own filing year."""
    return ModeloFormYearProjection(
        direction=TemporalProjectionDirection.AUTHORED,
        authored_filing_year=period.filing_year,
        reachable_grade=RegistryAuthorityGrade.FILING,
        reachable_grade_words="Synthetic filing grade words",
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
            ModeloFormGridColumn(key="base", heading=form_text("Base imponible")),
            ModeloFormGridColumn(key="tipo", heading=form_text("Tipo %")),
            ModeloFormGridColumn(key="cuota", heading=form_text("Cuota")),
        ),
        rows=(
            ModeloFormGridRow(
                key="r21",
                heading=form_text("Régimen general 21 %"),
                cells=(
                    ModeloFormGridCell(kind=FormCellKind.CASILLA, field=base),
                    ModeloFormGridCell(kind=FormCellKind.DESIGN_CONSTANT, literal="21,00"),
                    ModeloFormGridCell(kind=FormCellKind.CASILLA, field=quota),
                ),
            ),
        ),
    )
    first_section = form_section("p1.s1", "I. Actividades económicas", [income, expenses, net])
    grid_section = ModeloFormSection(
        id="p1.s2",
        heading=form_text("IVA devengado"),
        official_heading=None,
        blocks=(grid,),
        counts=form_counts([base, quota]),
        applies=True,
    )
    second_section = form_section("p2.s1", "III. Total liquidación", [withholding, result])
    pages = (
        ModeloFormPage(
            id="p1",
            heading=form_text("Liquidación"),
            official_ref="DR13001",
            condition=FormPageCondition.ALWAYS,
            applies=True,
            sections=(first_section, grid_section),
            counts=form_counts([income, expenses, net, base, quota]),
        ),
        ModeloFormPage(
            id="p2",
            heading=form_text("Resultado"),
            official_ref="DR13002",
            condition=FormPageCondition.ALWAYS,
            applies=True,
            sections=(second_section,),
            counts=form_counts([withholding, result]),
        ),
    )
    every = [income, expenses, net, base, quota, withholding, result, working]
    period = Period.from_year_and_code(2026, "1T")
    return ModeloWorkForm(
        modelo="130",
        filing_year=period.filing_year,
        period=period,
        registry_revision_id="2019-y-siguientes",
        year_projection=authored_year_projection(period),
        work_unit_id="a" * 64,
        calculation_revision_id=("b" * 64) if calculated else None,
        language=OutputLanguage.ES,
        layout_provenance=ModeloFormLayoutProvenance.GENERATED,
        pages=pages,
        outline=form_outline((), pages, OutputLanguage.ES, filed=False, working_figures=(working,)),
        working_figures=(working,),
        result_addresses=("19",),
        counts=form_counts(every),
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        operator_entries_known=True,
        edit_admitted=True,
    )


def with_pages(form: ModeloWorkForm, pages: tuple[ModeloFormPage, ...], **update: object) -> ModeloWorkForm:
    """The form showing ``pages`` instead, its outline grouping their sections page by page."""
    paged = form.model_copy(update={**update, "pages": pages})
    outline = form_outline(
        (), pages, form.language, filed=False, unplaced=paged.unplaced, working_figures=paged.working_figures
    )
    return paged.model_copy(update={"outline": outline})


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
    export_artefacts: tuple[ModeloExportArtefact, ...] = (ModeloExportArtefact.FICHERO_BOE,)
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

    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationControllerPort:
        """Record the submitted changes, then fail as an unavailable service would."""
        self.applied.append(changes)
        raise RuntimeError("no operation service in this test")

    async def take_apply_prerequisite(self) -> None:
        """The fake failed service has no private calculation prerequisite."""
        return None

    def calculation_evidence(self) -> WorkbenchCalculationEvidence | None:
        """Return the evidence the next calculation asks for, as the test set it."""
        return self.evidence

    async def calculate(
        self, m303_evidence: OrdinaryM303FilingEvidenceSubmission | None = None
    ) -> OperationControllerPort:
        """Record a calculate request and the evidence it carried; refuse as the test asks."""
        self.requested.append("calculate")
        self.evidence_given.append(m303_evidence)
        if self.refusal is not None:
            raise self.refusal
        raise RuntimeError("no operation service in this test")

    async def verify(self) -> OperationControllerPort:
        """Record a verify request."""
        self.requested.append("verify")
        raise RuntimeError("no operation service in this test")

    async def file(self) -> OperationControllerPort:
        """Record a file request."""
        self.requested.append("file")
        raise RuntimeError("no operation service in this test")

    def export_offer(self) -> WorkbenchExportOffer:
        """Offer the filing file, and the payment elections when the test asks for them."""
        return WorkbenchExportOffer(artefacts=self.export_artefacts, asks_elections=self.asks_elections)

    async def export(self, request: WorkbenchExportRequest) -> OperationControllerPort:
        """Record an export request."""
        self.exports.append(request)
        raise RuntimeError("no operation service in this test")

    async def export_result(self, projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV3 | None:
        """No export ever settles in these tests."""
        return None

    def refresh_product(self) -> None:
        """Count the product refreshes asked for."""
        self.refreshed += 1


__all__ = ["FakeActions", "FakeReader", "form_field", "synthetic_form"]
