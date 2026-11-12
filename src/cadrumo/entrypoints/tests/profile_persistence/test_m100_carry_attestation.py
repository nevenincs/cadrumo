"""A filer states that no earlier-ejercicio carry is pending on a Modelo 100, and it stays a statement.

The Modelo 100 carries the negative general bases still pending from the four
previous ejercicios (Ley 35/2006 art. 50.3) from the previous return. With no
earlier return held, those carries are unknown, never zero, so the filer states
that nothing is pending. The statement is a zero the operator layer marks
attested, kept apart from a zero typed, and a typed value withdraws it.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production admission and edit executor, every Modelo 100 year
the registry's support envelope admits.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.modelo.absence_statement_submission import (
    ModeloAbsenceStatementNothingOpenError,
    absence_statement_submission,
)
from ....application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditFindingSeverity,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from ....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ....application.modelo.edit_preflight import preflight_modelo_edit
from ....application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ....application.modelo.work_form_models import ModeloFormField, ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....application.modelo.work_missing_input import ModeloPriorCarryAbsenceUnstatedError, ModeloWorkMissingInputError
from ....application.operations.models import OperationRequest
from ....application.operations.next_step import OperationOpenWorkStepV1, error_next_step
from ....application.operator_actions.models import PreconditionVerdict
from ....core.aggregation import BindingSourceKind
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import (
    ErrorCategory,
    get_registered_error_code,
    public_error_context,
    resolve_error_message,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The carries of the negative general base still pending from the four previous ejercicios, as the
#: registry declares them, each read from a box of the previous Modelo 100.
_PENDING_CARRIES: tuple[BindingId, ...] = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: The previous return's Anexo C boxes each carry is read from, in the order of ``_PENDING_CARRIES``.
_CARRIED_FROM: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(token, surface="_CARRIED_FROM") for token in ("1391", "1390", "1387", "1384")
)
_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            published_authority_operation().snapshot(
                "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def _renta_years_with_a_prior_return() -> tuple[int, ...]:
    """The admitted Modelo 100 years whose previous year the envelope admits too, so its return can be stored."""
    years = _renta_years()
    return tuple(year for year in years if year - 1 in years)


#: The boxes the form prints for the four carries, in the order of ``_PENDING_CARRIES``.
_CARRY_BOXES = ("1388", "1385", "1382", "1380")


def _attest(binding_id: BindingId) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT
    )


def _attestable(work: SeededOperatorWork) -> frozenset[str]:
    return frozenset(
        entry.binding_id
        for entry in work.baseline().permitted_surface
        if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT in entry.allowed_intents
    )


@pytest.mark.parametrize("year", _renta_years())
def test_a_filer_states_no_carry_is_pending_and_the_revision_keeps_it_apart_from_a_typed_zero(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        # Only a carry from an earlier filing can be stated to hold nothing.
        attestable = _attestable(renta)
        assert set(_PENDING_CARRIES) <= attestable

        applied = renta.apply(binding=tuple(_attest(binding_id) for binding_id in _PENDING_CARRIES))
        assert applied.refusal is None
        layer = renta.require_head().operator_layer
        assert layer is not None
        assert layer.attested_binding_ids == _PENDING_CARRIES
        assert all(layer.binding_overrides[binding_id] == ATTESTED_ZERO for binding_id in _PENDING_CARRIES)
        # The statement answers the carries: none is left standing as an earlier filing nobody recorded.
        assert not [
            issue
            for issue in renta.require_head().source_issues
            if issue.reason == "unresolved_binding" and issue.binding_source is BindingSourceKind.PREVIOUS_FILING
        ]

        # Calculating the declaration again keeps the statement as the filer made it.
        recalculated = renta.recalculate().operator_layer
        assert recalculated is not None
        assert recalculated.attested_binding_ids == _PENDING_CARRIES

        # A figure typed over one carry is the filer's figure, no longer the statement.
        typed, *kept = _PENDING_CARRIES
        retyped = renta.apply(
            binding=(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=typed),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=Decimal("0"),
                ),
            )
        )
        assert retyped.refusal is None
        relayer = renta.require_head().operator_layer
        assert relayer is not None
        assert relayer.attested_binding_ids == tuple(kept)
        assert relayer.binding_overrides[typed] == ATTESTED_ZERO


@pytest.mark.parametrize("year", _renta_years_with_a_prior_return())
def test_an_earlier_return_stored_later_with_a_pending_amount_contradicts_the_statement(
    tmp_path: Path, year: int
) -> None:
    contradicted, *agreeing = _PENDING_CARRIES
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        assert renta.apply(binding=tuple(_attest(binding_id) for binding_id in _PENDING_CARRIES)).refusal is None

        # The earlier return turns up afterwards, and it shows a negative base still pending.
        save_stamped_observation(
            CalculationObservationRepository(),
            registry_grounded_modelo_observation(
                modelo="100",
                filing_year=year - 1,
                period="0A",
                casilla_values={
                    casilla_id: Decimal("1500.00") if index == 0 else Decimal("0")
                    for index, casilla_id in enumerate(_CARRIED_FROM)
                },
            ),
            source_kind="app_filing",
        )
        head = renta.recalculate()

    layer = head.operator_layer
    assert layer is not None
    assert layer.attested_binding_ids == _PENDING_CARRIES
    disputed = {
        issue.disagreement.key
        for issue in head.source_issues
        if issue.reason == "precedence_tier_divergence" and issue.disagreement is not None
    }
    assert contradicted in disputed, [(issue.reason, issue.disagreement) for issue in head.source_issues]
    assert not disputed & set(agreeing)


def _form(work: SeededOperatorWork, language: OutputLanguage) -> ModeloWorkForm:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=work.admit(),
        language=language,
    ).form


@pytest.mark.parametrize("year", _renta_years())
def test_the_form_offers_the_statement_while_a_carry_is_open_and_applying_it_closes_it(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        (offered,) = _form(renta, OutputLanguage.EN).carry_attestations
        assert offered.family is AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
        assert set(_PENDING_CARRIES) <= set(offered.binding_ids)
        (spanish,) = _form(renta, OutputLanguage.ES).carry_attestations
        assert spanish.binding_ids == offered.binding_ids
        assert spanish.action_words != offered.action_words
        assert spanish.effect_words != offered.effect_words

        # The window stages one statement per binding the form names, and nothing is left to state.
        assert renta.apply(binding=tuple(_attest(binding_id) for binding_id in offered.binding_ids)).refusal is None
        assert _form(renta, OutputLanguage.EN).carry_attestations == ()


def _carry_fields(form: ModeloWorkForm) -> dict[BindingId, ModeloFormField]:
    """The form's fields a pending carry feeds, by that carry."""
    return {
        field.bindings[0].binding_id: field
        for field in form.fields()
        if field.bindings and field.bindings[0].binding_id in _PENDING_CARRIES
    }


