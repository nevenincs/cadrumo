"""Reuse a built profile world by copying its settled bytes.

Registering a profile launches a KDF child and publishes a capsule, and most
tests that do so are about something else. A world is therefore built once per
pytest worker through the real door, closed so its bytes are at rest, and each
test receives its own filesystem copy: a mutation, a journal write or a session
in one copy reaches no other.

Three rules keep a copy equivalent to the world it came from:

* A world is private to the process that built it. Profile identity, salt and
  key are random per registration and the keychain addresses session keys by
  profile, so two workers must never hold copies of one world.
* The whole tree is copied, because custody material need not sit under the
  storage root. Only the runtime coordination directory stays behind: the
  installation records in it pin the origin's physical identity, and a copy is
  another root that installs its own on first use.
* A copy opens under the same authority generation and password as its origin.

A copy resumes through :func:`publish_created_profile_session`, the publication
registration and login share, from the key the build proved, so no password
derivation runs. A test whose subject is registration, login or custody keeps
the production door: nothing here replaces those paths for it, and a password
sign-in on a copy works because the copy holds the real wrapped key.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Generator, Hashable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast
from uuid import UUID

from .....application.user_profile.login_session import publish_created_profile_session
from .....core.config import load_settings
from .....core.hashing import sha256_hex
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from .....domain.calculations.registry.authority import bundled_indexed_authority
from ...storage.custody.tests.portable_password_custody import portable_password_custody
from ...storage.master_key.active_session import close_active_bucket_session, current_active_bucket_session
from ...storage.sql.engine import dispose_engine
from ...storage.storage_path_definitions import BUCKETS_DIRNAME
from ...storage.tests.secure_sql import isolated_profile_storage_root

if TYPE_CHECKING:
    from .....domain.calculations.registry.authority_artifact import ProfileDecodeContext

__all__ = [
    "SealedProfileWorld",
    "copied_profile_world",
    "copy_sealed_tree",
    "copy_world_into_storage_root",
    "publish_world_session",
    "sealed_profile_world",
    "sealed_tree",
    "storage_root_is_unused",
]

#: The directory an isolated world opens its storage root beneath.
_STORAGE_ROOT_NAME = "cadrumo-storage"

_TREES: dict[Hashable, tuple[Path, object]] = {}
_TREE_HOLDERS: list[TemporaryDirectory[str]] = []


@dataclass(frozen=True, slots=True)
class SealedProfileWorld:
    """One worker's settled world: its bytes at rest and the key its registration proved."""

    origin: Path
    profile_id: str
    dek: bytes = field(repr=False)


def _omit_installation_records(origin: Path) -> Callable[[str, list[str]], set[str]]:
    coordination = storage_location(StorageCategory.RUNTIME_COORDINATION).relative_path().name
    storage_roots = {origin, origin / _STORAGE_ROOT_NAME}

    def omit(directory: str, names: list[str]) -> set[str]:
        return {coordination} if coordination in names and Path(directory) in storage_roots else set()

    return omit


def copy_sealed_tree(origin: Path, destination: Path) -> Path:
    """Copy a settled tree, whose root is a storage root or holds one, without its installation records."""
    shutil.copytree(origin, destination, ignore=_omit_installation_records(origin), dirs_exist_ok=True)
    return destination


def sealed_tree[Built](
    key: Hashable,
    build: Callable[[Path], Built],
    *,
    parent: Path | None = None,
) -> tuple[Path, Built]:
    """Return this worker's settled tree for ``key``, building it on first use.

    ``build`` receives an empty directory and must leave it at rest. ``parent``
    names where it lives when the caller owns that lifetime; a tree whose
    directory has since gone is built again.
    """
    known = _TREES.get(key)
    if known is not None and known[0].is_dir():
        return known[0], cast(Built, known[1])
    holder = TemporaryDirectory(prefix="sealed-world-", dir=parent)
    _TREE_HOLDERS.append(holder)
    origin = Path(holder.name)
    built = build(origin)
    _TREES[key] = (origin, built)
    return origin, built


def sealed_profile_world(key: Hashable, register: Callable[[], str]) -> SealedProfileWorld:
    """Return this worker's world for ``key``, registering its one profile on first use.

    ``register`` runs inside an empty isolated root and returns the profile id
    with that profile's session live, as the registration door leaves it. Its
    key derivations are real Argon2id through the exact custody codec, joined
    in this process rather than launched as a child, because the child is not
    what any copy goes on to test.
    """
    with bundled_indexed_authority().operation() as operation:
        generation = str(operation.generation)
    password = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    identity = (key, generation, sha256_hex(password.encode()))

    def build(origin: Path) -> tuple[str, bytes]:
        try:
            with isolated_profile_storage_root(tmp_path=origin), portable_password_custody():
                profile_id = register()
                session = current_active_bucket_session()
                if session is None or session.bucket_id != profile_id:
                    raise AssertionError("a sealed world's registration must leave its own session live")
                dek = bytes(session.dek)
                close_active_bucket_session()
        finally:
            dispose_engine()
        return profile_id, dek

    origin, (profile_id, dek) = sealed_tree(identity, build)
    return SealedProfileWorld(origin=origin, profile_id=profile_id, dek=dek)


def publish_world_session(world: SealedProfileWorld, *, profile_decode_context: ProfileDecodeContext) -> None:
    """Resume a copied world's profile in this process, as its registration left it."""
    publish_created_profile_session(
        bucket_id=world.profile_id,
        dek=world.dek,
        profile_decode_context=profile_decode_context,
    )


def storage_root_is_unused(storage_root: Path) -> bool:
    """Return whether a world may be copied into ``storage_root``: it holds no profile and no session is live."""
    if storage_root.name != _STORAGE_ROOT_NAME or current_active_bucket_session() is not None:
        return False
    buckets = storage_root / BUCKETS_DIRNAME
    return not buckets.exists() or not any(buckets.iterdir())


def copy_world_into_storage_root(
    world: SealedProfileWorld, storage_root: Path, *, profile_decode_context: ProfileDecodeContext
) -> None:
    """Copy a world into the isolated root already open around the caller and resume its profile."""
    copy_sealed_tree(world.origin, storage_root.parent)
    publish_world_session(world, profile_decode_context=profile_decode_context)


@contextmanager
def copied_profile_world(
    world: SealedProfileWorld, tmp_path: Path, *, profile_decode_context: ProfileDecodeContext
) -> Generator[tuple[Path, UUID]]:
    """Open this test's own copy of ``world`` with its profile resumed; the session ends with the scope."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    copy_sealed_tree(world.origin, tmp_path)
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        publish_world_session(world, profile_decode_context=profile_decode_context)
        try:
            yield root, UUID(world.profile_id)
        finally:
            close_active_bucket_session()
