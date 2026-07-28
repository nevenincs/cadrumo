"""Dev-path isolation gate: the one-way ``src/cadrumo`` → ``dev/`` boundary.

``dev/`` is removable development scaffolding; ``src/cadrumo/`` is the shipped
application.  The dependency is strictly one-way:

* ``dev/`` imports from ``src/cadrumo`` through its public top-level facades.
* ``src/cadrumo/`` must never import ``dev.*`` and must never embed a path
  literal that reaches into the ``dev/`` tree at runtime.

This gate enforces both halves against **shipped modules** — the set that
lands in the installed wheel, read from the packaging config rather than
restated here.  Test trees are excluded from the wheel and sdist and may
freely use dev tooling (they encode "this suite requires the repo checkout
and the dev dependency group", which is always true and intended).  A shipped
module importing dev tooling raises ``ModuleNotFoundError`` for every
installed user; a shipped module reading a ``dev/`` path at runtime silently
fails the same way.

Single detector authority
-------------------------
Both detectors live in ``dev/import_hygiene_scan.py`` — Family 5 for the
``dev.*`` import half, Family 6 for the ``dev/`` path-reach half — and this
gate ASSERTS against them rather than carrying its own copy.  An earlier
revision re-implemented the import half inline, on the reasoning that a
boundary gate must not itself import ``dev.*``.  That reasoning does not hold:
this module is wheel-excluded, so its own imports have no bearing on the
shipped surface it measures, and a scanner's imports are not the thing the
boundary is about.  The duplication it produced had already drifted within a
single campaign — the shipped-``conftest.py`` case existed on one side only —
which is the concrete cost a second detector buys.  A silently forked
authority is worse than either alternative, so there is one.

What stays local here is the PROOF, not the detection: every firing and
silence proof below plants a synthetic module under an injectable root and
asserts what the shared detector returns for it.  That is the right division —
the detector is shared so it cannot fork, and the proofs are local so this
gate cannot pass while blind.

Anti-tautology coverage
-----------------------
Each of the two checks is proven by injecting a deliberate violation into a
temporary tree and asserting the scanner returns it.  Every detected *form* has
its own firing proof, and every near-miss the detector must stay silent on
(``/dev/tty``, a ``devengada`` Spanish stem, ``"".join``) has its own silence
proof — a firing proof alone cannot show the difference between a precise
detector and one that fires on everything.  A vacuity floor asserts the live
scan visited a realistic number of shipped modules so an empty-scan false-pass
can never read as a clean tree.

The standard this module holds itself to is stronger than "every form has a
test": **every discriminating branch of the shared detector must flip at least
one test here when it is removed.**  Form coverage alone does not deliver that.
Five branches have now been caught failing it while being individually
droppable, because the fixtures that exercised their neighbours produced the
same verdict with the branch gone.  Each has a proof written to isolate it:

* the ``join`` arity guard — a one-argument ``join`` whose sole argument is the
  bare ``"dev"`` constant;
* the newline rejection — a multi-line NON-docstring string, since docstring
  fixtures are skipped before the newline check is reached;
* the left-hand operand of a path join — a ``"dev" / root`` join;
* the requirement that an interpolation PRECEDE an f-string's constant tail —
  an f-string device path, ``f"/dev/null"``;
* the requirement that such a tail begin with a separator —
  ``f"{root}-sandbox/dev/notes.json"``, another tree's ``dev`` directory.

Two further branches survive a mutation with nothing red, and are kept as
declared redundancy rather than pinned: ``if not node.args`` in the call-join
reader was dead (``any`` over an empty sequence is already false) and has been
deleted, and the absolute-path guard in ``names_dev_directory`` is
defence-in-depth whose stated protection a different mechanism delivers — its
docstring now says so, so no future reader hunts for the fixture that proves
it.  When adding a branch to the detector, add the fixture that fails without
it — not merely one that covers the same form — or record in the detector why
no such fixture exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from dev.import_hygiene_scan import (
    DevPathForm,
    DevPathReachViolation,
    DevToolingImportViolation,
    find_dev_path_reach_violations,
    find_dev_tooling_import_violations,
    is_shipped_module,
    wheel_exclude_globs,
)

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------

_SRC_ROOT: Final[Path] = PROJECT_ROOT / "src"
_PKG_ROOT: Final[Path] = _SRC_ROOT / "cadrumo"

_UTF_8: Final[str] = "utf-8"

# Every shipped module must visit at least this many files before a hard-zero
# result is accepted.  Keeps an accidental empty-scan from reading as clean.
_VACUITY_FLOOR: Final[int] = 500

_TEST_TREE_EXCLUDES: Final[tuple[str, ...]] = (
    "src/cadrumo/tests",
    "src/cadrumo/tests/**",
    "src/cadrumo/**/tests",
    "src/cadrumo/**/tests/**",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _planted_module(root: Path, rel: str, body: str) -> Path:
    """Write a synthetic module at ``rel`` under ``root`` and return its path."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding=_UTF_8)
    return target


