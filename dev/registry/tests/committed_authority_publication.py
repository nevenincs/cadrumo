"""One canonical publication of the committed registry, shared by every test that reads it.

A full publication compiles and validates the registry in the canonical child
interpreter and then writes a ~120 MB indexed database, minutes of work that is
a pure function of its inputs. Every test that needs the committed authority as
a published generation therefore reads one publication per distinct input
instead of producing its own.

The publication is keyed on the two digests the development tooling already
derives: the legal source identity the publisher records as the generation's
``logical_generation``, and the compiler source-tree digest the development
compile caches key on, because the database bytes also depend on the code that
built them. It lives under the development cache root, so it is shared by every
xdist worker and survives across runs until either input changes. The first
process to need it publishes under an exclusive lock; the others wait for that
lock and then admit the result. Admission re-reads the descriptor and checks the
database's size, its SHA-256 and the recorded generation, which costs a hash of
one file rather than a validation.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.hashing import hash_file
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
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

_CACHE_NAME: Final = "published-authority"
_DESCRIPTOR_NAME: Final = "authority.current.json"
_PUBLICATION_WAIT_SECONDS: Final = 1800.0
"""How long a worker waits for the one publishing worker; a full publication takes minutes."""
_PUBLICATION_POLL_SECONDS: Final = 0.5
_RETAINED_PUBLICATIONS: Final = 3
"""Entries kept beside a fresh publication, so a concurrent run on older inputs keeps its own."""

AuthorityPublisher = Callable[[AuthoritySourceSet, Path], object]
"""Publishes one source set into a destination directory."""


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
    return published_authority(AuthoritySourceSet.bundled(), cache_root=dev_cache_dir(_CACHE_NAME))


def published_authority(
    sources: AuthoritySourceSet,
    *,
    cache_root: Path,
    publish: AuthorityPublisher | None = None,
) -> RunPublishedAuthority:
    """Admit the cached publication of ``sources``, or publish it once under the cache lock.

    A changed source set derives another identity and so another entry; an
    entry is never admitted for any identity but the one it records.
    """
    identity = authority_source_identity(
        registry_root=sources.registry_root,
        source_root=sources.source_evidence_root,
        profile_schema_path=sources.profile_schema_path,
    )
    root = cache_root / f"{identity[:16]}-{compiler_source_tree_digest()[:12]}"
    descriptor_path = root / _DESCRIPTOR_NAME
    admitted = _admit(descriptor_path, identity)
    if admitted is not None:
        return admitted
    cache_root.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(
        cache_root / root.name,
        timeout=_PUBLICATION_WAIT_SECONDS,
        retry_backoff=_PUBLICATION_POLL_SECONDS,
    ):
        admitted = _admit(descriptor_path, identity)
        if admitted is not None:
            return admitted
        # A partial entry left by an interrupted publication is never admitted;
        # the publisher's content-addressed install replaces or reuses its bytes.
        (publish or _canonical_publish)(sources, root)
        published = _admit(descriptor_path, identity)
        if published is None:
            raise RegistryValidationError(
                "the run publication does not record the sources it was keyed on; "
                "the bundled registry changed while it was being published"
            )
        _retire_older_publications(cache_root, current=root)
    return RunPublishedAuthority(
        descriptor_path=published.descriptor_path,
        descriptor=published.descriptor,
        source_identity_digest=identity,
        published_by_this_call=True,
    )


def _canonical_publish(sources: AuthoritySourceSet, destination: Path) -> None:
    publish_sqlite_authority_candidate(
        registry_root=sources.registry_root,
        source_root=sources.source_evidence_root,
        profile_schema_path=sources.profile_schema_path,
        destination=destination,
    )


def _admit(descriptor_path: Path, identity: str) -> RunPublishedAuthority | None:
    """Return the entry when its descriptor, database bytes and recorded generation all agree."""
    try:
        descriptor = AuthorityDescriptor.read(descriptor_path)
        digest, size = hash_file(descriptor_path.parent / descriptor.database)
    except (AuthorityStoreError, OSError, ValueError):
        return None
    if (digest, size) != (descriptor.database_sha256, descriptor.database_size):
        return None
    if descriptor.logical_generation != identity:
        return None
    return RunPublishedAuthority(
        descriptor_path=descriptor_path,
        descriptor=descriptor,
        source_identity_digest=identity,
        published_by_this_call=False,
    )


def _retire_older_publications(cache_root: Path, *, current: Path) -> None:
    """Remove all but the most recent entries; one another process still reads is left for later."""
    entries = sorted(
        (entry for entry in cache_root.iterdir() if entry.is_dir() and entry != current),
        key=lambda entry: entry.stat().st_mtime,
        reverse=True,
    )
    for entry in entries[_RETAINED_PUBLICATIONS - 1 :]:
        shutil.rmtree(entry, ignore_errors=True)
