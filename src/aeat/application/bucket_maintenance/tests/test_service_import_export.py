"""Service-contract tests for bucket sealed export/import.

Exercises ``BucketMaintenanceService.export`` and ``import_`` through real
profile storage, real sealed-archive writer/reader, real crypto, and real
bucket-event history. No CLI code participates in these tests; the service
contract stays in the application layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType, BucketImportError
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_profile_storage_root, isolated_runtime_profile
from ...user_profile import RegisterProfileCommand, profile_storage_session
from ...workflow import read_profile_bucket_by_id
from .. import BucketMaintenanceService, ExportBucketCommand, ImportBucketCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "bucket-maintenance-export-test"
_LABEL = "Export target"
_RECOVERY_WORDS = ("correct", "horse", "battery", "staple")


def _recovery_phrase() -> str:
    return " ".join(_RECOVERY_WORDS)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_LABEL,
    ) as profile:
        yield profile


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return tuple(facts)


@pytest.fixture
def registered_profile(runtime: TestRuntimeProfile) -> None:
    """Register a real profile so portable-bundle export has a source record."""
    from ...user_profile import (
        ProfileLifecycleService,
        ProfileValidationService,
        UserProfileLifecycleRepository,
    )

    schema = resources().user_profile_schema.singleton
    assert isinstance(schema, ProfileSchemaDefinition)
    service = ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(
            bucket_id=runtime.bucket_id,
            objects=runtime.repository,
        ),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=runtime.repository),
    )
    service.register(
        RegisterProfileCommand(
            profile_id=runtime.bucket_id,
            display_name=_LABEL,
            facts=_all_required_facts(schema),
        ),
    )


def test_export_writes_sealed_archive_and_bucket_event(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    del registered_profile
    archive_path = tmp_path / "exports" / "profile.aeat-bucket.tar.gz"

    result = BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    assert result.bucket_id == runtime.bucket_id
    assert result.output_path == archive_path
    assert result.recovery_wrap_present is True
    assert archive_path.is_file()
    archive_bytes = archive_path.read_bytes()
    assert _LABEL.encode("utf-8") not in archive_bytes

    catalogue = BucketEventHistoryRepository(objects=runtime.repository).load()
    export_events = tuple(
        event for event in catalogue.events.values() if event.event_type is BucketEventType.BUCKET_EXPORTED
    )
    assert len(export_events) == 1
    assert export_events[0].payload["manifest_digest"] == result.manifest_digest
    assert export_events[0].payload["recovery_wrap_present"] == "true"


def test_import_recovery_archive_provisions_profile_in_fresh_root(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    del registered_profile
    archive_path = tmp_path / "profile.aeat-bucket.tar.gz"
    exported = BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    with isolated_profile_storage_root(tmp_path=tmp_path / "import-root"):
        imported = BucketMaintenanceService().import_(
            ImportBucketCommand(
                source_path=archive_path,
                recovery_wrap_passphrase=_recovery_phrase(),
            ),
        )

        assert imported.bucket_id == runtime.bucket_id
        assert imported.manifest_digest == exported.manifest_digest
        pointer = read_profile_bucket_by_id(runtime.bucket_id)
        assert pointer is not None
        assert pointer.label == _LABEL

        with profile_storage_session(runtime.bucket_id):
            catalogue = BucketEventHistoryRepository().load()
        event_types = {event.event_type for event in catalogue.events.values()}
        assert BucketEventType.BUCKET_IMPORTED in event_types


def test_recovery_wrap_member_records_argon2id_password_kdf(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    """The recovery-wrap archive seals under Argon2id, not a bare HKDF pass.

    A recovery-passphrase archive may leave the host; sealing it under a password
    KDF with a real work factor is what defeats an offline brute force of the
    operator-chosen passphrase. The recovery-wrap member must declare ``argon2id``
    and carry the cost parameters so the importer reproduces the derivation.
    """
    import json

    from ....adapters.persistence.storage.bucket import read_sealed_archive

    archive_path = tmp_path / "profile.aeat-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    contents = read_sealed_archive(archive_path)
    assert contents.recovery_wrap_bytes is not None
    member = json.loads(contents.recovery_wrap_bytes.decode("utf-8"))
    assert member["kdf"] == "argon2id"
    assert member["memory_cost"] >= 19 * 1024
    assert member["time_cost"] >= 2
    assert member["parallelism"] >= 1
    assert isinstance(member["salt_b64"], str) and member["salt_b64"]


def test_import_recovery_archive_rejects_wrong_passphrase(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    """A wrong recovery passphrase derives the wrong KEK and the import fails closed."""
    del registered_profile
    archive_path = tmp_path / "profile.aeat-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    with isolated_profile_storage_root(tmp_path=tmp_path / "import-root"), pytest.raises(BucketImportError):
        BucketMaintenanceService().import_(
            ImportBucketCommand(
                source_path=archive_path,
                recovery_wrap_passphrase=f"wrong-{_recovery_phrase()}",
            ),
        )


def test_import_refuses_recovery_archive_without_passphrase(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    del registered_profile
    archive_path = tmp_path / "profile.aeat-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    with (
        isolated_profile_storage_root(tmp_path=tmp_path / "import-root"),
        pytest.raises(BucketImportError),
    ):
        BucketMaintenanceService().import_(ImportBucketCommand(source_path=archive_path))


def test_import_refuses_live_bucket_collision_without_force(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    del registered_profile
    archive_path = tmp_path / "profile.aeat-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    with pytest.raises(BucketImportError):
        BucketMaintenanceService().import_(
            ImportBucketCommand(
                source_path=archive_path,
                recovery_wrap_passphrase=_recovery_phrase(),
            ),
        )
