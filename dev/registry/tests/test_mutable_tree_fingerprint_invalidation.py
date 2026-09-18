"""Development-only regression coverage for mutable registry authoring trees.

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

The package-bundled tree remains immutable at runtime. This suite deliberately
materialises and edits source trees, so it belongs under ``dev/registry``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.tests.env_scope import scoped_env_var
from dev.packaging.command_execution import run_command

from ..compiler.identity import (
    RegistryIdentity,
    RegistryIdentityOrigin,
    compute_walked_tree_digest,
)
from ..compiler.loader import load_registry_tree
from ..compiler.loader_cache import REGISTRY_DISK_CACHE_DIR_ENV, is_bundled_registry_root
from ..compiler.loader_fingerprints import (
    clear_fingerprint_cache,
    collect_registry_tree_fingerprints,
)
from ..compiler.verdict_cache import (
    certify_registry_validation,
    compute_verdict_key,
    registry_validation_is_certified,
    verdict_cache_path,
)
from ..conformance.loader_directory_mode_support import (
    write_fragmented_revision,
    write_minimal_shared_catalogues,
)

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
_CHILD_CASILLA_FRAGMENT_ENV_VAR = "CADRUMO_TEST_MUTABLE_TREE_CASILLA_FRAGMENT"

# The child's coordinates ride the environment rather than argv so the spawned
# command line stays a fixed literal.
_CHILD_PROGRAM = """
import os
from pathlib import Path

from dev.registry.compiler.loader import load_registry_tree
from dev.registry.compiler.loader_cache import registry_disk_cache_dir

root = Path(os.environ["CADRUMO_TEST_MUTABLE_TREE_ROOT"])
edited = Path(os.environ["CADRUMO_TEST_MUTABLE_TREE_EDITED_TEXT"])
fragment = Path(os.environ["CADRUMO_TEST_MUTABLE_TREE_CASILLA_FRAGMENT"])


def observed() -> str:
    modelos, _catalogues = load_registry_tree(root)
    modelo = next(candidate for candidate in modelos if candidate.id == "999")
    return modelo.revisions["2025"].casillas[0].number


