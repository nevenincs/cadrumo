"""Canonical registry-tree identity: the one answer to "which tree is this?".

Every consumer derives tree identity HERE and nowhere else -- the authority's
in-process cache key, the loader's compiled-artefact key, the validation-verdict
match, and the release build's stamper. A second derivation of the digest, the
stamp filename, or the stamp location is what lets a build and a runtime
disagree about which tree they are looking at, so there is exactly one of each
and the development test tree's registry-identity enrolment gate proves no
other exists across the repository.

Identity has two ORIGINS, and the distinction is the whole point:

* **stamped** -- an installed, immutable registry tree carries a stamp written
  beside it by the release build. Its identity is read from one small JSON file:
  no directory walk, no per-file stat, no content hashing. An installed wheel's
  registry cannot change, so re-deriving its identity per process re-proves a
  fact the build already established.
* **walked** -- an authoring or editable tree has no stamp, because nothing
  stamps into a source checkout. Its files genuinely change, so its identity is
  the complete per-file fingerprint walk, exactly as before. Nothing about the
  authoring path is weakened by this module.

The stamp is a sibling of the registry root, never inside it, so its own
presence is not walked by the fingerprint it describes -- the same placement
rule :func:`~domain.calculations.registry._verdict_cache.shipped_verdict_location`
follows, and for the same reason.

The stamp is a statement of FACT, not a grant of permission: it says "the tree
at this root is exactly this", never "this tree is valid". What consumes it
decides what that identity permits. A stamp is honoured only for the
package-bundled root AND only when its schema and package version match the
running package; anything else falls back to the full walk. Per
``no-legacy-compatibility`` the stamp is derived and rebuildable: a mismatch
falls back and recomputes, and no shape but the current one is ever read.

See Also:
    :func:`~domain.calculations.registry.loader_cache.is_bundled_registry_root`
        Why a bundled root is not by itself an immutability claim, and why stamp
        presence is the discriminator this module adds on top of it.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

from pydantic import BaseModel

from .... import __version__
from ....core.external_constants import UTF_8_ENCODING
from ....core.models import STRICT_FROZEN_CONFIG
from .loader_cache import is_bundled_registry_root

FingerprintTuples = tuple[tuple[str, int, int, str], ...]
"""``(path, size, mtime_ns, content_digest)`` loader tuples, exactly as collected for the cache key."""

REGISTRY_IDENTITY_STAMP_FILENAME = "aeat-registry-identity.json"
"""The sole filename of the shipped identity stamp. Never spelled anywhere else."""

REGISTRY_IDENTITY_SCHEMA_VERSION = "registry-identity-v1"
"""Bumped when the stamp's shape changes; a foreign version falls back to the walk."""

_WALKED_DIGEST_LABEL = b"registry-identity-walked-v1"

_LOGGER = logging.getLogger(__name__)


class RegistryIdentityOrigin(StrEnum):
    """How a :class:`RegistryIdentity` was obtained."""

    STAMPED = "stamped"
    WALKED = "walked"


