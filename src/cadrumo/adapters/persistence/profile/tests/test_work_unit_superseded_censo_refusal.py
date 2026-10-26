"""A work unit for the superseded censo modelo is refused at every creation entry.

Modelo 037's registry ownership declares that it admits no work unit and names
036 as its successor. Both creation entries -- the canonical ``create_work_unit``
and the resume-or-create path the CLI and TUI take -- must refuse in those terms
before resolving a revision, not fail later on a missing registry revision.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import WorkUnitMutationRefusedError
from cadrumo.application.modelo.work_addressing import ensure_modelo_work_unit_for_active_target
from cadrumo.application.modelo.work_lifecycle import create_work_unit, list_work_units
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.censo_modelos import censo_ownership_refusing_work_units

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_PROFILE_ID = "13000000-0000-4000-8000-000000000037"
_SUPERSEDED = "037"
_SUCCESSOR = "036"
_MESSAGE = "application.modelo.errors.work_unit_create_superseded_modelo"
_SCENARIO = "modelo.work.create.censo.modelo_superseded"


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


def _ports(repository: WorkUnitCatalogueRepository) -> WorkLifecyclePorts:
    return WorkLifecyclePorts(work_unit_repository=repository, bucket_event_repository=BucketEventHistoryRepository())


def _assert_superseded_refusal(error: WorkUnitMutationRefusedError) -> None:
    assert error.translated_message == _MESSAGE
    assert error.context == {"modelo": _SUPERSEDED, "superseded_by": _SUCCESSOR, "active_work_unit_allowed": False}
    failure = error.precondition_failure
    assert failure is not None
    assert failure.identity == ("modelo.work.create", "modelo.work.create.censo.work_unit_allowed", _SCENARIO)
    assert failure.verdict.action is None
    assert failure.verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_only_the_superseded_censo_modelo_refuses_work_units(operation: PinnedAuthorityOperation) -> None:
    refused = censo_ownership_refusing_work_units(_SUPERSEDED, operation=operation)

    assert refused is not None
    assert refused.superseded_by == _SUCCESSOR
    assert refused.active_work_unit_allowed is False
    assert censo_ownership_refusing_work_units(_SUCCESSOR, operation=operation) is None
    assert censo_ownership_refusing_work_units("130", operation=operation) is None


def test_the_canonical_creation_door_refuses_and_writes_nothing(
    repository: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    bucket_id, repo = repository

    with pytest.raises(WorkUnitMutationRefusedError) as raised:
        create_work_unit(
            bucket_id=bucket_id,
            modelo=_SUPERSEDED,
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            revision_id="2026",
            ports=_ports(repo),
            clock=_T0,
            operation=operation,
        )

    _assert_superseded_refusal(raised.value)
    assert list_work_units(bucket_id=bucket_id, ports=_ports(repo), include_discarded=True) == ()


def test_the_resume_or_create_path_refuses_before_resolving_a_revision(
    repository: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    bucket_id, repo = repository

    with pytest.raises(WorkUnitMutationRefusedError) as raised:
        ensure_modelo_work_unit_for_active_target(
            bucket_id=bucket_id,
            modelo=_SUPERSEDED,
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            registry_revision_id=None,
            catalogue=repo.load(),
            ports=_ports(repo),
            operation=operation,
        )

    _assert_superseded_refusal(raised.value)