def _live_tree_scan_inputs() -> tuple[list[Path], list[Path], tuple[str, ...]]:
    """Return ``(all_py_files, shipped_subset, exclude_globs)`` for the real tree."""
    globs = wheel_exclude_globs()
    py_files = sorted(p for p in _PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    shipped = [p for p in py_files if is_shipped_module(p, src_root=_SRC_ROOT, exclude_globs=globs)]
    return py_files, shipped, globs


def _assert_not_vacuous(shipped: list[Path]) -> None:
    """Refuse a hard-zero result produced by a scan that visited almost nothing."""
    assert len(shipped) >= _VACUITY_FLOOR, (
        f"vacuity check: fewer than {_VACUITY_FLOOR} shipped modules were found under "
        f"{_PKG_ROOT} (found {len(shipped)}).  Either the packaging config changed or the "
        "scan resolved an empty tree; investigate before accepting a zero result."
    )


def _scan_planted_paths(
    tmp_path: Path,
    rel: str,
    body: str,
    *,
    excludes: tuple[str, ...] = (),
) -> list[DevPathReachViolation]:
    """Plant one module under ``tmp_path`` and return the dev-path reaches found in it."""
    planted = _planted_module(tmp_path, rel, body)
    return find_dev_path_reach_violations([planted], src_root=tmp_path, exclude_globs=excludes)


def _scan_planted_imports(
    tmp_path: Path,
    rel: str,
    body: str,
    *,
    excludes: tuple[str, ...] = (),
) -> list[DevToolingImportViolation]:
    """Plant one module under ``tmp_path`` and return the ``dev.*`` imports found in it."""
    planted = _planted_module(tmp_path, rel, body)
    return find_dev_tooling_import_violations([planted], src_root=tmp_path, exclude_globs=excludes)


# ---------------------------------------------------------------------------
# Live-tree gate: Check 1 — no shipped module imports dev.*
# ---------------------------------------------------------------------------


def test_no_shipped_module_imports_dev_tooling() -> None:
    """No shipped module under ``src/cadrumo`` may import ``dev.*``.

    ``dev/`` is development tooling absent from both the wheel and the sdist.
    A shipped module importing it raises ``ModuleNotFoundError`` for every
    installed user while resolving fine in the repo checkout — a defect no
    in-repository test run surfaces.

    Hard zero: no allowlist.  A new violation is fixed by moving what the
    shipped side needs under ``src/cadrumo``, never by recording an exception.
    """
    py_files, shipped, globs = _live_tree_scan_inputs()
    _assert_not_vacuous(shipped)

    violations = find_dev_tooling_import_violations(py_files, src_root=_SRC_ROOT, exclude_globs=globs)

    offenders = [
        f"{'[dynamic] ' if v.is_dynamic else ''}{v.importer_path}:{v.lineno} -> {v.target_mod}" for v in violations
    ]
    assert offenders == [], (
        "shipped module(s) under src/cadrumo import the unshipped dev/ tooling.  "
        "Move what the shipped side needs under src/cadrumo; do not add an allowlist:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Live-tree gate: Check 2 — no shipped module reaches a dev/ path
# ---------------------------------------------------------------------------


def test_no_shipped_module_reaches_a_dev_path() -> None:
    """No shipped module under ``src/cadrumo`` may build a path into ``dev/``.

    This is the metadata-loophole complement to the import check: a shipped
    module can reference dev/ artifacts through ``PROJECT_ROOT / "dev" /
    "baseline.json"`` without any ``import dev`` statement.  Both forms make the
    shipped module depend on development infrastructure that is absent from the
    installed wheel — the import check catches the code dependency; this check
    catches the data dependency.

    Hard zero: no allowlist.  A new violation is fixed by moving the artifact
    under ``src/cadrumo`` where it belongs.
    """
    py_files, shipped, globs = _live_tree_scan_inputs()
    _assert_not_vacuous(shipped)

    violations = find_dev_path_reach_violations(py_files, src_root=_SRC_ROOT, exclude_globs=globs)

    offenders = [f"{v.module_path}:{v.lineno} [{v.form}] -> {v.detail!r}" for v in violations]
    assert offenders == [], (
        "shipped module(s) under src/cadrumo build a path into the unshipped dev/ tree.  "
        "Move the artifact under src/cadrumo/_data/ or equivalent so the shipped side reads "
        "only its own tree; do not add an allowlist:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Anti-tautology: Check 1 — the import scanner MUST fire on a planted violation
# ---------------------------------------------------------------------------


def test_import_scanner_catches_planted_static_dev_import(tmp_path: Path) -> None:
    """A planted ``from dev.X import y`` in a shipped module MUST be detected.

    Without this proof the hard-zero assertion above is indistinguishable from
    a detector that cannot fire — the failure mode that lets a gate pass while
    blind to the thing it guards.
    """
    violations = _scan_planted_imports(
        tmp_path,
        "cadrumo/shipped_module.py",
        "from dev.registry.matrix import manager\n",
    )

    assert [(v.importer_path, v.target_mod, v.is_dynamic) for v in violations] == [
        ("cadrumo/shipped_module.py", "dev.registry.matrix", False)
    ], f"the scanner failed to catch a planted static dev import; it detected {violations!r}"


def test_import_scanner_catches_bare_dev_import(tmp_path: Path) -> None:
    """A bare ``import dev`` statement in a shipped module MUST be detected."""
    violations = _scan_planted_imports(tmp_path, "cadrumo/bare_import.py", "import dev\n")

    assert [v.target_mod for v in violations] == ["dev"], f"bare 'import dev' was not caught; violations={violations!r}"


def test_import_scanner_catches_planted_dynamic_dev_import(tmp_path: Path) -> None:
    """A ``importlib.import_module("dev...")`` literal in a shipped module MUST be caught.

    A dynamically-built module string is invisible to a naive AST import walk;
    this proves the dynamic-target branch fires on the literal-argument form.
    """
    violations = _scan_planted_imports(
        tmp_path,
        "cadrumo/dynamic_import.py",
        'import importlib\n\ndef load_manager():\n    return importlib.import_module("dev.registry.matrix.manager")\n',
    )

    dynamic_hits = [(v.importer_path, v.target_mod) for v in violations if v.is_dynamic]
    assert dynamic_hits == [("cadrumo/dynamic_import.py", "dev.registry.matrix.manager")], (
        f"dynamic dev import was not caught; all violations={violations!r}"
    )


def test_import_scanner_does_not_fire_on_excluded_test_module(tmp_path: Path) -> None:
    """The ruling proven: an identical import in an EXCLUDED test tree is NOT a violation.

    Pins the scope decision: test trees are excluded from the wheel/sdist and
    may legitimately import dev tooling (they run from the repo checkout).
    This very module is such a tree — it imports the scanner it asserts
    against.  If someone widens the family to test trees this test fails,
    forcing the change to be a deliberate ruling rather than a silent
    broadening.
    """
    violations = _scan_planted_imports(
        tmp_path,
        "cadrumo/tests/test_planted.py",
        "from dev.import_hygiene_scan import find_dev_tooling_import_violations\n",
        excludes=_TEST_TREE_EXCLUDES,
    )
    assert violations == [], (
        f"the import scanner fired on an excluded test module, contradicting its documented scope: {violations!r}"
    )


def test_import_scanner_does_not_fire_on_cadrumo_import(tmp_path: Path) -> None:
    """The scanner must not over-reach onto a legitimate ``cadrumo.*`` import."""
    violations = _scan_planted_imports(
        tmp_path,
        "cadrumo/clean_module.py",
        "from cadrumo.core import config\nfrom cadrumo.domain.calculations import registry\n",
    )
    assert violations == [], f"the import scanner fired on a legitimate cadrumo.* import: {violations!r}"


# ---------------------------------------------------------------------------
# Anti-tautology: Check 2 — the path scanner MUST fire on every planted form
# ---------------------------------------------------------------------------


def test_path_scanner_catches_planted_dev_path_literal(tmp_path: Path) -> None:
    """A ``"dev/some_file.json"`` string literal in a shipped module MUST be caught.

    Without this proof the hard-zero assertion above is indistinguishable from
    a detector that cannot fire — the failure mode that lets a gate pass while
    blind to the thing it guards.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/reads_dev_file.py",
        'from pathlib import Path\n\ndef load_baseline():\n    return Path("dev/import_hygiene_baseline.json").read_text()\n',
    )

    assert len(violations) == 1, f"expected exactly 1 dev-path reach; got {violations!r}"
    assert violations[0].module_path == "cadrumo/reads_dev_file.py"
    assert violations[0].form is DevPathForm.LITERAL
    assert violations[0].detail == "dev/import_hygiene_baseline.json"


def test_path_scanner_catches_relative_and_windows_separator_forms(tmp_path: Path) -> None:
    """``"./dev/"``, ``"../dev/"`` and the Windows ``"dev\\x"`` separator MUST be caught.

    The backslash form is the one a Windows-authored path literal takes; a
    scanner reading only ``/`` separators is blind to it on the platform this
    repository is developed on.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/relative_paths.py",
        "def load_a():\n"
        '    return open("./dev/some_config.json")\n'
        "def load_b():\n"
        '    return open("../dev/other_baseline.json")\n'
        "def load_c():\n"
        '    return open("dev\\\\windows_baseline.json")\n'
        "def load_d():\n"
        '    return open("..\\\\dev\\\\windows_parent.json")\n',
    )

    values = {v.detail for v in violations}
    assert values == {
        "./dev/some_config.json",
        "../dev/other_baseline.json",
        "dev\\windows_baseline.json",
        "..\\dev\\windows_parent.json",
    }, f"a relative or Windows-separator dev path was missed; violations={violations!r}"


def test_path_scanner_catches_project_root_anchored_join(tmp_path: Path) -> None:
    """``PROJECT_ROOT / "dev" / "file"`` MUST fire — this is the realistic violation.

    An earlier revision of this gate pinned this exact form as NOT a violation,
    on the reasoning that ``"dev"`` here is a bare segment rather than a
    ``"dev/"``-prefixed literal.  That reasoning inverted the risk: a bare
    ``open("dev/baseline.json")`` is CWD-relative and breaks on the first run
    from any other directory, so nobody writes it, while the
    ``PROJECT_ROOT``-anchored join works perfectly in the repo checkout and
    breaks only once installed as a wheel — silently, for users only.
    ``PROJECT_ROOT`` is exported from ``cadrumo.core.paths``, which this very
    module imports, so the form is one line away at all times.

    The scanner must therefore fire here, and this test is the pin that keeps
    it firing.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/anchored_join.py",
        "from cadrumo.core.paths import PROJECT_ROOT\n"
        "\n"
        'CONFORMANCE_BASELINE = PROJECT_ROOT / "dev" / "conformance_baseline.json"\n'
        "\n"
        "def load_baseline() -> str:\n"
        "    return CONFORMANCE_BASELINE.read_text(encoding='utf-8')\n",
    )

    assert len(violations) == 1, f"expected exactly 1 reach for the anchored join; got {violations!r}"
    assert violations[0].form is DevPathForm.PATH_JOIN, (
        f"the PROJECT_ROOT-anchored dev join was not reported as a path join: {violations!r}"
    )
    assert violations[0].lineno == 3


def test_path_scanner_catches_the_reversed_join_operand(tmp_path: Path) -> None:
    """``"dev" / root`` MUST fire — the segment can sit on either side of the join.

    ``Path.__rtruediv__`` makes a bare ``"dev"`` on the LEFT of the operator a
    valid join, so a detector reading only the right operand has a hole an
    author reaches by writing the expression the other way round.  Without this
    proof the left-operand branch is droppable: removing it flips no other test
    in this module, which is exactly how a preserved-but-unproven branch
    disappears in the next refactor.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/reversed_join.py",
        'from cadrumo.core.paths import PROJECT_ROOT\n\nBASELINE = "dev" / PROJECT_ROOT\n',
    )

    assert [v.form for v in violations] == [DevPathForm.PATH_JOIN], (
        f"a dev segment on the LEFT of a path join was missed; violations={violations!r}"
    )


def test_path_scanner_catches_call_assembled_dev_segment(tmp_path: Path) -> None:
    """``os.path.join``, the ``Path(...)`` factory and ``joinpath`` MUST all fire."""
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/call_joins.py",
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "def a(root):\n"
        '    return open(os.path.join(root, "dev", "baseline.json"))\n'
        "def b(root):\n"
        '    return Path(root, "dev", "worklist.json")\n'
        "def c(root):\n"
        '    return Path(root).joinpath("dev")\n',
    )

    assert [v.form for v in violations] == [DevPathForm.CALL_JOIN] * 3, (
        f"a call-assembled dev path segment was missed; violations={violations!r}"
    )
    assert sorted(v.lineno for v in violations) == [5, 7, 9]


