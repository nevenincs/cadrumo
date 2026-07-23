"""Prompter-singularity gate: one live prompter implementation, tree-wide.

``application/wizard/_prompter.py`` is the canonical home of the wizard's
interactive prompting, and its module docstring states that exactly two
implementations ship: ``CanonicalAnswerPrompter`` for structured
non-interactive invocations and ``QuestionaryPrompter`` for live operator
interaction. That claim was false for months. A third prompter --
``_QuestionaryTextPrompter`` plus a shadowing ``_TextAnswerPrompter``
protocol -- had been hand-copied into the CLI layer, and the copy drifted
exactly where a copy drifts: it took no injectable input/output (so it was
headlessly untestable) and it caught only ``OSError``, while
``prompt_toolkit.output.win32.NoConsoleScreenBufferError`` is NOT an
``OSError`` subclass -- so Windows operators without a console got a raw
traceback where the canonical prompter raises a translated
``WizardUnsupportedConsoleError``. The copy was found by accident. Nothing
structural prevented it, and nothing prevented a fourth.

This gate is that structural prevention. Three rules, recomputed from the
real ``ast`` module every run against the production tree (test modules
excluded), with NO stored baseline and NO per-violation allowlist:

1. ``questionary`` and runtime ``prompt_toolkit`` imports appear only in the
   sanctioned prompt/console surfaces: the wizard ``_prompter.py`` and the
   flow substrate's ``_line_frontend.py`` / ``_capability.py`` (see
   :data:`FLOW_SUBSTRATE_PROMPT_MODULES` — the deliberately-coexisting
   migration surfaces, enrolled as canonical owners, not muted violations).
   Type-only imports under ``TYPE_CHECKING`` are exempt: they annotate, they
   never construct a prompt.
2. Outside the ``application/wizard`` package, ``QuestionaryPrompter`` is
   reached only through ``QuestionaryPrompter.from_ambient_app_session()``
   -- never bare-constructed, never subclassed. That classmethod owns the
   ambient-console detection and the translated no-console refusal.
3. No class outside ``_prompter.py`` declares an ``ask``/``ask_text``
   method while its module carries a questionary/prompt_toolkit
   dependency.

Rules 1 and 2 make the ``_QuestionaryTextPrompter`` drift structurally
impossible together: a hand-copied prompter cannot reach a live terminal
without importing questionary (rule 1), and the console detection cannot be
forked without constructing the canonical prompter yourself (rule 2). Rule 3
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

from ._inventory import aeat_relative, production_ast_items, qualified_name, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


CANONICAL_PROMPTER_MODULE = "application/wizard/_prompter.py"
"""The one production module that may import questionary and own a prompter."""

FLOW_SUBSTRATE_PROMPT_MODULES = frozenset(
    {
        "application/flows/_line_frontend.py",
        "application/flows/_capability.py",
    },
)
"""The paged-flow substrate's own prompt/console surfaces, sanctioned for rule 1.

The flow substrate ships a second, deliberately-coexisting interactive
surface during the wizard-to-flow migration: ``_line_frontend.py`` is its
line-mode prompter (questionary over injectable ``prompt_toolkit`` IO), and
``_capability.py`` owns the SINGLE console-capability probe both the line
frontend and the frontend selector consult (``prompt_toolkit`` only, no
``questionary`` — it classifies a host, it never prompts). Rule 1 exempts
these two by name for the same reason it exempts the wizard prompter: they
are canonical owners of a prompting/console concern, not a hand-copied
drift copy. Rules 2 and 3 still bind them fully — neither constructs
``QuestionaryPrompter`` nor declares an ``ask``/``ask_text`` class — so the
drift this gate exists to catch stays structurally impossible."""

WIZARD_PACKAGE_PARTS = ("application", "wizard")
"""Package that owns the prompter; rule 2 governs every module outside it."""

PROMPTER_CLASS = "QuestionaryPrompter"

SANCTIONED_PROMPTER_ACCESSOR = "from_ambient_app_session"
"""The only ``QuestionaryPrompter`` member a module outside the wizard may reach.

