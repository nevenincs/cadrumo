"""A copied world is the world it was copied from, and no copy reaches another.

Every suite that reuses a built profile rests on these claims, so they are
proved against real custody: the real KDF child, real encrypted records and the
real registration door.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import pytest

from .....application.user_profile.authentication import ProfileAuthenticationRefusedError
from .....application.user_profile.login_session import authenticate_profile_for_invocation
from .....application.user_profile.registration import register_profile_with_credentials
from .....application.workflow.profile_bucket_scan import resolve_profile_bucket
from .....core.config import load_settings
from .....domain.user_profile.values import UserProfileFact
from ...storage.master_key.active_session import close_active_bucket_session, current_active_bucket_session
from ...storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    profile_authority_contexts,
    upsert_test_profile_facts,
)
from ...storage.tests.secure_sql import isolated_profile_storage_root
from .profile_registration import register_cli_profile
from .sealed_profile_world import (
    SealedProfileWorld,
    copied_profile_world,
    copy_sealed_tree,
    sealed_profile_world,
    sealed_tree,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _password() -> str:
    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _registered_world(label: str) -> SealedProfileWorld:
    create, decode = profile_authority_contexts()
    return sealed_profile_world(
        ("sealed-world-proof", label),
        lambda: (
            register_profile_with_credentials(
                label=label,
                passphrase=_password(),
                profile_create_context=create,
                profile_decode_context=decode,
            ).profile_id
        ),
    )


def _tree_shape(root: Path) -> set[str]:
    return {_UUID.sub("<id>", path.relative_to(root).as_posix()) for path in root.rglob("*") if path.is_file()}


def test_copy_leaves_only_the_storage_roots_coordination_behind(tmp_path: Path) -> None:
    for root in (tmp_path / "plain", tmp_path / "nested" / "cadrumo-storage"):
        (root / ".runtime").mkdir(parents=True)
        (root / ".runtime" / "installation.json").write_text("origin identity")
        (root / "buckets" / ".runtime").mkdir(parents=True)
        (root / "buckets" / ".runtime" / "kept").write_text("not coordination")
    (tmp_path / "nested" / "sibling-secrets").mkdir()
    (tmp_path / "nested" / "sibling-secrets" / "key").write_text("substrate")

    plain = copy_sealed_tree(tmp_path / "plain", tmp_path / "plain-copy")
    nested = copy_sealed_tree(tmp_path / "nested", tmp_path / "nested-copy")

    assert not (plain / ".runtime").exists()
    assert (plain / "buckets" / ".runtime" / "kept").read_text() == "not coordination"
    assert not (nested / "cadrumo-storage" / ".runtime").exists()
    assert (nested / "cadrumo-storage" / "buckets" / ".runtime" / "kept").is_file()
    assert (nested / "sibling-secrets" / "key").read_text() == "substrate"


def test_a_tree_is_built_once_per_key_and_again_when_its_directory_is_gone(tmp_path: Path) -> None:
    builds: list[Path] = []

    def build(origin: Path) -> int:
        builds.append(origin)
        return len(builds)

    parent = tmp_path / "owned"
    parent.mkdir()
    first_origin, first = sealed_tree(("once", tmp_path), build, parent=parent)
    again_origin, again = sealed_tree(("once", tmp_path), build, parent=parent)
    _, other = sealed_tree(("other", tmp_path), build, parent=parent)
    assert (first, again, other) == (1, 1, 2)
    assert first_origin == again_origin and first_origin.parent == parent

    first_origin.rmdir()
    _, rebuilt = sealed_tree(("once", tmp_path), build, parent=parent)
    assert rebuilt == 3


def test_a_copy_authenticates_with_its_password_through_the_real_kdf_child(tmp_path: Path) -> None:
    world = _registered_world("copy authenticates")
    _, decode = profile_authority_contexts()
    copy_sealed_tree(world.origin, tmp_path)
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = authenticate_profile_for_invocation(
            name=world.profile_id,
            passphrase_callback=_password,
            profile_decode_context=decode,
        )
        try:
            assert outcome.bucket_id == world.profile_id
            session = current_active_bucket_session()
            assert session is not None and bytes(session.dek) == world.dek
        finally:
            close_active_bucket_session()


def test_a_copy_refuses_the_wrong_password(tmp_path: Path) -> None:
    world = _registered_world("copy refuses")
    _, decode = profile_authority_contexts()
    copy_sealed_tree(world.origin, tmp_path)
    with isolated_profile_storage_root(tmp_path=tmp_path), pytest.raises(ProfileAuthenticationRefusedError):
        authenticate_profile_for_invocation(
            name=world.profile_id,
            passphrase_callback=lambda: _password() + "-wrong",
            profile_decode_context=decode,
        )


def test_a_resumed_copy_reads_its_record_and_its_writes_reach_no_other_copy(tmp_path: Path) -> None:
    world = _registered_world("copies isolated")
    _, decode = profile_authority_contexts()
    origin_files = {path: path.read_bytes() for path in world.origin.rglob("*") if path.is_file()}
    identity = UUID(world.profile_id)

    with copied_profile_world(world, tmp_path / "first", profile_decode_context=decode):
        with bound_test_profile_record(identity) as repository:
            before = repository.load(identity).record_revision
        upsert_test_profile_facts(world.profile_id, (UserProfileFact(path="identity.tax_id", value="12345678Z"),))
        with bound_test_profile_record(identity) as repository:
            assert repository.load(identity).record_revision != before

    with (
        copied_profile_world(world, tmp_path / "second", profile_decode_context=decode),
        bound_test_profile_record(identity) as repository,
    ):
        assert repository.load(identity).record_revision == before

    assert {path: path.read_bytes() for path in world.origin.rglob("*") if path.is_file()} == origin_files


def test_a_copy_has_the_shape_of_a_world_registered_for_real(tmp_path: Path) -> None:
    world = _registered_world("same shape")
    create, decode = profile_authority_contexts()
    registered = tmp_path / "registered"
    with isolated_profile_storage_root(tmp_path=registered):
        register_profile_with_credentials(
            label="same shape",
            passphrase=_password(),
            profile_create_context=create,
            profile_decode_context=decode,
        )
        close_active_bucket_session()
    copied = copy_sealed_tree(world.origin, tmp_path / "copied")
    assert _tree_shape(copied) == _tree_shape(registered)


def test_register_cli_profile_copies_into_an_unused_root_and_registers_beside_a_profile(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path / "a"):
        first = register_cli_profile(label="shared seed", log_in=False)
        beside = register_cli_profile(label="second profile", log_in=False)
        assert beside != first
        assert resolve_profile_bucket("shared seed") is not None
        assert resolve_profile_bucket("second profile") is not None
        close_active_bucket_session()
    with isolated_profile_storage_root(tmp_path=tmp_path / "b"):
        assert register_cli_profile(label="shared seed", log_in=False) == first
        pointer = resolve_profile_bucket("shared seed")
        assert pointer is not None and pointer.bucket_id == first
        close_active_bucket_session()
