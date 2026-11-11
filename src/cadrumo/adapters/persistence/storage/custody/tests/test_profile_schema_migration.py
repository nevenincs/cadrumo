"""Forward migration of every supported stored profile record through the real capsule.

Every adapter is real: the capsule is published by the production lifecycle
under a record session pinned to the stored schema, exactly as that build wrote
it, and then opened by the current record repository. Both supported stored
versions are exercised, so a profile that was never opened across a release
still opens: schema 6 crosses both transitions in one write and schema 7
crosses one.

The migration must keep every stored value its transitions cannot prove is a
default, drop exactly the default each cleared path carried -- ``false`` for a
yes/no fact and the old ``resident_irpf`` token for the one select -- leave
every other fact untouched, record what it cleared as typed history, run once,
and leave a current record alone.
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
from cadrumo.domain.calculations.registry.applicability import derive_modelo_applicability
from cadrumo.domain.calculations.registry.applicability_models import ApplicabilityVerdict
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.plantilla_media import (
    PlantillaMediaState,
    PlantillaMediaYear,
    plantilla_media_years,
)
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS,
    ProfileSchemaMigration,
)
from cadrumo.domain.user_profile.values import (
    UserProfileFact,
    UserProfileRecord,
)

from ......domain.calculations.registry.tests.authored_editions import latest_period_end
from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_legacy_support import publish_capsule, publish_legacy_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M347 = "obligations.third_party_transactions_above_347_threshold"
_M720 = "obligations.bienes_extranjero_above_threshold"
_M136 = "obligations.premio_loteria_gravamen_especial_sin_retencion"
_INTRACOMUNITARIO = "iva.does_intracomunitario"
_PAYS_PROFESSIONALS = "withholding.pays_professionals_with_retencion"
_PAYS_RENT = "withholding.pays_rent_with_retencion"
_HAS_EMPLOYEES = "withholding.has_employees"
_ART109 = "irpf.art109_activity_income_withholding_ge_70pct"
_PAYS_CAPITAL = "withholding.pays_capital_income_with_retencion"
_CAPITAL_GATED_MODELOS = ("117", "123", "126", "128", "187", "188", "193", "194")
_LARGE_COMPANY = "censo.large_company"
_RESIDENCY = "taxpayer_type.fiscal_residency"
_RESIDENT_CATEGORY = "resident_irpf"
_NON_RESIDENT_CATEGORY = "non_resident_irnr"
_RESIDENCY_DECIDED_MODELOS = ("100", "210")
_GROUP_MEMBER = "iva.group_member_enrolled"
_OSS = "iva.oss_enrolled"
_SII = "iva.sii_enrolled"
_INTRA_50000 = "iva.intracommunity_operations_exceed_50000_eur"
_MIGRATED_AT = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)

_CLEARED_FROM_V7 = (
    _LARGE_COMPANY,
    _ART109,
    _INTRACOMUNITARIO,
    _INTRA_50000,
    _OSS,
    _SII,
    _RESIDENCY,
    _PAYS_CAPITAL,
    _PAYS_PROFESSIONALS,
    _PAYS_RENT,
)
_CLEARED_FROM_V6 = (
    _LARGE_COMPANY,
    _ART109,
    _INTRACOMUNITARIO,
    _INTRA_50000,
    _OSS,
    _SII,
    _M347,
    _RESIDENCY,
    _PAYS_CAPITAL,
    _PAYS_PROFESSIONALS,
    _PAYS_RENT,
)
_EXPECTED_CLEARED = {6: _CLEARED_FROM_V6, 7: _CLEARED_FROM_V7}

_UNTOUCHED_FACTS = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="censo.public_administration_budget_gt_6000000", value=False),
)
"""Facts no transition touches: the identity axes and the hard-required IVA block.