The classmethod resolves the ambient ``prompt_toolkit`` app session and
raises the translated :class:`WizardUnsupportedConsoleError` when the host
has no console. Reaching any other member re-forks that detection.
"""

PROMPTER_LIBRARIES = frozenset({"questionary", "prompt_toolkit"})

ASK_METHODS = frozenset({"ask", "ask_text"})


def _is_canonical_prompter(path: Path) -> bool:
    return aeat_relative(path) == CANONICAL_PROMPTER_MODULE


def _is_sanctioned_prompt_library_module(path: Path) -> bool:
    """Whether a module may import a prompting/console library (rule 1 exemption).

    The wizard prompter and the flow substrate's line frontend / capability
    probe are the sanctioned owners; every other production module is bound.
    """
    return _is_canonical_prompter(path) or aeat_relative(path) in FLOW_SUBSTRATE_PROMPT_MODULES


def _is_inside_wizard_package(path: Path) -> bool:
    return aeat_relative(path).split("/")[: len(WIZARD_PACKAGE_PARTS)] == list(WIZARD_PACKAGE_PARTS)


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
    """Return rule-1 violations: runtime questionary/prompt_toolkit imports off the canonical module."""
    if is_canonical:
        return []
    walker = _RuntimeImportWalker()
    walker.visit(tree)
    return [
        f"{display_path}:{lineno}: imports {library!r} at runtime; "
        f"the interactive prompter is owned by {CANONICAL_PROMPTER_MODULE}"
        for lineno, library in walker.runtime_imports
    ]


def prompter_construction_violations(display_path: str, tree: ast.AST) -> list[str]:
    """Return rule-2 violations: ``QuestionaryPrompter`` reached outside its sanctioned accessor.

    Callers restrict this to modules outside the wizard package. Import
    statements and type annotations name the class without reaching its
    behaviour, so only construction, subclassing, and non-sanctioned member
    access are violations.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == PROMPTER_CLASS:
            violations.append(
                f"{display_path}:{node.lineno}: constructs {PROMPTER_CLASS}() directly; "
                f"call {PROMPTER_CLASS}.{SANCTIONED_PROMPTER_ACCESSOR}() so the ambient-console "
                f"detection and the translated no-console refusal are not re-forked"
            )
        elif isinstance(node, ast.ClassDef):
            violations.extend(
                f"{display_path}:{node.lineno}: class {node.name!r} subclasses {PROMPTER_CLASS}; "
                f"the prompter is owned by {CANONICAL_PROMPTER_MODULE} and is not an extension point"
                for base in node.bases
                if qualified_name(base).rsplit(".", 1)[-1] == PROMPTER_CLASS
            )
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == PROMPTER_CLASS
            and node.attr != SANCTIONED_PROMPTER_ACCESSOR
        ):
            violations.append(
                f"{display_path}:{node.lineno}: reaches {PROMPTER_CLASS}.{node.attr}; "
                f"the only sanctioned entry point is {PROMPTER_CLASS}.{SANCTIONED_PROMPTER_ACCESSOR}()"
            )
    return violations


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
    """Return rule-3 violations: an ask-shaped class in a questionary-dependent module."""
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
                f"The two shipped implementations live in {CANONICAL_PROMPTER_MODULE}"
            )
    return violations


