"""Prompt-singularity gate: one live prompt authority, tree-wide.

The flow substrate (:mod:`cadrumo.application.flows`) is the canonical home
of interactive prompting: ``_line_frontend.py`` is the one line-mode prompt
surface (questionary over injectable ``prompt_toolkit`` IO) and
``_capability.py`` owns the single console-capability probe every frontend
selector consults. No other production module may prompt.

The hazard this gate pins is historical and concrete. The retired one-shot
wizard's prompter module docstring claimed exactly two implementations
shipped, yet a third -- ``_QuestionaryTextPrompter`` plus a shadowing
``_TextAnswerPrompter`` protocol -- had been hand-copied into the CLI layer
and drifted exactly where a copy drifts: it took no injectable input/output
(so it was headlessly untestable) and it caught only ``OSError``, while
``prompt_toolkit.output.win32.NoConsoleScreenBufferError`` is NOT an
``OSError`` subclass -- so Windows operators without a console got a raw
traceback instead of a translated refusal. The copy was found by accident.
Nothing structural prevented it, and nothing prevented a fourth.

This gate is that structural prevention. Two rules, recomputed from the
real ``ast`` module every run against the production tree (test modules
excluded), with NO stored baseline and NO per-violation allowlist:

1. ``questionary`` and runtime ``prompt_toolkit`` imports appear only in
   the sanctioned prompt/console surfaces named by
   :data:`CANONICAL_PROMPT_MODULES`. Type-only imports under
   ``TYPE_CHECKING`` are exempt: they annotate, they never construct a
   prompt.
2. No class outside the sanctioned surfaces declares an ``ask``/``ask_text``
   method while its module carries a questionary/prompt_toolkit
   dependency.

Rule 1 makes a hand-copied prompter unable to reach a live terminal; rule 2
is defence in depth for a prompter assembled from a re-exported or
indirectly-bound questionary handle that rule 1's import walk would miss.

The detectors are pure ``(path, tree) -> list[str]`` functions so the
discrimination tests below can feed each one a synthetic violating module
and prove it fires. A gate that cannot fail is worse than no gate.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

import pytest

from ._inventory import aeat_relative, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


LINE_FRONTEND_MODULE = "application/flows/_line_frontend.py"
"""The flow substrate's line-mode prompt surface — the one questionary owner."""

CANONICAL_PROMPT_MODULES = frozenset(
    {
        LINE_FRONTEND_MODULE,
        "application/flows/_capability.py",
    },
)
"""The only production modules that may import a prompting/console library.

``_line_frontend.py`` is the substrate's line-mode prompter (questionary
over injectable ``prompt_toolkit`` IO), and ``_capability.py`` owns the
SINGLE console-capability probe both the line frontend and the frontend
selector consult (``prompt_toolkit`` only, no ``questionary`` — it
classifies a host, it never prompts). Rule 2 still binds them not to grow
a second ask-shaped class beside the one shipped frontend.
"""

PROMPTER_LIBRARIES = frozenset({"questionary", "prompt_toolkit"})

ASK_METHODS = frozenset({"ask", "ask_text"})


def _is_sanctioned_prompt_library_module(path: Path) -> bool:
    """Whether a module may import a prompting/console library (rule 1 exemption)."""
    return aeat_relative(path) in CANONICAL_PROMPT_MODULES


def _imported_roots(node: ast.Import | ast.ImportFrom) -> set[str]:
    """Return the top-level package names an import statement pulls in.

    A relative ``ImportFrom`` (``node.level`` non-zero) is first-party by
    construction and can never name a third-party prompting library.
    """
    if isinstance(node, ast.ImportFrom):
        if node.level or not node.module:
            return set()
        return {node.module.split(".", 1)[0]}
    return {alias.name.split(".", 1)[0] for alias in node.names}


