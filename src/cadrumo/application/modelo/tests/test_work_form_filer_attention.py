"""The form asks the filer only what could under-declare, says what to do about each finding, and prints rates.

Every form is built by the real builder over the published registry and its
published layout. Expectations come from the registry's own declarations, not
from the builder:

* a value the filer types that nobody is recorded as having entered is assumed,
  and waits for the filer, only in a box verification requires or when it is
  not zero; an optional box holding zero is optional and empty, yet still
  counted as unattributed, because a recalculation returns it to source;
* a declaration recorded as filed has nothing left to enter or confirm;
* each finding carries the catalogue key of one sentence saying what to do,
  chosen by its message and then by its kind;
* a Modelo 303 rate box carries the one rate its row's base binding declares,
  and agrees with the literal the official design prints for it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ledger_iva_bindings import LedgerIvaProvider
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_form_layouts import FormCellKind
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.filing.schema import ModeloValueKind
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.codes import ModeloCode
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
from ..work_form import build_modelo_work_form
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
    ModeloWorkForm,
    finding_action_locale_key,
    section_fields,
)
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACTION = "application.modelo.work_form.finding_action."
_LEGAL_REF = "rd-439-2007:art-110"


def _snapshot(operation: PinnedAuthorityOperation, modelo: str, year: int, code: str) -> RegistrySnapshot:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    return modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)


def _form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    *,
    held: dict[str, Decimal] | None = None,
    entered: frozenset[str] | None = None,
    lifecycle: CalculationRevisionState | None = None,
    findings: tuple[ModeloVerificationFinding, ...] = (),
) -> ModeloWorkForm:
    """Build a form whose ``held`` boxes carry the calculation's values; ``entered`` ``None`` is an unknown record."""
    snapshot = _snapshot(operation, modelo, year, code)
    values = held or {}
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000455",
        modelo=modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, code),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=None,
        lifecycle_state=lifecycle,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            row.model_copy(update={"value": values[str(row.casilla_id)], "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) in values
            else row
            for row in rows
        ),
        findings=findings,
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None if entered is None else frozenset(validated_casilla_id(item) for item in entered),
        overridden_binding_ids=None if entered is None else frozenset(),
        language=OutputLanguage.EN,
    )


