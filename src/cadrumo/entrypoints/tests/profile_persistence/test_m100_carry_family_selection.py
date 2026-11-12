"""Which families of earlier-ejercicio carries the statement of absence states, on a Modelo 100.

The form serves one statement per family with an open carry, and one statement
covers every open family: the calculation it leads to refuses while any family
stays unstated. The command names families with a repeatable ``--family``; with none
it answers only while exactly one family is open. A choice that leaves an open family out is refused
before anything is staged, naming the families left out and the doors that
cover them all.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production admission and edit executor, every Modelo 100 year
the registry's support envelope admits.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.modelo.carry_amount_statement import (
    ModeloPriorCarryAmountDuplicateError,
    ModeloPriorCarryAmountInvalidError,
    ModeloPriorCarryAmountNotACarryError,
    prior_carry_statement_submission,
    resolve_prior_carry_amounts,
)
from ....application.modelo.carry_attestation_submission import (
    ModeloPriorCarryNothingOpenError,
    prior_carry_attestation_submission,
)
from ....application.modelo.carry_family_selection import (
    ModeloPriorCarryFamilyChoiceRequiredError,
    ModeloPriorCarryFamilyNothingOpenError,
    family_door,
    prior_carry_binding_ids,
    select_prior_carry_attestations,
)
from ....application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ....application.modelo.edit_models import (
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditSubmissionV1,
)
from ....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ....application.modelo.edit_preflight import CARRY_LEFT_OPEN, preflight_modelo_edit
from ....application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ....application.modelo.work_form_models import ModeloFormCarryAttestation, ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....application.operations.models import OperationRequest
from ....application.operations.next_step import OperationOpenWorkStepV1, error_next_step
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import validated_casilla_id
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ...cli.modelo_work_carry_attestation_cli import attest_prior_carries_lines, attest_prior_carries_result
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_FAMILIES = tuple(AbsenceAttestationFamily)
_SORTED_FAMILIES = tuple(sorted(_FAMILIES, key=lambda each: each.value))
_GENERAL, _CAPITAL, _GAINS = (
    AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING,
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING,
)
_PARTIAL_CHOICES: tuple[tuple[AbsenceAttestationFamily, ...], ...] = ((), (_CAPITAL,), (_GENERAL, _GAINS))


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the registry support envelope admits at calculation grade."""
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


def _form(work: SeededOperatorWork) -> ModeloWorkForm:
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
        language=OutputLanguage.EN,
    ).form


def _open_families(work: SeededOperatorWork) -> set[AbsenceAttestationFamily]:
    return {item.family for item in _form(work).carry_attestations}


def _choose(
    work: SeededOperatorWork,
    *,
    families: tuple[AbsenceAttestationFamily, ...] = (),
    offered: tuple[ModeloFormCarryAttestation, ...] | None = None,
) -> tuple[ModeloFormCarryAttestation, ...]:
    return select_prior_carry_attestations(
        work.baseline(),
        _form(work).carry_attestations if offered is None else offered,
        families=families,
    )


def _apply(work: SeededOperatorWork, submission: ModeloEditSubmissionV1) -> CadrumoError | None:
    """Apply the staged statement as the command line submits it; the apply refusal."""
    return work.execute(
        OperationRequest(
            definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
            subject_ref=work.work_unit_id,
            payload=ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
            ),
        )
    )


def _settles(work: SeededOperatorWork, statements: tuple[ModeloFormCarryAttestation, ...]) -> None:
    """Apply ``statements``, then let the refused declaration calculate past every carry."""
    assert _apply(work, prior_carry_attestation_submission(work.baseline(), statements)) is None
    assert _open_families(work) == set()
    head = work.recalculate()
    assert head.operator_layer is not None
    assert set(head.operator_layer.attested_binding_ids) == {
        binding_id for item in statements for binding_id in item.binding_ids
    }