A stored IVA enrolment claims the Modelo IVA block, and a claimed block must
state its four required booleans and its composition either way, so those
travel with the untouched facts. The public-administration budget predicate is
the remaining stored ``false`` no transition clears: it cannot turn an
unanswered question into a not-applicable verdict, so its value keeps its
meaning.
"""

_STORED_PAYER_FACTS = (
    UserProfileFact(path=_HAS_EMPLOYEES, value=True),
    UserProfileFact(path=_M347, value=False),
    UserProfileFact(path=_M720, value=True),
    UserProfileFact(path=_INTRACOMUNITARIO, value=False),
    UserProfileFact(path=_ART109, value=False),
    UserProfileFact(path=_PAYS_CAPITAL, value=False),
    UserProfileFact(path=_PAYS_PROFESSIONALS, value=False),
    UserProfileFact(path=_LARGE_COMPANY, value=False),
    UserProfileFact(path=_RESIDENCY, value=_RESIDENT_CATEGORY),
    UserProfileFact(path=_GROUP_MEMBER, value=True),
    UserProfileFact(path=_OSS, value=False),
    UserProfileFact(path=_SII, value=False),
    UserProfileFact(path=_INTRA_50000, value=False),
    UserProfileFact(path=_PAYS_RENT, value=False, valid_from=date(2024, 1, 1), valid_to=date(2024, 12, 31)),
    UserProfileFact(path=_PAYS_RENT, value=False, valid_from=date(2025, 1, 1)),
)
"""Both supported stored versions could hold every one of these paths.

