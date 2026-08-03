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
from pathlib import Path

import pytest
from pydantic import ValidationError

from .._bucket_pointer_io import pointer_path
from .._storage_taxonomy import (
    FINGERPRINT_EXCLUDED_STORAGE_FIELDS,
    ROOT_DERIVED_STORAGE_FIELDS,
    STORAGE_FIELD_CATEGORIES,
    STORAGE_TAXONOMY,
    ExternalPathRole,
    FingerprintParticipation,
    StorageCategory,
    StorageGrouping,
    StorageLifecycle,
    StorageLocation,
    StorageNodeKind,
    StorageOverridePolicy,
    StorageScope,
    bucket_scoped_storage_path,
    storage_location,
    storage_path,
    storage_tree_targets,
)
from ..config import Settings, override_settings
from ..errors import CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# The exclusion oracle, re-derived independently from the drift-fingerprint
# module's own eight attribute reads rather than from the taxonomy, so the
# taxonomy cannot certify its own completeness. Field NAMES, never resolved
# paths: two fields overridden onto one directory shrink a resolved-path set
# while exactly the same fields are still consulted, so a cardinality
# comparison is wrong in both directions at once.
_FINGERPRINT_EXCLUDED_ORACLE = frozenset(
    {
        "cadrumo_corpus_text_cache_dir",
        "cadrumo_llm_cache_dir",
        "cadrumo_llm_run_telemetry_dir",
        "cadrumo_llm_usage_dir",
        "cadrumo_runs_dir",
        "cadrumo_status_cache_dir",
        "cadrumo_storage_backup_dir",
        "cadrumo_validation_verdict_cache_dir",
    },
)


def _axis_members(axis: type[StrEnum]) -> set[str]:
    return {member.value for member in axis}


def test_each_axis_is_a_closed_set() -> None:
    """Every axis names exactly the values it declares, and nothing else."""
    assert _axis_members(StorageNodeKind) == {"directory", "file"}
    assert _axis_members(StorageScope) == {"root", "bucket_relative", "keystore_relative"}
    assert _axis_members(StorageOverridePolicy) == {"operator_overridable", "fixed"}
    assert _axis_members(StorageLifecycle) == {"unbounded_by_design", "retention", "rotation", "ttl"}
    assert _axis_members(StorageGrouping) == {"state", "logs", "cache", "exports"}
    assert _axis_members(FingerprintParticipation) == {"participating", "excluded"}


def test_an_undeclared_axis_value_is_rejected_at_model_validation() -> None:
    """A closed set that accepts an unknown value is not closed."""
    declared = storage_location(StorageCategory.TOKENS).model_dump()
    declared["node_kind"] = "symlink"

    with pytest.raises(ValidationError):
        StorageLocation.model_validate(declared)


def test_external_path_role_carries_the_five_escape_roles() -> None:
    """An escape is a positive declaration of why, not an absence from a list."""
    assert _axis_members(ExternalPathRole) == {
        "bundled_resource",
        "operator_input",
        "third_party_cache",
        "external_executable",
        "operator_directed_output",
    }


def test_an_undeclared_escape_role_is_not_a_member() -> None:
    """A reason nobody declared cannot be used to excuse a path."""
    with pytest.raises(ValueError, match="oversight"):
        ExternalPathRole("oversight")


def test_the_taxonomy_is_total_over_the_category_enum() -> None:
    """A category with no declaration is a name that can never be resolved."""
    assert set(STORAGE_TAXONOMY) == set(StorageCategory)
    for category, location in STORAGE_TAXONOMY.items():
        assert location.category is category, "a declaration must sit under its own key"


def test_the_duplicated_names_resolve_to_distinct_members() -> None:
    """``blobs`` and ``audit`` each name a top-level category AND a bucket subdirectory.

    Both are correct, at different depths. A name-keyed authority would conflate
    them, which is why scope is part of a member's identity rather than a
    decoration on it.
    """
    for root_member, bucket_member, shared_name in (
        (StorageCategory.BLOBS, StorageCategory.BUCKET_BLOBS, "blobs"),
        (StorageCategory.AUDIT, StorageCategory.BUCKET_AUDIT, "audit"),
    ):
        assert root_member is not bucket_member
        root = storage_location(root_member)
        nested = storage_location(bucket_member)
        assert root.subpath == shared_name
        assert nested.subpath == shared_name
        assert root.scope is StorageScope.ROOT
        assert nested.scope is StorageScope.BUCKET_RELATIVE


