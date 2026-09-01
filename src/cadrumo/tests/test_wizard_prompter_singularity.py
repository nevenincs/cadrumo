"""Prompt-singularity gate: one live prompt authority, tree-wide.

The flow substrate (:mod:`cadrumo.application.flows`) is the canonical home
of interactive prompting: ``line_frontend.py`` is the one line-mode prompt
surface (questionary over injectable ``prompt_toolkit`` IO) and
``capability.py`` owns the single console-capability probe every frontend
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

This gate is that structural prevention. Three rules, recomputed from the
real ``ast`` module every run against the production tree (test modules
excluded), with NO stored baseline and NO per-violation allowlist:

1. ``questionary`` and runtime ``prompt_toolkit`` imports appear only in
   the sanctioned prompt/console surfaces named by
   :data:`CANONICAL_PROMPT_MODULES`. Type-only imports under
   ``TYPE_CHECKING`` are exempt: they annotate, they never construct a
   prompt.
2. No module outside the sanctioned surfaces imports a prompter-library
   handle *indirectly*, through a first-party module that re-exports one.
   Rule 1 reads import statements for a third-party root, so a rival
   reaching questionary as ``from ..flows.line_frontend import
   questionary`` names only a first-party module and walks straight past
   it. This rule resolves the re-export instead of matching the spelling.
3. No class outside the sanctioned surfaces declares an ``ask``/``ask_text``
   method while its module carries a questionary/prompt_toolkit
   dependency — where "carries" is likewise alias- and re-export-aware, so
   ``from ._reexports import questionary as q`` counts.

Rule 1 makes a hand-copied prompter unable to reach a live terminal, rule 2
closes the indirect route around it, and rule 3 is defence in depth
catching a prompter by its silhouette rather than by its imports.

Transitive closure and its residual limits
------------------------------------------
Rule 2 closes the re-export graph transitively (:func:`prompter_export_map`),
not to one hop: a handle laundered through a chain of first-party
re-exports still resolves to its library. Two shapes remain invisible to
any AST pass and are stated here rather than papered over:

* A module string built at runtime and fed to ``importlib.import_module``
  is not an import statement; no static walk can see its target. This is a
  documented structural limit of AST scanning, and the reason the
  ``aeat-architecture-boundaries`` discipline is author-side.
* A module-level ``__getattr__`` (PEP 562) that serves a prompter handle on
  attribute access binds no name an import statement declares, so a facade
  built that way is outside the closure. No production facade in this tree
  does so; rule 3's silhouette check is the backstop if one appears.

The detectors are pure functions over ``(display path, module path, tree)``
so the discrimination tests below can feed each one a synthetic violating
module and prove it fires. A gate that cannot fail is worse than no gate.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

import pytest

from .inventory import SRC_CADRUMO, aeat_relative, module_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path


LINE_FRONTEND_MODULE = "application/flows/line_frontend.py"
"""The flow substrate's line-mode prompt surface — the one questionary owner."""

