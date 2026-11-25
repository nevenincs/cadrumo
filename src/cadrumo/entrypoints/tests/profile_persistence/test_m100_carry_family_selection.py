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

from pathlib import Path

import pytest

from ....application.modelo.absence_statement_submission import (
    ModeloAbsenceStatementNothingOpenError,
    prior_carry_absence_submission,
)
from ....application.modelo.carry_amount_statement import (
    ModeloPriorCarryAmountDuplicateError,
    ModeloPriorCarryAmountInvalidError,
    ModeloPriorCarryAmountNotACarryError,
    resolve_prior_carry_amounts,
)
from ....application.modelo.carry_family_selection import (
    ModeloPriorCarryFamilyChoiceRequiredError,
    ModeloPriorCarryFamilyNothingOpenError,
    family_door,
    prior_carry_binding_ids,
)
from ....application.modelo.edit_models import (
    ModeloEditBindingAddressV1,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditPreflightEvaluatedV1,
)
from ....application.modelo.edit_preflight import CARRY_LEFT_OPEN, preflight_modelo_edit
from ....application.modelo.work_form_models import ModeloFormCarryAttestation
from ....application.operations.next_step import OperationOpenWorkStepV1, error_next_step
from ....core.absence_attestation_family import PRIOR_CARRY_FAMILIES, AbsenceAttestationFamily
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .m100_carry_family_support import (
    CAPITAL,
    FACTS,
    FAMILIES,
    GAINS,
    GENERAL,
    apply_statement,
    carry_form,
    choose_carries,
    first_carry_box,
    open_carry_families,
    renta_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SORTED_FAMILIES = tuple(sorted(FAMILIES, key=lambda each: each.value))


def _settles(work: SeededOperatorWork, statements: tuple[ModeloFormCarryAttestation, ...]) -> None:
    """Apply ``statements``, then let the refused declaration calculate past every carry."""
    assert apply_statement(work, prior_carry_absence_submission(work.baseline(), statements)) is None
    assert open_carry_families(work) == set()
    head = work.recalculate()
    assert head.operator_layer is not None
    assert set(head.operator_layer.attested_binding_ids) == {
        binding_id for item in statements for binding_id in item.binding_ids
    }


_SORTED_FAMILIES = tuple(sorted(FAMILIES, key=lambda each: each.value))
_PARTIAL_CHOICES: tuple[tuple[AbsenceAttestationFamily, ...], ...] = ((), (CAPITAL,), (GENERAL, GAINS))


@pytest.mark.parametrize("year", renta_years())
def test_a_choice_that_leaves_an_open_family_out_is_refused_before_staging_naming_it_and_the_doors(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        before = carry_form(renta).carry_attestations
        assert {item.family for item in before if item.family in PRIOR_CARRY_FAMILIES} == set(FAMILIES)
        work_unit_id = str(renta.work_unit_id)
        refusals: list[ModeloPriorCarryFamilyChoiceRequiredError] = []
        for choice in _PARTIAL_CHOICES:
            with pytest.raises(ModeloPriorCarryFamilyChoiceRequiredError) as refused:
                choose_carries(renta, families=choice)
            refusals.append(refused.value)
            # Nothing was staged: no calculation, no statement, the form still offers every family.
            assert renta.head() is None
            assert carry_form(renta).carry_attestations == before

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


@pytest.mark.parametrize("year", renta_years())
def test_every_open_family_named_with_a_repeated_family_commits_and_the_calculation_proceeds(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        chosen = choose_carries(renta, families=(CAPITAL, GENERAL, GAINS, GENERAL))
        assert {item.family for item in chosen} == set(FAMILIES)
        _settles(renta, chosen)


@pytest.mark.parametrize("year", renta_years())
def test_the_preflight_blocks_a_partial_statement_and_passes_a_complete_one(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        offered = carry_form(renta).carry_attestations
        general = tuple(item for item in offered if item.family is GENERAL)
        others = {binding_id for item in offered if item.family is not GENERAL for binding_id in item.binding_ids}

        def findings(statements: tuple[ModeloFormCarryAttestation, ...]) -> list[ModeloEditFindingV1]:
            submission = prior_carry_absence_submission(renta.baseline(), statements)
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


@pytest.mark.parametrize("year", renta_years())
def test_exactly_one_open_family_is_stated_without_a_flag_and_a_closed_family_is_refused(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        general_only = tuple(item for item in carry_form(renta).carry_attestations if item.family is GENERAL)
        assert [item.family for item in general_only] == [GENERAL]
        # A form that serves one family answers an unflagged choice and a named one alike.
        assert choose_carries(renta, offered=general_only) == general_only
        assert choose_carries(renta, families=(GENERAL,), offered=general_only) == general_only
        # A declaration that offers no statement at all is left to the submission builder's own refusal.
        assert choose_carries(renta, offered=()) == ()
        with pytest.raises(ModeloAbsenceStatementNothingOpenError):
            prior_carry_absence_submission(renta.baseline(), ())
        # A family that is not open has nothing to state.
        with pytest.raises(ModeloPriorCarryFamilyNothingOpenError) as closed:
            choose_carries(renta, families=(CAPITAL,), offered=general_only)

    assert get_registered_error_code(closed.value).code == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_NOTHING_OPEN"
    assert isinstance(error_next_step(closed.value, OutputLanguage.EN), OperationOpenWorkStepV1)
    for locale in ("es", "en", "ca", "hu"):
        message = resolve_error_message(closed.value, locale=locale)
        assert "%{" not in message
        assert CAPITAL.value in message


@pytest.mark.parametrize("year", renta_years())
def test_a_family_outside_the_carries_is_refused_by_the_family_door_before_staging(tmp_path: Path, year: int) -> None:
    """The work-income statement is its own door: naming it here states no carry, even beside the carries."""
    work_income = AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED
    assert work_income not in PRIOR_CARRY_FAMILIES
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        before = carry_form(renta).carry_attestations
        refusals: list[ModeloPriorCarryFamilyNothingOpenError] = []
        for choice in ((work_income,), (*FAMILIES, work_income)):
            with pytest.raises(ModeloPriorCarryFamilyNothingOpenError) as refused:
                choose_carries(renta, families=choice)
            refusals.append(refused.value)
            # Nothing was staged: no calculation, no statement, the form still offers what it offered.
            assert renta.head() is None
            assert carry_form(renta).carry_attestations == before

    for error in refusals:
        assert get_registered_error_code(error).code == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_NOTHING_OPEN"
        assert isinstance(error_next_step(error, OutputLanguage.EN), OperationOpenWorkStepV1)
        for locale in ("es", "en", "ca", "hu"):
            message = resolve_error_message(error, locale=locale)
            assert "%{" not in message
            assert work_income.value in message


@pytest.mark.parametrize("year", renta_years())
def test_an_amount_for_a_box_that_is_no_open_carry_of_a_named_family_or_that_is_malformed_is_refused(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=FACTS) as renta,
    ):
        statements = choose_carries(renta, families=FAMILIES)
        general = next(item for item in statements if item.family is GENERAL)
        box = first_carry_box(renta, general.binding_ids[0])
        only_savings = tuple(item for item in statements if item.family is not GENERAL)

        def resolve(options: list[str], named: tuple[ModeloFormCarryAttestation, ...] = statements) -> object:
            return resolve_prior_carry_amounts(renta.baseline(), carry_form(renta), named, options)

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
        assert open_carry_families(renta) == set(FAMILIES)

    for error, code in (
        (unknown.value, "REFUSED_MODELO_PRIOR_CARRY_AMOUNT_NOT_A_CARRY"),
        (twice.value, "REFUSED_MODELO_PRIOR_CARRY_AMOUNT_DUPLICATE"),
    ):
        assert get_registered_error_code(error).code == code
        assert isinstance(error_next_step(error, OutputLanguage.EN), OperationOpenWorkStepV1)
        for locale in ("es", "en", "ca", "hu"):
            assert "%{" not in resolve_error_message(error, locale=locale)
