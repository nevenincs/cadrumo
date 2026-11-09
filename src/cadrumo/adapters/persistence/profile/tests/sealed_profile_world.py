"""Reuse a built profile world by copying its settled bytes.

Registering a profile launches a KDF child and publishes a capsule, and most
tests that do so are about something else. A profile world is therefore built
once per test run through the real door, closed so its bytes are at rest, and
published through the run-wide artifact cache; every worker verifies it and
each test receives its own filesystem copy: a mutation, a journal write or a
session in one copy reaches no other.

Three rules keep a copy equivalent to the world it came from:

* Copies share the world's profile identity, so nothing a copy does may be
  addressed by the profile alone outside its own root. A sign-in receipt's
  keychain entry is addressed by the profile and that sign-in's random session
  identity, and a copy publishes its session without minting a receipt, so
  concurrent copies in several workers never meet in the keychain.
* The whole tree is copied, because custody material need not sit under the
  storage root. Only the runtime coordination directory stays behind: the
  installation records in it pin the origin's physical identity, and a copy is
  another root that installs its own on first use.
* A copy opens under the same authority generation and password as its origin.
* A copy is never taken on a clock earlier than the instant its world was
  sealed. A world's records carry the clock that registered it, and the key
  names the registration's inputs but not that clock, so a copy taken under an
  earlier frozen clock would date its next record update before the record
  was created; the copy is refused with the remedy instead.

A copy resumes through :func:`publish_created_profile_session`, the publication
registration and login share, from the key the build proved, so no password
derivation runs. A test whose subject is registration, login or custody keeps
the production door: nothing here replaces those paths for it, and a password
sign-in on a copy works because the copy holds the real wrapped key.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Generator, Hashable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast
from uuid import UUID

from .....application.user_profile.login_session import publish_created_profile_session
from .....core.config import load_settings
from .....core.errors.hierarchy import CadrumoError
from .....core.hashing import sha256_hex
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from .....core.time.clock import now
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....tests.run_artifact import file_inputs_digest, run_artifact, run_artifact_root
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
    "derived_profile_world",
    "publish_world_session",
    "sealed_profile_world",
    "sealed_tree",
    "storage_root_is_unused",
]

#: The directory an isolated world opens its storage root beneath.
_STORAGE_ROOT_NAME = "cadrumo-storage"

_TREES: dict[Hashable, tuple[Path, object]] = {}
_TREE_HOLDERS: list[TemporaryDirectory[str]] = []

_WORLD_KIND = "sealed-profile-world"
_WORLD_TREE = "tree"
_WORLD_RECORD = "world.json"
#: Every key is its own world rather than a newer version of one, so a run keeps all it publishes.
_WORLD_RETAIN = 4096
_WORLDS: dict[str, SealedProfileWorld] = {}


@dataclass(frozen=True, slots=True)
class SealedProfileWorld:
    """One worker's settled world: its bytes at rest, the key its registration proved and when it was sealed."""

    origin: Path
    profile_id: str
    dek: bytes = field(repr=False)
    sealed_at: datetime


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


def _register_world(tree: Path, register: Callable[[], str]) -> tuple[str, bytes]:
    """Register one profile into the empty ``tree`` and leave its bytes at rest."""
    try:
        with isolated_profile_storage_root(tmp_path=tree), portable_password_custody():
            profile_id = register()
            session = current_active_bucket_session()
            if session is None or session.bucket_id != profile_id:
                raise AssertionError("a sealed world's registration must leave its own session live")
            dek = bytes(session.dek)
            close_active_bucket_session()
    finally:
        dispose_engine()
    return profile_id, dek


def _tree_files(tree: Path) -> list[Path]:
    return [path for path in tree.rglob("*") if path.is_file()]


def _tree_digest(tree: Path) -> str:
    return file_inputs_digest(_WORLD_KIND, tree, _tree_files(tree))


