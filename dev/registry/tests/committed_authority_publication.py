"""One canonical publication of the committed registry, shared by every test that reads it.

A full publication compiles and validates the registry in the canonical child
interpreter and then writes a ~120 MB indexed database, minutes of work that is
a pure function of its inputs. Every test that needs the committed authority as
a published generation therefore reads the one run artifact for its inputs
instead of producing its own.

The entry is keyed on the two digests the development tooling already derives:
the legal source identity the publisher records as the generation's
``logical_generation``, and the compiler source-tree digest the development
compile caches key on, because the database bytes also depend on the code that
built them. It is kept in the development cache, so it survives across runs
until either input changes. Admission re-reads the descriptor and checks the
database's size, its SHA-256 and the recorded generation: a hash of one file,
never a validation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.hashing import hash_file
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.tests.run_artifact import run_artifact
from dev.cache_root import dev_cache_dir

from ..compiler.authority import AuthoritySourceSet
from ..compiler.compiler_source_tree import compiler_source_tree_digest
from ..pipeline.authority_publication import authority_source_identity, publish_sqlite_authority_candidate

__all__ = [
    "AuthorityPublisher",
    "RunPublishedAuthority",
    "committed_authority_publication",
    "published_authority",
]

_KIND: Final = "authority"
_DESCRIPTOR_NAME: Final = "authority.current.json"

AuthorityPublisher = Callable[[AuthoritySourceSet, Path], object]
"""Publishes one source set into an empty destination directory."""


@dataclass(frozen=True, slots=True)
class RunPublishedAuthority:
    """An admitted publication of one source set: its descriptor and the identity it records."""

    descriptor_path: Path
    descriptor: AuthorityDescriptor
    source_identity_digest: str
    published_by_this_call: bool

    @property
    def root(self) -> Path:
        """The directory holding the descriptor and the one database it names."""
        return self.descriptor_path.parent


def committed_authority_publication() -> RunPublishedAuthority:
    """Return the publication of the committed bundled sources, publishing it only if no current one exists."""
    return published_authority(AuthoritySourceSet.bundled(), cache_root=dev_cache_dir("run-artifacts"))


def published_authority(
    sources: AuthoritySourceSet,
    *,
    cache_root: Path,
    publish: AuthorityPublisher | None = None,
) -> RunPublishedAuthority:
    """Admit the run artifact publishing ``sources``, publishing it once if none is current.

    A changed source set derives another identity and so another entry; an
    entry is admitted only for the identity it records.
    """
    identity = authority_source_identity(
        registry_root=sources.registry_root,
        source_root=sources.source_evidence_root,
        profile_schema_path=sources.profile_schema_path,
    )
    publisher = publish or _canonical_publish

    def publish_into(destination: Path) -> None:
        publisher(sources, destination)
        if _descriptor(destination, identity) is None:
            raise RegistryValidationError(
                "the run publication does not record the sources it was keyed on; "
                "the registry changed while it was being published"
            )

    artifact = run_artifact(
        _KIND,
        f"{identity[:16]}{compiler_source_tree_digest()[:8]}",
        publish=publish_into,
        verify=lambda root: _descriptor(root, identity) is not None,
        cache_root=cache_root,
    )
    descriptor = _descriptor(artifact.root, identity)
    if descriptor is None:
        raise RegistryValidationError(f"the run publication at {artifact.root} changed after admission")
    return RunPublishedAuthority(
        descriptor_path=artifact.root / _DESCRIPTOR_NAME,
        descriptor=descriptor,
        source_identity_digest=identity,
        published_by_this_call=artifact.published_by_this_call,
    )


def _canonical_publish(sources: AuthoritySourceSet, destination: Path) -> None:
    publish_sqlite_authority_candidate(
        registry_root=sources.registry_root,
        source_root=sources.source_evidence_root,
        profile_schema_path=sources.profile_schema_path,
        destination=destination,
    )


def _descriptor(root: Path, identity: str) -> AuthorityDescriptor | None:
    """Return the descriptor when it, its database bytes and its recorded generation all agree."""
    try:
        descriptor = AuthorityDescriptor.read(root / _DESCRIPTOR_NAME)
        digest, size = hash_file(root / descriptor.database)
    except (AuthorityStoreError, OSError, ValueError):
        return None
    if (digest, size) != (descriptor.database_sha256, descriptor.database_size):
        return None
    if descriptor.logical_generation != identity:
        return None
    return descriptor