def test_a_declaration_forbids_extra_fields_and_refuses_mutation() -> None:
    """The taxonomy is read by the code it governs; a mutable one is not an authority."""
    declared = storage_location(StorageCategory.TOKENS)

    with pytest.raises(ValidationError):
        StorageLocation.model_validate({**declared.model_dump(), "unexpected": "value"})

    with pytest.raises(ValidationError):
        declared.subpath = "elsewhere"


def test_bucket_and_keystore_layout_is_fixed_not_operator_overridable() -> None:
    """An operator must not relocate a keystore out from under the bucket it unlocks."""
    scoped = [location for location in STORAGE_TAXONOMY.values() if location.scope is not StorageScope.ROOT]
    assert scoped, "the fixed layout must actually be declared, or this asserts nothing"
    for location in scoped:
        assert location.override_policy is StorageOverridePolicy.FIXED
        assert location.settings_field is None, "a fixed member must expose no operator-facing field"


def test_every_settings_field_a_member_names_exists_on_the_model() -> None:
    """A member naming a field that no longer exists is a declaration that has rotted."""
    assert STORAGE_FIELD_CATEGORIES, "the reverse index must not be empty, or this asserts nothing"
    for field_name in STORAGE_FIELD_CATEGORIES:
        assert field_name in Settings.model_fields, f"{field_name} is named by the taxonomy but absent from Settings"


def test_path_fields_stay_flat_attributes_on_settings(tmp_path: Path) -> None:
    """The gates that discover storage fields walk ``Settings.model_fields``.

    Moving these onto a nested object or behind a property would leave that
    discovery finding nothing -- which passes silently while covering nothing.
    Members therefore NAME their field rather than absorbing it.
    """
    settings = Settings(cadrumo_local_storage_root=tmp_path / "state")
    for field_name, category in STORAGE_FIELD_CATEGORIES.items():
        assert isinstance(getattr(settings, field_name, None), (Path, type(None))), (
            f"{category.value} names {field_name}, which must stay a flat path attribute"
        )


def test_fingerprint_participation_reproduces_the_independent_oracle() -> None:
    """Set equality in both directions, by field name.

    Excluding too much walks the digest toward the empty-tree constant that once
    defeated drift detection outright; excluding too little churns it on every
    cache write. Neither direction moves any other test, so both inclusions are
    asserted here.
    """
    assert FINGERPRINT_EXCLUDED_STORAGE_FIELDS == _FINGERPRINT_EXCLUDED_ORACLE, (
        f"missing: {sorted(_FINGERPRINT_EXCLUDED_ORACLE - FINGERPRINT_EXCLUDED_STORAGE_FIELDS)}; "
        f"extra: {sorted(FINGERPRINT_EXCLUDED_STORAGE_FIELDS - _FINGERPRINT_EXCLUDED_ORACLE)}"
    )


def test_the_opt_in_override_member_governs_its_name_without_deriving_its_field() -> None:
    """Governing a name and deriving a field are separate decisions.

    The registry disk cache resolver selects a shared temporary location under
    pytest precisely by observing that the field is unset, so deriving a default
    into it would silently retire that branch.
    """
    location = storage_location(StorageCategory.REGISTRY_DISK_CACHE)
    assert location.subpath == "cache/registry"
    assert location.settings_field == "cadrumo_registry_disk_cache_dir"
    assert not location.derives_settings_default
    assert location.settings_field not in ROOT_DERIVED_STORAGE_FIELDS


def test_storage_path_reads_the_member_field_so_an_override_wins(tmp_path: Path) -> None:
    """An explicit per-field override outranks root derivation, here as everywhere."""
    elsewhere = tmp_path / "operator-chosen-drafts"
    with override_settings(cadrumo_local_storage_root=tmp_path / "state", cadrumo_drafts_dir=elsewhere):
        assert storage_path(StorageCategory.DRAFTS) == elsewhere


def test_storage_path_falls_back_to_the_root_for_a_fieldless_member(tmp_path: Path) -> None:
    """Fixed-layout members carry no operator field and resolve from the root."""
    root = tmp_path / "state"
    with override_settings(cadrumo_local_storage_root=root):
        assert storage_path(StorageCategory.BUCKETS) == root / "buckets"
        assert storage_path(StorageCategory.ACTIVE_PROFILE_POINTER) == root / "active-profile"


