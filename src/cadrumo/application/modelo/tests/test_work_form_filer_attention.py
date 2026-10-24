"""The form asks the filer only what could under-declare, says what to do about each finding, and prints rates.

Every form is built by the real builder over the published registry and its
published layout. Expectations come from the registry's own declarations, not
from the builder:

* a value the filer types that nobody is recorded as having entered is assumed,
  and waits for the filer, only in a box verification requires or when it is
  not zero; an optional box holding zero is optional and empty, yet still
  counted as unattributed, because a recalculation returns it to source;
* a declaration recorded as filed has nothing left to enter or confirm, and
  every box on it stands done; a page that does not apply asks for no value;
* each finding carries the catalogue key of one sentence saying what to do,
  chosen by its message and then by its kind;
* a Modelo 303 rate box carries the one rate its row's base binding declares,
  and the rate the ledger bindings filling a row's base declare agrees with
  the literal the official design prints for its rate box.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ledger_iva_bindings import LedgerIvaProvider
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_form_layouts import FormCellKind
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.legal_inventory import legal_reference_ids
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...calculations.cross_period_models import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    NoPriorObligationProvenance,
)
from ..required_inputs import filer_required_casilla_ids
from ..verification_cross_period import cross_period_clean_state_findings
from ..work_form_models import (
    FINDING_KIND_ACTION_LOCALE_KEYS,
    FINDING_MESSAGE_ACTION_LOCALE_KEYS,
    ModeloFormAttention,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormRateUnit,
    ModeloFormStanding,
    ModeloWorkForm,
    field_needs_filer,
    finding_action_locale_key,
    section_fields,
)
from ..work_form_wording import field_value_text, origin_explanation, origin_words
from ..work_review import build_modelo_work_review_casillas
from .work_form_fixture import built_form, form_casilla, form_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACTION = "application.modelo.work_form.finding_action."
_LEGAL_REF = "rd-439-2007:art-110"


def _casilla_ids(fields: tuple[ModeloFormField, ...] | list[ModeloFormField]) -> set[str]:
    return {str(field.address.casilla_id) for field in fields if isinstance(field.address, ModeloFormCasillaAddressV1)}


def _optional_money_box(operation: PinnedAuthorityOperation) -> str:
    """A Modelo 210 amount the filer types and verification does not require, beside the gross income it does."""
    revision = form_snapshot(operation, "210", 2025, "0A").revision
    required = {str(item) for item in filer_required_casilla_ids(revision)}
    assert "rendimientos_integros" in required
    return next(
        str(casilla.id)
        for casilla in revision.casillas
        if casilla.input_kind is InputKind.MANUAL
        and casilla.data_type is CasillaDataType.MONEY
        and str(casilla.id) not in required
    )


# -- which held values are assumed -------------------------------------------


def test_a_held_value_is_assumed_only_where_it_could_under_declare(operation: PinnedAuthorityOperation) -> None:
    """Modelo 210 requires the gross income it taxes; its other typed boxes are optional.

    The four cases are a required box empty and holding zero or an amount, and
    an optional box holding zero or an amount. Nobody's entry is recorded.
    """
    optional = _optional_money_box(operation)

    empty = built_form(operation, "210", 2025, "0A")
    zeros = built_form(
        operation, "210", 2025, "0A", held={"rendimientos_integros": Decimal("0"), optional: Decimal("0")}
    )
    amounts = built_form(
        operation, "210", 2025, "0A", held={"rendimientos_integros": Decimal("1200.00"), optional: Decimal("35.00")}
    )

    assert form_casilla(empty, "rendimientos_integros").origin is ModeloFormOrigin.NEEDS_INPUT
    assert form_casilla(zeros, "rendimientos_integros").origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert form_casilla(amounts, "rendimientos_integros").origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert form_casilla(empty, optional).origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert form_casilla(zeros, optional).origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert form_casilla(amounts, optional).origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM

    # Every held value nobody entered stays unattributed, assumed or not; a box
    # that holds nothing is not.
    assert not form_casilla(empty, optional).unattributed
    assert form_casilla(zeros, optional).unattributed
    assert form_casilla(zeros, "rendimientos_integros").unattributed
    assert form_casilla(amounts, optional).unattributed

    # The counts follow the origins.
    assert zeros.counts.default_to_confirm == 1
    assert amounts.counts.default_to_confirm == 2


def test_a_value_the_filer_entered_is_never_assumed_whatever_it_holds(operation: PinnedAuthorityOperation) -> None:
    form = built_form(
        operation,
        "210",
        2025,
        "0A",
        held={"rendimientos_integros": Decimal("0")},
        entered=frozenset({"rendimientos_integros"}),
    )

    field = form_casilla(form, "rendimientos_integros")
    assert field.origin is ModeloFormOrigin.ENTERED
    assert not field.unattributed


def test_modelo_100_calculated_elsewhere_asks_only_for_the_income_it_holds(
    operation: PinnedAuthorityOperation,
) -> None:
    """A Renta calculated outside the workbench leaves every typed box holding a value nobody is recorded entering.

    As the documented Renta walkthrough calculates it, the filer supplies the
    salary in box 0003 and every other typed box holds zero. Read literally, the
    earlier rule assumed every one of them; the rule now assumes the salary and
    any box verification requires, and nothing else, while every held box stays
    unattributed.
    """
    snapshot = form_snapshot(operation, "100", 2025, "0A")
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    typed = {
        str(row.casilla_id) for row in rows if row.declared_input_kind is InputKind.MANUAL and not row.absent_by_design
    }
    held = {casilla_id: Decimal("0") for casilla_id in typed} | {"0003": Decimal("24000")}
    required = {str(item) for item in filer_required_casilla_ids(snapshot.revision)}

    form = built_form(operation, "100", 2025, "0A", held=held, entered=None)

    assumed = [field for field in form.fields() if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM]
    unattributed = [field for field in form.fields() if field.unattributed]
    # Before the rule changed, every unattributed box was assumed.
    assert len(unattributed) == len(typed) > 1000
    assert _casilla_ids(unattributed) == typed
    # After it, only the salary and the required boxes are.
    assert _casilla_ids(assumed) == {"0003"} | (required & typed)
    assert form.counts.default_to_confirm == len(assumed) < 50


# -- a declaration recorded as filed -----------------------------------------


def test_a_declaration_recorded_as_filed_counts_nothing_to_do(operation: PinnedAuthorityOperation) -> None:
    """A draft with a missing required box and an assumed amount counts both; the same declaration filed counts none."""
    held = {_optional_money_box(operation): Decimal("35.00")}
    draft = built_form(operation, "210", 2025, "0A", held=held)
    filed = built_form(operation, "210", 2025, "0A", held=held, lifecycle=CalculationRevisionState.PRESENTADO)

    assert draft.counts.needs_input > 0
    assert draft.counts.default_to_confirm > 0
    assert form_casilla(filed, "rendimientos_integros").origin is ModeloFormOrigin.NEEDS_INPUT
    for counts in (
        filed.counts,
        *(page.counts for page in filed.pages),
        *(section.counts for page in filed.pages for section in page.sections),
    ):
        assert counts.needs_input == 0
        assert counts.default_to_confirm == 0
    assert filed.counts.total == draft.counts.total
    assert filed.counts.imported == draft.counts.imported


# -- where each box stands for the filer --------------------------------------

_ASKS = {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM}
_NEEDS_YOU = _ASKS | {ModeloFormOrigin.CALCULATION_FAILED}
_WAITING = {ModeloFormOrigin.NOT_IMPORTED_YET, ModeloFormOrigin.NOT_CALCULATED_YET}


def _expected_standing(field: ModeloFormField, *, applies: bool) -> ModeloFormStanding:
    if field.blockers:
        return ModeloFormStanding.NEEDS_YOU
    if field.origin in _NEEDS_YOU and (applies or field.origin not in _ASKS):
        return ModeloFormStanding.NEEDS_YOU
    if field.origin in _WAITING:
        return ModeloFormStanding.WAITING
    return ModeloFormStanding.DONE


def _page_fields(form: ModeloWorkForm) -> Iterator[tuple[ModeloFormField, bool]]:
    for page in form.pages:
        for section in page.sections:
            for field in section_fields(section):
                yield field, page.applies is not False
    for field in form.working_figures:
        yield field, True
    for item in form.unplaced:
        yield item.field, True


def test_every_box_stands_where_its_origin_and_page_put_it(operation: PinnedAuthorityOperation) -> None:
    """A draft Modelo 210 with a required box empty and an optional amount nobody entered."""
    form = built_form(operation, "210", 2025, "0A", held={_optional_money_box(operation): Decimal("35.00")})

    standings = [(field.standing, _expected_standing(field, applies=applies)) for field, applies in _page_fields(form)]
    assert standings
    assert all(actual is expected for actual, expected in standings)
    assert {actual for actual, _ in standings} >= {ModeloFormStanding.NEEDS_YOU, ModeloFormStanding.DONE}
    asked = [field for field, _ in _page_fields(form) if field.standing is ModeloFormStanding.NEEDS_YOU]
    assert len(asked) == form.counts.needs_input + form.counts.default_to_confirm + form.counts.blocked


def test_a_page_that_does_not_apply_asks_for_no_value(operation: PinnedAuthorityOperation) -> None:
    """Modelo 303's annual page applies only in the fourth quarter and the twelfth month.

    The same typed box, holding an amount nobody entered, is assumed in both
    quarters; it asks the filer only where its page applies.
    """
    annual = next(page for page in built_form(operation, "303", 2026, "4T").pages if page.id == "dp30304")
    page_box = next(
        str(field.address.casilla_id)
        for section in annual.sections
        for field in section_fields(section)
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.origin is ModeloFormOrigin.OPTIONAL_EMPTY
        and field.data_type == "money"
    )
    held = {page_box: Decimal("125.00")}
    first = built_form(operation, "303", 2026, "1T", held=held)
    fourth = built_form(operation, "303", 2026, "4T", held=held)

    assert next(page for page in first.pages if page.id == "dp30304").applies is False
    assert next(page for page in fourth.pages if page.id == "dp30304").applies is True
    assert form_casilla(first, page_box).origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert form_casilla(fourth, page_box).origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert form_casilla(first, page_box).standing is ModeloFormStanding.DONE
    assert form_casilla(fourth, page_box).standing is ModeloFormStanding.NEEDS_YOU
    assert not field_needs_filer(form_casilla(first, page_box), applies=False)
    assert field_needs_filer(form_casilla(fourth, page_box))


def test_a_box_the_design_fixes_stands_done_and_is_never_confirmed(operation: PinnedAuthorityOperation) -> None:
    """Modelo 303's printed rates are design constants: nothing is asked of them and nothing can be confirmed.

    The rate boxes hold the figures a calculation gives them, which nobody is
    recorded as having entered: as typed boxes they would be assumed and ask
    the filer, so this proves the printed rate replaces that reading.
    """
    rates = _rate_cells(built_form(operation, "303", 2026, "1T"))
    form = built_form(operation, "303", 2026, "1T", held=dict.fromkeys(rates, Decimal("21.00")))
    fixed = [
        cell.field
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormGridBlock)
        for row in block.rows
        for cell in row.cells
        if cell.kind is FormCellKind.DESIGN_CONSTANT and cell.field is not None
    ]
    assert fixed
    assert {field.standing for field in fixed} == {ModeloFormStanding.DONE}
    assert not any(field.confirmable for field in fixed)


def test_on_a_declaration_recorded_as_filed_every_box_is_done(operation: PinnedAuthorityOperation) -> None:
    held = {_optional_money_box(operation): Decimal("35.00")}
    filed = built_form(operation, "210", 2025, "0A", held=held, lifecycle=CalculationRevisionState.PRESENTADO)

    assert {field.standing for field, _ in _page_fields(filed)} == {ModeloFormStanding.DONE}


# -- the words each box carries ------------------------------------------------


def _catalogue(key: str, language: OutputLanguage) -> str:
    text = lookup_translation(key, locale=language.value)
    assert text is not None
    return text


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_every_box_carries_its_origin_and_editability_in_the_forms_language(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    """A draft Modelo 210: the required box that is empty, and an optional box left at zero."""
    optional = _optional_money_box(operation)
    form = built_form(operation, "210", 2025, "0A", held={optional: Decimal("0")}, language=language)

    assert all(field.origin_words and field.editability_words for field in form.fields())
    assert form_casilla(form, "rendimientos_integros").origin_words == _catalogue(
        "tui.modelo.workbench.origin.needs_input", language
    )
    assert form_casilla(form, optional).origin_words == _catalogue(
        "tui.modelo.workbench.origin_held_zero.optional_empty", language
    )
    assert form_casilla(form, optional).editability_words == _catalogue(
        f"tui.modelo.workbench.editability.{form_casilla(form, optional).editability.value}", language
    )


def test_on_a_declaration_recorded_as_filed_an_empty_box_says_what_it_holds(
    operation: PinnedAuthorityOperation,
) -> None:
    filed = built_form(operation, "210", 2025, "0A", lifecycle=CalculationRevisionState.PRESENTADO)

    assert form_casilla(filed, "rendimientos_integros").origin_words == _catalogue(
        "tui.modelo.workbench.origin_filed.needs_input", OutputLanguage.EN
    )


def test_the_carried_words_are_the_ones_the_rule_gives_for_the_box(operation: PinnedAuthorityOperation) -> None:
    """Every frontend shows the carried words; the rule a terminal applies live gives the same ones."""
    form = built_form(operation, "130", 2026, "1T", held={"05": Decimal("0")})
    for field in form.fields():
        assert field.origin_words == origin_words(field, recorded=False, language=OutputLanguage.EN)
        assert field.origin_explanation == origin_explanation(field, OutputLanguage.EN)


@pytest.mark.parametrize(
    ("language", "amount", "zero"),
    [
        (OutputLanguage.EN, "1,234.56\u00a0€", "0.00\u00a0€"),
        (OutputLanguage.ES, "1.234,56\u00a0€", "0,00\u00a0€"),
    ],
)
def test_every_box_carries_the_figure_it_shows_in_the_forms_language(
    operation: PinnedAuthorityOperation, language: OutputLanguage, amount: str, zero: str
) -> None:
    """A Modelo 210 amount held, an optional box left at zero, and the required box still empty."""
    optional = _optional_money_box(operation)
    form = built_form(
        operation,
        "210",
        2025,
        "0A",
        held={"rendimientos_integros": Decimal("1234.56"), optional: Decimal("0")},
        language=language,
    )

    assert form_casilla(form, "rendimientos_integros").value_text == amount
    # A held zero is a figure, never shown as missing.
    assert form_casilla(form, optional).value_text == zero
    assert (
        form_casilla(built_form(operation, "210", 2025, "0A", language=language), "rendimientos_integros").value_text
        is None
    )


@pytest.mark.parametrize(
    ("language", "title", "period"),
    [
        (OutputLanguage.EN, "Modelo 130 · IRPF instalment payment, direct assessment", "1st quarter 2026"),
        (OutputLanguage.ES, "Modelo 130 · IRPF pago fraccionado estimación directa", "1.er trimestre 2026"),
    ],
)
def test_the_form_names_its_modelo_and_period_in_its_own_language(
    operation: PinnedAuthorityOperation, language: OutputLanguage, title: str, period: str
) -> None:
    form = built_form(operation, "130", 2026, "1T", language=language)

    assert (form.modelo_title, form.modelo_number, form.period_words) == (title, "Modelo 130", period)


def test_a_printed_rate_shows_as_the_form_prints_it_and_a_waiting_box_shows_no_figure(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "303", 2026, "1T")
    printed = [cell.field for cell in _rate_cells(form).values() if cell.field is not None and cell.field.printed_rate]
    assert printed
    for field in printed:
        assert field.value_text is not None
        assert field.value_text.endswith("%")
    # A box whose calculation waits or failed shows no figure, whatever it still holds.
    held = form_casilla(
        built_form(operation, "210", 2025, "0A", held={"rendimientos_integros": Decimal("1234.56")}),
        "rendimientos_integros",
    )
    assert field_value_text(held, OutputLanguage.EN) is not None
    for origin in (ModeloFormOrigin.NOT_CALCULATED_YET, ModeloFormOrigin.CALCULATION_FAILED):
        assert field_value_text(held.model_copy(update={"origin": origin}), OutputLanguage.EN) is None


# -- what to do about each finding -------------------------------------------


def _requirement(operation: PinnedAuthorityOperation) -> CrossPeriodDependencyRequirement:
    assert _LEGAL_REF in legal_reference_ids(operation)
    return CrossPeriodDependencyRequirement(
        source_modelo="100",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        source_casilla_ids=(validated_casilla_id("0670"),),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("modelo-130-pagos-fraccionados-anteriores",),
        legal_refs=(_LEGAL_REF,),
        source_refs=("aeat-modelo-130-instructions",),
    )


def _suppressed_by_the_declared_start(operation: PinnedAuthorityOperation) -> ModeloVerificationFinding:
    """The finding the real verification raises when the filer's declared activity start scopes out the 2025 Renta."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(operation),
        no_prior_obligation=NoPriorObligationProvenance(activity_start_date=date(2026, 1, 1)),
    )
    verdict = CrossPeriodCleanStateVerdict(
        bucket_id="13000000-0000-4000-8000-000000000456",
        target_modelo="130",
        target_filing_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        dependencies=(evidence,),
    )
    (finding,) = cross_period_clean_state_findings(verdict)
    return finding