class _RuntimeImportWalker(ast.NodeVisitor):
    """Collect imports that execute at runtime, skipping ``TYPE_CHECKING`` blocks."""

    def __init__(self) -> None:
        self._type_checking_depth = 0
        self.runtime_imports: list[tuple[int, str]] = []

    def _record(self, node: ast.Import | ast.ImportFrom) -> None:
        if self._type_checking_depth:
            return
        for root in _imported_roots(node) & PROMPTER_LIBRARIES:
            self.runtime_imports.append((node.lineno, root))

    @override
    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)

    @override
    def visit_If(self, node: ast.If) -> None:
        is_type_checking = node.test is not None and "TYPE_CHECKING" in ast.unparse(node.test)
        if is_type_checking:
            self._type_checking_depth += 1
        for child in node.body:
            self.visit(child)
        if is_type_checking:
            self._type_checking_depth -= 1
        for child in node.orelse:
            self.visit(child)


def prompter_library_import_violations(display_path: str, tree: ast.AST, *, is_canonical: bool) -> list[str]:
    """Return rule-1 violations: runtime questionary/prompt_toolkit imports off the sanctioned surfaces."""
    if is_canonical:
        return []
    walker = _RuntimeImportWalker()
    walker.visit(tree)
    return [
        f"{display_path}:{lineno}: imports {library!r} at runtime; "
        f"interactive prompting is owned by {LINE_FRONTEND_MODULE}"
        for lineno, library in walker.runtime_imports
    ]


def _module_names_a_prompter_library(tree: ast.AST) -> bool:
    """Return True when the module imports or names questionary/prompt_toolkit anywhere.

    Deliberately broader than the rule-1 walk: it counts ``TYPE_CHECKING``
    imports and bare name references, so a class holding a questionary handle
    bound indirectly (a re-export, a module attribute) still registers as
    carrying the dependency.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            if _imported_roots(node) & PROMPTER_LIBRARIES:
                return True
        elif isinstance(node, ast.Name) and node.id in PROMPTER_LIBRARIES:
            return True
    return False


def rival_prompter_class_violations(display_path: str, tree: ast.AST, *, is_canonical: bool) -> list[str]:
    """Return rule-2 violations: an ask-shaped class in a questionary-dependent module."""
    if is_canonical or not _module_names_a_prompter_library(tree):
        return []
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        asks = sorted(
            child.name
            for child in node.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name in ASK_METHODS
        )
        if asks:
            violations.append(
                f"{display_path}:{node.lineno}: class {node.name!r} declares {', '.join(asks)} "
                f"while its module depends on questionary/prompt_toolkit; this is a rival prompter. "
                f"Interactive prompting is owned by {LINE_FRONTEND_MODULE}"
            )
    return violations


def _production_modules(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    return production_ast_items(source_tree_ast)


def test_canonical_prompt_modules_are_present() -> None:
    """Anti-vacuity: both rules key off sanctioned modules that must exist.

    Were the line frontend or the capability probe renamed or moved, the
    rules below would pass by scanning a tree with no canonical owner --
    silently green, enforcing nothing. This pins the anchors.
    """
    present = {aeat_relative(path) for path, _ in production_ast_items()}
    missing = sorted(CANONICAL_PROMPT_MODULES - present)

    assert missing == [], f"expected every sanctioned prompt surface to exist under src/cadrumo/; missing {missing}"


def test_questionary_is_imported_only_by_the_sanctioned_prompt_surfaces(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 1: no production module outside the sanctioned surfaces imports a prompting library at runtime.

    A hand-copied prompter cannot reach a live terminal without one of these
    imports, so this rule is what makes the ``_QuestionaryTextPrompter``
    drift structurally impossible.
    """
    violations = [
        violation
        for path, tree in _production_modules(source_tree_ast)
        for violation in prompter_library_import_violations(
            repo_relative(path), tree, is_canonical=_is_sanctioned_prompt_library_module(path)
        )
    ]

    assert violations == [], (
        "questionary/prompt_toolkit must be imported only by the sanctioned prompt surfaces "
        "(the flow substrate's line frontend / capability probe):\n" + "\n".join(violations)
    )