def test_storage_path_refuses_a_scoped_member_rather_than_resolving_it(tmp_path: Path) -> None:
    """A bucket-scoped member needs a bucket; silently dropping it would misplace state."""
    with (
        override_settings(cadrumo_local_storage_root=tmp_path / "state"),
        pytest.raises(CoreValidationError) as refusal,
    ):
        storage_path(StorageCategory.BUCKET_KEYSTORE)

    assert "bucket_scoped_storage_path" in str(refusal.value), "the refusal must name the accessor that does resolve it"


def test_the_scoped_accessor_resolves_bucket_and_keystore_members(tmp_path: Path) -> None:
    """Keystore members nest under the bucket's keystore, not beside it."""
    root = tmp_path / "state"
    with override_settings(cadrumo_local_storage_root=root):
        bucket_tree = root / "buckets" / "primary"
        assert bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE, "primary") == bucket_tree / "db"
        assert bucket_scoped_storage_path(StorageCategory.BUCKET_MANIFEST, "primary") == bucket_tree / "manifest.toml"
        assert (
            bucket_scoped_storage_path(StorageCategory.KEYSTORE_PROFILE_SESSION, "primary")
            == bucket_tree / "keystore" / "session.v1.json"
        )


def test_the_scoped_accessor_refuses_a_root_member_and_a_blank_bucket(tmp_path: Path) -> None:
    """Passing a root category a bucket id is a mistake worth naming, not absorbing."""
    with override_settings(cadrumo_local_storage_root=tmp_path / "state"):
        with pytest.raises(CoreValidationError) as refusal:
            bucket_scoped_storage_path(StorageCategory.TOKENS, "primary")
        assert "storage_path" in str(refusal.value)

        with pytest.raises(CoreValidationError):
            bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE, "   ")


def test_tree_targets_give_a_file_member_its_parent_and_never_its_leaf(tmp_path: Path) -> None:
    """The one file-valued member must contribute the directory, not the document."""
    root = tmp_path / "state"
    with override_settings(cadrumo_local_storage_root=root) as settings:
        targets = storage_tree_targets(settings)
        ratios = Path(settings.cadrumo_usage_ratios_path)

    assert ratios.parent in targets, "the file's directory must be materialised"
    assert ratios not in targets, "materialising the leaf would put a directory where a document belongs"


def test_tree_targets_skip_fixed_layout_and_absent_opt_in_members(tmp_path: Path) -> None:
    """Per-bucket layout is provisioned per bucket; an unset opt-in was never asked for."""
    root = tmp_path / "state"
    with override_settings(cadrumo_local_storage_root=root) as settings:
        targets = storage_tree_targets(settings)

    assert root / "buckets" not in targets, "the bucket container is provisioned by the bucket lifecycle"
    assert root / "cache" / "registry" not in targets, "an unset opt-in override must not be materialised"
    assert root / "tokens" in targets, "a positive control: ordinary members ARE materialised"


def test_a_root_override_re_derives_every_non_overridden_category(tmp_path: Path) -> None:
    """The rebuild loop must cover the whole declared field set, not a stale copy.

    Flattening settings through ``model_dump`` turns every previously-derived
    absolute path into an explicit value, so without the pop the entire tree
    stays pinned to the previous root. That leak fails no individual test --
    each one still reads a path that exists -- which is why it is asserted
    directly, over every derived member rather than a sampled few.
    """
    first = tmp_path / "first-root"
    second = tmp_path / "second-root"

    with (
        override_settings(cadrumo_local_storage_root=first),
        override_settings(cadrumo_local_storage_root=second) as rebuilt,
    ):
        stale = {
            field_name: getattr(rebuilt, field_name)
            for field_name in ROOT_DERIVED_STORAGE_FIELDS
            if not str(getattr(rebuilt, field_name)).startswith(str(second))
        }

    assert ROOT_DERIVED_STORAGE_FIELDS, "the derived field set must be non-empty, or this asserts nothing"
    assert not stale, f"these stayed pinned to the previous root: {stale}"


def test_an_explicitly_overridden_category_is_not_re_derived(tmp_path: Path) -> None:
    """Positive control for the test above: the rebuild must not clobber an override.

    A loop that re-derived unconditionally would pass the assertion above while
    silently discarding exactly the operator intent the override expresses.
    """
    elsewhere = tmp_path / "operator-chosen-runs"

    with (
        override_settings(cadrumo_local_storage_root=tmp_path / "first", cadrumo_runs_dir=elsewhere),
        override_settings(cadrumo_local_storage_root=tmp_path / "second") as rebuilt,
    ):
        assert rebuilt.cadrumo_runs_dir == elsewhere


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
