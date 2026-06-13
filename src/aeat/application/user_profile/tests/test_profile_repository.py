"""Cross-store roundtrip and unit-of-work tests for :class:`ProfileRepository`.

The repository is the single, sole writer of a logical profile's
physical stores. These tests exercise it against the shared secure-SQL
test helper: a real master-key session, a real per-bucket SQLite
engine, and the real filesystem — never a mock.

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

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket._layout import bucket_paths
from ....adapters.persistence.storage.bucket._manifest_io import manifest_path
from ....adapters.persistence.storage.master_key._kdf_params import KdfParams
from ....core import BucketPointer, read_pointer, write_pointer
from ....domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaValidationError,
    UserProfileFact,
    UserProfileStatus,
)
from ....domain.user_profile._values import new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow._profile_bucket_scan import (
    list_profile_buckets,
    read_profile_bucket,
    read_profile_bucket_by_id,
)
from .._integrity import ProfileIntegrityError
from .._orchestration import ProfileAlreadyRegisteredError, profile_create_storage_span, profile_storage_session
from .._profile_repository import ProfileRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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
    UserProfileFact(path="identity.tax_id", value="00000001R") if fact.path == "identity.tax_id" else fact
    for fact in _VALID_FACTS
)
# An incomplete fact set: the required ``iva.regime`` field is dropped,
# so the schema validator rejects the record inside the lifecycle
# service's ``register`` — a real failure, not a patched one. Built
# from ``_SECOND_FACTS`` so its tax id is distinct from a profile
# registered with ``_VALID_FACTS``; the rejection under test is the
# schema failure, not the duplicate-tax-id refusal.
_INCOMPLETE_FACTS: tuple[UserProfileFact, ...] = tuple(fact for fact in _SECOND_FACTS if fact.path != "iva.regime")


def _create(
    repository: ProfileRepository,
    *,
    label: str,
    facts: tuple[UserProfileFact, ...],
    enforce_unique_tax_id: bool = True,
):
    """Wrap ``repository.create`` in a ``profile_create_storage_span``.

    ``ProfileRepository.create`` delegates bucket-bound storage to
    ``_lifecycle_service``, which resolves the active bucket session
    via the storage runtime. Production callers (CLI, wizard) supply
    that session through ``profile_create_storage_span`` before
    calling ``create``; tests must do the same.
    """
    profile_id = new_profile_id()
    with profile_create_storage_span(profile_id):
        return repository.create(
            label=label,
            facts=facts,
            profile_id=profile_id,
            routing_profile_id=profile_id,
            enforce_unique_tax_id=enforce_unique_tax_id,
        )


def _load(repository: ProfileRepository, profile_id: str):
    """Wrap ``repository.load`` in a ``profile_storage_session``."""
    with profile_storage_session(profile_id):
        return repository.load(profile_id)


def _delete(repository: ProfileRepository, profile_id: str):
    """Wrap ``repository.delete`` in a ``profile_storage_session``."""
    with profile_storage_session(profile_id):
        return repository.delete(profile_id)


def _select(repository: ProfileRepository, profile_id: str):
    """Wrap ``repository.select`` in a ``profile_storage_session``."""
    with profile_storage_session(profile_id):
        return repository.select(profile_id)


def _rename(repository: ProfileRepository, profile_id: str, *, new_label: str):
    """Wrap ``repository.rename`` in a ``profile_storage_session``."""
    with profile_storage_session(profile_id):
        return repository.rename(profile_id, new_label=new_label)


@pytest.fixture(autouse=True)
def _backend(tmp_path: Path) -> Iterator[Path]:
    """An empty real storage root with an active test key session."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def test_create_load_roundtrip_preserves_the_aggregate(_backend: Path) -> None:
    """A populated aggregate survives create / load with strict equality.

    Every defaultable field on the aggregate is set to a non-default
    value through ``create``: a multi-fact record (not the empty
    default), a non-default lifecycle path. A save-drops-field /
    load-re-defaults-field regression would surface as inequality.
    """

    repository = ProfileRepository()
    created = _create(repository, label="Roundtrip Operator", facts=_VALID_FACTS)

    loaded = _load(repository, created.profile_id)

    assert loaded == created
    assert loaded.label == "Roundtrip Operator"
    assert loaded.status is UserProfileStatus.ACTIVE
    assert loaded.record.facts == _VALID_FACTS
    assert loaded.recovery_enrolled is False
    canonical = KdfParams.default()
    assert loaded.kdf_params.model_dump(exclude={"salt"}) == canonical.to_manifest_params().model_dump(exclude={"salt"})
    assert KdfParams.model_validate(loaded.kdf_params.model_dump())


