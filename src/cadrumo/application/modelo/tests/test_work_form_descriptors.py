"""The form states where values come from, what the result settles to, what is owed and when, and how loud each finding is.

Every form here is built by the real builder from the published registry and
its published layout. Expectations are stated from the declarations
themselves, not read back from the builder:

* a carry names the earlier declaration its binding's window reads, and a
  ledger aggregate names the filer's records;
* a result's direction is the official "tipo de declaración" code the modelo's
  record design assigns to the sign of its result box, and a modelo whose
  registry names a result box but declares no such rule gets no direction;
* the boxes a form asks the filer for are the ones verification requires;
* a declaration recorded as filed offers nothing for editing;
* the deadline is the registry's window, moved past a weekend.
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
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
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
)
from ..edit_models import (
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditScalarIntentKind,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from ..edit_value_grammar import casilla_value_grammar
from ..source_policy import SourceFamily
from ..verification_cross_period import cross_period_clean_state_findings
from ..work_form import build_modelo_work_form
from ..work_form_models import (
    EXPLANATORY_FINDING_MESSAGE_KEYS,
    ModeloFormAttention,
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormResultDirection,
    ModeloWorkForm,
    address_key,
    finding_attention,
)
from ..work_form_service import modelo_form_deadline, modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_REF = "rd-439-2007:art-110"


def _snapshot(operation: PinnedAuthorityOperation, modelo: str, year: int, code: str) -> RegistrySnapshot:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    return modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)


def _review(
    operation: PinnedAuthorityOperation,
    snapshot: RegistrySnapshot,
    modelo: str,
    year: int,
    code: str,
    *,
    values: dict[str, Decimal] | None = None,
    lifecycle: CalculationRevisionState | None = None,
    findings: tuple[ModeloVerificationFinding, ...] = (),
) -> ModeloWorkReview:
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    held = values or {}
    return ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000453",
        modelo=modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, code),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="c" * 64,
        calculation_revision_id=None,
        lifecycle_state=lifecycle,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            row.model_copy(update={"value": held[str(row.casilla_id)], "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) in held
            else row
            for row in rows
        ),
        findings=findings,
        blockers=(),
    )


def _form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    *,
    values: dict[str, Decimal] | None = None,
    lifecycle: CalculationRevisionState | None = None,
    surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None = None,
    findings: tuple[ModeloVerificationFinding, ...] = (),
) -> ModeloWorkForm:
    snapshot = _snapshot(operation, modelo, year, code)
    return build_modelo_work_form(
        review=_review(operation, snapshot, modelo, year, code, values=values, lifecycle=lifecycle, findings=findings),
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=surface,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.ES,
    )


def _field(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(field for field in form.fields() if address_key(field.address) == ("casilla", casilla_id))


# -- where a value comes from ------------------------------------------------


def test_a_carried_box_names_the_earlier_declaration_it_reads(operation: PinnedAuthorityOperation) -> None:
    """Modelo 130 box 05 carries the instalments already paid this year: in the 2nd quarter, the 1st's."""
    form = _form(operation, "130", 2026, "2T")

    carried = _field(form, "05").source
    records = _field(form, "01").source

    assert carried is not None
    assert carried.family is SourceFamily.EARLIER_FILINGS
    assert carried.earlier_filings == (
        ModeloFormEarlierFiling(modelo="130", period=Period.from_year_and_code(2026, "1T")),
    )
    assert carried.binding_id == _field(form, "05").bindings[0].binding_id
    assert records is not None
    assert records.family is SourceFamily.RECORDS
    assert records.earlier_filings == ()
    assert _field(form, "06").source is None
    assert _field(form, "03").source is None


def test_a_carry_with_no_earlier_quarter_names_no_declaration(operation: PinnedAuthorityOperation) -> None:
    """In the 1st quarter there is no earlier instalment of the year, so none is named, never guessed."""
    carried = _field(_form(operation, "130", 2026, "1T"), "05").source

    assert carried is not None
    assert carried.family is SourceFamily.EARLIER_FILINGS
    assert carried.earlier_filings == ()