def _evidence_finding(message: str, *, blocking: bool) -> ModeloVerificationFinding:
    """A missing-document finding with the kind and severity its producer gives it."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE if blocking else ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.BLOCKING if blocking else ModeloVerificationFindingSeverity.WARNING,
        message_locale_key=f"application.modelo.findings.{message}",
        legal_refs=(_LEGAL_REF,),
    )


def test_each_finding_says_how_loud_it_is_and_what_to_do(operation: PinnedAuthorityOperation) -> None:
    suppressed = _suppressed_by_the_declared_start(operation)
    output = _evidence_finding("transaction_evidence_missing_output", blocking=False)
    deductible = _evidence_finding("transaction_evidence_missing_deductible", blocking=True)
    unmapped = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.registry_advisory_predicate_fired",
        legal_refs=(_LEGAL_REF,),
    )

    form = built_form(operation, "130", 2026, "1T", findings=(suppressed, output, deductible, unmapped))
    issues = {issue.finding.message_locale_key: issue for issue in form.issues}

    assert suppressed.message_locale_key == "application.modelo.findings.cross_period_operator_declared_suppression"
    explained = issues[suppressed.message_locale_key]
    assert explained.attention is ModeloFormAttention.INFO
    assert explained.action_locale_key == f"{_ACTION}nothing_to_do"
    for missing in (output, deductible):
        assert issues[missing.message_locale_key].action_locale_key == f"{_ACTION}attach_document"
    assert issues[output.message_locale_key].attention is ModeloFormAttention.CHECK
    assert issues[deductible.message_locale_key].attention is ModeloFormAttention.BLOCKS
    assert issues[unmapped.message_locale_key].action_locale_key == f"{_ACTION}read_and_decide"


def test_an_explanation_raised_as_a_blocker_takes_its_kinds_action(operation: PinnedAuthorityOperation) -> None:
    """A finding that must be resolved never tells the filer there is nothing to do."""
    explanation = _suppressed_by_the_declared_start(operation)
    blocker = explanation.model_copy(
        update={
            "kind": ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
            "severity": ModeloVerificationFindingSeverity.BLOCKING,
        }
    )

    assert finding_action_locale_key(explanation) == f"{_ACTION}nothing_to_do"
    assert finding_action_locale_key(blocker) == f"{_ACTION}settle_earlier_declaration"
    with pytest.raises(ValueError, match="action"):
        ModeloFormIssue(finding=blocker, action_locale_key=f"{_ACTION}nothing_to_do")


def test_every_finding_kind_has_an_action() -> None:
    assert set(FINDING_KIND_ACTION_LOCALE_KEYS) == set(ModeloVerificationFindingKind)


@pytest.mark.parametrize("language", [language.value for language in OutputLanguage])
def test_every_action_and_every_mapped_message_is_in_the_catalogue(language: str) -> None:
    keys = {
        *FINDING_KIND_ACTION_LOCALE_KEYS.values(),
        *FINDING_MESSAGE_ACTION_LOCALE_KEYS,
        *FINDING_MESSAGE_ACTION_LOCALE_KEYS.values(),
    }

    missing = sorted(key for key in keys if lookup_translation(key, locale=language) is None)

    assert not missing, f"finding keys with no {language} text: {missing}"


# -- the rate a rate box prints ----------------------------------------------


def _rate_cells(form: ModeloWorkForm) -> dict[str, ModeloFormGridCell]:
    """Every grid cell that shows a rate, by the casilla it shows."""
    return {
        str(cell.field.address.casilla_id): cell
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormGridBlock)
        for row in block.rows
        for cell in row.cells
        if cell.field is not None
        and isinstance(cell.field.address, ModeloFormCasillaAddressV1)
        and cell.field.data_type == "ratio"
    }


def test_a_303_rate_box_prints_the_one_rate_its_base_binding_declares(operation: PinnedAuthorityOperation) -> None:
    """Row [165]-[166] fills its base from a binding that admits one rate, and its rate box claims that rate.

    Rows [01]-[02], [04]-[05] and [07]-[08] fill their base by a formula that
    adds the promoter's autoconsumo to the ledger's base, row [153]-[154] admits
    two transitional rates and row [150]-[151] has no binding, so none of their
    rate boxes claims one.
    """
    snapshot = form_snapshot(operation, "303", 2026, "1T")
    bindings = {str(item.id): item for item in snapshot.revision.bindings}
    casillas = {str(item.id): item for item in snapshot.revision.casillas}
    cells = _rate_cells(built_form(operation, "303", 2026, "1T"))

    field = cells["166"].field
    assert field is not None
    rate = field.grounded_rate
    assert rate is not None
    assert rate.ratio == Decimal("0.02")
    assert rate.percent() == Decimal(2)
    assert rate.unit is ModeloFormRateUnit.FRACTION
    base_binding = casillas["165"].binding
    assert str(rate.binding_id) == str(base_binding)
    provider = bindings[str(base_binding)].provider
    assert isinstance(provider, LedgerIvaProvider)
    assert provider.applied_rates == (Decimal("0.02"),)
    for base_box in ("01", "04", "07"):
        assert casillas[base_box].input_kind is InputKind.COMPUTED, base_box
        assert casillas[base_box].binding is None, base_box
    for rate_box in ("02", "05", "08", "154", "151"):
        field = cells[rate_box].field
        assert field is not None
        assert field.grounded_rate is None, rate_box


def _grid_rows(form: ModeloWorkForm) -> list[tuple[ModeloFormGridCell, ...]]:
    """Every official grid row's cells, in the form's order."""
    return [
        row.cells
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormGridBlock)
        for row in block.rows
    ]


def test_a_grounded_rate_agrees_with_the_rate_the_official_design_prints(operation: PinnedAuthorityOperation) -> None:
    """The design prints [02] as 00400 and [05] as 01000, hundredths of a per cent: the same rates, found apart.

    Their rows' base boxes [01] and [04] add the promoter's autoconsumo to the
    ledger's base by formula. The rate compared is the one declared by the
    rate-specific ledger binding that fills the ledger's base each formula adds;
    the filer's autoconsumo base, which no binding fills, declares none.
    """
    snapshot = form_snapshot(operation, "303", 2026, "1T")
    bindings = {str(item.id): item for item in snapshot.revision.bindings}
    casillas = {str(item.id): item for item in snapshot.revision.casillas}
    formulas = {str(item.id): item for item in snapshot.revision.formulas}

    def added(expression: FormulaExpression) -> Iterator[str]:
        """The casillas a formula adds up."""
        if expression.casilla_id is not None:
            yield str(expression.casilla_id)
        elif expression.op == "add":
            for arg in expression.args:
                yield from added(arg)

    def declared_rates(base: str) -> set[Decimal]:
        """Every rate the rate-specific ledger bindings that fill a base box declare, bound or added by formula."""
        casilla = casillas[base]
        sources = (base,) if casilla.formula is None else tuple(added(formulas[str(casilla.formula)].expression))
        rates: set[Decimal] = set()
        for source in sources:
            filling = casillas[source]
            for binding_id in (filling.binding, *filling.alternate_bindings):
                provider = None if binding_id is None else bindings[str(binding_id)].provider
                if isinstance(provider, LedgerIvaProvider) and provider.applied_rates is not None:
                    rates.update(provider.applied_rates)
        return rates

    compared: set[str] = set()
    for cells in _grid_rows(built_form(operation, "303", 2026, "1T")):
        base = cells[0].field
        for cell in cells:
            if cell.kind is not FormCellKind.DESIGN_CONSTANT or cell.field is None or cell.literal is None:
                continue
            if (
                cell.field.data_type != "ratio"
                or base is None
                or not isinstance(base.address, ModeloFormCasillaAddressV1)
            ):
                continue
            rates = declared_rates(str(base.address.casilla_id))
            if not rates:
                continue
            assert rates == {Decimal(int(cell.literal)) / 10000}, cell.field.box
            compared.add(str(cell.field.box))
    assert compared == {"02", "05"}


def test_no_field_but_a_rate_box_carries_a_rate(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "303", 2026, "1T")

    carrying = [
        field
        for page in form.pages
        for section in page.sections
        for field in section_fields(section)
        if field.grounded_rate is not None
    ]

    assert carrying
    assert all(field.data_type == "ratio" for field in carrying)
    assert all(
        field.grounded_rate is None for field in (*form.working_figures, *(item.field for item in form.unplaced))
    )