def test_create_refuses_a_duplicate_tax_id(_backend: Path) -> None:
    """A second profile carrying an existing tax id is refused.

    Two profiles sharing a NIF / NIE / CIF silently split one
    taxpayer's filing history. ``create`` scans the registered
    profiles and refuses the duplicate before any store write.
    """

    repository = ProfileRepository()
    first = _create(repository, label="Original", facts=_VALID_FACTS)

    # `_VALID_FACTS` carries tax id 00000000T; a second create with the
    # same id under a different label must be refused.
    duplicate_facts = tuple(
        UserProfileFact(path="identity.tax_id", value="00000000T") if fact.path == "identity.tax_id" else fact
        for fact in _SECOND_FACTS
    )
    with pytest.raises(ProfileAlreadyRegisteredError) as excinfo:
        _create(repository, label="Duplicate", facts=duplicate_facts)
    assert excinfo.value.translated_message == "application.user_profile.errors.duplicate_tax_id"
    assert excinfo.value.context == {"tax_id": "00000000T", "profile": "Original"}

    # The refusal fired before any store write: no half-live profile.
    assert read_profile_bucket("Duplicate", root=_backend) is None
    # The original is untouched and still loads.
    assert _load(repository, first.profile_id).label == "Original"


def test_create_succeeds_with_different_nif_when_scan_hits_unreadable_profile(
    caplog: pytest.LogCaptureFixture,
    _backend: Path,
) -> None:
    """An unreadable live profile must NOT block creating a profile with a distinct NIF.

    One torn bucket is an operator storage problem; it must not prevent
    an entirely different taxpayer from being registered. The scan skips
    the unreadable profile with a warning and continues against the
    readable ones. The new profile is written and loads correctly.
    """

    repository = ProfileRepository()
    created = _create(repository, label="Torn Tax Id Holder", facts=_VALID_FACTS)

    # Corrupt the manifest so load() raises ProfileIntegrityError for this profile.
    target = manifest_path(bucket_paths(_backend, created.profile_id))
    corrupted = target.read_text(encoding="utf-8").replace(
        f'bucket_id = "{created.profile_id}"',
        'bucket_id = "00000000-0000-4000-8000-000000000000"',
    )
    assert "00000000-0000-4000-8000-000000000000" in corrupted, "manifest mutation did not apply"
    target.write_text(corrupted, encoding="utf-8")

    # A distinct NIF must succeed despite the torn profile — the warn-and-continue
    # path does not let a torn bucket block a new taxpayer registration.
    with caplog.at_level(logging.DEBUG, logger="aeat.application.user_profile._profile_repository"):
        new_profile = _create(repository, label="Different NIF", facts=_SECOND_FACTS)

    assert new_profile.label == "Different NIF"
    loaded = _load(repository, new_profile.profile_id)
    assert loaded.label == "Different NIF"
    assert "tax-id uniqueness scan: skipping unreadable profile" in caplog.text
    assert "tax-id uniqueness scan skipped unreadable profile" in caplog.text
    assert "error_type=" in caplog.text
    assert created.profile_id not in caplog.text
    assert "<profile-id>" in caplog.text


