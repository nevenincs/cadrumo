"""No production guard is disabled by a constant condition.

Proving a gate bites means breaking the guard it protects and watching the test
red. The safe way is to patch from outside the repository, but a guard written
as an inline conditional cannot be reached that way -- the only way to weaken it
is to edit the file, and this is a shared worktree where a peer's sweep can
commit the working tree at any moment.

That happened. A sweep captured ``application/user_profile/capsule_record.py``
carrying ``if False:`` in place of the assertion that an initial profile record
is exactly revision one without a predecessor, and a live integrity guard shipped
disabled. It was caught by hand, not by any gate.

Nothing in the toolchain catches it: ruff accepts ``if False:`` and ``if True:``
without complaint (verified against the project's own configuration), and the
weakened module imports, type-checks and passes every test that does not
specifically exercise the disabled branch. That is what makes this shape
dangerous rather than merely wrong -- a swept syntax error is loud and fixed in
minutes, while a swept constant condition is valid Python that reds nothing.

The gate is hard-cut with no allowlist because the tree contains no such
condition anywhere, production or test: the worklist is recomputed from the AST
on every run and can only ever be empty. ``while True:`` is untouched -- it is
the idiomatic infinite loop and appears throughout the substrate's retry and
poll paths. A FALSY ``while`` is dead code and is refused with the ``if``.
"""

from __future__ import annotations

import ast

import pytest

from .inventory import package_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Source of a guard neutered exactly the way the swept probe neutered one.
_NEUTERED_SAMPLE = "def guard(value):\n    if False:\n        raise ValueError('refused')\n"

#: Source carrying the shapes that must NOT be reported.
_LEGITIMATE_SAMPLE = (
    "from typing import TYPE_CHECKING\n"
    "def poll(stop):\n"
    "    while True:\n"
    "        if stop():\n"
    "            return\n"
    "    if TYPE_CHECKING:\n"
    "        pass\n"
)


def _is_neutered(node: ast.AST) -> bool:
    """Report whether ``node`` is a branch a literal already decided.

    An ``if`` whose test is a literal has no branch to take: the author either
    disabled the guarded code or forced it. A ``while`` on a falsy literal is a
    loop that never runs. ``while True:`` is deliberately excluded -- it is the
    ordinary way to write a loop that exits by ``return`` or ``break``.
    """
    if not isinstance(node, ast.If | ast.While):
        return False
    if not isinstance(node.test, ast.Constant):
        return False
    return not (isinstance(node, ast.While) and node.test.value)


def _neutered_conditions(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(line, source)`` for every condition a constant decides."""
    return [
        (node.lineno, ast.unparse(node.test))
        for node in ast.walk(tree)
        if _is_neutered(node) and isinstance(node, ast.If | ast.While)
    ]


def test_no_conditional_in_the_package_is_decided_by_a_constant() -> None:
    """DISCRIMINATING: the shape that shipped a disabled guard to main."""
    offenders = [
        f"{repo_relative(path)}:{line}: condition is always `{source}`"
        for path, tree in package_ast_items()
        for line, source in _neutered_conditions(tree)
    ]

    assert not offenders, (
        "these conditions are decided by a constant, so the branch they guard is "
        "unreachable or unconditional:\n  " + "\n  ".join(sorted(offenders)) + "\n"
        "If this appeared without you writing it, a sweep captured a probe mid-edit: "
        "restore the real condition rather than adding an exemption."
    )


def test_the_detector_reports_a_neutered_guard() -> None:
    """ANTI-TAUTOLOGY: proven without editing a tracked file.

    A detector that found nothing would pass the gate above against any tree at
    all. Driving it over a sample carrying the exact shape proves the emptiness
    is the tree's property and not the scanner's -- and does it without opening
    the very edit window this gate exists because of.
    """
    assert _neutered_conditions(ast.parse(_NEUTERED_SAMPLE)) == [(2, "False")]


def test_the_detector_leaves_the_idiomatic_shapes_alone() -> None:
    """``while True`` and ``if TYPE_CHECKING`` must never be reported.

    The first is how the substrate's retry and poll loops are written; the
    second is a Name, not a constant. A detector that flagged either would be
    reverted within a day and the gate lost with it.
    """
    assert _neutered_conditions(ast.parse(_LEGITIMATE_SAMPLE)) == []


def test_the_scan_actually_reaches_the_package() -> None:
    """ANTI-VACUITY: an empty file list reports a clean tree identically.

    The gate's whole value is the emptiness of its worklist, and a scan that
    walked nothing produces that emptiness for free.
    """
    assert len(package_ast_items()) > 500


def test_the_exclusion_is_exercised_against_real_package_code() -> None:
    """The synthetic probes prove the detector; this proves it on this tree.

    A detector can be correct on a hand-written sample and still never meet the
    shape in the wild. The substrate's retry and poll paths carry real
    ``while True:`` loops, so the scan genuinely encounters constant-tested
    nodes and has to decide about them -- and the gate above is green because
    it decided correctly, not because it never looked.
    """
    idiomatic_loops = sum(
        1
        for _path, tree in package_ast_items()
        for node in ast.walk(tree)
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value
    )

    assert idiomatic_loops > 10
    assert not [(path, line) for path, tree in package_ast_items() for line, _source in _neutered_conditions(tree)]
