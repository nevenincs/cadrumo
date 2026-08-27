"""A mutable authoring tree's compiled output may never predate a live edit.

The registry-tree fingerprint cache holds the COMPLETE tree fingerprint -- one
``(path, size, mtime_ns, content_digest)`` row per directory and per TOML file --
and that tuple is what keys the compiled-registry lru, the compiled disk pickle
and the persisted validation verdict. The only cheap freshness signal the cache
has is a directory walk, and writing to an existing file moves no
parent-directory stat, so a directory-level check cannot speak for the per-file
content digests the tuple carries. Serving such an entry hands every cache above
the loader a key describing a tree state that no longer exists.

These tests pin the invariant that closes that hole: a mutable authoring tree is
fingerprinted afresh on every call and is neither served from nor written to the
cache. They are deliberately independent of wall-clock timing -- the pre-edit
entry is planted with a live stamp, so it is maximally fresh by construction and
no sleep, TTL window or machine speed can make the proof vacuous.

The package-bundled tree keeps its declared window and is pinned separately by
:mod:`~domain.calculations.registry.tests.testloader_cache_isolation`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.loader import _load_registry_tree_cached, load_registry_tree
from cadrumo.domain.calculations.registry.loader_cache import is_bundled_registry_root
from cadrumo.domain.calculations.registry.loader_fingerprints import (
    _registry_fingerprint_cache,
    clear_fingerprint_cache,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .....core.config import override_settings
from .....core.resources import bundled_path
from .._loader_internals import (
    _collect_registry_directory_fingerprints,
    _collect_registry_tree_fingerprints,
    _collect_registry_tree_fingerprints_uncached,
)
from .._verdict_cache import (
    certify_registry_validation,
    compute_verdict_key,
    registry_validation_is_certified,
    verdict_cache_path,
)
from ..identity import RegistryIdentity, RegistryIdentityOrigin, compute_walked_tree_digest
from ..loader_cache import REGISTRY_DISK_CACHE_DIR_ENV_VAR

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _walked_identity(fingerprints: tuple[tuple[str, int, int, str], ...]) -> RegistryIdentity:
    """Build the walked identity the canonical resolver produces for a mutable tree."""
    return RegistryIdentity(
        digest=compute_walked_tree_digest(fingerprints),
        origin=RegistryIdentityOrigin.WALKED,
        fingerprints=fingerprints,
    )


_CASILLA_NUMBER_SENTINEL = "@@CASILLA_NUMBER@@"
_SUBPROCESS_TIMEOUT_SECONDS = 300
_CHILD_REGISTRY_ROOT_ENV_VAR = "CADRUMO_TEST_MUTABLE_TREE_ROOT"
_CHILD_EDITED_TEXT_ENV_VAR = "CADRUMO_TEST_MUTABLE_TREE_EDITED_TEXT"

# The child's coordinates ride the environment rather than argv so the spawned
# command line stays a fixed literal.
_CHILD_PROGRAM = """
import os
from pathlib import Path

from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.loader_cache import registry_disk_cache_dir

root = Path(os.environ["CADRUMO_TEST_MUTABLE_TREE_ROOT"])
edited = Path(os.environ["CADRUMO_TEST_MUTABLE_TREE_EDITED_TEXT"])


def observed() -> str:
    modelos, _catalogues = load_registry_tree(root)
    modelo = next(candidate for candidate in modelos if candidate.id == "999")
    return modelo.revisions["2025"].casillas[0].number


