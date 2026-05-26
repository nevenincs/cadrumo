"""Cross-store roundtrip and unit-of-work tests for :class:`ProfileRepository`.

The repository is the single, sole writer of a logical profile's
physical stores. These tests exercise it against real adapters — a real
:class:`EphemeralMasterKeyProvider`, a real per-bucket SQLite engine,
and the real filesystem — never a mock.

Three contracts are pinned:

- **Roundtrip**: a fully-populated :class:`ProfileAggregate` survives a
  ``create`` / ``load`` cycle with strict pydantic equality.
- **Anti-tautology**: corrupting one on-disk store and reloading
  surfaces the cross-store drift via :class:`ProfileIntegrityError` —
  never a silent inconsistent aggregate.
- **Unit-of-work**: a real induced failure partway through ``create``
  leaves no half-live profile — no manifest, no usable record, no
  stranded active-profile pointer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.bucket._layout import bucket_paths
from ...adapters.persistence.storage.bucket._manifest_io import manifest_path
from ...adapters.persistence.storage.master_key._kdf_params import KdfParams
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...core._bucket_pointer import BucketPointer
from ...core._bucket_pointer_io import read_pointer, write_pointer
from ...core.config import override_settings
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaValidationError,
    UserProfileFact,
    UserProfileStatus,
)
from ..workflow._profile_bucket_scan import (
    list_profile_buckets,
    read_profile_bucket,
    read_profile_bucket_by_id,
)
from ._integrity import ProfileIntegrityError
from ._orchestration import ProfileAlreadyRegisteredError
from ._profile_repository import ProfileRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# The minimum schema-valid fact set the user-profile schema accepts.
_VALID_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Roundtrip Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="provenance.source", value="manual_cli"),
)
# A second valid fact set carrying a DISTINCT tax id. ``create``
# refuses two profiles that share a tax id, so a test registering a
# second profile alongside one built from ``_VALID_FACTS`` must use a
# different taxpayer identity.
_SECOND_FACTS: tuple[UserProfileFact, ...] = tuple(
    UserProfileFact(path="identity.tax_id", value="00000001R")
    if fact.path == "identity.tax_id"
    else fact
    for fact in _VALID_FACTS
)
# An incomplete fact set: the required ``iva.regime`` field is dropped,
# so the schema validator rejects the record inside the lifecycle
# service's ``register`` — a real failure, not a patched one. Built
# from ``_SECOND_FACTS`` so its tax id is distinct from a profile
# registered with ``_VALID_FACTS``; the rejection under test is the
# schema failure, not the duplicate-tax-id refusal.
_INCOMPLETE_FACTS: tuple[UserProfileFact, ...] = tuple(
    fact for fact in _SECOND_FACTS if fact.path != "iva.regime"
)


@pytest.fixture
def _backend(tmp_path: Path) -> Iterator[Path]:
    """A real per-bucket storage root with an active master-key session."""

    dispose_engine()
    provider = EphemeralMasterKeyProvider()
    provider.__enter__()
    try:
        with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None):
            yield tmp_path
    finally:
        provider.__exit__(None, None, None)
        dispose_engine()


def test_create_load_roundtrip_preserves_the_aggregate(_backend: Path) -> None:
    """A populated aggregate survives create / load with strict equality.

    Every defaultable field on the aggregate is set to a non-default
    value through ``create``: a multi-fact record (not the empty
    default), a non-default lifecycle path. A save-drops-field /
    load-re-defaults-field regression would surface as inequality.
    """

    repository = ProfileRepository()
    created = repository.create(label="Roundtrip Operator", facts=_VALID_FACTS)

    loaded = repository.load(created.profile_id)

    assert loaded == created
    assert loaded.label == "Roundtrip Operator"
    assert loaded.status is UserProfileStatus.ACTIVE
    assert loaded.record.facts == _VALID_FACTS
    assert loaded.recovery_enrolled is False
    canonical = KdfParams.default()
    assert loaded.kdf_params.model_dump(exclude={"salt"}) == canonical.to_manifest_params().model_dump(
        exclude={"salt"}
    )
    assert KdfParams.model_validate(loaded.kdf_params.model_dump())


def test_create_refuses_a_duplicate_tax_id(_backend: Path) -> None:
    """A second profile carrying an existing tax id is refused.

    Two profiles sharing a NIF / NIE / CIF silently split one
    taxpayer's filing history. ``create`` scans the registered
    profiles and refuses the duplicate before any store write.
    """

    repository = ProfileRepository()
    first = repository.create(label="Original", facts=_VALID_FACTS)

    # `_VALID_FACTS` carries tax id 00000000T; a second create with the
    # same id under a different label must be refused.
    duplicate_facts = tuple(
        UserProfileFact(path="identity.tax_id", value="00000000T")
        if fact.path == "identity.tax_id"
        else fact
        for fact in _SECOND_FACTS
    )
    with pytest.raises(ProfileAlreadyRegisteredError, match=r"00000000T|Original"):
        repository.create(label="Duplicate", facts=duplicate_facts)

    # The refusal fired before any store write: no half-live profile.
    assert read_profile_bucket("Duplicate", root=_backend) is None
    # The original is untouched and still loads.
    assert repository.load(first.profile_id).label == "Original"


def test_create_allows_distinct_tax_ids(_backend: Path) -> None:
    """Two profiles with distinct tax ids both register cleanly."""

    repository = ProfileRepository()
    first = repository.create(label="First", facts=_VALID_FACTS)
    second = repository.create(label="Second", facts=_SECOND_FACTS)

    assert first.profile_id != second.profile_id
    assert repository.load(first.profile_id).label == "First"
    assert repository.load(second.profile_id).label == "Second"


def test_load_surfaces_manifest_uuid_drift(_backend: Path) -> None:
    """Corrupting the manifest ``bucket_id`` makes load raise, not lie.

    The companion roundtrip asserts a clean create / load cycle. This
    test mutates one on-disk store — the plaintext manifest's
    ``bucket_id`` — so the three identity claims (directory name,
    manifest, secure record) no longer agree. ``load`` must raise
    :class:`ProfileIntegrityError`; if it returned an aggregate the
    drift would be served silently and every load is tautological.
    """

    repository = ProfileRepository()
    created = repository.create(label="Drift Operator", facts=_VALID_FACTS)

    # Corrupt the manifest in place: rewrite bucket_id to a foreign UUID.
    target = manifest_path(bucket_paths(_backend, created.profile_id))
    corrupted = target.read_text(encoding="utf-8").replace(
        f'bucket_id = "{created.profile_id}"',
        'bucket_id = "00000000-0000-4000-8000-000000000000"',
    )
    assert "00000000-0000-4000-8000-000000000000" in corrupted, "manifest mutation did not apply"
    target.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ProfileIntegrityError):
        repository.load(created.profile_id)


def test_failed_create_leaves_no_half_live_profile(_backend: Path) -> None:
    """A real failure inside create leaves no reclaimable-garbage profile.

    The incomplete fact set makes the schema validator reject the
    encrypted-record write inside the lifecycle service — a genuine
    failure, induced by withholding a schema-required field, not a
    mock. After the failure the unit-of-work rollback must leave: no
    manifest (so the manifest scan reports nothing), no usable profile
    record, and the active-profile pointer exactly as it was found.
    """

    # A pre-existing profile so "pointer restored to its prior state"
    # is a non-trivial assertion: the pointer must end at the survivor.
    repository = ProfileRepository()
    survivor = repository.create(label="Survivor", facts=_VALID_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=survivor.profile_id, schema_version=1))
    prior_pointer = read_pointer(_backend)
    assert prior_pointer is not None

    with pytest.raises(ProfileSchemaValidationError):
        repository.create(label="Victim", facts=_INCOMPLETE_FACTS)

    # No half-live profile: no manifest scan hit, no pointer drift.
    assert read_profile_bucket("Victim", root=_backend) is None
    pointer_after = read_pointer(_backend)
    assert pointer_after is not None
    assert pointer_after.bucket_id == survivor.profile_id, (
        "the failed create stranded the active-profile pointer"
    )
    # The survivor is untouched and still loads cleanly.
    reloaded = repository.load(survivor.profile_id)
    assert reloaded.label == "Survivor"


def test_delete_tombstones_and_clears_the_pointer(_backend: Path) -> None:
    """``delete`` tombstones the record and clears the active pointer."""

    repository = ProfileRepository()
    created = repository.create(label="To Delete", facts=_VALID_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=created.profile_id, schema_version=1))

    deleted = repository.delete(created.profile_id)

    assert deleted.status is UserProfileStatus.TOMBSTONED
    assert deleted.record.status is UserProfileStatus.TOMBSTONED
    assert read_pointer(_backend) is None
    # The bucket directory + manifest survive — tombstone, not destroy.
    assert manifest_path(bucket_paths(_backend, created.profile_id)).is_file()


def test_failed_delete_leaves_no_torn_state(_backend: Path) -> None:
    """A real failure inside delete leaves both stores in their pre-delete state.

    ``delete`` integrity-checks the profile via ``load`` before touching
    any store. Corrupting the on-disk manifest UUID makes that ``load``
    raise :class:`ProfileIntegrityError` — a genuine induced failure, no
    mock. The contract: a failed delete is all-or-nothing. Neither store
    is mutated — the record stays live (not tombstoned) and the
    active-profile pointer still aims at the profile — so there is no
    torn "pointer cleared but record live" or "record tombstoned but
    pointer stranded" intermediate.
    """

    repository = ProfileRepository()
    created = repository.create(label="Torn Delete", facts=_VALID_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=created.profile_id, schema_version=1))

    # Corrupt the manifest UUID so delete's internal load fails.
    target = manifest_path(bucket_paths(_backend, created.profile_id))
    corrupted = target.read_text(encoding="utf-8").replace(
        f'bucket_id = "{created.profile_id}"',
        'bucket_id = "00000000-0000-4000-8000-000000000000"',
    )
    assert "00000000-0000-4000-8000-000000000000" in corrupted, "manifest mutation did not apply"
    target.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ProfileIntegrityError):
        repository.delete(created.profile_id)

    # No torn state: the pointer is untouched and the record is still
    # live. Restore the manifest so the record can be re-loaded.
    pointer_after = read_pointer(_backend)
    assert pointer_after is not None
    assert pointer_after.bucket_id == created.profile_id
    target.write_text(corrupted.replace(
        '00000000-0000-4000-8000-000000000000', created.profile_id
    ), encoding="utf-8")
    reloaded = repository.load(created.profile_id)
    assert reloaded.status is UserProfileStatus.ACTIVE


def test_delete_clears_pointer_before_tombstoning(_backend: Path) -> None:
    """``delete`` clears the pointer before it tombstones the record.

    The ordering matters: clearing the pointer first means a failure
    between the two steps leaves a live record with no active pointer —
    benign. This test pins the successful ordering's observable result:
    after a clean delete the pointer is gone and the record is
    tombstoned, and a profile that was NOT the active one keeps its
    own (untouched) state.
    """

    repository = ProfileRepository()
    active = repository.create(label="Active One", facts=_VALID_FACTS)
    other = repository.create(label="Other One", facts=_SECOND_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=active.profile_id, schema_version=1))

    repository.delete(active.profile_id)

    assert read_pointer(_backend) is None
    # Deleting a non-active profile must not clear another profile's pointer.
    write_pointer(_backend, BucketPointer(bucket_id=other.profile_id, schema_version=1))
    repository.delete(active.profile_id)  # idempotent re-delete of the same id
    pointer = read_pointer(_backend)
    assert pointer is not None
    assert pointer.bucket_id == other.profile_id


def test_list_summarises_every_registered_profile(_backend: Path) -> None:
    """``list`` returns one typed summary per registered profile."""

    repository = ProfileRepository()
    first = repository.create(label="First", facts=_VALID_FACTS)
    second = repository.create(label="Second", facts=_SECOND_FACTS)

    summaries = repository.list()
    by_id = {summary.profile_id: summary for summary in summaries}

    assert set(by_id) == {first.profile_id, second.profile_id}
    assert by_id[first.profile_id].label == "First"
    assert by_id[second.profile_id].label == "Second"
    assert all(summary.status is UserProfileStatus.ACTIVE for summary in summaries)


def test_delete_mirrors_the_tombstone_onto_the_manifest(_backend: Path) -> None:
    """``delete`` flips the plaintext manifest ``status`` to tombstoned.

    The manifest is the plaintext mirror the live-surface scan reads;
    after a soft delete it must carry ``TOMBSTONED`` so the scan can
    exclude the profile without unlocking the encrypted bucket.
    """

    from ...adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus
    from ...adapters.persistence.storage.bucket._manifest_io import read_manifest

    repository = ProfileRepository()
    created = repository.create(label="Soft Delete", facts=_VALID_FACTS)

    repository.delete(created.profile_id)

    manifest = read_manifest(bucket_paths(_backend, created.profile_id))
    assert manifest.status is BucketLifecycleStatus.TOMBSTONED


def test_tombstoned_profile_is_excluded_from_the_live_scan(_backend: Path) -> None:
    """A tombstoned profile leaves ``list_profile_buckets`` / ``read_profile_bucket``.

    Closes the ``profile list`` and ``profile switch`` leak: after a
    delete the manifest scan no longer surfaces the profile, so neither
    the listing nor the label-resolver can serve it. The by-id
    resolver still finds it — ``show`` and diagnostics inspect a
    tombstoned profile by UUID.
    """

    from ...adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus

    repository = ProfileRepository()
    created = repository.create(label="Vanishing", facts=_VALID_FACTS)
    assert read_profile_bucket("Vanishing", root=_backend) is not None

    repository.delete(created.profile_id)

    # Live scan: gone.
    assert read_profile_bucket("Vanishing", root=_backend) is None
    assert created.profile_id not in list_profile_buckets(root=_backend)
    # Full inventory: still present, marked tombstoned.
    full = list_profile_buckets(root=_backend, include_tombstoned=True)
    assert created.profile_id in full
    assert full[created.profile_id].status is BucketLifecycleStatus.TOMBSTONED
    # By-id resolver: still resolves, carries the tombstoned status.
    by_id = read_profile_bucket_by_id(created.profile_id, root=_backend)
    assert by_id is not None
    assert by_id.status is BucketLifecycleStatus.TOMBSTONED


def test_select_refuses_a_tombstoned_profile(_backend: Path) -> None:
    """``select`` refuses a tombstoned profile with ``ProfileNotFoundError``.

    Closes the ``profile switch`` leak at the repository layer: a
    deleted profile can never become the active one, refused with the
    same error class as an unknown profile.
    """

    repository = ProfileRepository()
    created = repository.create(label="Not Selectable", facts=_VALID_FACTS)
    repository.delete(created.profile_id)

    with pytest.raises(ProfileNotFoundError, match="tombstoned"):
        repository.select(created.profile_id)


def test_deleted_profile_name_is_reusable(_backend: Path) -> None:
    """After ``delete`` the freed display name is reusable by ``create``.

    Per the profile-UUID-identity ADR, display names are unique among
    *live* profiles only; a tombstoned profile's name is free to reuse.
    """

    repository = ProfileRepository()
    first = repository.create(label="Recyclable", facts=_VALID_FACTS)
    repository.delete(first.profile_id)

    # The freed name is accepted by a fresh create with a distinct id.
    recreated = repository.create(label="Recyclable", facts=_SECOND_FACTS)
    assert recreated.profile_id != first.profile_id
    assert recreated.label == "Recyclable"
    assert recreated.status is UserProfileStatus.ACTIVE


def test_deleted_profile_name_is_reusable_by_rename(_backend: Path) -> None:
    """After ``delete`` the freed display name is reusable by ``rename``.

    The duplicate-label refusal must consider only live profiles, so a
    rename onto a tombstoned profile's former name succeeds.
    """

    repository = ProfileRepository()
    retired = repository.create(label="Old Label", facts=_VALID_FACTS)
    repository.delete(retired.profile_id)
    live = repository.create(label="Live Label", facts=_SECOND_FACTS)

    renamed = repository.rename(live.profile_id, new_label="Old Label")
    assert renamed.label == "Old Label"


def test_load_surfaces_manifest_status_drift(_backend: Path) -> None:
    """Hand-desyncing the manifest status from the record makes load raise.

    The lifecycle status is denormalised: the encrypted record is the
    authority, the plaintext manifest mirrors it. This anti-tautology
    test corrupts one store — the manifest ``status`` — so the two
    copies disagree. ``load`` must raise :class:`ProfileIntegrityError`;
    if it returned an aggregate the drift would be served silently and
    the tombstone leak could recur undetected.
    """

    repository = ProfileRepository()
    created = repository.create(label="Status Drift", facts=_VALID_FACTS)
    # The fresh profile's record is ACTIVE and the manifest mirrors it.
    assert created.status is UserProfileStatus.ACTIVE

    # Hand-edit the on-disk manifest to claim TOMBSTONED while the
    # encrypted record stays ACTIVE — the exact drift state a crashed
    # delete or a manual edit could leave.
    target = manifest_path(bucket_paths(_backend, created.profile_id))
    corrupted = target.read_text(encoding="utf-8").replace(
        'status = "active"',
        'status = "tombstoned"',
    )
    assert 'status = "tombstoned"' in corrupted, "manifest status mutation did not apply"
    target.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ProfileIntegrityError, match="cross-store lifecycle drift"):
        repository.load(created.profile_id)