@pytest.mark.parametrize("year", _renta_years())
def test_a_stated_carry_reads_as_stated_and_a_typed_zero_does_not(tmp_path: Path, year: int) -> None:
    stated, typed, *also_stated = _PENDING_CARRIES
    # Every carry needs an answer for the declaration to calculate; one of them is a zero typed.
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        applied = renta.apply(
            binding=(
                *(_attest(binding_id) for binding_id in (stated, *also_stated)),
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=typed),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=Decimal("0"),
                ),
            )
        )
        assert applied.refusal is None
        fields = _carry_fields(_form(renta, OutputLanguage.EN))
        spanish = _carry_fields(_form(renta, OutputLanguage.ES))

    # Both hold a zero, but only the statement says it is one: the typed zero reads as a figure typed.
    assert {stated, typed} <= set(fields)
    assert fields[stated].stated_absent is AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
    assert fields[typed].stated_absent is None
    assert fields[stated].origin_words is not None
    assert fields[stated].origin_words != fields[typed].origin_words
    assert spanish[stated].origin_words not in {None, fields[stated].origin_words}


@pytest.mark.parametrize(("modelo", "period_code"), [("130", "1T"), ("303", "1T")])
def test_a_declaration_whose_registry_declares_no_statement_of_absence_offers_none(
    tmp_path: Path, modelo: str, period_code: str
) -> None:
    year = max(_renta_years())
    earlier = [
        binding.id
        for binding in published_authority_operation()
        .snapshot(modelo, filing_year=year, period=period_code, grade=RegistryAuthorityGrade.CALCULATION)
        .revision.bindings
        if binding.source is BindingSourceKind.PREVIOUS_FILING
    ]
    # The declaration does read earlier filings, so the refusal is the registry's, not an absence of carries.
    assert earlier
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo=modelo, filing_year=year, period_code=period_code) as work,
    ):
        assert _attestable(work) == frozenset()
        offered = _form(work, OutputLanguage.EN).carry_attestations
        assert offered == ()
        # The command line, staging what the form names, has nothing to state and refuses before any edit.
        with pytest.raises(ModeloAbsenceStatementNothingOpenError):
            absence_statement_submission(
                work.baseline(), offered, family=AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
            )