def test_no_rival_prompter_class_exists_outside_the_sanctioned_surfaces(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 2: an ask-shaped class in a questionary-dependent module is a rival prompter.

    This is the shape the deleted ``_QuestionaryTextPrompter`` had, caught by
    its silhouette rather than by its imports.
    """
    violations = [
        violation
        for path, tree in _production_modules(source_tree_ast)
        for violation in rival_prompter_class_violations(
            repo_relative(path), tree, is_canonical=_is_sanctioned_prompt_library_module(path)
        )
    ]

    assert violations == [], "only the sanctioned prompt surfaces may declare an ask-shaped class:\n" + "\n".join(
        violations
    )


# --------------------------------------------------------------------------
# Discrimination: each detector is fed the drift it exists to catch, plus the
# live shapes it must NOT flag. A structural gate that cannot fail pins a
# false green, which is the failure mode this gate exists to undo.
# --------------------------------------------------------------------------

_DRIFTED_COPY = """
import questionary

class _QuestionaryTextPrompter:
    def ask_text(self, prompt: str) -> str:
        try:
            return questionary.text(prompt).ask()
        except OSError:
            raise RuntimeError("no console")
"""

_LIVE_CLI_SHAPE = """
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_toolkit.input import Input


def run(pipe: Input | None = None) -> None:
    del pipe
"""


def test_rule_one_fires_on_a_hand_copied_questionary_import() -> None:
    violations = prompter_library_import_violations(
        "src/cadrumo/entrypoints/cli/_drifted.py", ast.parse(_DRIFTED_COPY), is_canonical=False
    )

    assert len(violations) == 1
    assert "questionary" in violations[0]
    assert LINE_FRONTEND_MODULE in violations[0]


def test_rule_one_exempts_type_only_imports_and_the_sanctioned_modules() -> None:
    """The live CLI shape must stay green: its only prompt_toolkit import is type-only."""
    assert (
        prompter_library_import_violations(
            "src/cadrumo/entrypoints/cli/_live.py", ast.parse(_LIVE_CLI_SHAPE), is_canonical=False
        )
        == []
    )
    assert (
        prompter_library_import_violations(
            f"src/cadrumo/{LINE_FRONTEND_MODULE}", ast.parse(_DRIFTED_COPY), is_canonical=True
        )
        == []
    )


def test_rule_two_fires_on_an_ask_shaped_class_in_a_questionary_module() -> None:
    violations = rival_prompter_class_violations(
        "src/cadrumo/entrypoints/cli/_drifted.py", ast.parse(_DRIFTED_COPY), is_canonical=False
    )

    assert len(violations) == 1
    assert "_QuestionaryTextPrompter" in violations[0]
    assert "rival prompter" in violations[0]


def test_rule_two_fires_when_the_questionary_handle_is_bound_indirectly() -> None:
    """Rule 2's reach beyond rule 1: a name reference with no import of its own."""
    source = """
from ._reexports import questionary

class _Rival:
    def ask(self, question: object) -> str:
        return questionary.text("x").ask()
"""
    violations = rival_prompter_class_violations(
        "src/cadrumo/entrypoints/cli/_x.py", ast.parse(source), is_canonical=False
    )

    assert len(violations) == 1
    assert "_Rival" in violations[0]


def test_rule_two_ignores_ask_shaped_classes_with_no_prompter_dependency() -> None:
    """An ``ask`` method alone is not a prompter; the questionary dependency is the tell."""
    source = """
class NonInteractiveAnswers:
    def ask(self, question: object) -> str:
        return "canned"
"""
    assert (
        rival_prompter_class_violations("src/cadrumo/application/other/_x.py", ast.parse(source), is_canonical=False)
        == []
    )
