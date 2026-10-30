"""The storage taxonomy is a closed, total, immutable declaration.

Where a byte lands was decided by four mutually unaware authorities, none of
which a structural gate could see. These tests hold the replacement to the
properties that make it an authority rather than a fifth opinion: every axis is
a closed set, every member has exactly one declaration, the declaration cannot
be mutated by the code reading it, and the two names that legitimately appear at
two different depths stay distinguishable.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
from pydantic import ValidationError

from cadrumo.core.bucket_pointer import pointer_path
from cadrumo.core.config import Settings, override_settings
from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.storage_taxonomy import (
    STORAGE_ROOT_SETTINGS_FIELD,
    FingerprintParticipation,
    StorageCategory,
    StorageDefaultAnchor,
    StorageGrouping,
    StorageLifecycle,
    StorageLocation,
    StorageNodeKind,
    StorageScope,
)
from cadrumo.core.storage_taxonomy_locations import (
    STORAGE_TAXONOMY,
    bucket_scoped_storage_path,
    storage_location,
    storage_path,
    storage_tree_targets,
    uses_external_transport,
)
from cadrumo.core.tests._settings_path_fields import path_typed_settings_fields
from cadrumo.core.tests.storage_taxonomy_views import FINGERPRINT_EXCLUDED_STORAGE_CATEGORIES
from cadrumo.tests.env_scope import derived_storage_settings

_BUCKET_ID = "primary"

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _axis_members(axis: type[StrEnum]) -> set[str]:
    return {member.value for member in axis}


def test_each_axis_is_a_closed_set() -> None:
    """Every axis names exactly the values it declares, and nothing else."""
    assert _axis_members(StorageNodeKind) == {"directory", "file"}
    assert _axis_members(StorageScope) == {"root", "bucket_relative", "keystore_root", "keystore_relative"}
    assert _axis_members(StorageDefaultAnchor) == {"scope", "darwin_transient"}
    assert _axis_members(StorageLifecycle) == {"unbounded_by_design", "retention", "rotation", "ttl"}
    assert _axis_members(StorageGrouping) == {"state", "logs", "cache", "exports"}
    assert _axis_members(FingerprintParticipation) == {"participating", "excluded"}


def test_an_undeclared_axis_value_is_rejected_at_model_validation() -> None:
    """A closed set that accepts an unknown value is not closed."""
    declared = storage_location(StorageCategory.TOKENS).model_dump()
    declared["node_kind"] = "symlink"

    with pytest.raises(ValidationError):
        StorageLocation.model_validate(declared)


def test_the_taxonomy_is_total_over_the_category_enum() -> None:
    """A category with no declaration is a name that can never be resolved."""
    assert set(STORAGE_TAXONOMY) == set(StorageCategory)
    for category, location in STORAGE_TAXONOMY.items():
        assert location.category is category, "a declaration must sit under its own key"


def test_the_duplicated_name_resolves_to_distinct_members() -> None:
    """``blobs`` names both a top-level category and a bucket subdirectory."""
    root_member = StorageCategory.BLOBS
    bucket_member = StorageCategory.BUCKET_BLOBS
    assert root_member is not bucket_member
    root = storage_location(root_member)
    nested = storage_location(bucket_member)
    assert root.subpath == "blobs"
    assert nested.subpath == "blobs"
    assert root.scope is StorageScope.ROOT
    assert nested.scope is StorageScope.BUCKET_RELATIVE


def test_a_declaration_forbids_extra_fields_and_refuses_mutation() -> None:
    """The taxonomy is read by the code it governs; a mutable one is not an authority."""
    declared = storage_location(StorageCategory.TOKENS)

    with pytest.raises(ValidationError):
        StorageLocation.model_validate({**declared.model_dump(), "unexpected": "value"})

    with pytest.raises(ValidationError):
        declared.subpath = "elsewhere"


def _resolved(location: StorageLocation, settings: Settings) -> Path | None:
    """Resolve any member through its scope's accessor; ``None`` for the OS-derived namespace."""
    if location.scope is StorageScope.ROOT:
        if uses_external_transport(location):
            return None
        return storage_path(location.category, settings=settings)
    return bucket_scoped_storage_path(location.category, _BUCKET_ID, settings=settings)


@pytest.mark.parametrize("retired", ["settings_field", "environment_variable", "override_policy"])
def test_a_member_cannot_declare_an_override_control(retired: str) -> None:
    """The storage root is the one control, so no member can carry a second one.

    A declaration naming a settings field, an environment variable or an
    override policy must be unconstructable, not merely absent from today's
    members. The positive control is the same declaration without the extra key.
    """
    declared = storage_location(StorageCategory.TOKENS).model_dump()

    assert StorageLocation.model_validate(declared) == storage_location(StorageCategory.TOKENS)
    with pytest.raises(ValidationError):
        StorageLocation.model_validate({**declared, retired: "cadrumo_live_state_dir"})
    assert retired not in StorageLocation.model_fields


