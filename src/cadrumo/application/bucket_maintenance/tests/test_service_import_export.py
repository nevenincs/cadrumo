"""Service-contract tests for bucket sealed export/import.

Exercises ``BucketMaintenanceService.export`` and ``import_`` through real
profile storage, real sealed-archive writer/reader, real crypto, and real
bucket-event history. No CLI code participates in these tests; the service
contract stays in the application layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage import ClassificationError, SensitivityClass
from ....adapters.persistence.storage.bucket import (
    ExportArchiveHeader,
    SealedArchiveContents,
    bucket_paths,
    read_sealed_archive,
    write_sealed_archive,
)
from ....adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record, encrypt_record
from ....adapters.persistence.storage.master_key import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    derive_kek_with_params,
)
from ....core import Period
from ....core.config import load_settings
from ....core.external_constants import UTF_8_ENCODING
from ....core.resources import resources
from ....domain.buckets import BucketEventType, BucketImportError
from ....domain.modelos import ModeloCode, WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ....domain.user_profile import (
    CarriedSecureObject,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfilePortableExport,
    UserProfileRecord,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_profile_storage_root, isolated_runtime_profile
from ....tests.user_profile import schema_valid_placeholder
from ...user_profile import RegisterProfileCommand, profile_storage_session, validate_bundle_payload
from ...workflow import read_profile_bucket_by_id
from .._contracts import ExportBucketCommand, ImportBucketCommand, InspectBucketArchiveCommand
from .._service import BucketMaintenanceService, _archive_associated_data, _recovery_wrap_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
_INCOMPLETE_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_LABEL = "Export target"
_RECOVERY_WORDS = ("correct", "horse", "battery", "staple")
_MANIFEST_DIGEST = "b" * 64
_INSTANT = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)


def _recovery_phrase() -> str:
    return " ".join(_RECOVERY_WORDS)


def _incomplete_archive_recovery_phrase() -> str:
    return " ".join(("incomplete", "archive", "recovery", "phrase"))


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_LABEL,
    ) as profile:
        yield profile


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts_by_path: dict[str, UserProfileFact] = {}
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                path = f"{section.key}.{field.key}"
                facts_by_path[path] = UserProfileFact(path=path, value=schema_valid_placeholder(field))
    facts_by_path.update(
        {
            "taxpayer_type.entity_type": UserProfileFact(
                path="taxpayer_type.entity_type",
                value="natural_person",
            ),
            "identity.name": UserProfileFact(path="identity.name", value="Export"),
            "identity.surnames": UserProfileFact(path="identity.surnames", value="Ready"),
        },
    )
    return tuple(facts_by_path.values())


def _write_incomplete_profile_archive(path: Path) -> None:
    bundle = UserProfilePortableExport(
        bundle_schema_version=3,
        exported_at=_INSTANT,
        profile=UserProfileRecord(
            profile_id=_INCOMPLETE_BUCKET_ID,
            display_name="Incomplete import",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_INSTANT,
            updated_at=_INSTANT,
        ),
    )
    payload = bundle.model_dump_json().encode(UTF_8_ENCODING)
    recovery_wrap_bytes = _recovery_wrap_bytes(
        b"c" * 16,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )
    sealing_key = derive_kek_with_params(
        _incomplete_archive_recovery_phrase().encode(UTF_8_ENCODING),
        b"c" * 16,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )
    encrypted = encrypt_record(
        payload,
        key=sealing_key,
        associated_data=_archive_associated_data(_INCOMPLETE_BUCKET_ID, _MANIFEST_DIGEST),
    )
    write_sealed_archive(
        path,
        header=ExportArchiveHeader(
            product="cadrumo",
            bucket_id=_INCOMPLETE_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            recovery_wrap_present=True,
            archive_schema_version=3,
            created_at=_INSTANT,
        ),
        payload_envelope_bytes=encrypted.to_wire(),
        recovery_wrap_bytes=recovery_wrap_bytes,
    )


def _write_schema_2_profile_archive(path: Path) -> None:
    bundle = UserProfilePortableExport(
        bundle_schema_version=2,
        exported_at=_INSTANT,
        profile=UserProfileRecord(
            profile_id=_INCOMPLETE_BUCKET_ID,
            display_name="Unsupported bundle import",
            facts=(
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="identity.name", value="Unsupported"),
                UserProfileFact(path="identity.surnames", value="Bundle"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
            ),
            created_at=_INSTANT,
            updated_at=_INSTANT,
        ),
    )
    payload = bundle.model_dump_json().encode(UTF_8_ENCODING)
    recovery_wrap_bytes = _recovery_wrap_bytes(
        b"d" * 16,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )
    sealing_key = derive_kek_with_params(
        _incomplete_archive_recovery_phrase().encode(UTF_8_ENCODING),
        b"d" * 16,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )
    encrypted = encrypt_record(
        payload,
        key=sealing_key,
        associated_data=_archive_associated_data(_INCOMPLETE_BUCKET_ID, _MANIFEST_DIGEST),
    )
    write_sealed_archive(
        path,
        header=ExportArchiveHeader(
            product="cadrumo",
            bucket_id=_INCOMPLETE_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            recovery_wrap_present=True,
            archive_schema_version=3,
            created_at=_INSTANT,
        ),
        payload_envelope_bytes=encrypted.to_wire(),
        recovery_wrap_bytes=recovery_wrap_bytes,
    )


def _write_unsupported_schema_archive(path: Path) -> None:
    write_sealed_archive(
        path,
        header=ExportArchiveHeader(
            product="cadrumo",
            bucket_id=_INCOMPLETE_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            recovery_wrap_present=False,
            archive_schema_version=1,
            created_at=_INSTANT,
        ),
        payload_envelope_bytes=b"schema gate rejects before decrypt",
    )


@pytest.fixture
def registered_profile(runtime: TestRuntimeProfile) -> None:
    """Register a real profile so portable-bundle export has a source record."""
    _register_profile(runtime)


def _register_profile(runtime: TestRuntimeProfile) -> None:
    """Register the complete real profile record an archive transport needs."""
    from ...user_profile import ProfileLifecycleService, ProfileValidationService, UserProfileLifecycleRepository

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
    archive_path = tmp_path / "exports" / "profile.cadrumo-bucket.tar.gz"

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
    contents = read_sealed_archive(archive_path)
    assert contents.header.archive_schema_version == 3

    catalogue = BucketEventHistoryRepository(objects=runtime.repository).load()
    export_events = tuple(
        event for event in catalogue.events.values() if event.event_type is BucketEventType.BUCKET_EXPORTED
    )
    assert len(export_events) == 1
    assert export_events[0].payload["manifest_digest"] == result.manifest_digest
    assert export_events[0].payload["archive_schema_version"] == "3"
    assert export_events[0].payload["recovery_wrap_present"] == "true"


def test_import_recovery_archive_provisions_profile_in_fresh_root(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    del registered_profile
    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
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


_POISON_NAMESPACE = "cadrumo.application.workflow.runs"
_POISON_DECLARED_CLASS = SensitivityClass.FINANCIAL
_POISON_WRONG_CLASS = SensitivityClass.IDENTITY
_WORK_UNIT_TIMESTAMP = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)


def _work_unit(bucket_id: str) -> WorkUnit:
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    revision_id = "2026-y-siguientes"
    modelo = ModeloCode("303")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"IVA-{filing_year}-{period.registry_token}-crash-window",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
        state=WorkUnitState.BORRADOR,
    )


def _decrypt_bundle(
    contents: SealedArchiveContents,
    *,
    recovery_wrap_passphrase: str,
) -> tuple[UserProfilePortableExport, bytes]:
    """Decrypt a real sealed archive's payload outside of a live bucket session.

    Mirrors what ``BucketMaintenanceService.import_`` does internally when a
    recovery-wrap archive is presented: derive the same KEK from the stored
    Argon2id parameters and the passphrase, then open the AEAD payload.
    """
    import json

    assert contents.recovery_wrap_bytes is not None
    member = json.loads(contents.recovery_wrap_bytes.decode(UTF_8_ENCODING))
    import base64

    salt = base64.b64decode(member["salt_b64"])
    sealing_key = derive_kek_with_params(
        recovery_wrap_passphrase.encode(UTF_8_ENCODING),
        salt,
        memory_cost=member["memory_cost"],
        time_cost=member["time_cost"],
        parallelism=member["parallelism"],
    )
    decrypted = decrypt_record(
        EncryptedBlob.from_wire(contents.payload_envelope_bytes),
        key=sealing_key,
        associated_data=_archive_associated_data(contents.header.bucket_id, contents.header.manifest_digest),
    )
    return validate_bundle_payload(decrypted), sealing_key


def _write_poisoned_archive(
    contents: SealedArchiveContents,
    *,
    poisoned_bundle: UserProfilePortableExport,
    sealing_key: bytes,
    output_path: Path,
) -> None:
    """Re-seal ``poisoned_bundle`` under the same header and recovery wrap."""
    encrypted = encrypt_record(
        poisoned_bundle.model_dump_json().encode(UTF_8_ENCODING),
        key=sealing_key,
        associated_data=_archive_associated_data(contents.header.bucket_id, contents.header.manifest_digest),
    )
    write_sealed_archive(
        output_path,
        header=contents.header,
        payload_envelope_bytes=encrypted.to_wire(),
        recovery_wrap_bytes=contents.recovery_wrap_bytes,
    )


def test_a_refused_carried_object_leaves_no_import_target(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    """A late carried-object refusal rolls back the whole new-bucket import.

    The archive is real AES-GCM payload encrypted under the real Argon2id
    recovery key. It is re-sealed with a carried object whose classification
    contradicts its registered namespace; the production secure-object policy
    is what refuses it after the typed work-unit importer has run. The active
    pointer and the whole target directory must nevertheless disappear, proving
    the create-span recovery owner covers activation, typed restoration, and
    completion-event emission as one import boundary.
    """
    del registered_profile
    work_unit = _work_unit(runtime.bucket_id)
    WorkUnitCatalogueRepository(bucket_id=runtime.bucket_id, objects=runtime.repository).save(
        WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
    )

    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    contents = read_sealed_archive(archive_path)
    bundle, sealing_key = _decrypt_bundle(contents, recovery_wrap_passphrase=_recovery_phrase())
    assert bundle.work_units, "the export must genuinely carry the work unit written above"

    # The poison: one caller-supplied carried object whose classification
    # does not match its namespace's registered sensitivity. This is the
    # SAME production refusal `test_custody_restore_atomicity.py` proves
    # `restore_carried_objects` itself handles atomically -- appended here,
    # one layer up, after work units that already committed.
    poisoned_carried = CarriedSecureObject(
        namespace=_POISON_NAMESPACE,
        object_key="crash-window-poison",
        classification=_POISON_WRONG_CLASS,
        schema_version=1,
        written_at=_WORK_UNIT_TIMESTAMP,
        payload_b64="eyJhIjogMX0=",  # {"a": 1}
    )
    poisoned_bundle = bundle.model_copy(update={"carried_objects": (*bundle.carried_objects, poisoned_carried)})

    poisoned_path = tmp_path / "poisoned.cadrumo-bucket.tar.gz"
    _write_poisoned_archive(
        contents,
        poisoned_bundle=poisoned_bundle,
        sealing_key=sealing_key,
        output_path=poisoned_path,
    )

    with isolated_profile_storage_root(tmp_path=tmp_path / "import-root"):
        with pytest.raises(ClassificationError):
            BucketMaintenanceService().import_(
                ImportBucketCommand(
                    source_path=poisoned_path,
                    recovery_wrap_passphrase=_recovery_phrase(),
                ),
            )

        pointer = read_profile_bucket_by_id(runtime.bucket_id)
        assert pointer is None, "a refused import must restore the pre-import active-pointer state"
        target_paths = bucket_paths(load_settings().cadrumo_local_storage_root, runtime.bucket_id)
        assert not target_paths.bucket_dir.exists(), "a refused import must remove typed-catalogue residue"


def _bucket_file_bytes(bucket_dir: Path) -> dict[str, bytes]:
    """Capture every durable file in one bucket for exact rollback proof.

    SQLite's ``-shm`` and ``-wal`` companions are connection-local runtime
    state, recreated when the restored database is opened. The main database
    remains the durable authority; typed and event-history reads below prove
    its restored contents.
    """
    return {
        path.relative_to(bucket_dir).as_posix(): path.read_bytes()
        for path in sorted(bucket_dir.rglob("*"))
        if path.is_file() and not path.name.endswith(("-shm", "-wal"))
    }


def test_a_refused_carried_object_preserves_existing_force_import_target(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    """A late force-import refusal restores every prior target artifact exactly.

    The source archive is real AES-GCM payload encrypted under its real
    Argon2id recovery wrap. Its added carried object is rejected by the
    production namespace-classification policy only after the typed work-unit
    save. The target is a distinct, already registered same-id bucket with no
    work unit, so a surviving source row proves a failed force import
    contaminated live taxpayer state. File bytes, typed rows, and event history
    all have to match their pre-import target values after the real refusal.
    """
    del registered_profile
    work_unit = _work_unit(runtime.bucket_id)
    WorkUnitCatalogueRepository(bucket_id=runtime.bucket_id, objects=runtime.repository).save(
        WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
    )

    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )
    contents = read_sealed_archive(archive_path)
    bundle, sealing_key = _decrypt_bundle(contents, recovery_wrap_passphrase=_recovery_phrase())
    assert bundle.work_units, "the export must genuinely carry the source work unit"
    poisoned_bundle = bundle.model_copy(
        update={
            "carried_objects": (
                *bundle.carried_objects,
                CarriedSecureObject(
                    namespace=_POISON_NAMESPACE,
                    object_key="force-crash-window-poison",
                    classification=_POISON_WRONG_CLASS,
                    schema_version=1,
                    written_at=_WORK_UNIT_TIMESTAMP,
                    payload_b64="eyJhIjogMX0=",  # {"a": 1}
                ),
            ),
        },
    )
    poisoned_path = tmp_path / "force-poisoned.cadrumo-bucket.tar.gz"
    _write_poisoned_archive(
        contents,
        poisoned_bundle=poisoned_bundle,
        sealing_key=sealing_key,
        output_path=poisoned_path,
    )

    with isolated_runtime_profile(
        tmp_path=tmp_path / "force-target-root",
        bucket_id=runtime.bucket_id,
        label=_LABEL,
    ) as target:
        _register_profile(target)
        target_paths = bucket_paths(load_settings().cadrumo_local_storage_root, target.bucket_id)
        before_files = _bucket_file_bytes(target_paths.bucket_dir)
        before_work_units = WorkUnitCatalogueRepository(bucket_id=target.bucket_id, objects=target.repository).load()
        before_events = BucketEventHistoryRepository(objects=target.repository).load()
        assert not before_work_units.work_units, "the target must not already contain the source work unit"

        with pytest.raises(ClassificationError):
            BucketMaintenanceService().import_(
                ImportBucketCommand(
                    source_path=poisoned_path,
                    force_replace=True,
                    recovery_wrap_passphrase=_recovery_phrase(),
                ),
            )

        assert _bucket_file_bytes(target_paths.bucket_dir) == before_files
        restored_work_units = WorkUnitCatalogueRepository(bucket_id=target.bucket_id, objects=target.repository).load()
        restored_events = BucketEventHistoryRepository(objects=target.repository).load()
        assert restored_work_units == before_work_units
        assert work_unit.work_unit_id not in restored_work_units.work_units
        assert restored_events == before_events

        imported = BucketMaintenanceService().import_(
            ImportBucketCommand(
                source_path=archive_path,
                force_replace=True,
                recovery_wrap_passphrase=_recovery_phrase(),
            ),
        )
        assert imported.bucket_id == target.bucket_id
        completed_work_units = WorkUnitCatalogueRepository(bucket_id=target.bucket_id, objects=target.repository).load()
        assert work_unit.work_unit_id in completed_work_units.work_units
        completed_events = BucketEventHistoryRepository(objects=target.repository).load()
        assert BucketEventType.BUCKET_IMPORTED in {event.event_type for event in completed_events.events.values()}


def test_import_refuses_profile_archive_missing_filing_baseline(tmp_path: Path) -> None:
    archive_path = tmp_path / "incomplete-profile.cadrumo-bucket.tar.gz"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _write_incomplete_profile_archive(archive_path)

        with pytest.raises(BucketImportError) as excinfo:
            BucketMaintenanceService().import_(
                ImportBucketCommand(
                    source_path=archive_path,
                    recovery_wrap_passphrase=_incomplete_archive_recovery_phrase(),
                ),
            )

        assert excinfo.value.translated_message == (
            "application.bucket_maintenance.errors.import_missing_filing_baseline"
        )
        assert excinfo.value.context == {"missing_flags": "--entity-type --name --surnames"}
        assert read_profile_bucket_by_id(_INCOMPLETE_BUCKET_ID) is None


def test_import_refuses_schema_1_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "schema-1.cadrumo-bucket.tar.gz"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _write_unsupported_schema_archive(archive_path)

        with pytest.raises(BucketImportError) as excinfo:
            BucketMaintenanceService().import_(ImportBucketCommand(source_path=archive_path))

        assert excinfo.value.translated_message == (
            "application.bucket_maintenance.errors.unsupported_archive_schema_version"
        )
        assert excinfo.value.context == {"archive_schema_version": "1"}


def test_import_refuses_schema_2_bundle_before_bucket_provisioning(tmp_path: Path) -> None:
    archive_path = tmp_path / "schema-2-bundle.cadrumo-bucket.tar.gz"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _write_schema_2_profile_archive(archive_path)

        with pytest.raises(BucketImportError) as excinfo:
            BucketMaintenanceService().import_(
                ImportBucketCommand(
                    source_path=archive_path,
                    recovery_wrap_passphrase=_incomplete_archive_recovery_phrase(),
                ),
            )

        assert excinfo.value.translated_message == "application.user_profile.errors.unsupported_bundle_schema_version"
        assert excinfo.value.context == {"bundle_schema_version": "2", "supported_versions": "3"}
        assert read_profile_bucket_by_id(_INCOMPLETE_BUCKET_ID) is None


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

    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
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
    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
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
    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
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
    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
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


def test_inspect_reads_header_without_decrypting_or_opening_session(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    """``inspect`` reports the plaintext header + file size for a real archive.

    Composes the same :func:`read_sealed_archive` reader ``import_`` uses,
    so a real ``export`` followed by ``inspect`` must agree with the
    ``export`` result on every header field. No decryption key is
    supplied to :meth:`BucketMaintenanceService.inspect`, proving the
    method never opens the AEAD payload.
    """
    del registered_profile
    archive_path = tmp_path / "inspect-me.cadrumo-bucket.tar.gz"
    exported = BucketMaintenanceService().export(
        ExportBucketCommand(
            bucket_id=runtime.bucket_id,
            output_path=archive_path,
            recovery_wrap_passphrase=_recovery_phrase(),
        ),
    )

    inspected = BucketMaintenanceService().inspect(InspectBucketArchiveCommand(source_path=archive_path))

    assert inspected.bucket_id == exported.bucket_id
    assert inspected.manifest_digest == exported.manifest_digest
    assert inspected.recovery_wrap_present == exported.recovery_wrap_present is True
    assert inspected.archive_schema_version == 3
    assert inspected.size_bytes == archive_path.stat().st_size
    assert inspected.size_bytes > 0


def test_inspect_same_host_archive_reports_no_recovery_wrap(
    runtime: TestRuntimeProfile,
    registered_profile: None,
    tmp_path: Path,
) -> None:
    """A same-host archive (no recovery passphrase) inspects as recovery_wrap_present=False."""
    del registered_profile
    archive_path = tmp_path / "same-host.cadrumo-bucket.tar.gz"
    BucketMaintenanceService().export(
        ExportBucketCommand(bucket_id=runtime.bucket_id, output_path=archive_path),
    )

    inspected = BucketMaintenanceService().inspect(InspectBucketArchiveCommand(source_path=archive_path))

    assert inspected.recovery_wrap_present is False


def test_inspect_refuses_malformed_archive(tmp_path: Path) -> None:
    """``inspect`` refuses a file that is not a valid sealed archive.

    Anti-tautology proof: a garbage file must not silently produce a
    fabricated header. It must raise, exactly as ``import_`` does when it
    reads the same malformed archive.
    """
    from ....adapters.persistence.storage.bucket import SealedArchiveLayoutError

    garbage_path = tmp_path / "not-an-archive.cadrumo-bucket.tar.gz"
    garbage_path.write_bytes(b"this is not a gzip tar archive at all")

    with pytest.raises(SealedArchiveLayoutError):
        BucketMaintenanceService().inspect(InspectBucketArchiveCommand(source_path=garbage_path))