``_GROUP_MEMBER`` is stored ``true`` and ``_RESIDENCY`` stores the token that
was the old default, so one cleared path proves a stated yes survives and the
other proves the select clears on its default alone.
"""


def _answer_residency(
    repository: ProfileRecordRepository,
    record: UserProfileRecord,
    *,
    token: str = _RESIDENT_CATEGORY,
) -> UserProfileRecord:
    """Re-answer the residency the migration cleared, as the operator must.

    Modelo 130 names the residencies it applies to, so its verdict stays
    INCOMPLETE until the category is stated again. A test about another fact
    states it first, so the verdict it asserts turns on the fact under test.
    """
    return repository.apply_fact_changes(
        PROFILE_ID,
        facts=(*record.facts, UserProfileFact(path=_RESIDENCY, value=token)),
        expected_revision=record.record_revision,
        expected_content_digest=record.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=_MIGRATED_AT,
    )


def _expected_kept(version: int) -> tuple[UserProfileFact, ...]:
    """Return the facts a record stored at ``version`` keeps, in stored order."""
    cleared = _EXPECTED_CLEARED[version]
    return (*_UNTOUCHED_FACTS, *(fact for fact in _STORED_PAYER_FACTS if fact.path not in cleared))


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


def _publish_legacy(
    root: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
    facts: tuple[UserProfileFact, ...],
    *,
    version: int,
) -> UserProfileRecord:
    create_context, decode_context = contexts
    return publish_legacy_capsule(
        root,
        facts=facts,
        create_context=create_context,
        decode_context=decode_context,
        version=version,
    )


@pytest.fixture(params=SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
def legacy_capsule(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> Iterator[tuple[ProfileRecordSession, UserProfileRecord, Path, int]]:
    version = int(request.param)
    stored = _publish_legacy(tmp_path, contexts, (*_UNTOUCHED_FACTS, *_STORED_PAYER_FACTS), version=version)
    assert stored.schema_version == version
    session = _session(contexts[1])
    drain_migration_cleared_paths()
    try:
        yield session, stored, tmp_path, version
    finally:
        session.close()
        drain_migration_cleared_paths()


def test_both_supported_stored_versions_are_older_than_the_current_schema() -> None:
    """The declared window must name real earlier versions, not the current one."""
    assert SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS == (6, 7)
    assert max(SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS) < MIGRATED_PROFILE_SCHEMA_VERSION


def test_a_stored_legacy_record_is_never_read_as_the_current_schema(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
) -> None:
    session, _stored, root, version = legacy_capsule

    with pytest.raises(ProfileRecordMigrationRequiredError, match=f"schema {version}") as refusal:
        ProfileRecordStore(session=session, root=root).load()

    assert refusal.value.stored_version == version


def test_opening_a_legacy_record_keeps_true_drops_false_payer_facts_and_leaves_the_rest(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
) -> None:
    session, stored, root, version = legacy_capsule
    expected_cleared = _EXPECTED_CLEARED[version]

    migrated = ProfileRecordRepository(session=session, root=root).load(PROFILE_ID)

    assert migrated.schema_version == MIGRATED_PROFILE_SCHEMA_VERSION
    assert migrated.record_revision == stored.record_revision + 1
    assert migrated.previous_record_digest == stored.content_digest
    assert migrated.created_at == stored.created_at
    assert migrated.facts == _expected_kept(version)
    assert drain_migration_cleared_paths() == expected_cleared

    store = ProfileRecordStore(session=session, root=root)
    assert store.schema_migrations() == (
        ProfileSchemaMigration(
            from_version=version,
            to_version=MIGRATED_PROFILE_SCHEMA_VERSION,
            cleared_paths=expected_cleared,
        ),
    )
    migration_events = [
        event for event in store.history() if event.event_type is BucketEventType.PROFILE_SCHEMA_MIGRATED
    ]
    assert len(migration_events) == 1
    assert migration_events[0].payload["schema_migration_from"] == str(version)
    assert migration_events[0].payload["schema_migration_to"] == str(MIGRATED_PROFILE_SCHEMA_VERSION)
    assert migration_events[0].payload["schema_migration_cleared_paths"] == "|".join(expected_cleared)


def test_a_schema_7_answer_to_a_dated_payer_fact_survives(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
) -> None:
    """Schema 7 already read a stored dated-payer ``false`` as an answer, so 7 keeps it and 6 drops it."""
    session, _stored, root, version = legacy_capsule

    migrated = ProfileRecordRepository(session=session, root=root).load(PROFILE_ID)

    stored_347 = [fact for fact in migrated.facts if fact.path == _M347]
    assert stored_347 == ([] if version == 6 else [UserProfileFact(path=_M347, value=False)])


def test_a_second_migration_run_is_a_no_op(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
) -> None:
    session, _stored, root, version = legacy_capsule
    first = migrate_profile_record_on_open(session, root=root)
    after_first = ProfileRecordStore(session=session, root=root).load().record
    drain_migration_cleared_paths()

    second = migrate_profile_record_on_open(session, root=root)

    assert first == ProfileSchemaMigration(
        from_version=version,
        to_version=MIGRATED_PROFILE_SCHEMA_VERSION,
        cleared_paths=_EXPECTED_CLEARED[version],
    )
    assert second is None
    assert ProfileRecordStore(session=session, root=root).load().record == after_first
    assert drain_migration_cleared_paths() == ()
    assert len(ProfileRecordStore(session=session, root=root).schema_migrations()) == 1


@pytest.mark.parametrize("version", SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
def test_the_migration_is_deterministic_across_capsules(
    version: int,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    results: list[tuple[UserProfileFact, ...]] = []
    for name in ("first", "second"):
        root = tmp_path / name
        _publish_legacy(root, contexts, (*_UNTOUCHED_FACTS, *_STORED_PAYER_FACTS), version=version)
        session = _session(contexts[1])
        try:
            migrate_profile_record_on_open(session, root=root)
            results.append(ProfileRecordStore(session=session, root=root).load().record.facts)
        finally:
            session.close()
            drain_migration_cleared_paths()

    assert results[0] == results[1]
    assert results[0] == _expected_kept(version)


def test_a_current_record_is_read_unchanged_and_never_migrated(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    create_context, decode_context = contexts
    facts = (
        *_UNTOUCHED_FACTS,
        UserProfileFact(path=_INTRACOMUNITARIO, value=False),
        UserProfileFact(path=_PAYS_PROFESSIONALS, value=False),
        UserProfileFact(path=_M136, value=False),
    )
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


@pytest.mark.parametrize("path", (_M136, "irpf.plantilla_media.0.year"))
def test_a_schema_6_record_carrying_a_later_schema_path_is_refused(
    path: str,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Schema 6 declared neither field, so a schema-6 row carrying one was forged."""
    value: object = 2024 if path.endswith("year") else True
    stored = _publish_legacy(
        tmp_path, contexts, (*_UNTOUCHED_FACTS, UserProfileFact(path=path, value=value)), version=6
    )
    session = _session(contexts[1])
    try:
        with pytest.raises(UserProfileValidationError, match="later-schema paths"):
            migrate_profile_record_on_open(session, root=tmp_path)
        with pytest.raises(ProfileRecordMigrationRequiredError):
            ProfileRecordStore(session=session, root=tmp_path).load()
        assert stored.schema_version == 6
    finally:
        session.close()


