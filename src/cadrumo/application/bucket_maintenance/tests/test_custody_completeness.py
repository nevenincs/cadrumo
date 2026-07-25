"""Full-custody completeness for the sealed bucket recovery archive.

These tests drive the real recovery transport end to end: seed the
previously-dropped per-bucket stores, export a sealed archive under a recovery
passphrase, import it into a *fresh storage root* (a distinct recipient DEK),
and assert the evidence bytes and audit trail survive. They are the
persistence-boundary proof for ``aeat-roundtrip-discipline`` applied to the
generic custody carry, plus an anti-tautology proof and a fail-closed
coverage-gate check.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....core.resources import resources
from ....domain.attachments import AttachmentValidationError
from ....domain.buckets import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....domain.user_profile import ProfileExportError, ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_profile_storage_root, isolated_runtime_profile
from ...modelo import (
    M145CommunicationCreateCommand,
    create_m145_communication_record,
    read_m145_communication_record,
)
from ...user_profile import RegisterProfileCommand, profile_storage_session
from ...workflow import read_profile_bucket_by_id
from .._contracts import ExportBucketCommand, ImportBucketCommand
from .._service import BucketMaintenanceService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5a5a5a5a-5a5a-45a5-85a5-5a5a5a5a5a5a"
_LABEL = "Custody complete"
_RECOVERY = "correct horse battery staple custody"
_EVIDENCE = b"%PDF-1.7 sealed-archive evidence \x00\xff bytes"
_INSTANT = datetime(2026, 6, 30, 8, 0, 0, tzinfo=UTC)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_LABEL) as profile:
        yield profile


def _required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: dict[str, UserProfileFact] = {}
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                path = f"{section.key}.{field.key}"
                facts[path] = UserProfileFact(path=path, value="placeholder")
    facts.update(
        {
            "taxpayer_type.entity_type": UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            "identity.name": UserProfileFact(path="identity.name", value="Custody"),
            "identity.surnames": UserProfileFact(path="identity.surnames", value="Complete"),
            "identity.tax_id": UserProfileFact(path="identity.tax_id", value="12345678Z"),
        },
    )
    return tuple(facts.values())


@pytest.fixture
def seeded_bucket(runtime: TestRuntimeProfile) -> str:
    """Register a profile and seed the previously-dropped stores."""
    from ...user_profile import ProfileLifecycleService, ProfileValidationService, UserProfileLifecycleRepository

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
            facts=_required_facts(schema),
        ),
    )

    AttachmentStore().put_bytes(_EVIDENCE)
    event_id = derive_bucket_event_id(
        bucket_id=runtime.bucket_id,
        event_type=BucketEventType.PROFILE_RENAMED,
        occurred_at=_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=runtime.bucket_id,
        payload={"display_name": "Audited"},
    )
    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    repo.save(
        BucketEventHistoryCatalogue(
            events={
                **catalogue.events,
                event_id: BucketEvent(
                    event_id=event_id,
                    bucket_id=runtime.bucket_id,
                    event_type=BucketEventType.PROFILE_RENAMED,
                    occurred_at=_INSTANT,
                    actor="operator",
                    object_type=BucketEventObjectType.PROFILE,
                    object_id=runtime.bucket_id,
                    payload_version=1,
                    payload={"display_name": "Audited"},
                ),
            },
        ),
    )
    return event_id


def test_sealed_archive_restores_evidence_and_audit_trail_in_fresh_root(
    runtime: TestRuntimeProfile,
    seeded_bucket: str,
    tmp_path: Path,
) -> None:
    seeded_event_id = seeded_bucket
    sha = AttachmentStore().put_bytes(_EVIDENCE)  # idempotent: returns the digest
    communication = create_m145_communication_record(
        M145CommunicationCreateCommand(
            communication_year=2026,
            field_values={
                "perceptor.nif": "12345678Z",
                "perceptor.primer-apellido": "Garcia",
                "perceptor.segundo-apellido": "Lopez",
                "perceptor.nombre": "Ana",
                "perceptor.anio-nacimiento": "1981",
            },
        ),
        bucket_id=runtime.bucket_id,
    )
    archive = tmp_path / "exports" / "bucket.cadrumo-bucket.tar.gz"

    BucketMaintenanceService().export(
        ExportBucketCommand(bucket_id=runtime.bucket_id, output_path=archive, recovery_wrap_passphrase=_RECOVERY),
    )

    with isolated_profile_storage_root(tmp_path=tmp_path / "recipient"):
        imported = BucketMaintenanceService().import_(
            ImportBucketCommand(source_path=archive, recovery_wrap_passphrase=_RECOVERY),
        )
        assert imported.bucket_id == runtime.bucket_id
        assert read_profile_bucket_by_id(runtime.bucket_id) is not None

        with profile_storage_session(runtime.bucket_id):
            # Evidence bytes resolve under the recipient bucket DEK.
            assert AttachmentStore().read_bytes(sha) == _EVIDENCE
            # The seeded audit event survives with its content-addressed id.
            restored = BucketEventHistoryRepository().load()
            assert seeded_event_id in restored.events
            assert BucketEventType.BUCKET_IMPORTED in {e.event_type for e in restored.events.values()}
            restored_communication = read_m145_communication_record(
                communication.communication_record_id,
                bucket_id=runtime.bucket_id,
            )
            assert restored_communication == communication


def test_carried_evidence_carry_is_not_tautological(tmp_path: Path) -> None:
    """Tampering a carried evidence payload must not silently restore clean bytes."""
    import base64

    from ....adapters.persistence.storage import StorageCustodyProfile
    from ....tests.secure_sql import isolated_two_bucket_runtime
    from ...user_profile import (
        restore_carried_objects,
        serialize_carried_objects,
    )

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as multi:
        sha = AttachmentStore().put_bytes(_EVIDENCE)
        carried = serialize_carried_objects(
            bucket_id=multi.primary.bucket_id,
            profile=StorageCustodyProfile.FULL,
        )
        blob = next(o for o in carried if o.namespace == "cadrumo.domain.attachments.blobs")
        tampered = blob.model_copy(
            update={"payload_b64": base64.b64encode(b"tampered-not-the-evidence").decode("ascii")},
        )
        others = tuple(o for o in carried if o is not blob)

        with multi.switch_to_secondary():
            restore_carried_objects((tampered, *others), target_bucket_id=multi.secondary.bucket_id)
            # The original sha now indexes tampered bytes, so the restored blob
            # no longer validates as a framed attachment payload.
            store = AttachmentStore()
            with pytest.raises(AttachmentValidationError, match="envelope prefix"):
                store.verify_blob(sha)


def test_full_custody_coverage_gate_refuses_unclassified_namespace() -> None:
    """A populated namespace with no registry classification fails the full-custody export."""
    from ...user_profile._bundle import _assert_full_custody_coverage

    with pytest.raises(ProfileExportError) as excinfo:
        _assert_full_custody_coverage(
            populated_namespaces=("cadrumo.domain.buckets.event_history", "aeat.surprise.new_store"),
            covered_namespaces=frozenset({"cadrumo.domain.buckets.event_history"}),
        )
    assert excinfo.value.context is not None
    assert "aeat.surprise.new_store" in str(excinfo.value.context["unclassified_namespaces"])


def test_full_export_tolerates_populated_process_local_namespace(tmp_path: Path) -> None:
    """A populated deliberately-excluded (PROCESS_LOCAL/DERIVED) store must not fail the FULL export.

    Regression: a real bucket populates the DERIVED participation index after any
    calculation and PROCESS_LOCAL workflow/credential stores in normal use. These
    are registry-classified as not-carried, so the coverage gate must treat them as
    accounted for rather than as an uncovered store.
    """
    from datetime import UTC, datetime

    from ....adapters.persistence.storage import StorageCustodyProfile
    from ....core.classification import SensitivityClass
    from ....tests.secure_sql import isolated_runtime_profile
    from ...user_profile._bundle import _build_secure_object_custody_payload

    envelope = b'{"schema_version":1,"written_at":"2026-06-30T00:00:00Z","classification":"financial","payload":{}}'
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="9b9b9b9b-9b9b-49b9-89b9-9b9b9b9b9b9b",
        label="Process-local source",
    ) as profile:
        profile.repository.save(
            namespace="cadrumo.workflow",  # PROCESS_LOCAL workflow state
            object_key="state",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=envelope,
        )
        # The FULL profile must build without raising even though a deliberately
        # excluded namespace is populated.
        carried, manifest = _build_secure_object_custody_payload(
            bucket_id=profile.bucket_id,
            custody_profile=StorageCustodyProfile.FULL,
        )
        # The excluded store is reported in the manifest, never carried.
        assert "cadrumo.workflow" in manifest.excluded_namespaces
        assert all(obj.namespace != "cadrumo.workflow" for obj in carried)


def test_every_carried_namespace_has_a_natural_key_resolver() -> None:
    """A new carried-disposition namespace must declare how its natural key resolves.

    The serialise path is fail-closed: a populated carried namespace with neither a
    registered resolver nor a fixed default object key raises. This gate makes that
    a build-time failure instead of an export-time surprise.
    """
    from ....adapters.persistence.storage import StorageCustodyProfile
    from ...user_profile import carried_namespace_definitions
    from ...user_profile._custody_carry import _natural_key_resolvers

    resolvers = set(_natural_key_resolvers())
    unresolved = [
        definition.namespace
        for definition in carried_namespace_definitions(StorageCustodyProfile.FULL)
        if definition.namespace not in resolvers and definition.default_object_key is None
    ]
    assert unresolved == [], f"carried namespaces without a natural-key resolver: {unresolved}"


def test_typed_category_namespaces_are_load_bearing_exclusions_from_the_generic_carry() -> None:
    """The typed-category subtraction must actually remove carried namespaces.

    The five typed categories ride dedicated bundle fields, so the generic carry
    subtracts them to avoid double-carrying. That subtraction is only meaningful
    if each member would otherwise be carried: were one to name a namespace that
    is absent from the registry, or one whose custody disposition keeps it out of
    the full profile anyway, the subtraction would be a silent no-op and a drifted
    member would double-carry undetected. This gate pins both halves — every
    member is a real full-profile carry candidate, and every member is in fact
    absent from the generic carry.
    """
    from ....adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY, StorageCustodyProfile
    from ...user_profile import carried_namespace_definitions
    from ...user_profile._custody_carry import TYPED_CATEGORY_NAMESPACES

    assert len(TYPED_CATEGORY_NAMESPACES) == 5

    # Non-vacuity: each member is a registered namespace the FULL profile would
    # otherwise carry, so subtracting it changes the carry set.
    full_profile_candidates = {
        definition.namespace
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces_for_custody_profile(StorageCustodyProfile.FULL)
    }
    not_candidates = sorted(TYPED_CATEGORY_NAMESPACES - full_profile_candidates)
    assert not_candidates == [], (
        "typed-category namespaces that the FULL profile would not carry anyway, "
        f"making their exclusion a no-op: {not_candidates}"
    )

    # Effect: none of them survives into the generic carry.
    carried = {definition.namespace for definition in carried_namespace_definitions(StorageCustodyProfile.FULL)}
    double_carried = sorted(TYPED_CATEGORY_NAMESPACES & carried)
    assert double_carried == [], f"typed-category namespaces also carried generically: {double_carried}"