@pytest.mark.parametrize("year", _renta_years())
def test_an_unstated_carry_with_no_earlier_return_is_refused_naming_every_open_carry_then_the_statement_settles_it(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        with pytest.raises(ModeloPriorCarryAbsenceUnstatedError) as refused:
            renta.recalculate()
        # Nothing was published, and the wizard's and the comparison's catches still see a missing input.
        assert renta.head() is None
        error = refused.value
        assert isinstance(error, ModeloWorkMissingInputError)
        assert error.family is AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
        assert error.open_carry_ids == tuple(sorted(_PENDING_CARRIES))
        code = get_registered_error_code(error)
        assert code.category is ErrorCategory.REFUSED
        assert code.code == "REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED"
        for locale in ("es", "en", "ca", "hu"):
            message = resolve_error_message(error, locale=locale)
            assert str(year) in message
            assert all(box in message for box in _CARRY_BOXES), message
            assert not any(binding_id in message for binding_id in _PENDING_CARRIES), message
        # The context the refusal is recorded and rendered with names boxes, never a registry binding.
        context = public_error_context(error)
        assert context is not None
        assert context["boxes"] == ", ".join(sorted(_CARRY_BOXES)), context
        assert "binding_id" not in context, context
        assert not any(binding_id in value for value in context.values() for binding_id in _PENDING_CARRIES), context
        verdict = error.terminal_precondition_verdict
        assert isinstance(verdict, PreconditionVerdict)
        assert verdict.failed_condition_id == "modelo.work.calculate.prior_carries.stated"
        # The way on is the statement itself, the command that stages it for this declaration.
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.modelo.work.attest_prior_carries"
        assert {binding.argument_name: binding.value for binding in verdict.argument_bindings} == {
            "work_unit_id": renta.work_unit_id
        }
        (evidence,) = verdict.evidence
        assert evidence.values["open_carries"] == ",".join(sorted(_PENDING_CARRIES))
        assert evidence.values["filing_year"] == year
        # The declaration's own form, which serves the statement, stays the window's way on.
        step = error_next_step(error, OutputLanguage.ES)
        assert isinstance(step, OperationOpenWorkStepV1)
        assert step.work_unit_id == renta.work_unit_id

        assert renta.apply(binding=tuple(_attest(binding_id) for binding_id in _PENDING_CARRIES)).refusal is None
        head = renta.recalculate()

    # The calculation now stands, and box 1380 holds the filer's statement, not a zero nobody gave.
    assert head.casilla_values[validated_casilla_id("1380", surface="test")] == Decimal("0")
    layer = head.operator_layer
    assert layer is not None
    assert layer.attested_binding_ids == _PENDING_CARRIES


def _apply_as_submitted(work: SeededOperatorWork, *, offered: ModeloWorkForm) -> CadrumoError | None:
    """Stage what the form names, check it, then apply it as the command line submits it; the apply's refusal."""
    submission = absence_statement_submission(
        work.baseline(),
        offered.carry_attestations,
        family=AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
    )
    review = preflight_modelo_edit(
        submission,
        work_catalogue=work.ports.work_unit_repository.load(),
        calculation_catalogue=work.ports.calculation_repository.load(),
        tax_id_format=runtime_tax_id_format(authority=work.operation),
    )
    assert isinstance(review, ModeloEditPreflightEvaluatedV1), review
    errors = [finding for finding in review.findings if finding.severity is ModeloEditFindingSeverity.ERROR]
    assert not errors, errors
    return work.execute(
        OperationRequest(
            definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
            subject_ref=work.work_unit_id,
            payload=ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
            ),
        )
    )


@pytest.mark.parametrize("year", _renta_years())
def test_the_command_line_statement_stages_what_the_form_names_and_lets_the_refused_declaration_calculate(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        with pytest.raises(ModeloPriorCarryAbsenceUnstatedError):
            renta.recalculate()

        offered = _form(renta, OutputLanguage.EN)
        staged = absence_statement_submission(
            renta.baseline(),
            offered.carry_attestations,
            family=AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
        ).binding_intents
        # One statement per carry the form names, and nothing else: no value travels with it.
        assert [intent.address.binding_id for intent in staged] == sorted(_PENDING_CARRIES)
        assert {intent.kind for intent in staged} == {ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT}
        assert all(intent.value is None for intent in staged)
        # Checking the staged statement records nothing: the form still offers it.
        assert renta.head() is None
        assert _form(renta, OutputLanguage.EN).carry_attestations == offered.carry_attestations

        assert _apply_as_submitted(renta, offered=offered) is None
        head = renta.recalculate()

        # A second statement has nothing left to answer, and is refused before anything is staged.
        settled = _form(renta, OutputLanguage.EN)
        assert settled.carry_attestations == ()
        with pytest.raises(ModeloAbsenceStatementNothingOpenError) as again:
            absence_statement_submission(
                renta.baseline(),
                settled.carry_attestations,
                family=AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
            )

    assert head.casilla_values[validated_casilla_id("1380", surface="test")] == Decimal("0")
    layer = head.operator_layer
    assert layer is not None
    assert layer.attested_binding_ids == _PENDING_CARRIES
    code = get_registered_error_code(again.value)
    assert code.category is ErrorCategory.REFUSED
    assert code.code == "REFUSED_MODELO_PRIOR_CARRY_NOTHING_OPEN"
    for locale in ("es", "en", "ca", "hu"):
        message = resolve_error_message(again.value, locale=locale)
        assert str(year) in message
        assert "%{" not in message