def test_create_still_refuses_duplicate_nif_against_readable_profiles(_backend: Path) -> None:
    """Duplicate NIF detection fires against readable profiles even when another is torn.

    When the scan skips an unreadable profile it must still detect a
    duplicate NIF in the readable portion of the registry. The
    anti-tautology proof: corrupting a THIRD profile does not disable
    detection of a duplicate against a perfectly readable profile.
    """

    repository = ProfileRepository()
    readable = _create(repository, label="Readable Holder", facts=_VALID_FACTS)
    torn = _create(repository, label="Torn Bystander", facts=_SECOND_FACTS)

    # Corrupt the torn profile's manifest.
    target = manifest_path(bucket_paths(_backend, torn.profile_id))
    corrupted = target.read_text(encoding="utf-8").replace(
        f'bucket_id = "{torn.profile_id}"',
        'bucket_id = "00000000-0000-4000-8000-000000000000"',
    )
    assert "00000000-0000-4000-8000-000000000000" in corrupted, "manifest mutation did not apply"
    target.write_text(corrupted, encoding="utf-8")

    # Attempt to create a profile that duplicates the READABLE profile's NIF.
    duplicate_facts = tuple(
        UserProfileFact(path="identity.tax_id", value="00000000T") if fact.path == "identity.tax_id" else fact
        for fact in _SECOND_FACTS
    )
    with pytest.raises(ProfileAlreadyRegisteredError) as excinfo:
        _create(repository, label="Duplicate", facts=duplicate_facts)
    assert excinfo.value.translated_message == "application.user_profile.errors.duplicate_tax_id"
    assert excinfo.value.context == {"tax_id": "00000000T", "profile": "Readable Holder"}

    # No half-live profile for the refused duplicate.
    assert read_profile_bucket("Duplicate", root=_backend) is None
    # The original readable profile is untouched.
    assert _load(repository, readable.profile_id).label == "Readable Holder"


def test_create_allows_distinct_tax_ids(_backend: Path) -> None:
    """Two profiles with distinct tax ids both register cleanly."""

    repository = ProfileRepository()
    first = _create(repository, label="First", facts=_VALID_FACTS)
    second = _create(repository, label="Second", facts=_SECOND_FACTS)

    assert first.profile_id != second.profile_id
    assert _load(repository, first.profile_id).label == "First"
    assert _load(repository, second.profile_id).label == "Second"


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
    created = _create(repository, label="Drift Operator", facts=_VALID_FACTS)

    # Corrupt the manifest in place: rewrite bucket_id to a foreign UUID.
    target = manifest_path(bucket_paths(_backend, created.profile_id))
    corrupted = target.read_text(encoding="utf-8").replace(
        f'bucket_id = "{created.profile_id}"',
        'bucket_id = "00000000-0000-4000-8000-000000000000"',
    )
    assert "00000000-0000-4000-8000-000000000000" in corrupted, "manifest mutation did not apply"
    target.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ProfileIntegrityError):
        _load(repository, created.profile_id)


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
    # is a non-trivial assertion: the pointer must end at the regression.
    repository = ProfileRepository()
    survivor = _create(repository, label="Survivor", facts=_VALID_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=survivor.profile_id, schema_version=1))
    prior_pointer = read_pointer(_backend)
    assert prior_pointer is not None

    with pytest.raises(ProfileSchemaValidationError):
        _create(repository, label="Victim", facts=_INCOMPLETE_FACTS)

    # No half-live profile: no manifest scan hit, no pointer drift.
    assert read_profile_bucket("Victim", root=_backend) is None
    pointer_after = read_pointer(_backend)
    assert pointer_after is not None
    assert pointer_after.bucket_id == survivor.profile_id, "the failed create stranded the active-profile pointer"
    # The regression is untouched and still loads cleanly.
    reloaded = _load(repository, survivor.profile_id)
    assert reloaded.label == "Survivor"


def test_delete_tombstones_and_clears_the_pointer(_backend: Path) -> None:
    """``delete`` tombstones the record and clears the active pointer."""

    repository = ProfileRepository()
    created = _create(repository, label="To Delete", facts=_VALID_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=created.profile_id, schema_version=1))

    deleted = _delete(repository, created.profile_id)

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
    created = _create(repository, label="Torn Delete", facts=_VALID_FACTS)
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
        _delete(repository, created.profile_id)

    # No torn state: the pointer is untouched and the record is still
    # live. Restore the manifest so the record can be re-loaded.
    pointer_after = read_pointer(_backend)
    assert pointer_after is not None
    assert pointer_after.bucket_id == created.profile_id
    target.write_text(corrupted.replace("00000000-0000-4000-8000-000000000000", created.profile_id), encoding="utf-8")
    reloaded = _load(repository, created.profile_id)
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
    active = _create(repository, label="Active One", facts=_VALID_FACTS)
    other = _create(repository, label="Other One", facts=_SECOND_FACTS)
    write_pointer(_backend, BucketPointer(bucket_id=active.profile_id, schema_version=1))

    _delete(repository, active.profile_id)

    assert read_pointer(_backend) is None
    # Deleting a non-active profile must not clear another profile's pointer.
    write_pointer(_backend, BucketPointer(bucket_id=other.profile_id, schema_version=1))
    _delete(repository, active.profile_id)  # idempotent re-delete of the same id
    pointer = read_pointer(_backend)
    assert pointer is not None
    assert pointer.bucket_id == other.profile_id


