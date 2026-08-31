"""Architecture gate: intra-package imports under ``src/cadrumo`` are relative.

Code inside the ``cadrumo`` package must reach its siblings through relative
imports (``from . import x``, ``from ..core import y``), never by re-importing
the package through its absolute path (``import cadrumo.core`` or
``from cadrumo.core import y``). Absolute self-imports make a module's position in
the package implicit, defeat straightforward relocation, and blur the layering
the hexagonal structure depends on.

The gate fails hard with a precise ``path:line`` enumeration of every absolute
self-import so the offending lines are trivial to find and fix. It is computed
from the AST on every run, so it cannot go stale.

The detector matches the package name in both the bare form (``import cadrumo``,
``from cadrumo import x``) and the dotted form (``import cadrumo.core``,
``from cadrumo.core import y``). Both halves matter and the dotted half carries
the traffic: the bare form is vanishingly rare in real code, so a detector that
recognises only the bare spelling reports green over every realistic violation.
That was the shipped state between the ``aeat``-to-``cadrumo`` package rename and
this note — the rename swept the bare comparison on both branches and left the
dotted ``startswith`` prefix pointing at the retired package name, so the gate
could not see either of the two spellings its own opening paragraph names as
forbidden. :func:`test_detector_fires_on_every_absolute_spelling` pins every
spelling so the next rename cannot half-sweep the matcher in silence.

Because the matcher is AST-based it reads only real import statements: an
absolute import written inside a docstring's ``Public API::`` block or inside a
subprocess script held in a string literal is documentation or test data, not an
import, and is correctly invisible here.

See Also:
    :mod:`~tests._inventory`
        Provides the package AST inventory and repository-relative path
        rendering used by this architecture gate.

This relative-import discipline is the local companion to the broader
cross-package import-hygiene contract: it keeps a module's position in its own
package explicit even before a symbol crosses a package boundary.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from .inventory import package_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_PACKAGE = "cadrumo"
"""The importable package name this gate defends.

Named once so a future package rename cannot update one comparison branch and
leave the other pointing at the retired name — the exact half-sweep that left
the dotted spelling undetected after the ``aeat``-to-``cadrumo`` rename.
"""


def _is_absolute_self_module(module: str) -> bool:
    """Return True when *module* names this package, bare or dotted."""
    return module == _PACKAGE or module.startswith(f"{_PACKAGE}.")


def _absolute_self_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, statement)`` for every absolute ``cadrumo`` import."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_absolute_self_module(alias.name):
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and _is_absolute_self_module(node.module):
                hits.append((node.lineno, f"from {node.module} import ..."))
    return hits


def test_no_absolute_self_imports_in_cadrumo_package(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No source file under ``src/cadrumo`` may import the ``cadrumo`` package absolutely."""
    violations: list[str] = []
    for path, tree in package_ast_items(source_tree_ast):
        rel = repo_relative(path).removeprefix("src/")
        for lineno, statement in _absolute_self_imports(tree):
            violations.append(f"  {rel}:{lineno}  {statement}")

    if violations:
        pytest.fail(
            f"{len(violations)} absolute intra-cadrumo imports found; use relative imports "
            "(from . / .. / ...):\n" + "\n".join(violations),
        )


@pytest.mark.parametrize(
    ("source", "expected_hits"),
    (
        pytest.param("import cadrumo\n", 1, id="bare-import"),
        pytest.param("from cadrumo import core\n", 1, id="bare-from-import"),
        pytest.param("import cadrumo.core\n", 1, id="dotted-import"),
        pytest.param("from cadrumo.core import Period\n", 1, id="dotted-from-import"),
        pytest.param(
            "from cadrumo.application.modelo import law_selected_revision_for_work_target\n",
            1,
            id="deep-from-import",
        ),
        pytest.param("import cadrumo.core as core\n", 1, id="dotted-import-aliased"),
        pytest.param("import cadrumo, os\n", 1, id="bare-import-among-siblings"),
        pytest.param("def f():\n    import cadrumo.core\n", 1, id="function-local-dotted-import"),
    ),
)
def test_detector_fires_on_every_absolute_spelling(source: str, expected_hits: int) -> None:
    """Anti-tautology proof: each forbidden spelling is planted and must be caught.

    A gate that has never been shown to fail is indistinguishable from one that
    cannot. This gate's green run was worth nothing for the dotted spellings
    between the package rename and this proof, because no case ever asserted the
    matcher fires. Each source below is parsed in memory; no violation is
    committed to the tree.
    """
    hits = _absolute_self_imports(ast.parse(source))

    assert len(hits) == expected_hits, f"detector missed the planted violation in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("from . import core\n", id="relative-sibling"),
        pytest.param("from ..core import Period\n", id="relative-parent"),
        pytest.param("from ...application.modelo import build\n", id="relative-grandparent"),
        pytest.param("import os\nfrom pathlib import Path\n", id="stdlib"),
        pytest.param("import cadrumo_something\n", id="prefix-lookalike-distinct-package"),
        pytest.param("from cadrumo_extra.core import x\n", id="prefix-lookalike-dotted"),
        pytest.param('SCRIPT = """\nimport cadrumo.core\n"""\n', id="import-inside-string-literal"),
    ),
)
def test_detector_stays_silent_on_permitted_imports(source: str) -> None:
    """The other direction: a permitted import must not be reported.

    The two lookalike cases matter structurally. ``cadrumo_something`` shares the
    package name as a bare prefix but is a different distribution, so the matcher
    compares against ``cadrumo.`` with the separator rather than against
    ``cadrumo`` alone. The string-literal case pins that an absolute import
    written inside a docstring example or a subprocess script is text, not an
    import — every occurrence of that shape in this tree today is exactly that.
    """
    assert _absolute_self_imports(ast.parse(source)) == []
