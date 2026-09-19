"""Stage the published registry authority into an isolated build root.

Every packaging lane builds from an isolated copy of the enumerated tree rather
than the live one, so a peer's concurrent edit cannot land inside a build in
flight. That enumeration is :func:`dev.source_tree.repository_files`, which is
the working tree minus what the repository's ``.gitignore`` files exclude —
deliberately, so a checker built on it cannot be blinded by an ignore rule.

The published authority is generated output *and* shipped runtime input. It
lives in a gitignored ``.authority/`` directory precisely so the repository does
not carry ~80 MB of regenerated binary in its history, which means the
enumeration correctly omits it and a snapshot alone produces a build root that
can only build an authority-less distribution. The enumeration is right and the
build root is incomplete; this module closes that gap explicitly rather than by
weakening the ignore-honouring seam every other consumer depends on.

The pair is staged back to ``.authority/`` in the destination, not to the
published path under ``src``. Staging it under ``src`` would make the copies
enumerable in the staged tree, so the content digest of the snapshot would no
longer equal the digest of the origin it was taken from — the drift check in
``dev/packaging/release_cohort.py`` exists to catch exactly that and would abort
the release. Staging to the ignored location leaves both enumerations equal.

Selection is descriptor-driven: the descriptor and the one database it names.
A directory copy would also carry the publication lock sidecar, which is
retained by design after every publish and says nothing about whether a lock is
held, a superseded database whose retirement was deferred because a reader held
it open, and any ``authority-candidate-*`` directory a publication in flight is
staging. None of those belong in a build root.

See Also:
    :func:`stage_published_authority`
        Copies the selected pair into a snapshot taken by
        :func:`dev.source_tree.snapshot`.
    :func:`authoring_authority_root`
        Resolves where a working tree keeps its published authority.
    :func:`dev.packaging.lane_verification_core.build_root_snapshot`
        The shared staging entry point that applies this module.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

__all__ = [
    "AUTHORING_AUTHORITY_DIRECTORY",
    "AUTHORITY_ROOT_ENV",
    "authoring_authority_root",
    "stage_published_authority",
]

#: Overrides where a working tree keeps its published authority. Unset, the
#: authority is read from :data:`AUTHORING_AUTHORITY_DIRECTORY` at the root.
AUTHORITY_ROOT_ENV: Final[str] = "CADRUMO_AUTHORITY_ROOT"

#: The gitignored directory holding the published authority, relative to the
#: repository root. The build hook resolves the same location.
AUTHORING_AUTHORITY_DIRECTORY: Final[str] = ".authority"

_DESCRIPTOR_NAME: Final[str] = "authority.current.json"


def authoring_authority_root(repo_root: Path) -> Path:
    """Return the directory a working tree keeps its published authority in.

    The answer is a location, not a promise that it is populated: a checkout
    that has never published has none, and the caller reports that against its
    own contract rather than having an empty path substituted here.
    """
    override = os.environ.get(AUTHORITY_ROOT_ENV)
    if override:
        return Path(override)
    return repo_root / AUTHORING_AUTHORITY_DIRECTORY


def stage_published_authority(source_root: Path, destination_root: Path) -> tuple[Path, Path]:
    """Copy the descriptor-selected authority pair into a staged build root.

    Returns the staged descriptor and database. Raises when the source tree has
    no published authority, because a build root missing it yields a
    distribution that installs without the only registry payload a product
    process may consume — a failure that would otherwise surface as a confusing
    runtime refusal in a lane far from its cause.
    """
    source = authoring_authority_root(source_root)
    descriptor_source = source / _DESCRIPTOR_NAME
    if not descriptor_source.is_file():
        raise FileNotFoundError(
            f"no published registry authority to stage: expected a descriptor at {descriptor_source}. "
            f"Publish the authority, or point ${AUTHORITY_ROOT_ENV} at the directory holding it.",
        )
    selected = AuthorityDescriptor.read(descriptor_source)
    database_source = source / selected.database
    if not database_source.is_file():
        raise FileNotFoundError(f"authority descriptor selects a missing database: {database_source}")

    destination = destination_root / AUTHORING_AUTHORITY_DIRECTORY
    destination.mkdir(parents=True, exist_ok=True)
    descriptor_staged = destination / descriptor_source.name
    database_staged = destination / database_source.name
    shutil.copy2(descriptor_source, descriptor_staged)
    shutil.copy2(database_source, database_staged)
    return descriptor_staged, database_staged