def _read_world(entry: Path) -> SealedProfileWorld | None:
    """Return the world an entry holds when its record names its tree's exact bytes."""
    try:
        record = json.loads((entry / _WORLD_RECORD).read_text(encoding="utf-8"))
        tree = entry / _WORLD_TREE
        if not isinstance(record, dict) or record.get("tree") != _tree_digest(tree):
            return None
        return SealedProfileWorld(
            origin=tree,
            profile_id=str(record["profile_id"]),
            dek=bytes.fromhex(record["dek"]),
            sealed_at=datetime.fromisoformat(record["sealed_at"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def sealed_profile_world(key: Hashable, register: Callable[[], str]) -> SealedProfileWorld:
    """Return this run's world for ``key``, registering its one profile on first use anywhere in the run.

    ``register`` runs inside an empty isolated root and returns the profile id
    with that profile's session live, as the registration door leaves it. Its
    key derivations are real Argon2id through the exact custody codec, joined
    in this process rather than launched as a child, because the child is not
    what any copy goes on to test. ``key`` must name every input ``register``
    depends on; it is identified by its ``repr`` together with the authority
    generation and password a copy opens under.

    The world's synthetic key is recorded beside its tree, because a copy is
    resumed from it in whichever worker takes the copy; the wrapped key it
    unlocks opens under the public development test password anyway.
    """
    with bundled_indexed_authority().operation() as operation:
        generation = str(operation.generation)
    password = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    digest = sha256_hex(repr((key, generation, sha256_hex(password.encode()))).encode())[:32]
    return _published_world(digest, lambda tree: _register_world(tree, register))


def derived_profile_world(
    base: SealedProfileWorld,
    key: Hashable,
    seed: Callable[[UUID], None],
    *,
    profile_decode_context: ProfileDecodeContext,
) -> SealedProfileWorld:
    """Return this run's world holding ``base`` after ``seed`` ran on it, seeding on first use anywhere in the run.

    ``seed`` receives the profile id inside its own copy of ``base`` with the
    session resumed, exactly as a test's copy starts, and writes through the
    real doors; the result is sealed as a world of its own, so a case that
    needs "the profile after seed X" copies it instead of repeating the seed.
    ``key`` must name every input ``seed`` depends on. Only a seed whose result
    is identical for every case belongs here; a case that needs a distinct
    seed runs it on its own copy.
    """
    digest = sha256_hex(repr((base.origin.parent.name, base.profile_id, key)).encode())[:32]

    def build(tree: Path) -> tuple[str, bytes]:
        try:
            with copied_profile_world(base, tree, profile_decode_context=profile_decode_context) as (_, profile_id):
                seed(profile_id)
        finally:
            dispose_engine()
        return base.profile_id, base.dek

    return _published_world(digest, build)


def _published_world(digest: str, build: Callable[[Path], tuple[str, bytes]]) -> SealedProfileWorld:
    """Return the run's verified world ``digest``, building it into an empty tree on first use anywhere in the run."""
    known = _WORLDS.get(digest)
    if known is not None and known.origin.is_dir():
        return known

    def publish(staging: Path) -> None:
        tree = staging / _WORLD_TREE
        tree.mkdir()
        profile_id, dek = build(tree)
        record = {
            "profile_id": profile_id,
            "dek": dek.hex(),
            "sealed_at": now().isoformat(),
            "tree": _tree_digest(tree),
        }
        (staging / _WORLD_RECORD).write_text(json.dumps(record), encoding="utf-8")

    def verify(entry: Path) -> bool:
        return _read_world(entry) is not None

    try:
        cache_root = run_artifact_root()
    except RuntimeError:
        # Outside a test run there is no run to share with, so the process keeps its own.
        holder = TemporaryDirectory(prefix="sealed-world-")
        _TREE_HOLDERS.append(holder)
        cache_root = Path(holder.name)
    artifact = run_artifact(
        _WORLD_KIND, digest, publish=publish, verify=verify, cache_root=cache_root, retain=_WORLD_RETAIN
    )
    world = _read_world(artifact.root)
    if world is None:
        raise CadrumoError(f"the sealed profile world {digest} changed after it was verified")
    _WORLDS[digest] = world
    return world


def _refuse_copy_before_seal(world: SealedProfileWorld) -> None:
    """Refuse a copy of ``world`` taken on a clock earlier than the instant it was sealed."""
    current = now()
    if current < world.sealed_at:
        raise AssertionError(
            f"this sealed profile world was sealed at {world.sealed_at.isoformat()}, but the clock now reads "
            f"{current.isoformat()}, so its profile record would be updated before it was created; register "
            "the frozen-clock test's profile under its own label or world key so its world is sealed under that clock"
        )


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
    _refuse_copy_before_seal(world)
    copy_sealed_tree(world.origin, storage_root.parent)
    publish_world_session(world, profile_decode_context=profile_decode_context)


@contextmanager
def copied_profile_world(
    world: SealedProfileWorld, tmp_path: Path, *, profile_decode_context: ProfileDecodeContext
) -> Generator[tuple[Path, UUID]]:
    """Open this test's own copy of ``world`` with its profile resumed; the session ends with the scope."""
    _refuse_copy_before_seal(world)
    tmp_path.mkdir(parents=True, exist_ok=True)
    copy_sealed_tree(world.origin, tmp_path)
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        publish_world_session(world, profile_decode_context=profile_decode_context)
        try:
            yield root, UUID(world.profile_id)
        finally:
            close_active_bucket_session()