def test_a_rate_the_design_prints_reads_as_set_by_the_form(operation: PinnedAuthorityOperation) -> None:
    rate = _field(_form(operation, "303", 2026, "1T"), "02")

    assert rate.editability is ModeloFormEditability.DESIGN_CONSTANT
    assert rate.source is not None
    assert rate.source.family is SourceFamily.FIXED_BY_DESIGN
    assert rate.source.binding_id is None


# -- the result and its direction -------------------------------------------


@pytest.mark.parametrize(
    ("value", "direction", "disposition"),
    [
        # "I (ingreso)": a positive box 19 is paid.
        (Decimal("1300.00"), ModeloFormResultDirection.TO_PAY, ResultDisposition.INGRESO),
        # "B (resultado a deducir)": a negative box 19 is deducted in later quarters.
        (Decimal("-50.00"), ModeloFormResultDirection.TO_CARRY_FORWARD, ResultDisposition.RESULTADO_A_DEDUCIR),
        # "N (negativa)": a zero result is a nil return.
        (Decimal("0.00"), ModeloFormResultDirection.NIL, ResultDisposition.NEGATIVA),
    ],
)
def test_the_modelo_130_result_settles_as_its_record_design_declares(
    operation: PinnedAuthorityOperation,
    value: Decimal,
    direction: ModeloFormResultDirection,
    disposition: ResultDisposition,
) -> None:
    result = _form(operation, "130", 2026, "1T", values={"19": value}).result

    assert result is not None
    assert result.box == "19"
    assert result.value == value
    assert result.direction is direction
    assert result.disposition is disposition
    assert not result.election_may_change


def test_a_result_not_calculated_yet_has_no_direction(operation: PinnedAuthorityOperation) -> None:
    result = _form(operation, "130", 2026, "1T").result

    assert result is not None
    assert result.box == "19"
    assert result.value is None
    assert result.direction is ModeloFormResultDirection.UNKNOWN


def test_a_modelo_303_credit_is_carried_forward_unless_a_refund_is_elected(
    operation: PinnedAuthorityOperation,
) -> None:
    """ "C (solicitud de compensación)": a negative box 71 is carried; a refund election may still turn it into D."""
    result = _form(operation, "303", 2026, "1T", values={"71": Decimal("-420.00")}).result

    assert result is not None
    assert result.box == "71"
    assert result.direction is ModeloFormResultDirection.TO_CARRY_FORWARD
    assert result.disposition is ResultDisposition.COMPENSACION
    assert result.election_may_change


def test_a_result_box_with_no_declared_sign_rule_has_no_direction(operation: PinnedAuthorityOperation) -> None:
    """Modelo 100 names box 0670 as its result, but the registry declares no rule for its sign."""
    result = _form(operation, "100", 2025, "0A", values={"0670": Decimal("-812.40")}).result

    assert result is not None
    assert result.box == "0670"
    assert result.value == Decimal("-812.40")
    assert result.direction is ModeloFormResultDirection.UNKNOWN
    assert result.disposition is None


def test_an_informative_return_has_no_settlement_box(operation: PinnedAuthorityOperation) -> None:
    assert _form(operation, "349", 2026, "1T").result is None


# -- what the filer owes -----------------------------------------------------


def test_modelo_100_asks_for_no_box_the_registry_does_not_require(operation: PinnedAuthorityOperation) -> None:
    """Hundreds of empty boxes sit in the Renta's calculation closure; verification requires none of them."""
    form = _form(operation, "100", 2025, "0A")
    snapshot = _snapshot(operation, "100", 2025, "0A")
    manifest = snapshot.revision.completeness_manifest
    assert manifest is not None
    closure = {str(item.casilla_id) for item in manifest.casillas}

    empty_typed_in_closure = [
        field
        for field in form.fields()
        if field.origin is ModeloFormOrigin.OPTIONAL_EMPTY and address_key(field.address)[1] in closure
    ]

    assert len(empty_typed_in_closure) > 150
    assert form.counts.needs_input == 0


