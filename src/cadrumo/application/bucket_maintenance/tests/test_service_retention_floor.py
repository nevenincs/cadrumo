"""Retention-floor gate tests for ``BucketMaintenanceService.delete``.

A destructive bucket erase must refuse to destroy a filed tax record that is
still inside its four-year LGT retention window (Ley 58/2003 art. 66/70) unless
the operator supplies an explicit legal-retention override with a reason. These
tests persist real :class:`ModeloRecord` filings through the encrypted
repository and exercise the real assessment + refusal, not a mock.

The full non-active-bucket hard-erase happy path shares the cross-bucket
master-key-session coupling documented as deferred in
``test_service_delete.py``; the gate itself is exercised here against the
active bucket's real filing catalogue and through the pure enforcement path.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core import Period
from ....core.resources import resources
from ....domain.modelos import (
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from ....domain.retention import RetentionBlockingRecord, RetentionFloorAssessment, RetentionFloorError
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ....tests.user_profile import schema_valid_placeholder
from ...user_profile import RegisterProfileCommand
from .. import AssessBucketDeletionCommand, BucketMaintenanceService, DeleteBucketCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "55555555-5555-4555-8555-555555555555"
_LABEL = "Retention bucket"


def _hex(seed: str) -> str:
    return (seed * 64)[:64]


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value=schema_valid_placeholder(field)))
    return tuple(facts)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_LABEL) as profile:
        yield profile


@pytest.fixture
def registered_profile(runtime: TestRuntimeProfile) -> None:
    from ...user_profile import (
        ProfileLifecycleService,
        ProfileValidationService,
        UserProfileLifecycleRepository,
    )

    schema = resources().user_profile_schema.singleton
    assert isinstance(schema, ProfileSchemaDefinition)
    ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=runtime.bucket_id, objects=runtime.repository),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=runtime.repository),
    ).register(
        RegisterProfileCommand(
            profile_id=runtime.bucket_id,
            display_name=_LABEL,
            facts=_all_required_facts(schema),
        ),
    )


def _persist_filing(bucket_id: str, *, filing_year: int, filed_at: datetime) -> ModeloRecord:
    work_unit_id = _hex("a")
    revision_id = _hex("b")
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "2T"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )
    ModeloRecordCatalogueRepository(bucket_id=bucket_id).save(
        ModeloRecordCatalogue(records={record_id: record}),
    )
    return record


def _blocking_assessment() -> RetentionFloorAssessment:
    return RetentionFloorAssessment(
        as_of=datetime(2026, 6, 1, tzinfo=UTC),
        floor_years=4,
        retained=(
            RetentionBlockingRecord(
                filing_record_id=_hex("a"),
                modelo="303",
                filing_year=2024,
                filed_at=datetime(2024, 7, 1, tzinfo=UTC),
                earliest_safe_erase_date=datetime(2028, 7, 1, tzinfo=UTC),
            ),
        ),
    )


def test_assess_reads_recent_filing_and_blocks(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """A filing inside the four-year window is read from storage and blocks erase."""
    del registered_profile
    _persist_filing(runtime.bucket_id, filing_year=2024, filed_at=datetime(2024, 7, 1, tzinfo=UTC))

    assessment = BucketMaintenanceService._assess_retention_floor(runtime.bucket_id)

    assert assessment.blocks_erase is True
    assert len(assessment.retained) == 1
    assert assessment.retained[0].earliest_safe_erase_date == datetime(2028, 7, 1, tzinfo=UTC)


def test_public_deletion_assessment_reports_blocker_without_mutating_durable_bucket(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The target-scoped preflight returns fingerprint + retention and leaves durable bytes unchanged."""
    del registered_profile
    _persist_filing(runtime.bucket_id, filing_year=2024, filed_at=datetime(2024, 7, 1, tzinfo=UTC))
    service = BucketMaintenanceService()
    before = service.assess_deletion(AssessBucketDeletionCommand(bucket_id=runtime.bucket_id))

    observed = service.assess_deletion(AssessBucketDeletionCommand(bucket_id=runtime.bucket_id))
    after = service.assess_deletion(AssessBucketDeletionCommand(bucket_id=runtime.bucket_id))

    assert observed.exists is True
    assert observed.label == _LABEL
    assert observed.fingerprint is not None
    assert observed.retention is not None
    assert observed.retention.blocks_erase is True
    assert observed.fingerprint == before.fingerprint == after.fingerprint
    assert runtime.paths.bucket_dir.is_dir()
    assert ModeloRecordCatalogueRepository(bucket_id=runtime.bucket_id).load().records