def test_list_summarises_every_registered_profile(_backend: Path) -> None:
    """``list`` returns one typed summary per registered profile."""

    repository = ProfileRepository()
    first = _create(repository, label="First", facts=_VALID_FACTS)
    second = _create(repository, label="Second", facts=_SECOND_FACTS)

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

    from ....adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus
    from ....adapters.persistence.storage.bucket._manifest_io import read_manifest

    repository = ProfileRepository()
    created = _create(repository, label="Soft Delete", facts=_VALID_FACTS)

    _delete(repository, created.profile_id)

    manifest = read_manifest(bucket_paths(_backend, created.profile_id))
    assert manifest.status is BucketLifecycleStatus.TOMBSTONED


def test_tombstoned_profile_is_excluded_from_the_live_scan(_backend: Path) -> None:
    """A tombstoned profile leaves ``list_profile_buckets`` / ``read_profile_bucket``.

    Closes the live-scan and unlock leak: after a
    delete the manifest scan no longer surfaces the profile, so neither
    the listing nor the label-resolver can serve it. The by-id
    resolver still finds it — ``show`` and diagnostics inspect a
    tombstoned profile by UUID.
    """

    from ....adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus

    repository = ProfileRepository()
    created = _create(repository, label="Vanishing", facts=_VALID_FACTS)
    assert read_profile_bucket("Vanishing", root=_backend) is not None

    _delete(repository, created.profile_id)

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

    Closes the activation leak at the repository layer: a
    deleted profile can never become the active one, refused with the
    same error class as an unknown profile.
    """

    repository = ProfileRepository()
    created = _create(repository, label="Not Selectable", facts=_VALID_FACTS)
    _delete(repository, created.profile_id)

    with pytest.raises(ProfileNotFoundError) as excinfo:
        _select(repository, created.profile_id)
    assert excinfo.value.translated_message == "application.user_profile.errors.profile_tombstoned_not_selectable"
    assert excinfo.value.context == {"profile": created.profile_id}


def test_deleted_profile_name_is_reusable(_backend: Path) -> None:
    """After ``delete`` the freed display name is reusable by ``create``.

    Display names are unique among *live* profiles only; a tombstoned
    profile's name is free to reuse.
    """

    repository = ProfileRepository()
    first = _create(repository, label="Recyclable", facts=_VALID_FACTS)
    _delete(repository, first.profile_id)

    # The freed name is accepted by a fresh create with a distinct id.
    recreated = _create(repository, label="Recyclable", facts=_SECOND_FACTS)
    assert recreated.profile_id != first.profile_id
    assert recreated.label == "Recyclable"
    assert recreated.status is UserProfileStatus.ACTIVE


def test_deleted_profile_name_is_reusable_by_rename(_backend: Path) -> None:
    """After ``delete`` the freed display name is reusable by ``rename``.

    The duplicate-label refusal must consider only live profiles, so a
    rename onto a tombstoned profile's former name succeeds.
    """

    repository = ProfileRepository()
    retired = _create(repository, label="Old Label", facts=_VALID_FACTS)
    _delete(repository, retired.profile_id)
    live = _create(repository, label="Live Label", facts=_SECOND_FACTS)

    renamed = _rename(repository, live.profile_id, new_label="Old Label")
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
    created = _create(repository, label="Status Drift", facts=_VALID_FACTS)
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

    with pytest.raises(ProfileIntegrityError, match="profile physical stores disagree on lifecycle status"):
        _load(repository, created.profile_id)