def test_every_member_subpath_is_relative_to_its_scope_anchor() -> None:
    """A subpath is a plain POSIX relative path: nothing in it can replace or escape its anchor."""
    for category, location in STORAGE_TAXONOMY.items():
        subpath = location.subpath
        assert not PurePosixPath(subpath).is_absolute(), category
        assert not PureWindowsPath(subpath).drive, category
        assert "\\" not in subpath, f"{category.value} must spell its subpath with POSIX separators"
        assert ".." not in PurePosixPath(subpath).parts, category
        assert not location.relative_path().is_absolute(), category


def test_every_member_lands_beneath_the_storage_root(tmp_path: Path) -> None:
    """Whatever its scope, a member resolves under the one root and nowhere else."""
    root = tmp_path / "state"
    settings = Settings(cadrumo_storage_root=root)

    resolved = {location.category: _resolved(location, settings) for location in STORAGE_TAXONOMY.values()}

    assert len(resolved) == len(StorageCategory)
    for category, path in resolved.items():
        if path is None:
            continue
        assert path.is_absolute(), category
        assert path.is_relative_to(root), f"{category.value} resolved to {path}, outside {root}"


def test_keystore_members_never_resolve_beneath_the_bucket_container(tmp_path: Path) -> None:
    """The keystore is sibling to ``buckets/`` whatever the root is: no setting can nest it."""
    root = tmp_path / "state"
    settings = Settings(cadrumo_storage_root=root)
    container = storage_path(StorageCategory.BUCKETS, settings=settings)

    keystore_members = [
        location
        for location in STORAGE_TAXONOMY.values()
        if location.scope in {StorageScope.KEYSTORE_ROOT, StorageScope.KEYSTORE_RELATIVE}
    ]
    assert keystore_members, "the keystore layout must actually be declared, or this asserts nothing"
    for location in keystore_members:
        path = bucket_scoped_storage_path(location.category, _BUCKET_ID, settings=settings)
        assert not path.is_relative_to(container), location.category


def test_the_storage_root_is_a_flat_path_attribute_on_settings(tmp_path: Path) -> None:
    """The root is a plain ``Path`` field, not a nested object or a property.

    Gates that discover storage controls walk ``Settings.model_fields``; behind
    a property the root would be invisible to them while still working.
    """
    root = tmp_path / "state"
    assert STORAGE_ROOT_SETTINGS_FIELD == "cadrumo_storage_root"
    assert Settings.model_fields[STORAGE_ROOT_SETTINGS_FIELD].annotation is Path
    assert getattr(Settings(cadrumo_storage_root=root), STORAGE_ROOT_SETTINGS_FIELD) == root


def test_no_other_path_setting_places_a_storage_member(tmp_path: Path) -> None:
    """Pointing every other path-valued setting elsewhere moves no member off the root."""
    root = tmp_path / "state"
    others = {
        name: tmp_path / "elsewhere" / name
        for name in sorted(path_typed_settings_fields(Settings) - {STORAGE_ROOT_SETTINGS_FIELD})
    }
    assert others, "the selector found no other path setting, so this asserts nothing"

    with override_settings(cadrumo_storage_root=root, **others) as settings:
        for name, value in others.items():
            assert getattr(settings, name) == value, f"{name} was not applied, so it was not exercised"
        for location in STORAGE_TAXONOMY.values():
            path = _resolved(location, settings)
            if path is not None:
                assert path.is_relative_to(root), location.category


@pytest.mark.parametrize("retired", ["cadrumo_drafts_dir", "cadrumo_runs_dir", "cadrumo_usage_ratios_path"])
def test_a_per_member_setting_does_not_exist_and_relocates_nothing(tmp_path: Path, retired: str) -> None:
    """Naming a member's old setting is not a relocation: the member stays at its subpath."""
    root = tmp_path / "state"
    elsewhere = tmp_path / "operator-chosen"
    assert retired not in Settings.model_fields

    with override_settings(cadrumo_storage_root=root, **{retired: elsewhere}) as settings:
        assert not hasattr(settings, retired)
        for category in (StorageCategory.DRAFTS, StorageCategory.RUNS, StorageCategory.USAGE_RATIOS):
            assert storage_path(category) == root / storage_location(category).relative_path()