def test_deletion_fingerprint_changes_when_authoritative_filing_content_changes(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """A real filing-catalogue revision changes the deletion/resume fingerprint."""
    del registered_profile
    _persist_filing(runtime.bucket_id, filing_year=2024, filed_at=datetime(2024, 7, 1, tzinfo=UTC))
    service = BucketMaintenanceService()
    before = service.assess_deletion(AssessBucketDeletionCommand(bucket_id=runtime.bucket_id))
    assert before.fingerprint is not None

    _persist_filing(runtime.bucket_id, filing_year=2025, filed_at=datetime(2025, 7, 1, tzinfo=UTC))
    after = service.assess_deletion(AssessBucketDeletionCommand(bucket_id=runtime.bucket_id))

    assert after.fingerprint is not None
    assert after.fingerprint.digest != before.fingerprint.digest
    assert after.retention is not None
    assert after.retention.retained[0].filing_year == 2025


def test_assess_reads_old_filing_and_allows(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """A filing whose four-year window has elapsed does not block erase."""
    del registered_profile
    _persist_filing(runtime.bucket_id, filing_year=2019, filed_at=datetime(2019, 7, 1, tzinfo=UTC))

    assessment = BucketMaintenanceService._assess_retention_floor(runtime.bucket_id)

    assert assessment.blocks_erase is False
    assert assessment.retained == ()


def test_enforce_refuses_without_override() -> None:
    """A blocking assessment refuses erase, naming the count and safe-erase date."""
    command = DeleteBucketCommand(bucket_id=_BUCKET_ID, confirmed=True)

    with pytest.raises(RetentionFloorError) as raised:
        BucketMaintenanceService._enforce_retention_floor(command, _blocking_assessment())

    context = raised.value.context or {}
    assert context["retained_record_count"] == 1
    assert context["earliest_safe_erase_date"] == "2028-07-01"
    assert context["bucket_id"] == _BUCKET_ID


def test_enforce_allows_with_acknowledged_override_and_reason() -> None:
    """An explicit override with a reason erases the still-retained record."""
    command = DeleteBucketCommand(
        bucket_id=_BUCKET_ID,
        confirmed=True,
        acknowledge_retention_override=True,
        retention_override_reason="Court order requiring erasure of this subject's data.",
    )

    override_used = BucketMaintenanceService._enforce_retention_floor(command, _blocking_assessment())

    assert override_used is True


def test_enforce_refuses_acknowledgement_without_reason() -> None:
    """Acknowledging the override without a reason is not a valid override."""
    command = DeleteBucketCommand(
        bucket_id=_BUCKET_ID,
        confirmed=True,
        acknowledge_retention_override=True,
        retention_override_reason=None,
    )

    with pytest.raises(RetentionFloorError):
        BucketMaintenanceService._enforce_retention_floor(command, _blocking_assessment())


def test_enforce_allows_when_nothing_retained() -> None:
    """An empty assessment needs no override and reports no override used."""
    command = DeleteBucketCommand(bucket_id=_BUCKET_ID, confirmed=True)
    empty = RetentionFloorAssessment(as_of=datetime(2026, 6, 1, tzinfo=UTC), floor_years=4)

    assert BucketMaintenanceService._enforce_retention_floor(command, empty) is False
