"""Forward migration of a stored schema-6 profile record through the real capsule.

Every adapter is real: the capsule is published by the production lifecycle
under a record session pinned to schema 6, exactly as a schema-6 build wrote
it, and then opened by the schema-7 record repository. The migration must keep
every stored ``true``, drop every stored ``false`` on the payer-fact paths,
leave every other fact untouched, record what it cleared as typed history, run
once, and leave a schema-7 record alone.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.profile_path_values import ProfilePathValuesPersistenceAdapter
from cadrumo.application.user_profile.capsule_record import (
    ProfileRecordMigrationRequiredError,
    ProfileRecordSession,
    ProfileRecordStore,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.profile_schema_migration import (
    drain_migration_cleared_paths,
    migrate_profile_record_on_open,
)
from cadrumo.application.user_profile.projections import projection_for_taxpayer
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.plantilla_media import (
    PlantillaMediaState,
    PlantillaMediaYear,
    plantilla_media_years,
)
from cadrumo.domain.user_profile.schema_migration import ProfileSchemaMigration
from cadrumo.domain.user_profile.values import (
    UserProfileFact,
    UserProfileRecord,
)

from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_v6_support import publish_capsule, publish_v6_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M347 = "obligations.third_party_transactions_above_347_threshold"
_M720 = "obligations.bienes_extranjero_above_threshold"
_M721 = "obligations.monedas_virtuales_extranjero_above_threshold"
_M136 = "obligations.premio_loteria_gravamen_especial_sin_retencion"
_MIGRATED_AT = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)
_CLEARED = (_M721, _M347)

_UNTOUCHED_FACTS = (
    UserProfileFact(path="identity.tax_id", value="X1234567L"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="withholding.has_employees", value=False),
    UserProfileFact(path="withholding.pays_capital_income_with_retencion", value=False),
)
_STORED_V6_PAYER_FACTS = (
    UserProfileFact(path=_M347, value=False),
    UserProfileFact(path=_M720, value=True),
    UserProfileFact(path=_M721, value=False, valid_from=date(2024, 1, 1), valid_to=date(2024, 12, 31)),
    UserProfileFact(path=_M721, value=False, valid_from=date(2025, 1, 1)),
)


@pytest.fixture
def contexts() -> Iterator[tuple[ProfileCreateContext, ProfileDecodeContext]]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_create_context(), operation.profile_decode_context()


def _session(decode_context: ProfileDecodeContext) -> ProfileRecordSession:
    return record_session(decode_context)


def _publish(
    root: Path,
    *,
    facts: tuple[UserProfileFact, ...],
    create_context: ProfileCreateContext,
    decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    return publish_capsule(root, facts=facts, create_context=create_context, decode_context=decode_context)


def _publish_v6(
    root: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
    facts: tuple[UserProfileFact, ...],
) -> UserProfileRecord:
    create_context, decode_context = contexts
    return publish_v6_capsule(root, facts=facts, create_context=create_context, decode_context=decode_context)


@pytest.fixture
def v6_capsule(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> Iterator[tuple[ProfileRecordSession, UserProfileRecord, Path]]:
    stored = _publish_v6(tmp_path, contexts, (*_UNTOUCHED_FACTS, *_STORED_V6_PAYER_FACTS))
    assert stored.schema_version == 6
    session = _session(contexts[1])
    drain_migration_cleared_paths()
    try:
        yield session, stored, tmp_path
    finally:
        session.close()
        drain_migration_cleared_paths()


def test_a_stored_v6_record_is_never_read_as_the_current_schema(
    v6_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    session, _stored, root = v6_capsule

    with pytest.raises(ProfileRecordMigrationRequiredError, match="schema 6"):
        ProfileRecordStore(session=session, root=root).load()


def test_opening_a_v6_record_keeps_true_drops_false_payer_facts_and_leaves_the_rest(
    v6_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    session, stored, root = v6_capsule

    migrated = ProfileRecordRepository(session=session, root=root).load(PROFILE_ID)

    assert migrated.schema_version == 7
    assert migrated.record_revision == stored.record_revision + 1
    assert migrated.previous_record_digest == stored.content_digest
    assert migrated.created_at == stored.created_at
    assert migrated.facts == (*_UNTOUCHED_FACTS, UserProfileFact(path=_M720, value=True))
    assert drain_migration_cleared_paths() == _CLEARED

    store = ProfileRecordStore(session=session, root=root)
    assert store.schema_migrations() == (ProfileSchemaMigration(cleared_paths=_CLEARED),)
    migration_events = [
        event for event in store.history() if event.event_type is BucketEventType.PROFILE_SCHEMA_MIGRATED
    ]
    assert len(migration_events) == 1
    assert migration_events[0].payload["schema_migration_cleared_paths"] == "|".join(_CLEARED)


def test_a_second_migration_run_is_a_no_op(
    v6_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    session, _stored, root = v6_capsule
    first = migrate_profile_record_on_open(session, root=root)
    after_first = ProfileRecordStore(session=session, root=root).load().record
    drain_migration_cleared_paths()

    second = migrate_profile_record_on_open(session, root=root)

    assert first == ProfileSchemaMigration(cleared_paths=_CLEARED)
    assert second is None
    assert ProfileRecordStore(session=session, root=root).load().record == after_first
    assert drain_migration_cleared_paths() == ()
    assert len(ProfileRecordStore(session=session, root=root).schema_migrations()) == 1


def test_the_migration_is_deterministic_across_capsules(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    results: list[tuple[UserProfileFact, ...]] = []
    for name in ("first", "second"):
        root = tmp_path / name
        _publish_v6(root, contexts, (*_UNTOUCHED_FACTS, *_STORED_V6_PAYER_FACTS))
        session = _session(contexts[1])
        try:
            migrate_profile_record_on_open(session, root=root)
            results.append(ProfileRecordStore(session=session, root=root).load().record.facts)
        finally:
            session.close()
            drain_migration_cleared_paths()

    assert results[0] == results[1]


def test_a_v7_record_is_read_unchanged_and_never_migrated(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    create_context, decode_context = contexts
    facts = (*_UNTOUCHED_FACTS, UserProfileFact(path=_M347, value=False), UserProfileFact(path=_M136, value=False))
    written = _publish(tmp_path, facts=facts, create_context=create_context, decode_context=decode_context)
    session = _session(decode_context)
    try:
        assert migrate_profile_record_on_open(session, root=tmp_path) is None
        loaded = ProfileRecordRepository(session=session, root=tmp_path).load(PROFILE_ID)
        assert loaded == written
        assert ProfileRecordStore(session=session, root=tmp_path).schema_migrations() == ()
        assert drain_migration_cleared_paths() == ()
    finally:
        session.close()


def test_a_v6_record_carrying_a_schema_7_path_is_refused(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    stored = _publish_v6(tmp_path, contexts, (*_UNTOUCHED_FACTS, UserProfileFact(path=_M136, value=True)))
    session = _session(contexts[1])
    try:
        with pytest.raises(UserProfileValidationError, match="schema-7 paths"):
            migrate_profile_record_on_open(session, root=tmp_path)
        with pytest.raises(ProfileRecordMigrationRequiredError):
            ProfileRecordStore(session=session, root=tmp_path).load()
        assert stored.schema_version == 6
    finally:
        session.close()


def test_the_cleared_fact_stays_pending_until_answered_and_no_then_excludes_the_modelo(
    v6_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    session, _stored, root = v6_capsule
    repository = ProfileRecordRepository(session=session, root=root)
    migrated = repository.load(PROFILE_ID)
    schema = contexts[1].schema

    assert repository.pending_cleared_payer_fact_paths(PROFILE_ID) == _CLEARED
    with bundled_indexed_authority().operation():
        undeclared = derive_modelo_applicability(projection_for_taxpayer(migrated, schema=schema), "347")
    assert undeclared.verdict is ApplicabilityVerdict.INCOMPLETE

    answered = repository.apply_fact_changes(
        PROFILE_ID,
        facts=(*migrated.facts, UserProfileFact(path=_M347, value=False)),
        expected_revision=migrated.record_revision,
        expected_content_digest=migrated.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=_MIGRATED_AT,
    )

    assert repository.pending_cleared_payer_fact_paths(PROFILE_ID) == (_M721,)
    with bundled_indexed_authority().operation():
        declared_no = derive_modelo_applicability(projection_for_taxpayer(answered, schema=schema), "347")
    assert declared_no.verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_a_restored_v6_capsule_is_accepted_and_migrates_on_first_open(
    v6_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    session, stored, root = v6_capsule
    store = ProfileRecordStore(session=session, root=root)
    database = root / "restore-stage" / storage_location(StorageCategory.BUCKET_DATABASE_FILE).relative_path()
    database.parent.mkdir(parents=True)
    source = next(root.rglob("cadrumo.db"))
    database.write_bytes(source.read_bytes())

    staged = store.validate_staged_database(stage_path=root / "restore-stage")

    assert staged.record == stored


def test_a_migrated_v6_record_carries_no_average_workforce_instance(
    v6_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    session, _stored, root = v6_capsule

    migrated = ProfileRecordRepository(session=session, root=root).load(PROFILE_ID)

    assert not [fact for fact in migrated.facts if fact.path.startswith("irpf.plantilla_media")]


def test_a_v6_record_carrying_an_average_workforce_instance_is_refused(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    _publish_v6(
        tmp_path, contexts, (*_UNTOUCHED_FACTS, UserProfileFact(path="irpf.plantilla_media.0.year", value=2024))
    )
    session = _session(contexts[1])
    try:
        with pytest.raises(UserProfileValidationError, match="schema-7 paths"):
            migrate_profile_record_on_open(session, root=tmp_path)
    finally:
        session.close()


def test_a_v7_average_workforce_instance_round_trips_with_its_typed_meaning(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    create_context, decode_context = contexts
    instances = (
        UserProfileFact(path="irpf.plantilla_media.0.year", value=2024),
        UserProfileFact(path="irpf.plantilla_media.0.average_workforce", value=Decimal("12.50")),
        UserProfileFact(path="irpf.plantilla_media.0.state", value="observed"),
        UserProfileFact(path="irpf.plantilla_media.1.year", value=2025),
        UserProfileFact(path="irpf.plantilla_media.1.average_workforce", value=Decimal("13.05")),
        UserProfileFact(path="irpf.plantilla_media.1.state", value="committed"),
    )
    written = _publish(
        tmp_path,
        facts=(*_UNTOUCHED_FACTS, *instances),
        create_context=create_context,
        decode_context=decode_context,
    )
    session = _session(decode_context)
    try:
        loaded = ProfileRecordStore(session=session, root=tmp_path).load().record
    finally:
        session.close()

    assert loaded == written
    years = plantilla_media_years({fact.path: fact.value for fact in loaded.facts})
    assert years == (
        PlantillaMediaYear(year=2024, average_workforce=Decimal("12.50"), state=PlantillaMediaState.OBSERVED),
        PlantillaMediaYear(year=2025, average_workforce=Decimal("13.05"), state=PlantillaMediaState.COMMITTED),
    )
    assert str(years[0].average_workforce) == "12.50"


def test_the_profile_path_port_reads_average_workforce_as_typed_years(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Consumers read through the path port, which projects every stored value as a string."""
    create_context, decode_context = contexts
    instances = (
        UserProfileFact(path="irpf.plantilla_media.0.year", value=2024),
        UserProfileFact(path="irpf.plantilla_media.0.average_workforce", value=Decimal("12.50")),
        UserProfileFact(path="irpf.plantilla_media.0.state", value="observed"),
        UserProfileFact(path="irpf.plantilla_media.1.year", value=2025),
        UserProfileFact(path="irpf.plantilla_media.1.average_workforce", value=Decimal("7")),
        UserProfileFact(path="irpf.plantilla_media.1.state", value="committed"),
    )
    _publish(
        tmp_path, facts=(*_UNTOUCHED_FACTS, *instances), create_context=create_context, decode_context=decode_context
    )
    session = _session(decode_context)
    try:
        port = ProfilePathValuesPersistenceAdapter(repository=ProfileRecordRepository(session=session, root=tmp_path))
        values = port.load_path_values(bucket_id=str(PROFILE_ID))
    finally:
        session.close()

    assert values is not None
    assert values["irpf.plantilla_media.0.year"] == "2024", "the port projects stored values as strings"
    assert plantilla_media_years(values) == (
        PlantillaMediaYear(year=2024, average_workforce=Decimal("12.50"), state=PlantillaMediaState.OBSERVED),
        PlantillaMediaYear(year=2025, average_workforce=Decimal("7"), state=PlantillaMediaState.COMMITTED),
    )


@pytest.mark.parametrize(
    ("subfield", "stored"),
    (("year", "2024.5"), ("average_workforce", "12.505"), ("average_workforce", "-1"), ("state", "planned")),
)
def test_a_malformed_stored_string_is_still_refused_after_restoration(subfield: str, stored: str) -> None:
    """Restoring the stored representation must not loosen any rule."""
    values = {
        "irpf.plantilla_media.0.year": "2024",
        "irpf.plantilla_media.0.average_workforce": "12.50",
        "irpf.plantilla_media.0.state": "observed",
        f"irpf.plantilla_media.0.{subfield}": stored,
    }
    with pytest.raises(UserProfileValidationError, match=rf"irpf\.plantilla_media\.0\.{subfield}"):
        plantilla_media_years(values)