def test_fingerprint_participation_is_a_declared_axis_on_every_member() -> None:
    """Participation is declared per member, not inferred from another axis.

    What the exclusion set must *contain* is asserted against a reasoned oracle
    in :mod:`~core.tests.test_storage_fingerprint_participation_gate`, together
    with the behavioural halves that catch a digest degraded to the empty-tree
    constant. Two independent statements of one set is the duplicate authority
    this taxonomy exists to remove, so this keeps only what belongs here: the
    axis is total over the members, and only root-scoped members are excluded
    from the data-root digest.
    """
    for category, location in STORAGE_TAXONOMY.items():
        assert isinstance(location.fingerprint_participation, FingerprintParticipation), category

    excluded = {
        category
        for category, location in STORAGE_TAXONOMY.items()
        if location.fingerprint_participation is FingerprintParticipation.EXCLUDED
    }
    assert FINGERPRINT_EXCLUDED_STORAGE_CATEGORIES, "the derived exclusion view is empty, so this asserts nothing"
    assert FINGERPRINT_EXCLUDED_STORAGE_CATEGORIES.issubset(excluded)
    assert all(STORAGE_TAXONOMY[category].scope is StorageScope.ROOT for category in excluded), (
        "only a root-scoped member can be excluded from the data-root digest"
    )


def test_storage_path_resolves_every_root_member_from_the_root(tmp_path: Path) -> None:
    """Root members carry no operator field and resolve at their subpath beneath the root."""
    root = tmp_path / "state"
    with override_settings(cadrumo_storage_root=root):
        assert storage_path(StorageCategory.BUCKETS) == root / "buckets"
        assert storage_path(StorageCategory.ACTIVE_PROFILE_POINTER) == root / "active-profile"
        for location in STORAGE_TAXONOMY.values():
            if location.scope is StorageScope.ROOT and not uses_external_transport(location):
                assert storage_path(location.category) == root / location.relative_path(), location.category


def test_storage_path_refuses_a_scoped_member_rather_than_resolving_it(tmp_path: Path) -> None:
    """A bucket-scoped member needs a bucket; silently dropping it would misplace state."""
    with (
        override_settings(cadrumo_storage_root=tmp_path / "state"),
        pytest.raises(CoreValidationError) as refusal,
    ):
        storage_path(StorageCategory.BUCKET_KEYSTORE)

    assert "bucket_scoped_storage_path" in str(refusal.value), "the refusal must name the accessor that does resolve it"


def test_the_scoped_accessor_resolves_bucket_and_keystore_members(tmp_path: Path) -> None:
    """The keystore is sibling to buckets/, never nested inside the bucket it unlocks.

    Production states and enforces this separation
    (:func:`~adapters.persistence.storage.bucket.validate_keystore_separation`);
    an earlier version of this assertion pinned the keystore resolving under
    ``buckets/primary/keystore/`` and was itself the bug, passing because
    nothing checked the resolved path against the production invariant it
    exists to satisfy. See
    :func:`test_the_keystore_anchor_passes_the_production_separation_check`
    for that check.
    """
    root = tmp_path / "state"
    with override_settings(cadrumo_storage_root=root):
        bucket_tree = root / "buckets" / "primary"
        assert bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE, "primary") == bucket_tree / "db"
        assert bucket_scoped_storage_path(StorageCategory.BUCKET_MANIFEST, "primary") == bucket_tree / "manifest.toml"

        keystore_tree = root / "keystore" / "primary"
        assert bucket_scoped_storage_path(StorageCategory.BUCKET_KEYSTORE, "primary") == keystore_tree
        assert (
            bucket_scoped_storage_path(StorageCategory.KEYSTORE_PROFILE_SESSION, "primary")
            == keystore_tree / "session.v2.json"
        )
        assert (
            bucket_scoped_storage_path(StorageCategory.KEYSTORE_LOGIN_THROTTLE, "primary")
            == keystore_tree / "login-throttle.json"
        )


def test_the_keystore_anchor_passes_the_production_separation_check(tmp_path: Path) -> None:
    """Bind the taxonomy's keystore resolution to production's own security check.

    A test asserting only a literal path would not have caught the original
    defect either -- the literal it would have pinned was itself wrong. This
    asserts the accessor's output against ``validate_keystore_separation``,
    the real function that later refuses a session whose keystore resolves
    under the bucket tree, so a regression that renests the keystore under
    ``buckets/`` reds here structurally rather than by restating a coordinate.
    """
    from cadrumo.adapters.persistence.storage.bucket.keystore_paths import validate_keystore_separation

    root = tmp_path / "state"
    with override_settings(cadrumo_storage_root=root):
        resolved = bucket_scoped_storage_path(StorageCategory.BUCKET_KEYSTORE, "primary")

    # Must not raise: a resolution nested under buckets/ or the per-bucket db
    # dir is exactly what this refuses.
    validate_keystore_separation(root, "primary", configured_keystore=resolved)


