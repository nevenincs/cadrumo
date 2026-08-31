"""Registry filing schedule selection tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from .....core.errors.severity import BaseSeverity
from .....core.resources.bundled_data import bundled_path
from ....deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from ....user_profile.loader import load_user_profile_schema
from ....user_profile.registry_contract import validate_user_profile_registry_contract
from .._validate import RegistryValidator
from ..authority import ValidatedRegistryAuthority
from ..errors import RegistryValidationError
from ..schedules import applicable_filing_schedules
from ..schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_111_selects_monthly_schedule_from_profile_enrollment_facts(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("111", 2026, "01")

    schedules = applicable_filing_schedules(
        snapshot.revision,
        {"enrollment": {"large_company": True, "public_administration_budget_gt_6000000": False}},
        period="01",
    )

    assert [schedule.id for schedule in schedules] == ["modelo-111-mensual"]
    assert schedules[0].period_kind == "monthly"


def test_modelo_111_selects_monthly_schedule_from_profile_object(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("111", 2026, "01")
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        enrollment=ModeloEnrollment(large_company=True),
    )

    schedules = applicable_filing_schedules(snapshot.revision, profile, period="01")

    assert [schedule.id for schedule in schedules] == ["modelo-111-mensual"]


def test_modelo_111_selects_quarterly_schedule_from_profile_enrollment_facts(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("111", 2026, "1T")

    schedules = applicable_filing_schedules(
        snapshot.revision,
        {"enrollment": {"large_company": False, "public_administration_budget_gt_6000000": False}},
        period="1T",
    )

    assert [schedule.id for schedule in schedules] == ["modelo-111-trimestral"]
    assert schedules[0].period_kind == "quarterly"


def test_validator_rejects_schedule_periods_outside_revision_selector(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    modelo = registry_authority.modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = revision.filing_schedules[0].model_copy(update={"periods": ("1T", "99")})
    mutated_revision = revision.model_copy(update={"filing_schedules": (schedule, *revision.filing_schedules[1:])})
    mutated_modelo = modelo.model_copy(update={"revisions": {revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="declares periods outside revision selector"):
        RegistryValidator(registry_authority.catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


@pytest.mark.parametrize(
    ("modelo_id", "declared_kind", "contradictory_kind"),
    (
        ("111", "quarterly", "annual"),
        ("184", "annual", "quarterly"),
    ),
)
def test_validator_rejects_filing_schedule_cadence_contradictions(
    registry_authority: ValidatedRegistryAuthority,
    modelo_id: str,
    declared_kind: str,
    contradictory_kind: str,
) -> None:
    modelo = registry_authority.modelo(modelo_id)
    # Select the revision BY THE PROPERTY UNDER TEST, never by position. Modelo
    # 184 declares six revisions and only the newest two carry a filing
    # schedule at all, so taking the first one reached whichever revision the
    # mapping happened to yield -- 2015, which declares none -- and the test
    # died on an empty search instead of exercising the validator.
    revision, schedule = next(
        (candidate, item)
        for candidate in modelo.revisions.values()
        for item in candidate.filing_schedules
        if item.period_kind == declared_kind
    )
    contradictory = schedule.model_copy(update={"period_kind": contradictory_kind})
    mutated_revision = revision.model_copy(update={"filing_schedules": (contradictory,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match=r"period_kind .* contradicts periods"):
        RegistryValidator(registry_authority.catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


@pytest.mark.parametrize("modelo_id", ("036", "111", "184", "202", "369", "840"))
def test_shipped_filing_schedule_cadences_pass_canonical_period_classification(
    registry_authority: ValidatedRegistryAuthority,
    modelo_id: str,
) -> None:
    modelo = registry_authority.modelo(modelo_id)

    RegistryValidator(registry_authority.catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_filing_schedule_predicate_with_unknown_field_is_reported_as_contract_error(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    modelo = registry_authority.modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.profile_conditions)
    bad_condition = schedule.profile_conditions[0].model_copy(update={"field": "unknown_predicate_field"})
    bad_schedule = schedule.model_copy(update={"profile_conditions": (bad_condition,)})
    mutated_revision = revision.model_copy(update={"filing_schedules": (bad_schedule, *revision.filing_schedules[1:])})
    mutated_modelo = modelo.model_copy(update={"revisions": {revision.id: mutated_revision}})
    schema = load_user_profile_schema()

    report = validate_user_profile_registry_contract([mutated_modelo], schema)

    matching = [i for i in report.issues if i.surface == "filing_schedule" and i.selector == "unknown_predicate_field"]
    assert matching, f"expected a filing_schedule issue for unknown_predicate_field; issues={report.issues}"
    assert matching[0].severity is BaseSeverity.ERROR


def test_deadline_window_predicate_with_unknown_field_is_reported_as_contract_error(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    modelo = registry_authority.modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    window = next(w for w in revision.deadline_windows if w.applicability_conditions)
    bad_condition = window.applicability_conditions[0].model_copy(update={"field": "unknown_predicate_field"})
    bad_window = window.model_copy(update={"applicability_conditions": (bad_condition,)})
    mutated_revision = revision.model_copy(update={"deadline_windows": (bad_window, *revision.deadline_windows[1:])})
    mutated_modelo = modelo.model_copy(update={"revisions": {revision.id: mutated_revision}})
    schema = load_user_profile_schema()

    report = validate_user_profile_registry_contract([mutated_modelo], schema)

    matching = [i for i in report.issues if i.surface == "deadline_window" and i.selector == "unknown_predicate_field"]
    assert matching, f"expected a deadline_window issue for unknown_predicate_field; issues={report.issues}"
    assert matching[0].severity is BaseSeverity.ERROR
