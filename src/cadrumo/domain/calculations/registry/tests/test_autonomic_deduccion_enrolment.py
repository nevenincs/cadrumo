"""The autonomic deducción enrolment: its load-time refusals and its post-hydration reference checks.

The enrolment is read from the formula of each enrolled box. A declaration outside
the vocabulary is refused when the registry loads; a declaration whose names do not
resolve in the hydrated revision is reported by the referential-integrity sweep. Each
refusal and each check is exercised here on a representative defect, the checks on
the published editions' own enrolments with one field altered.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from ..autonomic_deduccion_enrolment import (
    AscendantMinimumEntitlementAxis,
    AutonomicDeduccionEnrolment,
    AutonomicEligibilityAxis,
)
from ..autonomic_deduccion_enrolment_checks import autonomic_deduccion_enrolments, check_autonomic_deduccion_enrolments
from ..errors import RegistryValidationError
from ..reference_checker import IdReferenceChecker
from ..schema import RegistrySnapshot
from .authored_editions import filing_year_envelope, newest_authored_edition
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ASCENDANT_ROLE = "irpf_deduccion_madrid_cuidado_ascendientes"
_DESCENDANT_ROLE = "irpf_deduccion_madrid_nacimiento_adopcion"


def _snapshot(year: int | None = None) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year or newest_authored_edition("100"), period="0A")


def _enrolment(role: str) -> AutonomicDeduccionEnrolment:
    (enrolment,) = (
        enrolment
        for _formula, enrolment in autonomic_deduccion_enrolments(_snapshot().revision)
        if enrolment.target_semantic_role == role
    )
    return enrolment


def _declaration(role: str, **changes: Any) -> dict[str, Any]:
    declaration = _enrolment(role).model_dump()
    declaration.update(changes)
    return declaration


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_every_published_enrolment_passes_its_reference_checks(year: int) -> None:
    snapshot = _snapshot(year)
    checker = IdReferenceChecker(snapshot)

    check_autonomic_deduccion_enrolments(checker, snapshot.revision)

    assert checker.failures == []


def test_the_newest_edition_enrols_one_box_on_each_axis() -> None:
    axes = {enrolment.axis for _formula, enrolment in autonomic_deduccion_enrolments(_snapshot().revision)}

    assert axes == set(AutonomicEligibilityAxis)


@pytest.mark.parametrize(
    ("role", "changes", "message"),
    [
        (_ASCENDANT_ROLE, {"legal_refs": ("madrid-dl-1-2010:art-7-bis",)}, "ley-35-2006:art-77"),
        (_ASCENDANT_ROLE, {"legal_refs": ("ley-35-2006:art-77",)}, "own provision"),
        (_ASCENDANT_ROLE, {"prorrateo": "equal_parts"}, "cannot apply"),
        (_DESCENDANT_ROLE, {"prorrateo": "state_minimum_sharing"}, "cannot apply"),
        (_ASCENDANT_ROLE, {"eligibility": {"kind": "household_size"}}, "household_size"),
        (_ASCENDANT_ROLE, {"weight": "1"}, "weight"),
    ],
    ids=[
        "no-framework-article",
        "no-comunidad-provision",
        "ascendant-equal-parts",
        "descendant-minimum-sharing",
        "unknown-axis",
        "unknown-field",
    ],
)
def test_a_declaration_outside_the_vocabulary_is_refused_at_load(
    role: str, changes: dict[str, Any], message: str
) -> None:
    with pytest.raises((RegistryValidationError, ValueError), match=message):
        AutonomicDeduccionEnrolment.model_validate(_declaration(role, **changes))


def test_a_unidad_familiar_limit_without_its_terms_is_refused_at_load() -> None:
    declaration = _declaration(_DESCENDANT_ROLE)
    declaration["income_limit"] = {**declaration["income_limit"], "other_members_base_binding": None}

    with pytest.raises((RegistryValidationError, ValueError), match="other members"):
        AutonomicDeduccionEnrolment.model_validate(declaration)


def _altered(role: str, alter: Callable[[AutonomicDeduccionEnrolment], AutonomicDeduccionEnrolment]) -> list[str]:
    snapshot = _snapshot()
    formulas = tuple(
        formula.model_copy(update={"autonomic_deduccion": alter(formula.autonomic_deduccion)})
        if formula.autonomic_deduccion is not None and formula.autonomic_deduccion.target_semantic_role == role
        else formula
        for formula in snapshot.revision.formulas
    )
    altered = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"formulas": formulas})})
    checker = IdReferenceChecker(altered)
    check_autonomic_deduccion_enrolments(checker, altered.revision)
    return checker.failures


@pytest.mark.parametrize(
    ("role", "changes", "message"),
    [
        (_ASCENDANT_ROLE, {"target_semantic_role": _DESCENDANT_ROLE}, "but the formula targets box"),
        (_ASCENDANT_ROLE, {"count_binding": "renta-profile-madrid-nacimiento-adopcion-eligible-count"}, "is not read"),
        (_ASCENDANT_ROLE, {"count_binding": "renta-profile-no-such-binding"}, "unknown binding"),
        (_ASCENDANT_ROLE, {"amount": "renta-deduccion-madrid-nacimiento-adopcion-cuantia"}, "is not read"),
        (_ASCENDANT_ROLE, {"legal_refs": ("ley-35-2006:art-77", "madrid-dl-1-2010:art-4")}, "does not cite"),
    ],
    ids=["role-of-another-box", "binding-not-read", "unknown-binding", "amount-not-read", "uncited-provision"],
)
def test_a_name_the_revision_does_not_resolve_is_reported(role: str, changes: dict[str, Any], message: str) -> None:
    failures = _altered(role, lambda enrolment: enrolment.model_copy(update=changes))

    assert any(message in failure for failure in failures), failures


def test_two_enrolments_of_one_box_are_reported() -> None:
    snapshot = _snapshot()
    enrolled = next(formula for formula in snapshot.revision.formulas if formula.autonomic_deduccion is not None)
    duplicate = enrolled.model_copy(update={"id": f"{enrolled.id}-duplicate"})
    revision = snapshot.revision.model_copy(update={"formulas": (*snapshot.revision.formulas, duplicate)})
    checker = IdReferenceChecker(snapshot.model_copy(update={"revision": revision}))

    check_autonomic_deduccion_enrolments(checker, revision)

    assert any("already enrols" in failure for failure in checker.failures), checker.failures


def _revision_failures(snapshot: RegistrySnapshot, **revision_changes: Any) -> list[str]:
    revision = snapshot.revision.model_copy(update=revision_changes)
    checker = IdReferenceChecker(snapshot.model_copy(update={"revision": revision}))
    check_autonomic_deduccion_enrolments(checker, revision)
    return checker.failures


def test_an_axis_threshold_with_a_fractional_dated_value_is_reported() -> None:
    snapshot = _snapshot()
    eligibility = _enrolment(_ASCENDANT_ROLE).eligibility
    assert isinstance(eligibility, AscendantMinimumEntitlementAxis)
    parameters = tuple(
        parameter.model_copy(
            update={
                "values": tuple(
                    dated.model_copy(update={"value": dated.value + Decimal("0.5")}) for dated in parameter.values
                )
            }
        )
        if parameter.id == eligibility.minimum_age
        else parameter
        for parameter in snapshot.revision.parameters
    )

    failures = _revision_failures(snapshot, parameters=parameters)

    assert any("is not a dated whole number" in failure for failure in failures), failures


def test_a_count_binding_reading_two_profile_paths_is_reported() -> None:
    snapshot = _snapshot()
    count_binding = _enrolment(_ASCENDANT_ROLE).count_binding
    bindings = tuple(
        binding.model_copy(
            update={
                "provider": binding.provider.model_copy(
                    update={"profile_keys": ("renta_family.ascendientes_count", "renta_family.descendientes_count")}
                )
            }
        )
        if binding.id == count_binding
        else binding
        for binding in snapshot.revision.bindings
    )

    failures = _revision_failures(snapshot, bindings=bindings)

    assert any("does not read one profile path" in failure for failure in failures), failures