def test_path_scanner_catches_fstring_composed_dev_path(tmp_path: Path) -> None:
    """An f-string composing a dev path MUST fire.

    ``f"{root}/dev/x.json"`` stores its segment as the constant
    ``"/dev/x.json"``, which starts with a separator and matches no ``dev/``
    prefix — invisible to a prefix-only scan.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/fstrings.py",
        "def a(root):\n"
        '    return open(f"{root}/dev/conformance_baseline.json")\n'
        "def b(name):\n"
        '    return open(f"dev/{name}.json")\n',
    )

    assert [v.form for v in violations] == [DevPathForm.FSTRING] * 2, (
        f"an f-string-composed dev path was missed; violations={violations!r}"
    )
    assert {v.detail for v in violations} == {"/dev/conformance_baseline.json", "dev/"}


# ---------------------------------------------------------------------------
# Anti-tautology: Check 2 — the near-misses the scanner MUST stay silent on
# ---------------------------------------------------------------------------


def test_path_scanner_does_not_fire_on_posix_device_paths(tmp_path: Path) -> None:
    """``/dev/tty`` and ``/dev/null`` are device nodes, NOT the repo dev tree.

    This is not hypothetical: shipped code at
    ``src/cadrumo/entrypoints/cli/_config/_secure_input.py`` opens ``/dev/tty``
    to read a secret without echo, and is correct to do so.  A substring match
    on ``/dev/`` would red this gate on sound code — and a gate that fires on
    correct code teaches the next author to weaken it.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/device_paths.py",
        "import sys\n"
        "\n"
        "def tty_path() -> str:\n"
        '    return "CONOUT$" if sys.platform == "win32" else "/dev/tty"\n'
        "def null_sink():\n"
        '    return open("/dev/null", "w")\n',
    )

    assert violations == [], f"the scanner fired on a POSIX device path, which is not the dev tree: {violations!r}"


