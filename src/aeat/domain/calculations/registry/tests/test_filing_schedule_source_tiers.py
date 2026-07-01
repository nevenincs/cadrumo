"""Filing-schedule source-tier validation."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidationError, RegistryValidator
from ._registry_schema_support import _committed_modelo, _with_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validator_rejects_filing_schedule_without_official_guidance_source() -> None:
    modelo, catalogues = _committed_modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = revision.filing_schedules[0]
    mutated_schedule = schedule.model_copy(update={"source_refs": ("aeat-dr-111-2019-v18",)})
    mutated_revision = revision.model_copy(
        update={"filing_schedules": (mutated_schedule, *revision.filing_schedules[1:])},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"filing schedule modelo-111-trimestral requires official_source_guidance source evidence",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )


def test_validator_rejects_filing_schedule_condition_without_official_guidance_source() -> None:
    modelo, catalogues = _committed_modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = revision.filing_schedules[0]
    condition = schedule.profile_conditions[0]
    mutated_condition = condition.model_copy(update={"source_refs": ("aeat-dr-111-2019-v18",)})
    mutated_schedule = schedule.model_copy(
        update={"profile_conditions": (mutated_condition, *schedule.profile_conditions[1:])},
    )
    mutated_revision = revision.model_copy(
        update={"filing_schedules": (mutated_schedule, *revision.filing_schedules[1:])},
    )

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"filing schedule modelo-111-trimestral condition enrollment\.large_company "
            r"requires official_source_guidance source evidence"
        ),
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )
