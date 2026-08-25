"""Import-edge integrity gate: a deletion that landed without its consumer sweep.

A deletion breaks an edge between two files, and the commit that lands it
contains only one end. The other end -- the consumer left pointing at nothing,
or the module left with nobody pointing at it -- lives in a file the commit
does not touch. No per-file check can see that, and a pre-commit hook scoped to
changed files structurally cannot: the file it would have to read is not in its
input. Both gates here therefore run over the complete first-party tree.

Two families, because the edge has two ends and a check that sees one reports
the split as clean half the time:

- **Family 8 (dangling first-party import targets).** An import naming a
  first-party module that no longer exists, or a symbol the target module no
  longer binds. Gated at HARD ZERO, with no named-exception set: unlike a
  private-import reach there is no reading under which importing something
  deleted is a considered exception.
- **Family 9 (orphaned modules).** A module nothing in the first-party tree
  reaches. Only the pure-re-export-bridge subset is gated, at hard zero -- such
  a module owns no behaviour, so once nothing imports it there is no reading
  under which it is dormant-but-intended. Modules with real definitions of
  their own are reported by the scanner and deliberately NOT gated here: a dead
  module and a module whose consumer has not been written yet are the same
  shape, and that judgement is not one a gate is entitled to make.

These do not duplicate the type checker, which computes the same import fact
tree-wide and is enrolled in both the pre-commit hook set and CI. They extract
it. That checker carries hundreds of unrelated diagnostics at rest, so a newly
dangling edge moves its verdict from red to red and nobody sees it; it reported
four live dangling imports on this tree and they shipped anyway. Scoped to the
one question that can sit at zero, the same fact becomes enforceable.

Coverage boundary, stated here because it is not discoverable from a green
run: family 8's export half declines to judge a PEP 562 lazy facade, whose
export set no AST walk can enumerate. Nineteen of the package's facades resolve
that way. Declining is correct -- guessing would report every lazily-resolved
export as dangling -- but an import of a dropped name from such a facade is not
covered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._paths import REPO_ROOT
from ..quality.import_hygiene_scan import (
    DanglingImportKind,
    discover_facades,
    find_dangling_first_party_imports,
    find_orphaned_modules,
    find_shim_modules,
    first_party_census_files,
    walk_module_imports,
)
from .test_import_hygiene_gate import _package_import_sites, _package_py_files, _plant_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# Family 8: dangling first-party import targets
# ---------------------------------------------------------------------------


def _scan_planted_dangling(root: Path, modules: dict[str, str]) -> list[object]:
    """Plant a synthetic ``cadrumo`` tree and return its dangling import edges."""
    planted = [_plant_module(root, rel, body) for rel, body in modules.items()]
    sites = [site for path in planted for site in walk_module_imports(path, src_root=root)]
    return list(find_dangling_first_party_imports(sites, src_root=root))


def test_family8_has_no_dangling_first_party_import_targets() -> None:
    """No import anywhere in the package may name a first-party target that is gone.

    This is the consumer end of a deletion that landed without its sweep. It
    is gated at hard zero rather than against a named set on purpose: unlike a
    private-import reach, there is no reading under which an import of a
    deleted module or a dropped export is a considered exception -- it is
    broken now, for whoever next imports the importing module.

    The whole-tree type checker computes the same fact and is enrolled in CI,
    but it carries hundreds of unrelated diagnostics at rest, so a new dangling
    edge changes its verdict from red to red. This gate holds a clean floor and
    therefore actually moves when the defect appears.
    """
    dangling = find_dangling_first_party_imports(_package_import_sites())

    rendered = [
        f"{d.importer_path}:{d.lineno} -> {d.target_mod}" + (f" :: {d.symbol}" if d.symbol else "") for d in dangling
    ]
    assert rendered == [], (
        "first-party import target(s) that no longer resolve — a deletion landed without its "
        "consumer sweep; fix the consumer or restore the export:\n  " + "\n  ".join(rendered)
    )


def test_family8_reports_a_planted_deleted_module(tmp_path: Path) -> None:
    """A consumer importing a module that does not exist is reported."""
    dangling = _scan_planted_dangling(
        tmp_path,
        {
            "cadrumo/__init__.py": "",
            "cadrumo/consumer.py": "from cadrumo.departed import Gone\n",
        },
    )

    assert [(d.target_mod, d.symbol, d.kind) for d in dangling] == [
        ("cadrumo.departed", None, DanglingImportKind.MISSING_MODULE)
    ]


def test_family8_reports_a_planted_dropped_export(tmp_path: Path) -> None:
    """A consumer importing a name the target module no longer binds is reported.

    The subtler half, and the one that reproduced on this tree: the module is
    still present, so nothing about the file layout looks wrong.
    """
    dangling = _scan_planted_dangling(
        tmp_path,
        {
            "cadrumo/__init__.py": "",
            "cadrumo/owner.py": "KEPT = 1\n",
            "cadrumo/consumer.py": "from cadrumo.owner import KEPT, REMOVED\n",
        },
    )

    assert [(d.target_mod, d.symbol, d.kind) for d in dangling] == [
        ("cadrumo.owner", "REMOVED", DanglingImportKind.MISSING_EXPORT)
    ]


def test_family8_declines_to_judge_a_lazily_resolved_facade(tmp_path: Path) -> None:
    """A PEP 562 facade binds names no AST walk can see, so it is not judged.

    The architecture rule sanctions lazy ``__getattr__`` resolution as an
    equal alternative to an eager facade. A detector that answered anyway
    would report every lazily-resolved export in the codebase as dangling,
    which is the failure mode that makes a gate get switched off.
    """
    dangling = _scan_planted_dangling(
        tmp_path,
        {
            "cadrumo/__init__.py": "",
            "cadrumo/lazy/__init__.py": "def __getattr__(name):\n    raise AttributeError(name)\n",
            "cadrumo/consumer.py": "from cadrumo.lazy import ResolvedAtRuntime\n",
        },
    )

    assert dangling == []


@pytest.mark.parametrize(
    ("binding", "symbol"),
    (
        pytest.param("PAIRED, OTHER = build()\n", "PAIRED", id="tuple-unpacking"),
        pytest.param("type Aliased = int\n", "Aliased", id="pep695-type-alias"),
        pytest.param("Annotated: int = 1\n", "Annotated", id="annotated-assignment"),
        pytest.param("for Looped in ():\n    pass\n", "Looped", id="for-target"),
        pytest.param("from other import Renamed as Local\n", "Local", id="import-alias"),
    ),
)
def test_family8_accepts_every_module_level_binding_form(tmp_path: Path, binding: str, symbol: str) -> None:
    """Each binding form below was measured as a live false positive first.

    A name bound by tuple unpacking or a PEP 695 ``type`` statement is as real
    as one bound by ``def``. An early build of this detector understood only
    ``Name`` assignment targets and reported eleven hits on this tree, seven of
    which were one tuple-unpacked pair of loader collectors. Each parameter
    here is one such shape, pinned so the surface walk cannot narrow again.
    """
    dangling = _scan_planted_dangling(
        tmp_path,
        {
            "cadrumo/__init__.py": "",
            "cadrumo/owner.py": binding,
            "cadrumo/consumer.py": f"from cadrumo.owner import {symbol}\n",
        },
    )

    assert dangling == []


def test_family8_accepts_a_submodule_imported_from_its_package(tmp_path: Path) -> None:
    """``from package import submodule`` binds a module, not a name in the body."""
    dangling = _scan_planted_dangling(
        tmp_path,
        {
            "cadrumo/__init__.py": "",
            "cadrumo/pkg/__init__.py": "",
            "cadrumo/pkg/leaf.py": "VALUE = 1\n",
            "cadrumo/consumer.py": "from cadrumo.pkg import leaf\n",
        },
    )

    assert dangling == []


# ---------------------------------------------------------------------------
# Family 9: orphaned modules
# ---------------------------------------------------------------------------


def _scan_planted_orphans(root: Path, modules: dict[str, str]) -> list[object]:
    """Plant a synthetic tree and return its orphaned modules."""
    planted = [_plant_module(root, rel, body) for rel, body in modules.items()]
    census = [(path, root) for path in planted]
    return list(find_orphaned_modules(planted, census, (), repo_root=root, src_root=root))


def test_family9_has_no_orphaned_reexport_bridges() -> None:
    """No pure re-export bridge may survive the loss of its last consumer.

    Scoped to the bridge subset, which the "no standing non-``__init__``
    re-export bridge modules" rule already forbids outright: such a module
    owns no behaviour, so once nothing imports it there is no reading under
    which it is dormant-but-intended, and it can be deleted on this evidence
    alone.

    Modules with real definitions of their own are reported by the scanner but
    NOT gated here. Two live ones exist and are owned by other lanes; more to
    the point, a dead module and a module whose consumer has not been written
    yet are the same shape, so that subset needs a per-module judgement this
    gate is not entitled to make.
    """
    orphans = find_orphaned_modules(
        _package_py_files(),
        first_party_census_files(),
        (
            shim.path
            for shim in find_shim_modules(_package_py_files(), discover_facades())
            if shim.reason == "pure_reexport_shape"
        ),
    )

    bridges = [o.path for o in orphans if o.is_reexport_surface]
    assert bridges == [], (
        "re-export bridge module(s) with no importer anywhere in the first-party tree — the "
        "bridge forwards nothing to nobody; delete it:\n  " + "\n  ".join(bridges)
    )


def test_family9_reports_a_planted_orphan(tmp_path: Path) -> None:
    """A module nothing reaches is reported; an imported one is not.

    Asserted as membership rather than as the whole list, because the consumer
    doing the importing has no importer of its own in a four-file tree and is
    therefore an orphan too — correctly, and irrelevantly to the claim here.
    """
    orphans = {
        o.path
        for o in _scan_planted_orphans(
            tmp_path,
            {
                "cadrumo/__init__.py": "",
                "cadrumo/reached.py": "VALUE = 1\n",
                "cadrumo/consumer.py": "from cadrumo.reached import VALUE\n",
                "cadrumo/abandoned.py": "def stranded():\n    return 1\n",
            },
        )
    }

    assert "cadrumo/abandoned.py" in orphans, f"the unreached module was not reported: {sorted(orphans)}"
    assert "cadrumo/reached.py" not in orphans, f"an imported module was reported as orphaned: {sorted(orphans)}"


def test_family9_counts_a_module_named_only_by_a_string(tmp_path: Path) -> None:
    """A lazy command table, a subprocess target and a path probe are all reach.

    Each of these three shapes reaches a live module through a string the
    import graph cannot follow, and each produced a false orphan on the real
    tree before it was counted. A false-orphan verdict is the dangerous
    direction: it is the one somebody acts on by deleting a working module.
    """
    orphans = {
        o.path
        for o in _scan_planted_orphans(
            tmp_path,
            {
                "cadrumo/__init__.py": "",
                "cadrumo/dotted_target.py": "VALUE = 1\n",
                "cadrumo/registered.py": "VALUE = 2\n",
                "cadrumo/probed.py": "VALUE = 3\n",
                "cadrumo/reacher.py": (
                    'SUBPROCESS = "cadrumo.dotted_target"\n'
                    'TABLE = (("app", "cmd", ".registered"),)\n'
                    'PROBE = "probed.py"\n'
                ),
            },
        )
    }

    named_by_a_string = {"cadrumo/dotted_target.py", "cadrumo/registered.py", "cadrumo/probed.py"}
    assert orphans & named_by_a_string == set(), (
        f"module(s) reached only through a string reported as orphaned: {sorted(orphans & named_by_a_string)}"
    )


def test_family9_excludes_the_shapes_reached_without_an_import(tmp_path: Path) -> None:
    """A package body, a ``-m`` entry point and pytest's path-loaded files are not orphans.

    Excluded by SHAPE, not by a per-module allowlist: a zero-importer verdict
    on any of these says nothing about whether it is live, so reporting them
    would be noise that has to be suppressed one name at a time.
    """
    orphans = _scan_planted_orphans(
        tmp_path,
        {
            "cadrumo/__init__.py": "",
            "cadrumo/__main__.py": "def main():\n    return 1\n",
            "cadrumo/conftest.py": "def fixture_root():\n    return 1\n",
            "cadrumo/test_something.py": "def test_it():\n    assert True\n",
        },
    )

    assert orphans == []


def test_family9_census_spans_the_whole_first_party_tree() -> None:
    """The reach census must cover every tree that can import the package.

    Modules can read as orphaned when the census is the package alone because
    their only importers live in development tooling. Scoping the census to the scanner's own subject is
    the exact mistake that turns this detector into a deletion hazard, so the
    census composition is asserted rather than assumed.
    """
    census_roots = {src_root for _path, src_root in first_party_census_files()}
    covered = {str(root).replace("\\", "/") for root in census_roots}

    assert any(c.endswith("/src") for c in covered), f"census omits the package source root: {sorted(covered)}"
    assert any(c == str(REPO_ROOT).replace("\\", "/") for c in covered), (
        f"census omits the development tooling tree: {sorted(covered)}"
    )