def test_path_scanner_does_not_fire_on_an_fstring_device_path(tmp_path: Path) -> None:
    """An f-string device path MUST stay silent, and only one branch keeps it so.

    The plain-constant device fixture above cannot reach the f-string arm at
    all, so it says nothing about it — and an f-string tail carries the device
    path in exactly the shape the tail reader accepts: ``"/dev/null"`` splits
    to an empty leading segment followed by ``dev``.  What holds it out is the
    requirement that an interpolation PRECEDE the constant, which no other
    fixture here exercises: ``f"{root}/dev/x.json"`` fires by design, and the
    near-miss f-strings interpolate a non-dev tail.  Drop the
    preceding-interpolation requirement and this is the only test that reds.

    Both forms are planted: the fully-constant ``f"/dev/null"`` (still parsed
    as an f-string node, never folded to a plain constant) and the realistic
    ``f"/dev/{name}"``, whose interpolation sits AFTER the device path and so
    must not license it either.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/fstring_device_paths.py",
        'def null_sink():\n    return open(f"/dev/null", "w")\ndef terminal(name):\n    return open(f"/dev/{name}")\n',
    )

    assert violations == [], f"the scanner fired on an f-string POSIX device path: {violations!r}"


def test_path_scanner_does_not_fire_on_a_mid_path_dev_segment_after_an_interpolation(tmp_path: Path) -> None:
    """``f"{root}-sandbox/dev/notes.json"`` names another tree's ``dev``, and MUST stay silent.

    The f-string tail reader accepts a constant only where the interpolation IS
    the root — the tail has to begin with a separator, so ``dev`` sits directly
    beneath it.  Here the interpolation is glued into the tail's own first
    segment, so the path resolves under a sibling of the repo root and its
    ``dev`` directory is one level below a different tree.

    That empty-leading-segment requirement is droppable without this fixture:
    every other f-string case here either has no ``dev`` segment at all or
    already begins with the separator, so each returns the same verdict with
    the requirement gone.  This is the one plant that distinguishes it.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/sibling_tree.py",
        'def sibling_notes(root):\n    return open(f"{root}-sandbox/dev/notes.json")\n',
    )

    assert violations == [], f"the scanner read another tree's dev/ directory as this repository's: {violations!r}"


