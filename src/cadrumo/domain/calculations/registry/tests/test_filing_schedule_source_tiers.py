"""Filing-schedule evidence-tier validation."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.validate import RegistryValidator
from ._registry_schema_support import _committed_modelo, _with_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validator_rejects_filing_schedule_legal_ref_without_legal_authority() -> None:
    modelo, catalogues = _committed_modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = revision.filing_schedules[0]
    legal = dict(catalogues.legal)
    legal_ref = schedule.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"filing schedule modelo-111-trimestral legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


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


def test_validator_rejects_filing_schedule_condition_legal_ref_without_legal_authority() -> None:
    modelo, catalogues = _committed_modelo("111")
    revision = modelo.revisions["2019-y-siguientes"]
    schedule = revision.filing_schedules[0]
    condition = schedule.profile_conditions[0]
    legal = dict(catalogues.legal)
    legal_ref = condition.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"filing schedule modelo-111-trimestral condition enrollment\.large_company "
            r"legal ref .* is not legal authority"
        ),
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


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