def _production_modules(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    return production_ast_items(source_tree_ast)


def test_canonical_prompter_module_is_present() -> None:
    """Anti-vacuity: the gate's three rules all key off one module that must exist.

    Were ``_prompter.py`` renamed or moved, every rule below would pass by
    scanning a tree with no canonical owner -- silently green, enforcing
    nothing. This pins the anchor.
    """
    canonical = [path for path, _ in production_ast_items() if _is_canonical_prompter(path)]

    assert len(canonical) == 1, (
        f"expected exactly one canonical prompter module at src/cadrumo/{CANONICAL_PROMPTER_MODULE}; found {canonical}"
    )


def test_questionary_is_imported_only_by_the_canonical_prompter(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Rule 1: no production module outside ``_prompter.py`` imports a prompting library at runtime.

    A hand-copied prompter cannot reach a live terminal without one of these
    imports, so this rule is the first half of what makes the
    ``_QuestionaryTextPrompter`` drift structurally impossible.
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
        "(the wizard prompter and the flow substrate's line frontend / capability probe):\n" + "\n".join(violations)
    )


def test_prompter_is_reached_only_through_its_ambient_session_accessor(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 2: outside the wizard package the prompter is never constructed or subclassed.

    ``from_ambient_app_session()`` owns the console detection; constructing
    the prompter directly is how a caller ends up re-deriving it, which is
    how the drifted copy shipped a refusal that missed
    ``NoConsoleScreenBufferError``.
    """
    violations = [
        violation
        for path, tree in _production_modules(source_tree_ast)
        if not _is_inside_wizard_package(path)
        for violation in prompter_construction_violations(repo_relative(path), tree)
    ]

    assert violations == [], (
        f"{PROMPTER_CLASS} is reachable outside the wizard only via "
        f"{PROMPTER_CLASS}.{SANCTIONED_PROMPTER_ACCESSOR}():\n" + "\n".join(violations)
    )


def test_no_rival_prompter_class_exists_outside_the_canonical_module(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 3: an ask-shaped class in a questionary-dependent module is a rival prompter.

    This is the shape the deleted ``_QuestionaryTextPrompter`` had, caught by
    its silhouette rather than by its imports.
    """
    violations = [
        violation
        for path, tree in _production_modules(source_tree_ast)
        for violation in rival_prompter_class_violations(
            repo_relative(path), tree, is_canonical=_is_canonical_prompter(path)
        )
    ]

    assert violations == [], "only the canonical prompter module may declare an ask-shaped class:\n" + "\n".join(
        violations
    )


# --------------------------------------------------------------------------
# Discrimination: each detector is fed the drift it exists to catch, plus the
# live shapes it must NOT flag. A structural gate that cannot fail pins a
# false green, which is the failure mode this whole campaign exists to undo.
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

from ...application.wizard import QuestionaryPrompter

if TYPE_CHECKING:
    from prompt_toolkit.input import Input


def run(prompter: QuestionaryPrompter) -> None:
    active = QuestionaryPrompter.from_ambient_app_session()
    active.ask_text("hello")
"""


def test_rule_one_fires_on_a_hand_copied_questionary_import() -> None:
    violations = prompter_library_import_violations(
        "src/cadrumo/entrypoints/cli/_drifted.py", ast.parse(_DRIFTED_COPY), is_canonical=False
    )

    assert len(violations) == 1
    assert "questionary" in violations[0]
    assert CANONICAL_PROMPTER_MODULE in violations[0]


def test_rule_one_exempts_type_only_imports_and_the_canonical_module() -> None:
    """The live CLI shape must stay green: its only prompt_toolkit import is type-only."""
    assert (
        prompter_library_import_violations(
            "src/cadrumo/entrypoints/cli/_live.py", ast.parse(_LIVE_CLI_SHAPE), is_canonical=False
        )
        == []
    )
    assert (
        prompter_library_import_violations(
            f"src/cadrumo/{CANONICAL_PROMPTER_MODULE}", ast.parse(_DRIFTED_COPY), is_canonical=True
        )
        == []
    )


@pytest.mark.parametrize(
    ("source", "expected_fragment"),
    [
        ("prompter = QuestionaryPrompter()", "constructs QuestionaryPrompter() directly"),
        ("class Forked(QuestionaryPrompter):\n    pass", "subclasses QuestionaryPrompter"),
        ("QuestionaryPrompter.ask_text('hi')", "reaches QuestionaryPrompter.ask_text"),
    ],
)
def test_rule_two_fires_on_each_forbidden_prompter_reference(source: str, expected_fragment: str) -> None:
    violations = prompter_construction_violations("src/cadrumo/entrypoints/cli/_drifted.py", ast.parse(source))

    assert len(violations) == 1
    assert expected_fragment in violations[0]


def test_rule_two_permits_the_sanctioned_accessor_annotation_and_import() -> None:
    """The live CLI shape names, annotates, and calls the accessor: all sanctioned."""
    assert prompter_construction_violations("src/cadrumo/entrypoints/cli/_live.py", ast.parse(_LIVE_CLI_SHAPE)) == []


def test_rule_three_fires_on_an_ask_shaped_class_in_a_questionary_module() -> None:
    violations = rival_prompter_class_violations(
        "src/cadrumo/entrypoints/cli/_drifted.py", ast.parse(_DRIFTED_COPY), is_canonical=False
    )

    assert len(violations) == 1
    assert "_QuestionaryTextPrompter" in violations[0]
    assert "rival prompter" in violations[0]


def test_rule_three_fires_when_the_questionary_handle_is_bound_indirectly() -> None:
    """Rule 3's reach beyond rule 1: a name reference with no import of its own."""
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


def test_rule_three_ignores_ask_shaped_classes_with_no_prompter_dependency() -> None:
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