@pytest.mark.parametrize("year", _renta_years())
def test_a_choice_that_leaves_an_open_family_out_is_refused_before_staging_naming_it_and_the_doors(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        before = _form(renta).carry_attestations
        assert {item.family for item in before} == set(_FAMILIES)
        work_unit_id = str(renta.work_unit_id)
        refusals: list[ModeloPriorCarryFamilyChoiceRequiredError] = []
        for choice in _PARTIAL_CHOICES:
            with pytest.raises(ModeloPriorCarryFamilyChoiceRequiredError) as refused:
                _choose(renta, families=choice)
            refusals.append(refused.value)
            # Nothing was staged: no calculation, no statement, the form still offers every family.
            assert renta.head() is None
            assert _form(renta).carry_attestations == before

    for error, choice in zip(refusals, _PARTIAL_CHOICES, strict=True):
        code = get_registered_error_code(error)
        assert code.category is ErrorCategory.REFUSED
        assert code.code == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_CHOICE_REQUIRED"
        assert isinstance(error_next_step(error, OutputLanguage.EN), OperationOpenWorkStepV1)
        left_out = ", ".join(family.value for family in _SORTED_FAMILIES if family not in choice)
        for locale in ("es", "en", "ca", "hu"):
            message = resolve_error_message(error, locale=locale)
            assert "%{" not in message
            assert left_out in message
            # The one door offered names every open family.
            assert family_door(work_unit_id, _SORTED_FAMILIES) in message


@pytest.mark.parametrize("year", _renta_years())
def test_every_open_family_named_with_a_repeated_family_commits_and_the_calculation_proceeds(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        chosen = _choose(renta, families=(_CAPITAL, _GENERAL, _GAINS, _GENERAL))
        assert {item.family for item in chosen} == set(_FAMILIES)
        _settles(renta, chosen)


@pytest.mark.parametrize("year", _renta_years())
def test_the_preflight_blocks_a_partial_statement_and_passes_a_complete_one(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        offered = _form(renta).carry_attestations
        general = tuple(item for item in offered if item.family is _GENERAL)
        others = {binding_id for item in offered if item.family is not _GENERAL for binding_id in item.binding_ids}

        def findings(statements: tuple[ModeloFormCarryAttestation, ...]) -> list[ModeloEditFindingV1]:
            submission = prior_carry_attestation_submission(renta.baseline(), statements)
            review = preflight_modelo_edit(
                submission,
                work_catalogue=renta.ports.work_unit_repository.load(),
                calculation_catalogue=renta.ports.calculation_repository.load(),
                tax_id_format=runtime_tax_id_format(authority=renta.operation),
                prior_carry_bindings=prior_carry_binding_ids(renta.operation, submission),
            )
            assert isinstance(review, ModeloEditPreflightEvaluatedV1), review
            return [finding for finding in review.findings if finding.code == CARRY_LEFT_OPEN]

        partial = findings(general)
        addresses = [finding.address for finding in partial]
        assert all(isinstance(address, ModeloEditBindingAddressV1) for address in addresses)
        assert {
            address.binding_id for address in addresses if isinstance(address, ModeloEditBindingAddressV1)
        } == others
        assert {finding.severity for finding in partial} == {ModeloEditFindingSeverity.ERROR}
        assert findings(offered) == []
    for locale in ("es", "en", "ca", "hu"):
        assert "%{" not in tr(f"workspace.modelo.review.finding.{CARRY_LEFT_OPEN}", locale=locale)


@pytest.mark.parametrize("year", _renta_years())
def test_with_one_open_family_and_no_option_the_review_and_receipt_name_that_family(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        general_only = tuple(item for item in _form(renta).carry_attestations if item.family is _GENERAL)
        chosen = _choose(renta, offered=general_only)
        assert chosen == general_only
        submission = prior_carry_attestation_submission(renta.baseline(), chosen)
        result = attest_prior_carries_result(submission, chosen, [], {}, None)
        selection = "".join(f" --family {item.family.value}" for item in chosen)
        lines = attest_prior_carries_lines(result, str(renta.work_unit_id), selection)

    assert [statement.family for statement in result.statements] == [_GENERAL.value]
    assert f"family	{_GENERAL.value}" in lines
    assert all(f"carry	{_GENERAL.value}	" in line for line in lines if line.startswith("carry	"))
    assert any(f"--family {_GENERAL.value}" in line for line in lines)


@pytest.mark.parametrize("year", _renta_years())
def test_exactly_one_open_family_is_stated_without_a_flag_and_a_closed_family_is_refused(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        general_only = tuple(item for item in _form(renta).carry_attestations if item.family is _GENERAL)
        assert [item.family for item in general_only] == [_GENERAL]
        # A form that serves one family answers an unflagged choice and a named one alike.
        assert _choose(renta, offered=general_only) == general_only
        assert _choose(renta, families=(_GENERAL,), offered=general_only) == general_only
        # A declaration that offers no statement at all is left to the submission builder's own refusal.
        assert _choose(renta, offered=()) == ()
        with pytest.raises(ModeloPriorCarryNothingOpenError):
            prior_carry_attestation_submission(renta.baseline(), ())
        # A family that is not open has nothing to state.
        with pytest.raises(ModeloPriorCarryFamilyNothingOpenError) as closed:
            _choose(renta, families=(_CAPITAL,), offered=general_only)

    assert get_registered_error_code(closed.value).code == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_NOTHING_OPEN"
    assert isinstance(error_next_step(closed.value, OutputLanguage.EN), OperationOpenWorkStepV1)
    for locale in ("es", "en", "ca", "hu"):
        message = resolve_error_message(closed.value, locale=locale)
        assert "%{" not in message
        assert _CAPITAL.value in message


def _first_box(work: SeededOperatorWork, binding_id: str) -> str:
    boxes = [
        field.box
        for field in _form(work).fields()
        if field.box is not None and field.bindings and field.bindings[0].binding_id == binding_id
    ]
    assert boxes
    return boxes[0]


@pytest.mark.parametrize("year", _renta_years())
def test_one_statement_gives_an_amount_for_one_carry_and_nothing_pending_for_the_rest(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        statements = _choose(renta, families=_FAMILIES)
        general = next(item for item in statements if item.family is _GENERAL)
        carry = general.binding_ids[0]
        box = _first_box(renta, carry)
        amounts = resolve_prior_carry_amounts(renta.baseline(), _form(renta), statements, [f"{box}=1234.50"])
        assert amounts == {carry: Decimal("1234.50")}
        submission = prior_carry_statement_submission(renta.baseline(), statements, amounts)
        by_binding = {intent.address.binding_id: intent for intent in submission.binding_intents}
        assert by_binding[carry].kind is ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE
        assert by_binding[carry].value == Decimal("1234.50")
        others = [intent for binding_id, intent in by_binding.items() if binding_id != carry]
        assert others
        assert {intent.kind for intent in others} == {ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT}

        result = attest_prior_carries_result(submission, statements, [], amounts, None)
        lines = attest_prior_carries_lines(result, str(renta.work_unit_id), "")
        assert any(line.startswith(f"carry\t{_GENERAL.value}\t{carry}\t") and "1234.50" in line for line in lines)
        assert sum(line.startswith("carry\t") for line in lines) == len(by_binding)

        assert _apply(renta, submission) is None
        assert _open_families(renta) == set()
        head = renta.recalculate()

    assert Decimal(str(head.binding_overrides[carry])) == Decimal("1234.50")
    assert head.operator_layer is not None
    assert carry not in head.operator_layer.attested_binding_ids
    assert set(head.operator_layer.attested_binding_ids) == set(by_binding) - {carry}
    assert head.casilla_values[validated_casilla_id(box, surface="test")] == Decimal("1234.50")


@pytest.mark.parametrize("year", _renta_years())
def test_an_amount_for_a_box_that_is_no_open_carry_of_a_named_family_or_that_is_malformed_is_refused(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        statements = _choose(renta, families=_FAMILIES)
        general = next(item for item in statements if item.family is _GENERAL)
        box = _first_box(renta, general.binding_ids[0])
        only_savings = tuple(item for item in statements if item.family is not _GENERAL)

        def resolve(options: list[str], named: tuple[ModeloFormCarryAttestation, ...] = statements) -> object:
            return resolve_prior_carry_amounts(renta.baseline(), _form(renta), named, options)

        with pytest.raises(ModeloPriorCarryAmountNotACarryError) as unknown:
            resolve(["9999=10"])
        with pytest.raises(ModeloPriorCarryAmountNotACarryError):
            resolve([f"{box}=10"], only_savings)
        for bad in (
            f"{box}",
            f"{box}=",
            f"{box}=-5",
            f"{box}=0",
            f"{box}=1,5",
            f"{box}=1.234",
            f"{box}=1e3",
            f"{box}=abc",
        ):
            with pytest.raises(ModeloPriorCarryAmountInvalidError):
                resolve([bad])
        with pytest.raises(ModeloPriorCarryAmountDuplicateError) as twice:
            resolve([f"{box}=10", f"{box}=20"])
        # No refusal staged anything.
        assert renta.head() is None
        assert _open_families(renta) == set(_FAMILIES)

    for error, code in (
        (unknown.value, "REFUSED_MODELO_PRIOR_CARRY_AMOUNT_NOT_A_CARRY"),
        (twice.value, "REFUSED_MODELO_PRIOR_CARRY_AMOUNT_DUPLICATE"),
    ):
        assert get_registered_error_code(error).code == code
        assert isinstance(error_next_step(error, OutputLanguage.EN), OperationOpenWorkStepV1)
        for locale in ("es", "en", "ca", "hu"):
            assert "%{" not in resolve_error_message(error, locale=locale)