def test_a_schema_7_record_carrying_those_paths_migrates_because_schema_7_declared_them(
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    facts = (
        *_UNTOUCHED_FACTS,
        UserProfileFact(path=_M136, value=True),
        UserProfileFact(path="obligations.premio_loteria_gravamen_especial_trimestres", value="2025-1T"),
    )
    _publish_legacy(tmp_path, contexts, facts, version=7)
    session = _session(contexts[1])
    try:
        migration = migrate_profile_record_on_open(session, root=tmp_path)
        migrated = ProfileRecordStore(session=session, root=tmp_path).load().record
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert migration == ProfileSchemaMigration(from_version=7, to_version=MIGRATED_PROFILE_SCHEMA_VERSION)
    assert migrated.facts == facts


def test_the_cleared_fact_stays_pending_until_answered_and_no_then_excludes_the_modelo(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    session, _stored, root, version = legacy_capsule
    repository = ProfileRecordRepository(session=session, root=root)
    migrated = repository.load(PROFILE_ID)
    schema = contexts[1].schema
    still_pending = tuple(path for path in _EXPECTED_CLEARED[version] if path != _INTRACOMUNITARIO)

    assert repository.pending_cleared_payer_fact_paths(PROFILE_ID) == _EXPECTED_CLEARED[version]
    with bundled_indexed_authority().operation():
        undeclared = derive_modelo_applicability(
            projection_for_taxpayer(migrated, schema=schema), "349", reference_date=latest_period_end()
        )
    assert undeclared.verdict is ApplicabilityVerdict.INCOMPLETE

    answered = repository.apply_fact_changes(
        PROFILE_ID,
        facts=(*migrated.facts, UserProfileFact(path=_INTRACOMUNITARIO, value=False)),
        expected_revision=migrated.record_revision,
        expected_content_digest=migrated.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=_MIGRATED_AT,
    )

    assert repository.pending_cleared_payer_fact_paths(PROFILE_ID) == still_pending
    with bundled_indexed_authority().operation():
        declared_no = derive_modelo_applicability(
            projection_for_taxpayer(answered, schema=schema), "349", reference_date=latest_period_end()
        )
    assert declared_no.verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_the_cleared_art109_coverage_fact_reopens_modelo_130_until_it_is_answered(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Both stored versions defaulted the Art. 109 question, so neither stored ``false`` is an answer."""
    session, _stored, root, version = legacy_capsule
    repository = ProfileRecordRepository(session=session, root=root)
    migrated = repository.load(PROFILE_ID)
    schema = contexts[1].schema

    assert _ART109 in _EXPECTED_CLEARED[version]
    assert not [fact for fact in migrated.facts if fact.path == _ART109]
    assert _ART109 in repository.pending_cleared_payer_fact_paths(PROFILE_ID)
    resident = _answer_residency(repository, migrated)
    with bundled_indexed_authority().operation():
        undeclared = derive_modelo_applicability(
            projection_for_taxpayer(resident, schema=schema), "130", reference_date=latest_period_end()
        )
    assert undeclared.verdict is ApplicabilityVerdict.INCOMPLETE

    answered = repository.apply_fact_changes(
        PROFILE_ID,
        facts=(*resident.facts, UserProfileFact(path=_ART109, value=False)),
        expected_revision=resident.record_revision,
        expected_content_digest=resident.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=_MIGRATED_AT,
    )

    assert _ART109 not in repository.pending_cleared_payer_fact_paths(PROFILE_ID)
    with bundled_indexed_authority().operation():
        declared_no = derive_modelo_applicability(
            projection_for_taxpayer(answered, schema=schema), "130", reference_date=latest_period_end()
        )
    assert declared_no.verdict is ApplicabilityVerdict.APPLICABLE


@pytest.mark.parametrize("version", SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
def test_a_stored_art109_yes_survives_every_transition(
    version: int,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Only the negative is unprovable; a stored yes is the taxpayer's own Art. 109 exception."""
    _publish_legacy(tmp_path, contexts, (*_UNTOUCHED_FACTS, UserProfileFact(path=_ART109, value=True)), version=version)
    session = _session(contexts[1])
    try:
        repository = ProfileRecordRepository(session=session, root=tmp_path)
        migrated = repository.load(PROFILE_ID)
        resident = _answer_residency(repository, migrated)
        with bundled_indexed_authority().operation():
            verdict = derive_modelo_applicability(
                projection_for_taxpayer(resident, schema=contexts[1].schema),
                "130",
                reference_date=latest_period_end(),
            )
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert [fact for fact in migrated.facts if fact.path == _ART109] == [
        UserProfileFact(path=_ART109, value=True),
    ]
    assert verdict.verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_the_cleared_capital_income_fact_reopens_its_eight_modelos_until_it_is_answered(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Both stored versions defaulted the capital-income question, so neither stored ``false`` is an answer."""
    session, _stored, root, version = legacy_capsule
    repository = ProfileRecordRepository(session=session, root=root)
    migrated = repository.load(PROFILE_ID)
    schema = contexts[1].schema

    assert _PAYS_CAPITAL in _EXPECTED_CLEARED[version]
    assert not [fact for fact in migrated.facts if fact.path == _PAYS_CAPITAL]
    assert _PAYS_CAPITAL in repository.pending_cleared_payer_fact_paths(PROFILE_ID)
    with bundled_indexed_authority().operation():
        undeclared = tuple(
            derive_modelo_applicability(
                projection_for_taxpayer(migrated, schema=schema), modelo, reference_date=latest_period_end()
            ).verdict
            for modelo in _CAPITAL_GATED_MODELOS
        )
    assert undeclared == (ApplicabilityVerdict.INCOMPLETE,) * len(_CAPITAL_GATED_MODELOS)

    answered = repository.apply_fact_changes(
        PROFILE_ID,
        facts=(*migrated.facts, UserProfileFact(path=_PAYS_CAPITAL, value=False)),
        expected_revision=migrated.record_revision,
        expected_content_digest=migrated.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=_MIGRATED_AT,
    )

    assert _PAYS_CAPITAL not in repository.pending_cleared_payer_fact_paths(PROFILE_ID)
    with bundled_indexed_authority().operation():
        declared_no = tuple(
            derive_modelo_applicability(
                projection_for_taxpayer(answered, schema=schema), modelo, reference_date=latest_period_end()
            ).verdict
            for modelo in _CAPITAL_GATED_MODELOS
        )
    assert declared_no == (ApplicabilityVerdict.NOT_APPLICABLE,) * len(_CAPITAL_GATED_MODELOS)


@pytest.mark.parametrize("version", SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
def test_a_stored_capital_income_yes_survives_every_transition(
    version: int,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Only the negative is unprovable; a stored yes is the taxpayer's own statement that he pays."""
    _publish_legacy(
        tmp_path,
        contexts,
        (*_UNTOUCHED_FACTS, UserProfileFact(path=_PAYS_CAPITAL, value=True)),
        version=version,
    )
    session = _session(contexts[1])
    try:
        migrated = ProfileRecordRepository(session=session, root=tmp_path).load(PROFILE_ID)
        with bundled_indexed_authority().operation():
            verdicts = tuple(
                derive_modelo_applicability(
                    projection_for_taxpayer(migrated, schema=contexts[1].schema),
                    modelo,
                    reference_date=latest_period_end(),
                ).verdict
                for modelo in _CAPITAL_GATED_MODELOS
            )
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert [fact for fact in migrated.facts if fact.path == _PAYS_CAPITAL] == [
        UserProfileFact(path=_PAYS_CAPITAL, value=True),
    ]
    assert verdicts == (ApplicabilityVerdict.APPLICABLE,) * len(_CAPITAL_GATED_MODELOS)


def test_the_cleared_residency_reopens_the_residency_gated_modelos_until_it_is_answered(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """The one select here: a stored ``resident_irpf`` is exactly what the wizard wrote unasked."""
    session, _stored, root, version = legacy_capsule
    repository = ProfileRecordRepository(session=session, root=root)
    migrated = repository.load(PROFILE_ID)
    schema = contexts[1].schema

    assert _RESIDENCY in _EXPECTED_CLEARED[version]
    assert not [fact for fact in migrated.facts if fact.path == _RESIDENCY]
    assert _RESIDENCY in repository.pending_cleared_payer_fact_paths(PROFILE_ID)
    with bundled_indexed_authority().operation():
        undeclared = tuple(
            derive_modelo_applicability(
                projection_for_taxpayer(migrated, schema=schema), modelo, reference_date=latest_period_end()
            ).verdict
            for modelo in _RESIDENCY_DECIDED_MODELOS
        )
    assert undeclared == (ApplicabilityVerdict.INCOMPLETE,) * len(_RESIDENCY_DECIDED_MODELOS)

    answered = repository.apply_fact_changes(
        PROFILE_ID,
        facts=(*migrated.facts, UserProfileFact(path=_RESIDENCY, value=_RESIDENT_CATEGORY)),
        expected_revision=migrated.record_revision,
        expected_content_digest=migrated.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=_MIGRATED_AT,
    )

    assert _RESIDENCY not in repository.pending_cleared_payer_fact_paths(PROFILE_ID)
    with bundled_indexed_authority().operation():
        declared = {
            modelo: derive_modelo_applicability(
                projection_for_taxpayer(answered, schema=schema), modelo, reference_date=latest_period_end()
            ).verdict
            for modelo in _RESIDENCY_DECIDED_MODELOS
        }
    assert declared["100"] is ApplicabilityVerdict.APPLICABLE
    assert declared["210"] is ApplicabilityVerdict.NOT_APPLICABLE


@pytest.mark.parametrize("version", SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
def test_a_stored_non_resident_residency_survives_every_transition(
    version: int,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """Only the old default token is unprovable; the other category was never written unasked."""
    _publish_legacy(
        tmp_path,
        contexts,
        (
            *_UNTOUCHED_FACTS,
            UserProfileFact(path=_RESIDENCY, value=_NON_RESIDENT_CATEGORY),
            UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="FR"),
        ),
        version=version,
    )
    session = _session(contexts[1])
    try:
        migrated = ProfileRecordRepository(session=session, root=tmp_path).load(PROFILE_ID)
        with bundled_indexed_authority().operation():
            verdicts = {
                modelo: derive_modelo_applicability(
                    projection_for_taxpayer(migrated, schema=contexts[1].schema),
                    modelo,
                    reference_date=latest_period_end(),
                ).verdict
                for modelo in _RESIDENCY_DECIDED_MODELOS
            }
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert [fact for fact in migrated.facts if fact.path == _RESIDENCY] == [
        UserProfileFact(path=_RESIDENCY, value=_NON_RESIDENT_CATEGORY),
    ]
    assert verdicts["210"] is ApplicabilityVerdict.APPLICABLE
    assert verdicts["100"] is ApplicabilityVerdict.NOT_APPLICABLE


@pytest.mark.parametrize("version", SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
def test_a_stored_iva_enrolment_yes_survives_every_transition(
    version: int,
    tmp_path: Path,
    contexts: tuple[ProfileCreateContext, ProfileDecodeContext],
) -> None:
    """A stated enrolment is the taxpayer's own opt-in and is never dropped."""
    _publish_legacy(
        tmp_path,
        contexts,
        (*_UNTOUCHED_FACTS, UserProfileFact(path=_OSS, value=True)),
        version=version,
    )
    session = _session(contexts[1])
    try:
        migrated = ProfileRecordRepository(session=session, root=tmp_path).load(PROFILE_ID)
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert [fact for fact in migrated.facts if fact.path == _OSS] == [UserProfileFact(path=_OSS, value=True)]


def test_a_restored_legacy_capsule_is_accepted_and_migrates_on_first_open(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
) -> None:
    """A bundle or archive restore stages its database through this one door, at either version.

    ``ProfileCapsuleLifecycle._stage_and_validate_restore_database`` calls
    ``validate_staged_profile_record_database``, which is this method, so an
    imported portable profile is accepted as stored and then carried forward by
    the same open-time migration as a profile that never left the machine.
    """
    session, stored, root, version = legacy_capsule
    store = ProfileRecordStore(session=session, root=root)
    database = root / "restore-stage" / storage_location(StorageCategory.BUCKET_DATABASE_FILE).relative_path()
    database.parent.mkdir(parents=True)
    source = next(root.rglob("cadrumo.db"))
    database.write_bytes(source.read_bytes())

    staged = store.validate_staged_database(stage_path=root / "restore-stage")

    assert staged.record == stored
    assert staged.record.schema_version == version
    opened = ProfileRecordRepository(session=session, root=root).load(PROFILE_ID)
    assert opened.schema_version == MIGRATED_PROFILE_SCHEMA_VERSION
    assert opened.facts == _expected_kept(version)


def test_the_migration_rewrites_the_record_row_and_appends_one_event_and_nothing_else(
    legacy_capsule: tuple[ProfileRecordSession, UserProfileRecord, Path, int],
) -> None:
    """A filed revision, snapshot or any other stored object must not be rewritten.

    The migration's whole write is the one current record row plus one history
    event, so every other event already in the bucket survives unchanged and in
    order, and a second open adds nothing.
    """
    session, _stored, root, _version = legacy_capsule
    store = ProfileRecordStore(session=session, root=root)
    before = store.history()

    ProfileRecordRepository(session=session, root=root).load(PROFILE_ID)
    after = store.history()

    assert after[: len(before)] == before
    appended = after[len(before) :]
    assert [event.event_type for event in appended] == [BucketEventType.PROFILE_SCHEMA_MIGRATED]
    assert migrate_profile_record_on_open(session, root=root) is None
    assert store.history() == after


def test_an_average_workforce_instance_round_trips_with_its_typed_meaning(
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