print("before=" + observed())
print("pickles=" + str(len(list(registry_disk_cache_dir().glob("cadrumo_registry_*.pkl")))))
(root / "modelos" / "999.toml").write_text(edited.read_text(encoding="utf-8"), encoding="utf-8", newline="\\n")
print("after=" + observed())
"""

_MODELO_TEXT = """
[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "01"
number = "@@CASILLA_NUMBER@@"
section = ["section"]
input_kind = "manual"
continuidad_id = "cont_01"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()


def _modelo_text(number: str) -> str:
    return _MODELO_TEXT.replace(_CASILLA_NUMBER_SENTINEL, number)


#: The one registry-wide declaration the loader requires of any tree.
_SUPPORTED_FILING_YEARS_TEXT = "[supported_filing_years]\nyears = [2025]\n"


def _write_registry_tree(tmp_path: Path, *, number: str) -> Path:
    """Materialise (or rewrite) the synthetic authoring tree and return its root."""
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    legal_dir.mkdir(parents=True, exist_ok=True)
    # The loader requires every authoring tree to declare its supported
    # filing years, so a synthetic tree omitting it fails to load before
    # this test can observe anything about fingerprint caching.
    (legal_dir / "supported-filing-years.toml").write_text(
        _SUPPORTED_FILING_YEARS_TEXT,
        encoding="utf-8",
        newline="\n",
    )
    modelos_dir = registry_root / "modelos"
    modelos_dir.mkdir(parents=True, exist_ok=True)
    (modelos_dir / "999.toml").write_text(_modelo_text(number), encoding="utf-8", newline="\n")
    return registry_root


def _casilla_number(modelos: tuple[ModeloDefinition, ...]) -> str:
    """Read the one observable field back out of the compiled registry."""
    modelo = next(candidate for candidate in modelos if candidate.id == "999")
    return modelo.revisions["2025"].casillas[0].number


def test_a_mutable_authoring_tree_leaves_no_fingerprint_cache_entry(tmp_path: Path) -> None:
    """Loading a mutable tree must not deposit an entry that a later call could be served.

    The structural half of the invariant, and the one that makes the behavioural
    half impossible to regress quietly: there is no entry to serve, so no
    freshness check has to be trusted. The bundled root is asserted alongside so
    the test cannot pass by the cache being globally inert.
    """
    clear_fingerprint_cache()
    registry_root = _write_registry_tree(tmp_path, number="01")
    resolved = registry_root.resolve()
    assert is_bundled_registry_root(resolved) is False

    modelos, _catalogues = load_registry_tree(registry_root)
    assert _casilla_number(modelos) == "01"
    assert resolved not in _registry_fingerprint_cache, (
        "a mutable authoring tree must not be written to the fingerprint cache"
    )

    bundled_root = bundled_path("registry", "aeat").resolve()
    _collect_registry_tree_fingerprints(bundled_root)
    assert bundled_root in _registry_fingerprint_cache, (
        "sanity: the bundled tree must still be cached, or the assertion above proves nothing"
    )


def test_a_mutable_tree_edit_is_seen_under_a_warm_verdict_and_warm_compiled_cache(tmp_path: Path) -> None:
    """The edit is served even with every warm artefact for the pre-edit tree present.

    Warm regime, built explicitly rather than assumed: a real green validation
    verdict is persisted on disk for the pre-edit fingerprint key, the compiled
    lru is confirmed to still hold the pre-edit payload under the pre-edit key,
    and the pre-edit fingerprint entry is planted with a live stamp so it is
    maximally fresh. Under a directory-only freshness check every one of those
    would combine to serve the superseded compile; the load must still return
    the edited value, and the persisted verdict must no longer certify the tree.
    """
    clear_fingerprint_cache()
    registry_root = _write_registry_tree(tmp_path, number="01")
    resolved = registry_root.resolve()

    with override_settings(
        cadrumo_validation_verdict_cache_dir=tmp_path / "verdict",
        cadrumo_registry_disk_cache_dir=tmp_path / "registry-disk-cache",
    ):
        before, _catalogues = load_registry_tree(registry_root)
        assert _casilla_number(before) == "01"

        fingerprints_before = _collect_registry_tree_fingerprints_uncached(resolved)
        directories_before = _collect_registry_directory_fingerprints(resolved)
        identity_before = _walked_identity(fingerprints_before)
        verdict_key_before = compute_verdict_key(
            identity_digest=identity_before.digest,
            source_evidence_fingerprints=(),
        )
        certify_registry_validation(resolved, verdict_key=verdict_key_before)
        assert verdict_cache_path(resolved).is_file(), "the warm regime requires a persisted verdict on disk"
        assert registry_validation_is_certified(
            resolved,
            verdict_key=verdict_key_before,
            identity=identity_before,
        ), "sanity: the freshly written verdict must certify the tree it was written for"

        _write_registry_tree(tmp_path, number="02")

        # The pre-edit compile is genuinely still warm: asking the compiled lru
        # for the pre-edit key returns it without recompiling, which is exactly
        # what a stale fingerprint would have handed the caller.
        warm_payload, _warm_catalogues = _load_registry_tree_cached(str(resolved), fingerprints_before)
        assert _casilla_number(warm_payload) == "01", "sanity: the pre-edit compile must still be warm in the lru"

        # Plant the maximally fresh pre-edit entry: this is exactly the tuple a
        # directory-only freshness check would have accepted a moment ago.
        _registry_fingerprint_cache[resolved] = (time.time(), directories_before, fingerprints_before)

        after, _after_catalogues = load_registry_tree(registry_root)
        assert _casilla_number(after) == "02", (
            "a mutable authoring tree served compiled output that predates the edit on disk"
        )

        fingerprints_after = _collect_registry_tree_fingerprints_uncached(resolved)
        assert fingerprints_after != fingerprints_before, (
            "sanity: the edit must move the complete tree fingerprint for this proof to mean anything"
        )
        identity_after = _walked_identity(fingerprints_after)
        assert identity_after.digest != identity_before.digest, (
            "sanity: the edit must move the tree IDENTITY, which is what every cache now keys on"
        )
        assert verdict_cache_path(resolved).is_file(), "the persisted verdict must still be on disk, merely unusable"
        assert not registry_validation_is_certified(
            resolved,
            verdict_key=compute_verdict_key(
                identity_digest=identity_after.digest,
                source_evidence_fingerprints=(),
            ),
            identity=identity_after,
        ), "the verdict persisted for the pre-edit tree must not certify the edited tree"


def test_a_mutable_tree_edit_is_seen_in_the_production_disk_cache_regime(tmp_path: Path) -> None:
    """The same invariant holds where the cross-process compiled pickle is live.

    Under pytest the disk pickle is deliberately gated off for a mutable root,
    so this half is proven in a child interpreter with the pytest markers
    removed -- the production regime, where ``load_registry_tree`` really does
    write and read the compiled pickle. The child asserts a pickle was written
    for the pre-edit tree before it edits, so the warm artefact is confirmed
    present rather than assumed.
    """
    registry_root = _write_registry_tree(tmp_path, number="01")
    edited_text_path = tmp_path / "edited-999.toml"
    edited_text_path.write_text(_modelo_text("02"), encoding="utf-8", newline="\n")
    isolated_cache_dir = tmp_path / "registry-disk-cache"
    isolated_cache_dir.mkdir()

    env: dict[str, str] = {
        **os.environ,
        REGISTRY_DISK_CACHE_DIR_ENV_VAR: str(isolated_cache_dir),
        _CHILD_REGISTRY_ROOT_ENV_VAR: str(registry_root),
        _CHILD_EDITED_TEXT_ENV_VAR: str(edited_text_path),
    }
    for marker in ("PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER", "PYTEST_VERSION"):
        env.pop(marker, None)

    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_PROGRAM],
        check=True,
        capture_output=True,
        env=env,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    reported = dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)
    assert reported["before"] == "01", f"child did not compile the pre-edit tree: {completed.stdout}"
    assert int(reported["pickles"]) == 1, (
        f"the production regime must have written a compiled pickle before the edit: {completed.stdout}"
    )
    assert reported["after"] == "02", (
        f"the production-regime load served compiled output that predates the edit: {completed.stdout}"
    )