def _casilla(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(
        field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and str(field.address.casilla_id) == casilla_id
    )


def _casilla_ids(fields: tuple[ModeloFormField, ...] | list[ModeloFormField]) -> set[str]:
    return {str(field.address.casilla_id) for field in fields if isinstance(field.address, ModeloFormCasillaAddressV1)}


def _optional_money_box(operation: PinnedAuthorityOperation) -> str:
    """A Modelo 210 amount the filer types and verification does not require, beside the gross income it does."""
    revision = _snapshot(operation, "210", 2025, "0A").revision
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

    empty = _form(operation, "210", 2025, "0A")
    zeros = _form(operation, "210", 2025, "0A", held={"rendimientos_integros": Decimal("0"), optional: Decimal("0")})
    amounts = _form(
        operation, "210", 2025, "0A", held={"rendimientos_integros": Decimal("1200.00"), optional: Decimal("35.00")}
    )

    assert _casilla(empty, "rendimientos_integros").origin is ModeloFormOrigin.NEEDS_INPUT
    assert _casilla(zeros, "rendimientos_integros").origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert _casilla(amounts, "rendimientos_integros").origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert _casilla(empty, optional).origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert _casilla(zeros, optional).origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert _casilla(amounts, optional).origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM

    # Every held value nobody entered stays unattributed, assumed or not; a box
    # that holds nothing is not.
    assert not _casilla(empty, optional).unattributed
    assert _casilla(zeros, optional).unattributed
    assert _casilla(zeros, "rendimientos_integros").unattributed
    assert _casilla(amounts, optional).unattributed

    # The counts follow the origins.
    assert zeros.counts.default_to_confirm == 1
    assert amounts.counts.default_to_confirm == 2


def test_a_value_the_filer_entered_is_never_assumed_whatever_it_holds(operation: PinnedAuthorityOperation) -> None:
    form = _form(
        operation,
        "210",
        2025,
        "0A",
        held={"rendimientos_integros": Decimal("0")},
        entered=frozenset({"rendimientos_integros"}),
    )

    field = _casilla(form, "rendimientos_integros")
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
    snapshot = _snapshot(operation, "100", 2025, "0A")
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    typed = {
        str(row.casilla_id) for row in rows if row.declared_input_kind is InputKind.MANUAL and not row.absent_by_design
    }
    held = {casilla_id: Decimal("0") for casilla_id in typed} | {"0003": Decimal("24000")}
    required = {str(item) for item in filer_required_casilla_ids(snapshot.revision)}

    form = _form(operation, "100", 2025, "0A", held=held, entered=None)

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
    draft = _form(operation, "210", 2025, "0A", held=held)
    filed = _form(operation, "210", 2025, "0A", held=held, lifecycle=CalculationRevisionState.PRESENTADO)

    assert draft.counts.needs_input > 0
    assert draft.counts.default_to_confirm > 0
    assert _casilla(filed, "rendimientos_integros").origin is ModeloFormOrigin.NEEDS_INPUT
    for counts in (
        filed.counts,
        *(page.counts for page in filed.pages),
        *(section.counts for page in filed.pages for section in page.sections),
    ):
        assert counts.needs_input == 0
        assert counts.default_to_confirm == 0
    assert filed.counts.total == draft.counts.total
    assert filed.counts.imported == draft.counts.imported


# -- what to do about each finding -------------------------------------------


def _requirement(operation: PinnedAuthorityOperation) -> CrossPeriodDependencyRequirement:
    assert _LEGAL_REF in operation.legal_reference_ids()
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

    form = _form(operation, "130", 2026, "1T", findings=(suppressed, output, deductible, unmapped))
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
    """Rows [01]-[02], [04]-[05] and [165]-[166] each fill their base from a binding that admits one rate.

    Row [153]-[154] admits two transitional rates, row [07]-[08] is rate-blind
    and row [150]-[151] has no binding, so none of their rate boxes claims one.
    """
    snapshot = _snapshot(operation, "303", 2026, "1T")
    bindings = {str(item.id): item for item in snapshot.revision.bindings}
    casillas = {str(item.id): item for item in snapshot.revision.casillas}
    cells = _rate_cells(_form(operation, "303", 2026, "1T"))

    for rate_box, base_box, expected in (("02", "01", "0.04"), ("05", "04", "0.10"), ("166", "165", "0.02")):
        field = cells[rate_box].field
        assert field is not None
        rate = field.grounded_rate
        assert rate is not None, rate_box
        assert rate.ratio == Decimal(expected)
        assert rate.percent() == Decimal(expected) * 100
        assert rate.unit is ModeloFormRateUnit.FRACTION
        base_binding = casillas[base_box].binding
        assert str(rate.binding_id) == str(base_binding)
        provider = bindings[str(base_binding)].provider
        assert isinstance(provider, LedgerIvaProvider)
        assert provider.applied_rates == (Decimal(expected),)
    for rate_box in ("154", "08", "151"):
        field = cells[rate_box].field
        assert field is not None
        assert field.grounded_rate is None, rate_box


def test_a_grounded_rate_agrees_with_the_rate_the_official_design_prints(operation: PinnedAuthorityOperation) -> None:
    """The design prints [02] as 00400 and [05] as 01000, hundredths of a per cent: the same rates, found apart."""
    form = _form(operation, "303", 2026, "1T")
    printed = {
        casilla_id: cell for casilla_id, cell in _rate_cells(form).items() if cell.kind is FormCellKind.DESIGN_CONSTANT
    }

    compared = 0
    for casilla_id, cell in printed.items():
        rate = None if cell.field is None else cell.field.grounded_rate
        if rate is None or cell.literal is None:
            continue
        assert Decimal(int(cell.literal)) / 10000 == rate.ratio, casilla_id
        compared += 1
    assert compared == 2


def test_no_field_but_a_rate_box_carries_a_rate(operation: PinnedAuthorityOperation) -> None:
    form = _form(operation, "303", 2026, "1T")

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