CANONICAL_PROMPT_MODULES = frozenset(
    {
        LINE_FRONTEND_MODULE,
        "application/flows/capability.py",
    },
)
"""The only production modules that may import a prompting/console library.

``line_frontend.py`` is the substrate's line-mode prompter (questionary
over injectable ``prompt_toolkit`` IO), and ``capability.py`` owns the
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
        self.runtime_import_from: list[ast.ImportFrom] = []

    def _record(self, node: ast.Import | ast.ImportFrom) -> None:
        if self._type_checking_depth:
            return
        for root in _imported_roots(node) & PROMPTER_LIBRARIES:
            self.runtime_imports.append((node.lineno, root))
        if isinstance(node, ast.ImportFrom):
            self.runtime_import_from.append(node)

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


# --------------------------------------------------------------------------
# Rule 2: the indirect route around rule 1's third-party-root import walk.
# --------------------------------------------------------------------------


def _package_base(path: Path) -> str:
    """Return the dotted package a relative import inside *path* resolves against."""
    dotted = module_name(path)
    if path.name == "__init__.py":
        return dotted
    parent, _, _ = dotted.rpartition(".")
    return parent


def _resolved_import_target(path: Path, node: ast.ImportFrom) -> str | None:
    """Return the absolute dotted module an ``ImportFrom`` in *path* names."""
    if not node.level:
        return node.module
    base_parts = _package_base(path).split(".")
    ascent = node.level - 1
    if ascent >= len(base_parts):
        return None
    anchor = ".".join(base_parts[: len(base_parts) - ascent])
    if not anchor:
        return None
    return f"{anchor}.{node.module}" if node.module else anchor


def _module_level_runtime_imports(tree: ast.AST) -> list[ast.Import | ast.ImportFrom]:
    """Return import statements executing at module import time, outside ``TYPE_CHECKING``.

    Only a module-level binding is importable by another module, so this is
    the surface that can re-export a prompter handle onward. Function-local
    imports bind a name nothing outside the function can reach.
    """
    statements: list[ast.Import | ast.ImportFrom] = []
    pending: list[ast.stmt] = list(tree.body) if isinstance(tree, ast.Module) else list[ast.stmt]()
    while pending:
        node = pending.pop(0)
        if isinstance(node, ast.Import | ast.ImportFrom):
            statements.append(node)
        elif isinstance(node, ast.If):
            guarded = node.test is not None and "TYPE_CHECKING" in ast.unparse(node.test)
            branch: list[ast.stmt] = list(node.orelse) if guarded else [*node.body, *node.orelse]
            pending = branch + pending
        elif isinstance(node, ast.Try):
            handled: list[ast.stmt] = [statement for handler in node.handlers for statement in handler.body]
            pending = [*node.body, *handled, *node.orelse, *node.finalbody, *pending]
    return statements


def _direct_prompter_bindings(tree: ast.AST) -> dict[str, str]:
    """Return module-level local names bound directly to a prompting library."""
    bindings: dict[str, str] = {}
    for node in _module_level_runtime_imports(tree):
        libraries = _imported_roots(node) & PROMPTER_LIBRARIES
        if not libraries:
            continue
        library = sorted(libraries)[0]
        for alias in node.names:
            bindings[alias.asname or alias.name.split(".", 1)[0]] = library
    return bindings


def prompter_export_map(modules: Iterable[tuple[Path, ast.AST]]) -> dict[str, dict[str, str]]:
    """Return ``dotted module -> {re-exported name: library root}``, closed transitively.

    Seeded from every module-level direct binding, then propagated across
    first-party ``from ... import`` edges until it stops growing, so a handle
    laundered through a chain of re-exports still resolves to its library
    rather than only surviving one hop.
    """
    parsed = tuple(modules)
    exports: dict[str, dict[str, str]] = {}
    edges: dict[str, list[tuple[str, tuple[ast.alias, ...]]]] = {}
    for path, tree in parsed:
        dotted = module_name(path)
        exports[dotted] = _direct_prompter_bindings(tree)
        module_edges: list[tuple[str, tuple[ast.alias, ...]]] = []
        for node in _module_level_runtime_imports(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = _resolved_import_target(path, node)
            if target is not None:
                module_edges.append((target, tuple(node.names)))
        edges[dotted] = module_edges

    changed = True
    while changed:
        changed = False
        for dotted, module_edges in edges.items():
            for target, names in module_edges:
                exported = exports.get(target)
                if not exported:
                    continue
                for adopted, library in _adopted_bindings(names, exported).items():
                    if exports[dotted].get(adopted) != library:
                        exports[dotted][adopted] = library
                        changed = True
    return exports


def _adopted_bindings(names: Iterable[ast.alias], exported: Mapping[str, str]) -> dict[str, str]:
    """Return the prompter handles an import of *names* pulls from *exported*."""
    adopted: dict[str, str] = {}
    for alias in names:
        if alias.name == "*":
            adopted.update(exported)
            continue
        library = exported.get(alias.name)
        if library is not None:
            adopted[alias.asname or alias.name] = library
    return adopted


def indirect_prompter_binding_violations(
    display_path: str,
    path: Path,
    tree: ast.AST,
    prompter_exports: Mapping[str, Mapping[str, str]],
    *,
    is_canonical: bool,
) -> list[str]:
    """Return rule-2 violations: a prompter handle reached through a first-party re-export."""
    if is_canonical:
        return []
    walker = _RuntimeImportWalker()
    walker.visit(tree)
    violations: list[str] = []
    for node in walker.runtime_import_from:
        target = _resolved_import_target(path, node)
        if target is None:
            continue
        exported = prompter_exports.get(target)
        if not exported:
            continue
        for local, library in _adopted_bindings(node.names, exported).items():
            violations.append(
                f"{display_path}:{node.lineno}: binds {local!r} to {library!r} through "
                f"{target}; a re-exported prompter handle is still a prompter handle. "
                f"Interactive prompting is owned by {LINE_FRONTEND_MODULE}"
            )
    return violations


# --------------------------------------------------------------------------
# Rule 3: the prompter silhouette, alias- and re-export-aware.
# --------------------------------------------------------------------------


def _prompter_handle_names(
    path: Path,
    tree: ast.AST,
    prompter_exports: Mapping[str, Mapping[str, str]],
) -> frozenset[str]:
    """Return local names in this module denoting a prompting library.

    Deliberately broader than the rule-1 walk: ``TYPE_CHECKING`` imports and
    function-local imports both count, and every alias spelling resolves, so
    ``from ._reexports import questionary as q`` registers under ``q``.
    """
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom) and _imported_roots(node) & PROMPTER_LIBRARIES:
            for alias in node.names:
                names[alias.asname or alias.name.split(".", 1)[0]] = "direct"
        if isinstance(node, ast.ImportFrom):
            target = _resolved_import_target(path, node)
            exported = prompter_exports.get(target) if target is not None else None
            if exported:
                names.update(dict.fromkeys(_adopted_bindings(node.names, exported), "reexport"))
    return frozenset(names)


def _module_names_a_prompter_library(tree: ast.AST, handle_names: frozenset[str]) -> bool:
    """Return True when the module carries a prompting-library dependency.

    A resolved handle binding is conclusive. Absent one, a bare reference to
    a library's own name still counts: it is a handle arriving by a route
    this pass cannot resolve (a PEP 562 module ``__getattr__``, an attribute
    off an object), and rule 3 is the backstop for exactly that case.
    """
    if handle_names:
        return True
    return any(isinstance(node, ast.Name) and node.id in PROMPTER_LIBRARIES for node in ast.walk(tree))


def rival_prompter_class_violations(
    display_path: str,
    tree: ast.AST,
    *,
    is_canonical: bool,
    handle_names: frozenset[str] = frozenset(),
) -> list[str]:
    """Return rule-3 violations: an ask-shaped class in a questionary-dependent module."""
    if is_canonical or not _module_names_a_prompter_library(tree, handle_names):
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


def test_no_module_reaches_a_prompter_library_through_a_reexport(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 2: no production module binds a prompter handle through a first-party re-export.

    Rule 1 matches a third-party import root, so a rival importing
    ``questionary`` from a first-party module that re-exports it names only
    first-party code and passes rule 1 untouched. This resolves the
    re-export graph transitively instead.
    """
    modules = _production_modules(source_tree_ast)
    exports = prompter_export_map(modules)
    violations = [
        violation
        for path, tree in modules
        for violation in indirect_prompter_binding_violations(
            repo_relative(path),
            path,
            tree,
            exports,
            is_canonical=_is_sanctioned_prompt_library_module(path),
        )
    ]

    assert violations == [], "a prompter handle must not be reached through a first-party re-export:\n" + "\n".join(
        violations
    )


