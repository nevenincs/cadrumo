"""Concurrency and cold-install durability of the registry identity stamp.

Two properties the stamp must hold before anything is allowed to skip a walk on
the strength of it.

**Concurrent writers never expose a half-written stamp.** Several processes may
stamp the same location at once -- a release build racing a sibling, or xdist
workers sharing a tree -- and a reader that observed a torn file could either
crash or, far worse, parse a truncated digest and treat it as an identity. The
stamp is written through the atomic writer and read through a strict model, so
the intended outcome of any race is "a complete stamp, or nothing".

**A cold install works and stays read-only.** With no stamp present and a
package directory the process cannot write to, identity resolution must fall
back to the walk and must not attempt to create anything beside the tree. A
stamp is written by the BUILD; a runtime that tried to write one would both fail
on a read-only install and, on a writable one, mint an immutability claim for a
tree nobody proved.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ..... import __version__
from .....core.atomic_write import atomic_write_best_effort_text
from .....tests.attribute_scope import scoped_attribute
from .. import _loader_cache as loader_cache
from .._identity import (
    REGISTRY_IDENTITY_SCHEMA_VERSION,
    RegistryIdentityOrigin,
    RegistryIdentityStamp,
    read_registry_identity_stamp,
    registry_identity_stamp_location,
    resolve_registry_identity,
)
from .._loader import clear_fingerprint_cache
from .._loader_cache import _bundled_registry_root, _bundled_root_match

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SHORT_DIGEST = "a" * 8
_LONG_DIGEST = "b" * 4096
"""Two payloads of wildly different length.

Length is what makes a torn write DETECTABLE: writing same-sized payloads over
each other could interleave into something that still parses, and the test would
pass without exercising anything. A 4 KB payload replacing an 8-byte one cannot
be confused for it.
"""


def _registry_root(tmp_path: Path) -> Path:
    """Create a real registry root the stamp can sit beside."""
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)
    (root / "manifest.toml").write_text("modelos = []\n", encoding="utf-8")
    return root


@pytest.fixture
def durability_bundled_root_pointing_at() -> Iterator[Callable[[Path], None]]:
    """Redirect the bundled registry root at a caller-chosen real tree.

    Rebinds inside ``_loader_cache``, which holds its own reference to
    ``bundled_path``; patching ``core.resources`` would leave the predicate
    calling the original. Both memoised roots are cleared on repoint.
    """
    if not callable(loader_cache.bundled_path):
        raise AssertionError("the registry bundled-path resolver must remain callable")
    real_bundled_path = loader_cache.bundled_path
    target: dict[str, Path] = {}

    def _redirected(*parts: str) -> Path:
        if tuple(parts) == ("registry", "aeat") and "root" in target:
            return target["root"]
        return real_bundled_path(*parts)

    def _clear() -> None:
        _bundled_registry_root.cache_clear()
        _bundled_root_match.cache_clear()
        clear_fingerprint_cache()

    def _point_at(root: Path) -> None:
        target["root"] = root.resolve()
        _clear()

    with scoped_attribute(loader_cache, "bundled_path", _redirected):
        yield _point_at
    _clear()


def test_a_truncated_stamp_is_refused_rather_than_parsed(tmp_path: Path) -> None:
    """The anti-tautology half of the concurrency proof.

    If a truncated stamp could parse, the race test above would pass no matter
    how the writer behaved. This plants the exact damage a torn write produces
    and requires the read to refuse it.
    """
    root = _registry_root(tmp_path)
    location = registry_identity_stamp_location(root)
    whole = RegistryIdentityStamp(
        schema_version=REGISTRY_IDENTITY_SCHEMA_VERSION,
        package_version=__version__,
        tree_digest=_LONG_DIGEST,
        entry_count=len(_LONG_DIGEST),
    ).model_dump_json()
    atomic_write_best_effort_text(location, whole, encoding="utf-8")
    assert read_registry_identity_stamp(root) is not None, "sanity: the whole stamp must read back"

    location.write_text(whole[: len(whole) // 2], encoding="utf-8")

    assert read_registry_identity_stamp(root) is None


def test_a_cold_read_only_install_resolves_and_writes_nothing(
    tmp_path: Path,
    durability_bundled_root_pointing_at: Callable[[Path], None],
) -> None:
    """No stamp, no write permission beside the tree: the walk still answers.

    The runtime must never mint a stamp. Asserted by counting the files beside
    the registry root before and after, so a write is caught even on a platform
    where the read-only attribute below is advisory rather than enforced.
    """
    root = _registry_root(tmp_path)
    durability_bundled_root_pointing_at(root)
    package_dir = root.parent
    before = {path.name for path in package_dir.iterdir()}
    assert registry_identity_stamp_location(root).name not in before

    walked: list[Path] = []

    def _collect(target: Path) -> tuple[tuple[str, int, int, str], ...]:
        walked.append(target)
        return ((str(target / "manifest.toml"), 12, 34, ""),)

    identity = resolve_registry_identity(root, collect_fingerprints=_collect)

    assert identity.origin is RegistryIdentityOrigin.WALKED
    assert walked == [root.resolve()], "a cold install must fall back to the walk, once"
    assert {path.name for path in package_dir.iterdir()} == before, (
        "resolving identity wrote into the package directory; the stamp is the BUILD's to write"
    )