def test_path_scanner_does_not_fire_on_spanish_stems_or_dev_substrings(tmp_path: Path) -> None:
    """``devengada``, ``devolucion``, ``device`` and ``dev.example.com`` MUST stay silent.

    The Spanish stems are pervasive in this codebase (IVA devengada, solicitud
    de devolucion).  A substring match on ``dev`` would fire on hundreds of
    correct sites; matching must be whole-path-segment.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/near_misses.py",
        'CUOTA = "iva/devengada/total.json"\n'
        'DEVOLUCION = "devolucion/pendiente.json"\n'
        'DEVICE = "device/serial.json"\n'
        'LOCALE_KEY = "cli.config.dev.help"\n'
        'DOCS_URL = "https://dev.example.com/guide"\n'
        "\n"
        "def totals(root):\n"
        '    return root / "devengada" / "cuota.json"\n'
        "def refund(root):\n"
        '    return open(f"{root}/devolucion.json")\n',
    )

    assert violations == [], f"the scanner fired on a 'dev' substring that is not a dev/ path segment: {violations!r}"


def test_path_scanner_does_not_fire_on_string_join(tmp_path: Path) -> None:
    """``"".join(parts)`` is a string operation, not a path assembly."""
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/string_joins.py",
        'def flatten(parts):\n    return "".join(parts)\ndef label():\n    return ", ".join(["dev", "prod"])\n',
    )

    assert violations == [], f"the scanner read a string join as a path assembly: {violations!r}"


def test_path_scanner_does_not_fire_on_a_single_argument_join_of_dev(tmp_path: Path) -> None:
    """``"x".join("dev")`` is a string operation, and the arity guard is what proves it.

    This is the case the arity-of-two-or-more guard exists for, and the only
    one that distinguishes it: a one-argument ``join`` whose sole argument IS
    the bare ``"dev"`` constant.  The two-argument path-assembly forms are
    permitted by the guard anyway and the ``"".join(parts)`` case has no bare
    ``"dev"`` argument to match, so neither can tell whether the guard is
    present.  Deleting the guard flips no other test in this module — this one
    is the pin that makes it load-bearing.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/single_arg_join.py",
        'def label():\n    return "x".join("dev")\n',
    )

    assert violations == [], f"a one-argument string join was read as a path assembly: {violations!r}"


