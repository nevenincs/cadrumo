"""Screen the test surface for gates that assert an empty result without scanning.

The shape this finds is the one that shipped twice in a single day: a gate walks
a corpus, asserts the violation set is empty, and would pass identically if the
walk had found nothing at all. A scan that cannot match reports exactly what a
clean tree reports, so nothing distinguishes the two states from the outside.

This is a SCREEN, not a gate. It produces a worklist to read, deliberately
over-reporting rather than under-reporting, because the two failure modes are not
symmetric: a false positive costs one read, and a false negative is the defect
itself. Two classes of expected false positive are known and are not bugs here.

- A legitimate absence assertion, where empty IS the property under test (a
  module proven deleted, a missing file proven to yield nothing).
- A corpus guarded OFF-MODULE, where emptiness of the shared substrate would
  fail loudly in a sibling gate that asserts a concrete known path is present.
  Such a guard counts, and a hit whose substrate carries one is not a finding.

That second exemption is SAME-CORPUS, not module-wide. A sibling asserting the
shared substrate is populated vouches only for scans over that same substrate;
it does not vouch for a scan over a corpus it never touched. Crediting it
module-wide was the original shape, and it silenced 110 functions tree-wide —
more than five times the worklist it was hiding them behind. The credit is
matched by name, so a scan reaching its corpus through a call rather than a bare
name gets none and is flagged, which is the safe direction.

What it does NOT see, stated so the coverage is not overread: it detects one of
the four known shapes only. A gate asserting a TOTAL where the property is a
DECOMPOSITION passes this screen, as does a pattern that compiles but cannot
match, and an escape that has outlived the construct justifying it. Those are
found by measuring a compiled pattern against a target and a near-miss, which is
per-gate work this screen cannot do for you.

Run as ``python -m dev.audit.vacuity_screen``.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8

#: Trees carrying gate modules. Both are required to exist: a screen that
#: silently walked nothing would be the very defect it hunts.
SCREENED_TREES = ("src/cadrumo/tests", "dev")

#: Both spellings of a function definition. A screen reading only the sync form
#: reports clean over every ``async def test_...`` in its corpus - not because
#: those tests prove they scanned anything, but because it never looked at
#: them. An instrument whose whole purpose is refusing silent green cannot
#: itself go silent on a whole function form.
_FUNCTION_DEFINITIONS: Final = (ast.FunctionDef, ast.AsyncFunctionDef)


#: Builtins whose no-argument call constructs an empty collection. ``set()`` has
#: no literal spelling at all, so a screen reading only literals is structurally
#: blind to the one empty collection Python forces you to write as a call.
_EMPTY_CONSTRUCTORS = frozenset({"set", "frozenset", "list", "tuple", "dict"})


def _is_empty_collection(node: ast.expr) -> bool:
    """True when ``node`` denotes an empty collection, literal or constructed."""
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    if isinstance(node, ast.Call):
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in _EMPTY_CONSTRUCTORS
            and not node.args
            and not node.keywords
        )
    return False


def asserts_emptiness(node: ast.AST) -> bool:
    """True when ``node`` asserts a collection is empty or a count is zero.

    Constructed empties count alongside literal ones. ``assert x == set()`` is
    the same claim as ``assert x == []`` and carries the same risk, but ``set()``
    is a call rather than a literal -- and an empty set has no literal spelling
    in Python, so a reader that matched only literals could never see it. That
    blind spot was found by this screen failing to flag a test in its own suite
    that used precisely that spelling.
    """
    if not isinstance(node, ast.Assert):
        return False
    test = node.test
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return True
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    right = test.comparators[0]
    if _is_empty_collection(right):
        return True
    return isinstance(right, ast.Constant) and right.value == 0


def proves_it_scanned(node: ast.AST) -> bool:
    """True when ``node`` asserts a lower bound, a membership, or a truthy corpus.

    Any of these fails when the walk returns nothing, which is the property that
    separates a measured clean result from a blind one.

    This predicate governs the MODULE-level exemption, so it must speak only to
    the shared substrate. Equality against a planted literal is deliberately NOT
    accepted here -- see :func:`asserts_a_non_empty_result` for why that is a
    function-scoped signal and why conflating the two silently weakens the
    screen.
    """
    if not isinstance(node, ast.Assert):
        return False
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        return isinstance(test.ops[0], ast.GtE | ast.Gt | ast.In)
    # Attribute and subscript reads count alongside bare names and calls: a
    # corpus is as often reached as ``Model.model_fields`` or ``data["rows"]``
    # as it is as a local. Omitting them made the screen re-flag a gate that
    # had just been guarded, which teaches its reader that guarding does not
    # clear the hit.
    return isinstance(test, ast.Name | ast.Call | ast.Attribute | ast.Subscript)


def _is_non_empty_literal(node: ast.expr) -> bool:
    """True when ``node`` is a literal no empty walk could have produced."""
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return bool(node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.keys)
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and node.value != 0
    )


def asserts_a_non_empty_result(node: ast.AST) -> bool:
    """True when ``node`` asserts a call produced a specific non-empty value.

    This is what makes a paired detector control not vacuous. A function
    asserting ``detector(planted) == ["a.b"]`` alongside
    ``detector(clean) == []`` is the anti-tautology proof itself: the empty
    assertion is the quiet half of a control, not an unguarded corpus scan.
    Without this distinction the screen flagged every such pair in the tree --
    14 of 22 entries on the worklist -- burying the genuine findings under the
    tests that do the most to prevent the defect being screened for.

    Deliberately FUNCTION-scoped, and deliberately excluded from
    :func:`proves_it_scanned`. Accepting it there would let a literal-input
    control satisfy the module-level exemption and silence every genuine corpus
    scan in the same file. That is not hypothetical: doing exactly that
    suppressed a real finding in the locale-honesty module, whose controls run
    on planted dictionaries while its sibling gates walk four shipped
    catalogues. Proving a detector works says nothing about whether the corpus
    it is pointed at exists.

    Conservative about what counts as non-empty. A bare string comparison is
    excluded even though it also proves execution, because over-accepting
    produces this screen's dangerous error -- real vacuity left unflagged --
    while under-accepting only produces noise.
    """
    if not isinstance(node, ast.Assert):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and _is_non_empty_literal(test.comparators[0])
    )


def with_called_helpers(body: list[ast.AST], helpers: Mapping[str, list[ast.AST]]) -> list[ast.AST]:
    """Return ``body`` plus the bodies of same-module helpers it calls.

    A proof of scan is often best placed at the corpus SOURCE rather than at each
    consumer: three gates walk one ``_markdown_docs()`` helper, so guarding the
    helper means a fourth consumer added later inherits the proof instead of
    forgetting it. Reading only the test body punishes exactly that shape, and a
    screen that re-flags a gate after it has been correctly guarded teaches its
    reader that guarding is pointless.

    One level, and only helpers the test actually calls. Following the call graph
    transitively would drift back toward the module-wide credit this screen
    deliberately replaced, where a proof anywhere in a file silenced every scan
    in it.
    """
    called = {node.func.id for node in body if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    extended = list(body)
    for name in sorted(called & set(helpers)):
        extended.extend(helpers[name])
    return extended


def referenced_names(nodes: list[ast.AST]) -> frozenset[str]:
    """Return every bare name the nodes read, as a proxy for the corpus in play."""
    return frozenset(node.id for node in nodes if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load))


def module_proofs_by_corpus(parsed: ast.AST) -> list[frozenset[str]]:
    """Return, per module-level proof-of-scan, the corpus names it vouches for.

    A module-level proof is credited to a sibling only when the two speak about
    the same corpus. That is the distinction between the guard the screen
    sanctions and the laundering it must not perform.

    Crediting a proof to the WHOLE module was the original shape, and it silences
    a scan over a corpus the proof never touched: one ``assert len(PAGES) >= 100``
    vouches for a sibling walking ``CATALOGUES``, which nothing has established is
    non-empty. Same-corpus credit keeps the sanctioned case — the sibling that
    asserts the shared substrate is populated — while refusing the unrelated one.

    Name-level, not dataflow. A scan reaching its corpus through a call rather
    than a bare name gets no credit and is flagged, which is the safe direction:
    this screen's dangerous error is real vacuity left unflagged, and its cheap
    error is one extra read.
    """
    proofs: list[frozenset[str]] = []
    for node in ast.walk(parsed):
        if not isinstance(node, _FUNCTION_DEFINITIONS):
            continue
        for statement in ast.walk(node):
            if proves_it_scanned(statement) and isinstance(statement, ast.Assert):
                proofs.append(referenced_names(list(ast.walk(statement))))
    return proofs


def _tracked_test_paths(root: Path) -> frozenset[str]:
    """Return the repository-tracked paths under the screened trees.

    ``scanned`` is the denominator of the vacuity proportion, so an untracked
    tree inflates it silently: the screen reports a healthier ratio while
    walking files no reviewer can act on.  An interrupted benchmark run leaves
    a gitignored copy of the whole source tree under ``dev``, which is exactly
    that failure.  Absence of git is raised rather than degraded to a
    filesystem walk, because a silent fallback restores the defect.
    """
    listed = subprocess.run(  # noqa: S603  # fixed read-only git subcommand assembled only by this module
        ("git", "ls-files", "-z", "--", *SCREENED_TREES),  # noqa: S607  # repository tool is fixed
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return frozenset(entry for entry in listed.split(chr(0)) if entry)


def screen(root: Path) -> tuple[int, list[tuple[str, str, int]], list[str]]:
    """Return the modules screened, the flagged functions, and what could not be read.

    A module that fails to parse used to increment ``scanned`` and then be
    skipped, so it landed in the denominator as though it had been screened
    clean - a file the screen could not read at all, counted as evidence of
    health. That is the same inflation this module's header warns about for an
    untracked tree, arriving through a different door.

    It is reported separately rather than folded into the findings: failing to
    parse is a different condition from asserting nothing, and one number
    answering two questions is what this screen exists to stop.
    """
    flagged: list[tuple[str, str, int]] = []
    unreadable: list[str] = []
    tracked = _tracked_test_paths(root)
    scanned = 0
    for tree in SCREENED_TREES:
        base = root / tree
        if not base.is_dir():
            raise SystemExit(f"screened tree is missing, so the result would be meaningless: {base}")
        for path in scan_directory(base, pattern="test_*.py", recursive=True, prune_directories=("__pycache__",)):
            if path.relative_to(root).as_posix() not in tracked:
                continue
            try:
                source = path.read_text(encoding=_UTF_8)
            except OSError as exc:
                # NOT the `unreadable` channel. A file that fails to parse is a
                # persistent fact about that file, and reporting it leaves the rest
                # of the census sound. A file the walk listed and the read cannot
                # reach means the tree moved underneath this walk, so `scanned` is
                # a denominator over a population that no longer exists -- the same
                # inflation the missing-tree refusal above already refuses to serve.
                moved = (
                    f"screened tree changed under the walk at {path}: {exc}. "
                    "The scanned count would answer for a population that no longer exists."
                )
                raise SystemExit(moved) from exc
            try:
                parsed = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                unreadable.append(path.relative_to(root).as_posix())
                continue
            scanned += 1
            proofs = module_proofs_by_corpus(parsed)
            helpers = {
                node.name: list(ast.walk(node))
                for node in ast.walk(parsed)
                if isinstance(node, _FUNCTION_DEFINITIONS) and not node.name.startswith("test_")
            }
            for func in ast.walk(parsed):
                if not isinstance(func, _FUNCTION_DEFINITIONS) or not func.name.startswith("test_"):
                    continue
                body = list(ast.walk(func))
                if not any(asserts_emptiness(n) for n in body):
                    continue
                if any(proves_it_scanned(n) for n in with_called_helpers(body, helpers)):
                    continue
                names = referenced_names(body)
                if any(proof & names for proof in proofs):
                    continue
                if any(asserts_a_non_empty_result(n) for n in body):
                    continue
                flagged.append((path.relative_to(root).as_posix(), func.name, func.lineno))
    return scanned, flagged, unreadable


def main() -> int:
    """Print the worklist. Always exits 0 -- this reports, it does not gate."""
    root = REPO_ROOT
    scanned, flagged, unreadable = screen(root)

    if scanned == 0:
        raise SystemExit("screened zero modules; the result would be meaningless")

    print(f"screened {scanned} test modules under {', '.join(SCREENED_TREES)}")
    print(f"flagged {len(flagged)} empty-assert functions with no proof they scanned anything\n")
    if unreadable:
        print(f"{len(unreadable)} module(s) could not be parsed and were NOT screened:")
        for name in sorted(unreadable):
            print(f"  {name}")
        print("")
    for path, func, line in sorted(flagged):
        print(f"{path}:{line}  {func}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