def test_no_rival_prompter_class_exists_outside_the_sanctioned_surfaces(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 3: an ask-shaped class in a questionary-dependent module is a rival prompter.

    This is the shape the deleted ``_QuestionaryTextPrompter`` had, caught by
    its silhouette rather than by its imports.
    """
    modules = _production_modules(source_tree_ast)
    exports = prompter_export_map(modules)
    violations = [
        violation
        for path, tree in modules
        for violation in rival_prompter_class_violations(
            repo_relative(path),
            tree,
            is_canonical=_is_sanctioned_prompt_library_module(path),
            handle_names=_prompter_handle_names(path, tree, exports),
        )
    ]

    assert violations == [], "only the sanctioned prompt surfaces may declare an ask-shaped class:\n" + "\n".join(
        violations
    )


def test_the_canonical_line_frontend_is_a_live_taint_source(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Anti-vacuity for rule 2: the export map must really carry a prompter handle.

    Rule 2 compares imports against :func:`prompter_export_map`. Were that map
    empty — the line frontend renamed, its ``import questionary`` moved into a
    function, the module-level walk broken — rule 2 would scan every module
    against nothing and report green while enforcing nothing. This pins the
    seed the closure grows from.
    """
    exports = prompter_export_map(_production_modules(source_tree_ast))
    frontend = exports.get(f"cadrumo.{LINE_FRONTEND_MODULE.removesuffix('.py').replace('/', '.')}")

    assert frontend, "expected the line frontend to expose a module-level prompter binding"
    assert "questionary" in frontend, f"expected a questionary handle in the line frontend's exports; got {frontend}"


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


def _synthetic_modules(sources: Mapping[str, str]) -> tuple[tuple[Path, ast.AST], ...]:
    """Return ``(path, tree)`` pairs for synthetic modules keyed by aeat-relative path.

    Paths are composed under ``src/cadrumo`` so ``module_name`` and the
    relative-import resolver treat them exactly as they treat a real module,
    while the sources are parsed from memory — no planted violation is ever
    written into the tree.
    """
    return tuple((SRC_CADRUMO / relative, ast.parse(source, filename=relative)) for relative, source in sources.items())


_LAUNDERED_THROUGH_REEXPORTS: Mapping[str, str] = {
    LINE_FRONTEND_MODULE: "import questionary\n",
    "entrypoints/cli/_reexports.py": "from ...application.flows.line_frontend import questionary\n",
    "entrypoints/cli/_rival.py": (
        "from ._reexports import questionary as prompt_lib\n"
        "\n"
        "\n"
        "class _Rival:\n"
        "    def ask(self, question: object) -> str:\n"
        '        return prompt_lib.text("x").ask()\n'
    ),
}
"""A prompter handle laundered two hops out of the canonical owner.

Neither consumer names a third-party root, so rule 1's import walk reports
green over both while ``prompt_lib`` really is ``questionary``.
"""


def test_rule_two_fires_on_a_handle_laundered_through_first_party_reexports() -> None:
    """Anti-tautology proof for rule 2, including the second hop.

    ``_reexports`` takes the handle straight off the canonical owner and
    ``_rival`` takes it from ``_reexports`` under a new alias. Both are
    violations, and the second only resolves because the export map is closed
    transitively rather than stopped at one hop.
    """
    modules = _synthetic_modules(_LAUNDERED_THROUGH_REEXPORTS)
    exports = prompter_export_map(modules)
    violations = [
        violation
        for path, tree in modules
        for violation in indirect_prompter_binding_violations(
            aeat_relative(path),
            path,
            tree,
            exports,
            is_canonical=_is_sanctioned_prompt_library_module(path),
        )
    ]

    assert len(violations) == 2, f"expected both re-export hops to be caught; got {violations}"
    assert any("_reexports.py" in violation and "questionary" in violation for violation in violations)
    second_hop = [violation for violation in violations if "_rival.py" in violation]
    assert len(second_hop) == 1, f"the second hop must resolve transitively; got {violations}"
    assert "'prompt_lib'" in second_hop[0] and "'questionary'" in second_hop[0]


def test_rule_two_ignores_ordinary_imports_from_the_canonical_prompt_surfaces() -> None:
    """A non-prompter symbol re-exported by a sanctioned surface is not a handle.

    This is the live shape in the tree: the flows package imports
    ``detect_frontend_capability`` and the line frontend imports
    ``NO_CONSOLE_ERRORS``. Both are locally-defined symbols, not library
    handles, and flagging them would make rule 2 unusable.
    """
    modules = _synthetic_modules(
        {
            LINE_FRONTEND_MODULE: "import questionary\n\n\nclass LineFlowFrontend:\n    pass\n",
            "application/flows/capability.py": (
                "def detect_frontend_capability():\n    return None\n\n\nNO_CONSOLE_ERRORS = (OSError,)\n"
            ),
            "application/flows/__init__.py": (
                "from .capability import NO_CONSOLE_ERRORS, detect_frontend_capability\n"
                "from .line_frontend import LineFlowFrontend\n"
            ),
        },
    )
    exports = prompter_export_map(modules)
    consumer = SRC_CADRUMO / "application/flows/__init__.py"

    violations = [
        violation
        for path, tree in modules
        if path == consumer
        for violation in indirect_prompter_binding_violations(
            aeat_relative(path), path, tree, exports, is_canonical=False
        )
    ]

    assert violations == [], f"a locally-defined re-exported symbol is not a prompter handle; got {violations}"


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


def test_rule_three_fires_when_the_reexported_handle_is_renamed() -> None:
    """Anti-tautology proof for rule 3's alias awareness.

    The silhouette check used to key on a bare reference spelled
    ``questionary``, so renaming the re-exported handle walked past it while
    the class went on prompting. Resolving the binding removes the escape.
    """
    modules = _synthetic_modules(_LAUNDERED_THROUGH_REEXPORTS)
    exports = prompter_export_map(modules)
    rival = SRC_CADRUMO / "entrypoints/cli/_rival.py"
    tree = next(tree for path, tree in modules if path == rival)

    handle_names = _prompter_handle_names(rival, tree, exports)
    assert "prompt_lib" in handle_names, f"expected the renamed handle to resolve; got {sorted(handle_names)}"

    violations = rival_prompter_class_violations(
        aeat_relative(rival), tree, is_canonical=False, handle_names=handle_names
    )

    assert len(violations) == 1, f"expected the renamed-handle rival to be caught; got {violations}"
    assert "_Rival" in violations[0]

    unaware = rival_prompter_class_violations(aeat_relative(rival), tree, is_canonical=False)
    assert unaware == [], (
        "guard on the proof itself: without resolved handle names this rival is invisible, "
        "which is exactly the blindness the alias resolution removes"
    )


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