def test_path_scanner_does_not_fire_on_multiline_prose_outside_a_docstring(tmp_path: Path) -> None:
    """A multi-line string naming ``dev/`` is prose, even when it is not a docstring.

    The docstring skip only reaches module, class and function docstrings.  A
    multi-line assertion message or module constant that happens to begin with
    a dev path is prose too, and the newline rejection is what carries that —
    a path literal never contains a line break.  Deleting that rejection flips
    no other test here, because every other prose fixture is a docstring and
    is skipped before the check is reached.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/multiline_prose.py",
        'MESSAGE = "dev/import_hygiene_baseline.json\\nis maintained by the dev-side scanner"\n',
    )

    assert violations == [], f"the scanner read multi-line prose as a dev-tree dependency: {violations!r}"


def test_path_scanner_does_not_fire_on_prose_naming_dev_tooling(tmp_path: Path) -> None:
    """A docstring naming a ``dev/`` tool is documentation, not a runtime read.

    Shipped modules legitimately cite the dev tooling that produced a shipped
    sidecar (the corpus extractor, the terminology handbook authoring tool).
    The planted docstrings here BEGIN with the ``dev/`` path, so the
    docstring-skip is load-bearing rather than incidentally satisfied by the
    leading-segment rule.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/prose.py",
        '"""dev/corpus/extract_manual_corpus_text.py produces the shipped sidecar."""\n'
        "\n"
        "def parse(text):\n"
        '    """dev/docs/terminology_handbook.py authors the compiled fragments."""\n'
        "    return text\n",
    )

    assert violations == [], f"the scanner read documentation prose as a dev-tree dependency: {violations!r}"