def test_modelo_210_asks_for_the_boxes_the_registry_requires(operation: PinnedAuthorityOperation) -> None:
    form = _form(operation, "210", 2025, "0A")

    needs = {address_key(field.address)[1] for field in form.fields() if field.origin is ModeloFormOrigin.NEEDS_INPUT}

    assert needs == {"rendimientos_integros", "tipo_renta"}
    assert all(_field(form, casilla_id).required for casilla_id in needs)


# -- a declaration recorded as filed -----------------------------------------


def test_a_declaration_recorded_as_filed_offers_nothing_for_editing(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot(operation, "130", 2026, "1T")
    casilla = next(item for item in snapshot.revision.casillas if item.id == "06")
    surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] = (
        ModeloEditWritableScalarSurfaceEntryV1(
            casilla_id="06",
            data_type=casilla.data_type,
            allowed_intents=(ModeloEditScalarIntentKind.SET_TYPED_VALUE,),
            grammar=casilla_value_grammar(casilla),
        ),
    )

    draft = _form(operation, "130", 2026, "1T", surface=surface)
    filed = _form(operation, "130", 2026, "1T", surface=surface, lifecycle=CalculationRevisionState.PRESENTADO)
    superseded = _form(
        operation, "130", 2026, "1T", surface=surface, lifecycle=CalculationRevisionState.PRESENTADO_SUPERSEDIDO
    )

    assert draft.edit_admitted
    assert draft.edit_closure is None
    assert draft.filing is None
    assert _field(draft, "06").editability is ModeloFormEditability.EDITABLE_VALUE
    for closed in (filed, superseded):
        assert not closed.edit_admitted
        assert closed.edit_closure is ModeloFormEditClosure.RECORDED_AS_FILED
        assert closed.filing is not None
        assert closed.filing.recorded_at is None
        assert _field(closed, "06").editability is ModeloFormEditability.NO_ADMISSION


# -- the deadline --------------------------------------------------------------


def test_a_deadline_on_a_working_day_stands_and_counts_the_days_left(operation: PinnedAuthorityOperation) -> None:
    deadline = modelo_form_deadline(
        operation,
        ModeloCode("130"),
        Period.from_year_and_code(2026, "1T"),
        holiday_territory=None,
        reference_on=date(2026, 4, 10),
    )

    assert deadline is not None
    assert deadline.nominal_closes_on == date(2026, 4, 20)
    assert deadline.closes_on == date(2026, 4, 20)
    assert deadline.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert deadline.days_remaining == 10
    assert deadline.days_overdue is None


def test_a_deadline_on_a_saturday_moves_to_the_next_working_day(operation: PinnedAuthorityOperation) -> None:
    """The window stores the nominal 20 January 2024, a Saturday; the filer has until Monday the 22nd."""
    deadline = modelo_form_deadline(
        operation,
        ModeloCode("136"),
        Period.from_year_and_code(2023, "4T"),
        holiday_territory=None,
        reference_on=date(2024, 1, 25),
    )

    assert deadline is not None
    assert deadline.nominal_closes_on == date(2024, 1, 20)
    assert deadline.closes_on == date(2024, 1, 22)
    assert deadline.days_overdue == 3
    assert deadline.days_remaining is None


def test_a_period_with_no_window_has_no_deadline(operation: PinnedAuthorityOperation) -> None:
    assert (
        modelo_form_deadline(
            operation,
            ModeloCode("130"),
            Period.from_year_and_code(2026, "0A"),
            holiday_territory=None,
            reference_on=date(2026, 4, 10),
        )
        is None
    )


# -- how loud each finding is ------------------------------------------------


