"""Real-behavior tests for the discarded-work-unit refusal on ``create_work_unit``.

A work-unit id is content-addressed over bucket, modelo, filing year, period and
registry revision, so re-creating a discarded target re-derives the same id.
Returning that record handed the caller a unit every downstream verb then reports
as absent, stranding the filing target permanently. These tests pin the refusal,
and pin that it is narrow enough not to break idempotent re-creation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.modelos import WorkUnit, WorkUnitState
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .._action_errors import WorkUnitMutationRefusedError
from .._work_lifecycle import create_work_unit, discard_work_unit, list_work_units

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_DISCARD_PROFILE_ID = "13000000-0000-4000-8000-000000000231"
_MODELO = "130"
_FILING_YEAR = 2026
_PERIOD_CODE = "1T"
_REVISION_ID = "2019-y-siguientes"

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Discard Refusal"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="provenance.source", value="test_fixture"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    UserProfileLifecycleRepository(bucket_id=bucket_id, objects=objects).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Work unit discard refusal profile",
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


@pytest.fixture
def discard_repos(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield a real work-unit repository over one isolated runtime profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_DISCARD_PROFILE_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(objects, bucket_id=profile.bucket_id)
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=objects)


def _create(repository: WorkUnitCatalogueRepository, *, bucket_id: str) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE),
        revision_id=_REVISION_ID,
        repository=repository,
        clock=_T0,
    )


def test_recreating_a_discarded_target_refuses_instead_of_returning_it(
    discard_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The defect: the discarded unit was handed back and every verb then denied it."""
    bucket_id, repository = discard_repos
    created = _create(repository, bucket_id=bucket_id)
    discard_work_unit(
        created.work_unit_id,
        actor="operator",
        reason="changed my mind",
        repository=repository,
        clock=_T0,
    )

    with pytest.raises(WorkUnitMutationRefusedError) as raised:
        _create(repository, bucket_id=bucket_id)

    assert raised.value.translated_message == "application.modelo.errors.work_unit_create_discarded"


def test_the_refusal_names_the_state_and_the_target_coordinates(
    discard_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Structure only: an operator must be able to see WHICH target and WHY."""
    bucket_id, repository = discard_repos
    created = _create(repository, bucket_id=bucket_id)
    discard_work_unit(created.work_unit_id, actor="operator", repository=repository, clock=_T0)

    with pytest.raises(WorkUnitMutationRefusedError) as raised:
        _create(repository, bucket_id=bucket_id)

    context = raised.value.context
    assert context is not None
    assert context["state"] == WorkUnitState.DESCARTADO.value
    assert context["work_unit_id"] == created.work_unit_id
    assert context["modelo"] == _MODELO
    assert context["filing_year"] == str(_FILING_YEAR)
    assert context["period"] == _PERIOD_CODE
    assert context["discarded_by"] == "operator"


def test_the_refusal_does_not_reuse_the_circular_mutation_message(
    discard_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The sibling key advises creating a fresh unit, which is what just failed.

    Pinning the key rather than the prose keeps this a structural assertion while
    still catching a future author who routes this refusal onto the generic
    mutation-refused message and reintroduces the circular instruction.
    """
    bucket_id, repository = discard_repos
    created = _create(repository, bucket_id=bucket_id)
    discard_work_unit(created.work_unit_id, actor="operator", repository=repository, clock=_T0)

    with pytest.raises(WorkUnitMutationRefusedError) as raised:
        _create(repository, bucket_id=bucket_id)

    assert raised.value.translated_message != "application.modelo.errors.work_unit_mutation_refused"


def test_an_active_unit_still_returns_idempotently(
    discard_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Anti-vacuity: the guard must be narrow, not a blanket refusal on re-create.

    Without this, a refusal that fired on every existing unit would satisfy the
    tests above while breaking the documented idempotent-create contract.
    """
    bucket_id, repository = discard_repos
    first = _create(repository, bucket_id=bucket_id)
    second = _create(repository, bucket_id=bucket_id)

    assert second.work_unit_id == first.work_unit_id
    assert second.state is WorkUnitState.BORRADOR


def test_discovery_and_creation_now_agree_that_a_discarded_unit_is_gone(
    discard_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The asymmetry being closed: listing hid it while creation handed it back."""
    bucket_id, repository = discard_repos
    created = _create(repository, bucket_id=bucket_id)
    discard_work_unit(created.work_unit_id, actor="operator", repository=repository, clock=_T0)

    active = list_work_units(bucket_id=bucket_id, repository=repository)
    assert all(unit.work_unit_id != created.work_unit_id for unit in active)

    with pytest.raises(WorkUnitMutationRefusedError):
        _create(repository, bucket_id=bucket_id)

    audit = list_work_units(bucket_id=bucket_id, include_discarded=True, repository=repository)
    assert any(unit.work_unit_id == created.work_unit_id for unit in audit)