def test_path_scanner_does_not_fire_on_excluded_test_module(tmp_path: Path) -> None:
    """Every violating form in an EXCLUDED test module is NOT a violation.

    Test trees ship in neither the wheel nor the sdist and legitimately read
    dev/ baselines from the repo checkout — this module's own siblings do.  If
    someone widens the family to the excluded trees this test fails, forcing the
    change to be a deliberate ruling rather than a silent broadening.
    """
    violations = _scan_planted_paths(
        tmp_path,
        "cadrumo/tests/test_with_dev_path.py",
        "from pathlib import Path\n"
        "from cadrumo.core.paths import PROJECT_ROOT\n"
        "\n"
        'BASELINE = Path("dev/import_hygiene_baseline.json")\n'
        'ANCHORED = PROJECT_ROOT / "dev" / "import_hygiene_baseline.json"\n'
        "\n"
        "def composed(root):\n"
        '    return f"{root}/dev/size_budget_baseline.json"\n',
        excludes=_TEST_TREE_EXCLUDES,
    )

    assert violations == [], f"the path scanner fired on an excluded test module: {violations!r}"


# ---------------------------------------------------------------------------
# Both families on one module: the shipped package-root conftest.py
# ---------------------------------------------------------------------------


def test_both_families_catch_a_planted_shipped_conftest(tmp_path: Path) -> None:
    """A package-root ``conftest.py`` SHIPS, so both a ``dev.`` import and a dev path fire.

    ``src/cadrumo/conftest.py`` is a real wheel member: it carries no ``tests/``
    path component, so the packaging excludes never shed it.  A name-based
    "anything called conftest is test infrastructure" scope would silently
    exempt a genuinely shipped module.

    This case was the first observed drift between the two implementations of
    the import half, back when there were two — proven on one side and absent
    from the other.  With a single detector authority it can no longer be
    proven for one half and not the other, and this test holds both halves to
    it on the same file.
    """
    body = 'import dev\nfrom cadrumo.core.paths import PROJECT_ROOT\n\nBASELINE = PROJECT_ROOT / "dev" / "x.json"\n'
    planted = _planted_module(tmp_path, "cadrumo/conftest.py", body)

    import_violations = find_dev_tooling_import_violations(
        [planted], src_root=tmp_path, exclude_globs=_TEST_TREE_EXCLUDES
    )
    path_violations = find_dev_path_reach_violations([planted], src_root=tmp_path, exclude_globs=_TEST_TREE_EXCLUDES)

    assert [(v.importer_path, v.target_mod) for v in import_violations] == [("cadrumo/conftest.py", "dev")], (
        f"a shipped package-root conftest.py importing dev/ must be caught; detected {import_violations!r}"
    )
    assert [(v.module_path, v.form) for v in path_violations] == [("cadrumo/conftest.py", DevPathForm.PATH_JOIN)], (
        f"a shipped package-root conftest.py reaching a dev/ path must be caught; detected {path_violations!r}"
    )