class RegistryIdentityStamp(BaseModel):
    """The release build's factual record of which registry tree it packaged.

    Carries no verdict and no validity claim. ``entry_count`` is diagnostic --
    it makes a truncated or wrong-tree stamp legible in a bug report without
    costing a walk to read.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: str
    package_version: str
    tree_digest: str
    entry_count: int


@dataclass(frozen=True, slots=True, eq=False)
class RegistryIdentity:
    """One registry tree's identity, and how it was established.

    ``fingerprints`` is empty for a stamped identity: the point of the stamp is
    that the tuples were never collected. A consumer that needs per-file tuples
    must therefore ask whether the identity is stamped rather than assuming the
    sequence is populated.

    Hashes and compares on ``digest`` alone so it can key a cache directly. The
    digest already folds every fingerprint field, so equality is unweakened;
    what is avoided is re-hashing the whole corpus on every cache lookup, which
    is the cost that made a tuple-keyed cache pay for the tree once per probe.
    """

    digest: str
    origin: RegistryIdentityOrigin
    fingerprints: FingerprintTuples

    @override
    def __hash__(self) -> int:
        return hash(self.digest)

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, RegistryIdentity) and self.digest == other.digest

    @property
    def is_stamped(self) -> bool:
        """Whether this identity came from a shipped stamp rather than a walk."""
        return self.origin is RegistryIdentityOrigin.STAMPED


def registry_identity_stamp_location(registry_root: Path) -> Path:
    """Return the identity-stamp file location for ``registry_root``.

    A sibling of the root, never inside it, so the stamp is not walked by the
    fingerprint it describes. Shared by the release build (which writes here)
    and the runtime read, so the two cannot disagree about where it lives.

    Returns:
        The stamp path beside ``registry_root``.
    """
    return registry_root.parent / REGISTRY_IDENTITY_STAMP_FILENAME


def compute_walked_tree_digest(fingerprints: Iterable[Iterable[object]]) -> str:
    """Digest the complete fingerprint tuples into a walked-tree identity.

    Folds every field of every tuple, so any content, size, mtime or path change
    anywhere in the tree yields a different identity -- the complete-tree
    invariant the registry authority flow requires. Costs no filesystem calls:
    the caller has already paid for the walk that produced ``fingerprints``.

    Typed as a bare iterable-of-iterables rather than :data:`FingerprintTuples`:
    the fold below reads every field of every entry generically (``str(field)``)
    with no positional or count assumption, so the wider, honest type is the one
    this function actually relies on. Every real caller still passes
    :data:`FingerprintTuples`, which satisfies this parameter.

    Returns:
        The hex SHA-256 identity of the walked tree.
    """
    hasher = hashlib.sha256()
    hasher.update(_WALKED_DIGEST_LABEL)
    for entry in fingerprints:
        for field in entry:
            hasher.update(str(field).encode("utf-8"))
            hasher.update(b"\x1f")
        hasher.update(b"\x1e")
    return hasher.hexdigest()


def read_registry_identity_stamp(registry_root: Path) -> RegistryIdentityStamp | None:
    """Read the shipped identity stamp for ``registry_root``, or ``None``.

    ``None`` for an absent, unreadable, foreign, schema-mismatched or
    version-mismatched stamp -- every one of which means "fall back to the
    walk", never "serve a degraded identity". Strict-parsed, so a stamp carrying
    an unexpected field is refused rather than partially honoured.

    Returns:
        The parsed stamp when it describes this package's tree, else ``None``.
    """
    path = registry_identity_stamp_location(registry_root)
    if not path.is_file():
        return None
    try:
        stamp = RegistryIdentityStamp.model_validate_json(path.read_text(encoding=UTF_8_ENCODING))
    except Exception:
        _LOGGER.debug("Ignoring unreadable or foreign registry identity stamp at %s; walking", path, exc_info=True)
        return None
    if stamp.schema_version != REGISTRY_IDENTITY_SCHEMA_VERSION:
        return None
    if stamp.package_version != __version__:
        return None
    return stamp


def stamped_cache_key_tuples(identity: RegistryIdentity) -> FingerprintTuples:
    """Return the fingerprint-shaped cache key for a STAMPED identity.

    Caches downstream of this module are keyed on fingerprint tuples, and a
    stamped identity deliberately has none -- not collecting them is the saving.
    This projects the stamp's digest into one synthetic entry so those caches
    keep their existing key type while keying on the identity that actually
    describes the tree. It lives here, beside the digest derivations, so no
    consumer invents its own placeholder shape.

    Raises:
        ValueError: When ``identity`` was walked, which has real tuples and must
            use them; a synthetic key there would collapse every distinct
            authoring tree onto one cache entry.

    Returns:
        A one-entry tuple carrying the stamped digest.
    """
    if not identity.is_stamped:
        raise ValueError("stamped_cache_key_tuples requires a stamped identity; a walked one carries real tuples")
    return ((f"{REGISTRY_IDENTITY_STAMP_FILENAME}:{identity.digest}", 0, 0, identity.digest),)


def resolve_registry_identity(
    registry_root: Path,
    *,
    collect_fingerprints: Callable[[Path], FingerprintTuples],
) -> RegistryIdentity:
    """Resolve one tree's identity, preferring a shipped stamp over a walk.

    A stamp is honoured only when ``registry_root`` is the package-bundled root
    AND a schema- and version-matching stamp sits beside it. The bundled-root
    test alone is NOT sufficient -- under an editable install it is true of the
    live source directory, which is edited constantly -- and the stamp alone is
    not either, since a stamp could be planted beside an arbitrary tree. Both
    together mean "the build packaged this exact tree", which is the claim.

    ``collect_fingerprints`` is injected rather than imported so this module
    stays free of a loader import edge and so a test can prove the walk is NOT
    taken on the stamped path by passing a collector that raises.

    Returns:
        The stamped identity when one applies, else the walked identity.
    """
    resolved = registry_root.resolve()
    if is_bundled_registry_root(resolved):
        stamp = read_registry_identity_stamp(resolved)
        if stamp is not None:
            return RegistryIdentity(
                digest=stamp.tree_digest,
                origin=RegistryIdentityOrigin.STAMPED,
                fingerprints=(),
            )
    fingerprints = collect_fingerprints(resolved)
    return RegistryIdentity(
        digest=compute_walked_tree_digest(fingerprints),
        origin=RegistryIdentityOrigin.WALKED,
        fingerprints=fingerprints,
    )


__all__ = [
    "REGISTRY_IDENTITY_SCHEMA_VERSION",
    "REGISTRY_IDENTITY_STAMP_FILENAME",
    "FingerprintTuples",
    "RegistryIdentity",
    "RegistryIdentityOrigin",
    "RegistryIdentityStamp",
    "compute_walked_tree_digest",
    "read_registry_identity_stamp",
    "registry_identity_stamp_location",
    "resolve_registry_identity",
    "stamped_cache_key_tuples",
]