def _requirement(operation: PinnedAuthorityOperation) -> CrossPeriodDependencyRequirement:
    assert _LEGAL_REF in operation.legal_reference_ids()
    return CrossPeriodDependencyRequirement(
        source_modelo="111",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "4T"),
        source_casilla_ids=(validated_casilla_id("30"),),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("modelo-130-pagos-fraccionados-anteriores",),
        legal_refs=(_LEGAL_REF,),
        source_refs=("aeat-modelo-130-instructions",),
    )


def _cross_period_findings(operation: PinnedAuthorityOperation) -> dict[str, ModeloVerificationFinding]:
    """Findings the real cross-period verification emits for one dependency carrying every advisory."""
    evidence = CrossPeriodDependencyEvidence(
        requirement=_requirement(operation),
        non_official_local_chain_advisory=True,
        modelo_not_applicable_advisory=True,
        zero_value_previous_filing_advisory=True,
        m111_no_retenciones_no_obligation_advisory=True,
    )
    verdict = CrossPeriodCleanStateVerdict(
        bucket_id="13000000-0000-4000-8000-000000000454",
        target_modelo="130",
        target_filing_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        dependencies=(evidence,),
    )
    return {finding.message_locale_key: finding for finding in cross_period_clean_state_findings(verdict)}


def test_explanatory_advisories_are_information_and_the_rest_are_worth_checking(
    operation: PinnedAuthorityOperation,
) -> None:
    findings = _cross_period_findings(operation)
    attention = {key: finding_attention(finding) for key, finding in findings.items()}

    assert attention == {
        "application.modelo.findings.cross_period_non_official_local_chain.message": ModeloFormAttention.CHECK,
        "application.modelo.findings.cross_period_zero_value_previous_filing": ModeloFormAttention.INFO,
        "application.modelo.findings.cross_period_m111_no_retenciones": ModeloFormAttention.INFO,
        "application.modelo.findings.cross_period_modelo_not_applicable.message": ModeloFormAttention.INFO,
    }


def test_a_blocking_finding_blocks_whatever_its_message(operation: PinnedAuthorityOperation) -> None:
    advisory = next(iter(_cross_period_findings(operation).values()))
    blocking = advisory.model_copy(
        update={
            "severity": ModeloVerificationFindingSeverity.BLOCKING,
            "kind": ModeloVerificationFindingKind.BLOCKING_RULE,
            "message_locale_key": "application.modelo.findings.cross_period_zero_value_previous_filing",
        }
    )
    warning_of_another_kind = advisory.model_copy(
        update={
            "kind": ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            "message_locale_key": "application.modelo.findings.cross_period_zero_value_previous_filing",
        }
    )

    assert finding_attention(blocking) is ModeloFormAttention.BLOCKS
    assert finding_attention(warning_of_another_kind) is ModeloFormAttention.CHECK


def test_every_issue_on_the_form_carries_its_attention(operation: PinnedAuthorityOperation) -> None:
    findings = tuple(_cross_period_findings(operation).values())
    form = _form(operation, "130", 2026, "1T", findings=findings)

    assert {issue.finding.message_locale_key: issue.attention for issue in form.issues} == {
        key: finding_attention(finding) for key, finding in _cross_period_findings(operation).items()
    }
    issue = ModeloFormIssue(finding=findings[0])
    assert issue.attention is finding_attention(findings[0])
    with pytest.raises(ValueError, match="attention"):
        ModeloFormIssue(finding=findings[0], attention=ModeloFormAttention.BLOCKS)


@pytest.mark.parametrize("language", [language.value for language in OutputLanguage])
def test_every_explanatory_key_names_a_real_finding_message(language: str) -> None:
    missing = sorted(
        key for key in EXPLANATORY_FINDING_MESSAGE_KEYS if lookup_translation(key, locale=language) is None
    )

    assert not missing, f"explanatory finding keys with no {language} message: {missing}"
