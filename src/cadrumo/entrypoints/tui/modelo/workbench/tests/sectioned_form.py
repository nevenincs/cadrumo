"""A synthetic quarterly form with repeated headings, a page that may not apply and assumed values in several parts.

The first page prints "Resultado" in two separate parts, as some official
layouts do, with a corrective part between them. The second page is only for
the last quarter; the read model states whether it applies, and it holds a
missing value and an assumed one. The third page holds one more assumed value.
A second form holds one long section of assumed values, for a list that
scrolls. Values are synthetic.
"""

from __future__ import annotations

from decimal import Decimal

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.work_form_models import (
    ModeloFormCounts,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloFormValueSource,
    ModeloWorkForm,
)
from ......application.modelo.work_review import ModeloWorkProgress
from ......core.aggregation import BindingSourceKind
from ......core.external_constants import OutputLanguage
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.schema_form_layouts import FormPageCondition
from .workbench_fixture import fed_by, form_field

LAST_QUARTER_PAGE = "p2"
"""The page only the last quarter fills in."""


def _text(text: str) -> ModeloFormText:
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.LOCALIZED)


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


def _assumed(box: str, value: str) -> ModeloFormField:
    return form_field(box, f"Casilla manual {box}", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal(value))


def _page(
    page_id: str,
    heading: str,
    sections: tuple[ModeloFormSection, ...],
    fields: list[ModeloFormField],
    *,
    condition: FormPageCondition = FormPageCondition.ALWAYS,
    applies: bool | None = True,
) -> ModeloFormPage:
    return ModeloFormPage(
        id=page_id,
        heading=_text(heading),
        official_ref=None,
        condition=condition,
        applies=applies,
        sections=sections,
        counts=_counts(fields),
    )


def sectioned_form(*, last_quarter_applies: bool | None = False) -> ModeloWorkForm:
    """The form, with the last-quarter page stated to apply, not to apply, or undecided."""
    income = form_field(
        "01",
        "Ingresos computables",
        ModeloFormOrigin.IMPORTED,
        Decimal("24000.00"),
        editability=ModeloFormEditability.LOCKED_SOURCE,
        help_text="Box 01: Income from the activity in the quarter.",
        bindings=(fed_by("m130.ingresos", BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION),),
    ).model_copy(
        update={
            "source": ModeloFormValueSource(
                family=SourceFamily.RECORDS,
                binding_id="m130.ingresos",
                source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            )
        }
    )
    first_assumed = _assumed("05", "100.00")
    result_assumed = _assumed("07", "0.00")
    corrective = form_field("08", "Declaración complementaria", ModeloFormOrigin.OPTIONAL_EMPTY)
    second_result_assumed = _assumed("09", "12.00")
    missing_last_quarter = form_field("80", "Volumen anual de operaciones", ModeloFormOrigin.NEEDS_INPUT)
    assumed_last_quarter = _assumed("81", "5.00")
    other_assumed = _assumed("20", "3.00")
    first_fields = [income, first_assumed, result_assumed, corrective, second_result_assumed]
    pages = (
        _page(
            "p1",
            "Liquidación",
            (
                _section("p1.actividades", "I. Actividades económicas", [income, first_assumed]),
                _section("p1.resultado", "Resultado", [result_assumed]),
                _section("p1.rectificativa", "Rectificativa", [corrective]),
                _section("p1.resultado-2", "Resultado", [second_result_assumed]),
            ),
            first_fields,
        ),
        _page(
            LAST_QUARTER_PAGE,
            "Solo último periodo",
            (_section("p2.exonerados", "Exonerados del modelo 390", [missing_last_quarter, assumed_last_quarter]),),
            [missing_last_quarter, assumed_last_quarter],
            condition=FormPageCondition.PERIOD_RESTRICTED,
            applies=last_quarter_applies,
        ),
        _page("p3", "Información adicional", (_section("p3.otros", "Otros datos", [other_assumed]),), [other_assumed]),
    )
    every = [*first_fields, missing_last_quarter, assumed_last_quarter, other_assumed]
    return ModeloWorkForm(
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        registry_revision_id="2026-y-siguientes",
        work_unit_id="c" * 64,
        calculation_revision_id="d" * 64,
        language=OutputLanguage.ES,
        layout_provenance=ModeloFormLayoutProvenance.REVIEWED,
        pages=pages,
        working_figures=(),
        result_addresses=(),
        counts=_counts(every),
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        operator_entries_known=True,
        edit_admitted=True,
    )


def long_section_form(boxes: int) -> ModeloWorkForm:
    """One page holding one section of ``boxes`` assumed values, box 30 onwards, longer than a short list shows."""
    assumed = [_assumed(f"{30 + index:02d}", "1.00") for index in range(boxes)]
    page = _page("p1", "Liquidación", (_section("p1.manual", "Casillas manuales", assumed),), assumed)
    return sectioned_form().model_copy(update={"pages": (page,), "counts": _counts(assumed)})


__all__ = ["LAST_QUARTER_PAGE", "long_section_form", "sectioned_form"]
