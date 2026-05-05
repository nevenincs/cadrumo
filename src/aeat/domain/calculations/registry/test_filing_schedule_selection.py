"""Registry filing schedule selection tests."""

from __future__ import annotations

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import (
    RegistryValidationError,
    RegistryValidator,
    applicable_filing_schedules,
    build_snapshot,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_modelo_111_selects_monthly_schedule_from_profile_enrollment_facts() -> None:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "111")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="01")

    schedules = applicable_filing_schedules(
        snapshot.revision,
        {"enrollment": {"large_company": True, "public_administration_budget_gt_6000000": False}},
        period="01",
    )

    assert [schedule.id for schedule in schedules] == ["modelo-111-mensual"]
    assert schedules[0].period_kind == "monthly"


def test_modelo_111_selects_quarterly_schedule_from_profile_enrollment_facts() -> None:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "111")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="1T")

    schedules = applicable_filing_schedules(
        snapshot.revision,
        {"enrollment": {"large_company": False, "public_administration_budget_gt_6000000": False}},
        period="1T",
    )

    assert [schedule.id for schedule in schedules] == ["modelo-111-trimestral"]
    assert schedules[0].period_kind == "quarterly"


def test_validator_rejects_schedule_periods_outside_revision_selector() -> None:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = revision.filing_schedules[0].model_copy(update={"periods": ("1T", "99")})
    mutated_revision = revision.model_copy(
        update={"filing_schedules": (schedule, *revision.filing_schedules[1:])}
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="declares periods outside revision selector"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)