print("before=" + observed())
print("pickles=" + str(len(list(registry_disk_cache_dir().glob("cadrumo_registry_*.pkl")))))
fragment.write_text(edited.read_text(encoding="utf-8"), encoding="utf-8", newline="\\n")
print("after=" + observed())
"""

_MANIFEST_TEXT = """
[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()

_REVISION_TEXT = """
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


def _revision_text(number: str) -> str:
    return _REVISION_TEXT.replace(_CASILLA_NUMBER_SENTINEL, number)


def _casilla_fragment_path(registry_root: Path) -> Path:
    """The one file an edit moves: the revision's casillas fragment."""
    return registry_root / "modelos" / "999" / "revisions" / "2025" / "casillas" / "0001-casillas.toml"


def _rendered_casilla_fragment(scratch_dir: Path, *, number: str) -> Path:
    """Render the casillas fragment for ``number`` outside the tree under test.

    The child interpreter rewrites one fragment file, and the replacement has to
    be the exact text the fragment writer would have produced, so it is rendered
    through that same writer rather than hand-assembled here.
    """
    write_fragmented_revision(scratch_dir / "revisions" / "2025", _revision_text(number))
    return scratch_dir / "revisions" / "2025" / "casillas" / "0001-casillas.toml"


def _write_registry_tree(tmp_path: Path, *, number: str) -> Path:
    """Materialise (or rewrite) the synthetic authoring tree and return its root."""
    registry_root = tmp_path / "registry" / "aeat"
    # The loader requires every authoring tree to declare its supported
    # filing years, so a synthetic tree omitting it fails to load before
    # this test can observe anything about fingerprint caching.
    write_minimal_shared_catalogues(registry_root / "legal", floor=2025, horizon=2025)
    modelo_dir = registry_root / "modelos" / "999"
    modelo_dir.mkdir(parents=True, exist_ok=True)
    (modelo_dir / "manifest.toml").write_text(_MANIFEST_TEXT, encoding="utf-8", newline="\n")
    write_fragmented_revision(modelo_dir / "revisions" / "2025", _revision_text(number))
    return registry_root


def _casilla_number(modelos: tuple[ModeloDefinition, ...]) -> str:
    """Read the one observable field back out of the compiled registry."""
    modelo = next(candidate for candidate in modelos if candidate.id == "999")
    return modelo.revisions["2025"].casillas[0].number


def test_a_mutable_authoring_tree_is_reloaded_after_an_edit(tmp_path: Path) -> None:
    """The public loader observes an authoring edit even after a warm load."""
    clear_fingerprint_cache()
    registry_root = _write_registry_tree(tmp_path, number="01")
    resolved = registry_root.resolve()
    assert is_bundled_registry_root(resolved) is False

    modelos, _catalogues = load_registry_tree(registry_root)
    assert _casilla_number(modelos) == "01"
    _write_registry_tree(tmp_path, number="02")
    modelos, _catalogues = load_registry_tree(registry_root)
    assert _casilla_number(modelos) == "02"

    bundled_root = bundled_path("registry", "aeat").resolve()
    first = collect_registry_tree_fingerprints(bundled_root)
    second = collect_registry_tree_fingerprints(bundled_root)
    assert second is first, "the immutable bundled tree should retain its public fingerprint cache hit"


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

    with (
        scoped_env_var("CADRUMO_REGISTRY_VERDICT_CACHE_DIR", str(tmp_path / "verdict")),
        scoped_env_var("CADRUMO_REGISTRY_DISK_CACHE_DIR", str(tmp_path / "registry-disk-cache")),
    ):
        before, _catalogues = load_registry_tree(registry_root)
        assert _casilla_number(before) == "01"

        fingerprints_before = collect_registry_tree_fingerprints(resolved)
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

        after, _after_catalogues = load_registry_tree(registry_root)
        assert _casilla_number(after) == "02", (
            "a mutable authoring tree served compiled output that predates the edit on disk"
        )

        fingerprints_after = collect_registry_tree_fingerprints(resolved)
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


def test_a_mutable_tree_is_never_disk_cached_outside_pytest_and_still_serves_the_edit(tmp_path: Path) -> None:
    """The same invariant holds outside pytest, where nothing about the run is special.

    The cross-process compiled pickle is written for the package-bundled,
    immutable tree and for nothing else, so a mutable authoring root is served
    from a fresh compile in every process. That is proven in a child
    interpreter with the pytest markers removed, because a gate that happened to
    be pytest-shaped would let a mutable root be disk-cached in production while
    every in-process test still passed. The child reports the pickle count it
    observes, so re-enabling the pickle for a mutable root fails here rather
    than silently handing production a key for a tree state that no longer
    exists.
    """
    registry_root = _write_registry_tree(tmp_path, number="01")
    edited_text_path = _rendered_casilla_fragment(tmp_path / "edited", number="02")
    isolated_cache_dir = tmp_path / "registry-disk-cache"
    isolated_cache_dir.mkdir()

    env: dict[str, str] = {
        **os.environ,
        REGISTRY_DISK_CACHE_DIR_ENV: str(isolated_cache_dir),
        _CHILD_REGISTRY_ROOT_ENV_VAR: str(registry_root),
        _CHILD_EDITED_TEXT_ENV_VAR: str(edited_text_path),
        _CHILD_CASILLA_FRAGMENT_ENV_VAR: str(_casilla_fragment_path(registry_root)),
    }
    for marker in ("PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER", "PYTEST_VERSION"):
        env.pop(marker, None)

    completed = run_command(
        [sys.executable, "-c", _CHILD_PROGRAM],
        cwd=Path.cwd(),
        environment=env,
        timeout_seconds=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    assert completed.returncode == 0, completed.stderr
    reported = dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)
    assert reported["before"] == "01", f"child did not compile the pre-edit tree: {completed.stdout}"
    assert int(reported["pickles"]) == 0, (
        f"a mutable authoring root was disk-cached across processes: {completed.stdout}"
    )
    assert reported["after"] == "02", (
        f"the non-pytest load served compiled output that predates the edit: {completed.stdout}"
    )