def test_the_production_separation_check_still_refuses_a_nested_keystore(tmp_path: Path) -> None:
    """Positive control: the check above must still be capable of firing.

    Without this, the previous test would pass identically against a
    validator that had degraded to a no-op, which is the exact failure mode a
    security check silently disabled looks like.
    """
    from cadrumo.adapters.persistence.storage.bucket.errors import BucketValidationError
    from cadrumo.adapters.persistence.storage.bucket.keystore_paths import validate_keystore_separation

    root = tmp_path / "state"
    # Deliberately the WRONG shape -- this is the composition
    # validate_keystore_separation must reject, not a pin of the correct
    # keystore location (that is `root / "keystore" / "primary"`, asserted
    # above in test_the_scoped_accessor_resolves_bucket_and_keystore_members).
    nested = root / "buckets" / "primary" / "keystore"

    with pytest.raises(BucketValidationError):
        validate_keystore_separation(root, "primary", configured_keystore=nested)


def test_the_scoped_accessor_refuses_a_root_member_and_a_blank_bucket(tmp_path: Path) -> None:
    """Passing a root category a bucket id is a mistake worth naming, not absorbing."""
    with override_settings(cadrumo_storage_root=tmp_path / "state"):
        with pytest.raises(CoreValidationError) as refusal:
            bucket_scoped_storage_path(StorageCategory.TOKENS, "primary")
        assert "storage_path" in str(refusal.value)

        with pytest.raises(CoreValidationError):
            bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE, "   ")


def test_tree_targets_give_a_file_member_its_parent_and_never_its_leaf(tmp_path: Path) -> None:
    """The one file-valued member must contribute the directory, not the document."""
    root = tmp_path / "state"
    with override_settings(cadrumo_storage_root=root) as settings:
        targets = storage_tree_targets(settings)
        ratios = storage_path(StorageCategory.USAGE_RATIOS, settings=settings)

    assert ratios.parent in targets, "the file's directory must be materialised"
    assert ratios not in targets, "materialising the leaf would put a directory where a document belongs"


def test_tree_targets_skip_fixed_layout_members_and_stay_beneath_the_root(tmp_path: Path) -> None:
    """Per-bucket layout is provisioned per bucket; nothing leaves the root."""
    root = tmp_path / "state"
    with override_settings(cadrumo_storage_root=root) as settings:
        targets = storage_tree_targets(settings)
        unmaterialised = [
            storage_path(location.category, settings=settings)
            for location in STORAGE_TAXONOMY.values()
            if location.scope is StorageScope.ROOT
            and not location.materialised
            and location.node_kind is StorageNodeKind.DIRECTORY
        ]

    assert root / "buckets" not in targets, "the bucket container is provisioned by the bucket lifecycle"
    assert root / "tokens" in targets, "a positive control: ordinary members ARE materialised"
    assert unmaterialised, "no unmaterialised directory member was found, so this asserts nothing"
    assert not set(unmaterialised) & set(targets)
    assert all(target.is_relative_to(root) for target in targets)


def test_a_root_override_moves_every_member(tmp_path: Path) -> None:
    """Rebuilding settings under a new root leaves no member pinned to the previous one.

    The baseline derives every path from ``first``; overriding the root to
    ``second`` must move all of them, asserted over every declared member
    rather than a sampled few, since a member left on the old root fails no
    individual test -- each one still reads a path that exists.
    """
    first = tmp_path / "first-root"
    second = tmp_path / "second-root"

    with (
        derived_storage_settings(first),
        override_settings(cadrumo_storage_root=second) as rebuilt,
    ):
        resolved = {
            location.category: _resolved(location, rebuilt)
            for location in STORAGE_TAXONOMY.values()
            if not (location.scope is StorageScope.ROOT and uses_external_transport(location))
        }

    assert resolved, "the declared member set must be non-empty, or this asserts nothing"
    stale = {category: path for category, path in resolved.items() if path is None or not path.is_relative_to(second)}
    assert not stale, f"these stayed pinned to the previous root: {stale}"


def test_the_settings_cache_key_watches_the_file_the_pointer_reader_writes(tmp_path: Path) -> None:
    """The cache key and the pointer reader must resolve one and the same file.

    The settings cache keys on the active-profile pointer so that a login or
    logout inside a live process is observed rather than served from a held
    instance. That only works while both sides name the same file, and the key
    used to re-type the filename instead of resolving it. A rename would have
    left the key watching a file nothing writes: no error, no failing test, and
    a stale database route for the life of the process.

    Compared as resolved paths under one root, with no process mutation --
    the key's own root read is a direct environment lookup by design, because
    it has to answer which pointer the NEXT construction would see.
    """
    root = tmp_path / "keyed-root"
    from_taxonomy = root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()

    assert from_taxonomy == pointer_path(root)
