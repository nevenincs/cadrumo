"""Reachability classification over a synthetic shipped tree.

In-process checks against a throwaway ``src/`` layout built in ``tmp_path``:
the walk from the entry point, the string-literal dynamic edges, the
``TYPE_CHECKING`` split, the package collapse, the exact top-level symbol
resolution, the weaker member layer, the shipped-data clearing, the orphaned
tests, and the confidence tiers are each proven in both directions (a defect
is reported AND the healthy neighbour is not). The gate that runs the scanner
over the real tree lives in ``test_unreachable_code_scan``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..unreachable_code import (
    Confidence,
    EntryPoint,
    ModuleReach,
    OutsideCorpus,
    ShippedTreeSpec,
    SymbolKind,
    UnreachableCodeOutcome,
    UnreachableCodeResult,
    filter_by_confidence,
    render_console_report,
    result_as_json,
    scan_unreachable_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXCLUDES = ("src/pkg/tests", "src/pkg/tests/**", "src/pkg/**/tests", "src/pkg/**/tests/**")
_DATA_GLOBS = ("_data/**/*.toml",)

_CLI = '''
"""Entry module.

This prose names orphan_fn and UNUSED_CONST, which must not clear them.
"""

from typing import TYPE_CHECKING

from . import shelf as _shelf
from .used import run

if TYPE_CHECKING:
    from .typed import Shape

HANDLER = ("pkg.lazy", "handler")
RELATIVE = ".relative"


def main() -> tuple[tuple[str, str], str]:
    run()
    _shelf.shelved()
    return HANDLER, RELATIVE
'''

_USED = """
from enum import StrEnum


class Color(StrEnum):
    RED = "r"
    BLUE = "b"


class Modelo(StrEnum):
    M100 = "100"
    M303 = "303"


class Config(StrEnum):
    DECLARED_IN_DATA = "declared_in_data"
    NEVER_ANYWHERE = "never_anywhere"


class Widget:
    label: str
    hidden_field: int
    data_field: int

    def shown(self) -> None: ...

    def hidden(self) -> None: ...

    def on_mount(self) -> None: ...

    def __repr__(self) -> str: ...


MAX = 3
UNUSED_CONST = 4


def helper() -> None: ...


def orphan_fn() -> None: ...


def run() -> None:
    helper()
    Widget(label="x").shown()
    for modelo in Modelo:
        pass
    return Color.RED, MAX
"""

# Defines a name that also exists in `used`, and calls only its own copy. The
# bare load here must not clear `used.helper`.
_SHELF = """
def helper() -> None: ...


def shelved() -> None:
    helper()
"""

_TESTS = """
from pkg.loner import x
from pkg.used import orphan_fn
import pkg.dead.a
"""

_LIVE_TESTS = """
from pkg.loner import x
from pkg.used import run
"""

_DEV = """
import pkg.dead.b
from pkg.used import UNUSED_CONST
"""

_TOOL_MAIN = """
from .work import go

if __name__ == "__main__":
    go()
"""

_DATA = """
[binding]
field = "data_field"
value = "DECLARED_IN_DATA"
"""


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_tree(root: Path) -> ShippedTreeSpec:
    _write(root, "src/pkg/__init__.py")
    _write(root, "src/pkg/cli.py", _CLI)
    _write(root, "src/pkg/used.py", _USED)
    _write(root, "src/pkg/shelf.py", _SHELF)
    _write(root, "src/pkg/lazy.py", "def handler() -> None: ...\n")
    _write(root, "src/pkg/relative.py", "")
    _write(root, "src/pkg/typed.py", "class Shape: ...\n")
    _write(root, "src/pkg/loner.py", "x = 1\n")
    _write(root, "src/pkg/dead/__init__.py")
    _write(root, "src/pkg/dead/a.py", "")
    _write(root, "src/pkg/dead/b.py", "from . import a\n")
    _write(root, "src/pkg/tool/__init__.py")
    _write(root, "src/pkg/tool/__main__.py", _TOOL_MAIN)
    _write(root, "src/pkg/tool/work.py", "def go() -> None: ...\n")
    _write(root, "src/pkg/_data/bindings.toml", _DATA)
    _write(root, "src/pkg/tests/__init__.py")
    _write(root, "src/pkg/tests/test_things.py", _TESTS)
    _write(root, "src/pkg/tests/test_live.py", _LIVE_TESTS)
    _write(root, "src/pkg/tests/test_harness_only.py", "import pytest\n")
    _write(root, "dev/tool.py", _DEV)
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        module_roots=("pkg.tool.__main__",),
        exclude_globs=_EXCLUDES,
        outside=(
            OutsideCorpus(label="tests", root=root / "src" / "pkg", test_modules_only=True),
            OutsideCorpus(label="dev", root=root / "dev"),
        ),
        data_globs=_DATA_GLOBS,
    )


@pytest.fixture
def result(tmp_path: Path) -> UnreachableCodeResult:
    """One scan over the synthetic tree, shared by the classification tests."""
    return scan_unreachable_code(_build_tree(tmp_path))


def test_modules_reached_statically_dynamically_or_relatively_are_not_reported(result: UnreachableCodeResult) -> None:
    """Static imports, ``"pkg.lazy"`` handler strings, and ``".relative"`` strings are edges."""
    reported = {finding.module for finding in result.modules}

    assert result.outcome is UnreachableCodeOutcome.FINDINGS
    assert reported.isdisjoint({"pkg", "pkg.cli", "pkg.used", "pkg.lazy", "pkg.relative", "pkg.shelf"})
    assert result.roots == ("pkg.cli:main", "pkg.tool.__main__ (python -m)")
    assert result.reachable_modules == 9


def test_a_module_execution_entrypoint_is_a_walk_root(result: UnreachableCodeResult) -> None:
    """``python -m pkg.tool`` is a surface an installed user has, so it seeds the walk.

    What it reaches is alive, but only weakly: no console script leads there,
    so it is reported as module-exec-only rather than either hidden or called
    dead. Hiding it would let dev-only trees launder unreachable code.
    """
    by_module = {finding.module: finding for finding in result.modules}

    assert {"pkg.tool", "pkg.tool.__main__", "pkg.tool.work"} <= set(by_module)
    for name in ("pkg.tool", "pkg.tool.__main__", "pkg.tool.work"):
        assert by_module[name].reach is ModuleReach.MODULE_EXEC_ONLY
    assert result.module_exec_only_total == 3
    assert result.unreachable_module_total == 4


def test_repository_discovers_its_module_execution_roots() -> None:
    """The real tree's ``__main__.py`` files are found without being restated."""
    spec = ShippedTreeSpec.from_repository(REPO_ROOT)

    assert "cadrumo.entrypoints.tui.__main__" in spec.module_roots
    assert all(root.endswith(".__main__") for root in spec.module_roots)


def test_wholly_unreachable_package_collapses_to_one_labelled_folder(result: UnreachableCodeResult) -> None:
    """``pkg.dead`` is reported once, spanning three modules, with its dev/test use as a label."""
    dead = next(finding for finding in result.modules if finding.module == "pkg.dead")

    assert dead.reach is ModuleReach.UNREACHABLE
    assert dead.is_package
    assert dead.path == "src/pkg/dead/"
    assert dead.spanned_modules == 3
    assert dead.used_by == ("dev", "tests")
    assert not any(finding.module in {"pkg.dead.a", "pkg.dead.b"} for finding in result.modules)


def test_test_only_module_is_reported_with_the_tests_label(result: UnreachableCodeResult) -> None:
    """A module only a test imports is unreachable; the label says who still touches it."""
    loner = next(finding for finding in result.modules if finding.module == "pkg.loner")

    assert loner.reach is ModuleReach.UNREACHABLE
    assert not loner.is_package
    assert loner.path == "src/pkg/loner.py"
    assert loner.used_by == ("tests",)


def test_type_checking_only_import_is_reported_as_type_only(result: UnreachableCodeResult) -> None:
    """A ``TYPE_CHECKING`` import does not execute, so the module is not runtime-reachable."""
    typed = next(finding for finding in result.modules if finding.module == "pkg.typed")

    assert typed.reach is ModuleReach.TYPE_ONLY
    assert typed.used_by == ()
    assert result.type_only_module_total == 1
    assert result.unreachable_module_total == 4


def test_symbol_layer_reports_only_definitions_shipped_code_never_references(result: UnreachableCodeResult) -> None:
    """Loads, attribute access, keyword construction, iteration, and hooks all count as use."""
    by_qualname = {finding.qualname: finding for finding in result.symbols}

    assert set(by_qualname) == {
        "Color.BLUE",
        "Config",
        "Config.NEVER_ANYWHERE",
        "Widget.hidden_field",
        "Widget.hidden",
        "UNUSED_CONST",
        "orphan_fn",
    }
    assert by_qualname["Color.BLUE"].kind is SymbolKind.ENUM_MEMBER
    assert by_qualname["Widget.hidden_field"].kind is SymbolKind.ATTRIBUTE
    assert by_qualname["Widget.hidden"].kind is SymbolKind.METHOD
    assert by_qualname["UNUSED_CONST"].kind is SymbolKind.CONSTANT
    assert by_qualname["orphan_fn"].kind is SymbolKind.FUNCTION
    assert by_qualname["orphan_fn"].used_by == ("tests",)
    assert by_qualname["UNUSED_CONST"].used_by == ("dev",)
    assert by_qualname["Widget.hidden"].used_by == ()
    assert by_qualname["orphan_fn"].path == "src/pkg/used.py"
    assert by_qualname["orphan_fn"].line > 0
    # Clearing a member through the data payload never vouches for its class:
    # nothing constructs Config, so the class itself stays a finding.
    assert by_qualname["Config"].kind is SymbolKind.CLASS


def test_docstring_prose_naming_a_symbol_does_not_clear_it(result: UnreachableCodeResult) -> None:
    """The entry module's docstring names two dead symbols; prose describes, it does not reach."""
    reported = {finding.qualname for finding in result.symbols}

    assert {"orphan_fn", "UNUSED_CONST"} <= reported


def test_a_same_named_symbol_in_another_module_does_not_clear_the_dead_one(
    result: UnreachableCodeResult,
) -> None:
    """``shelf.helper`` is called by ``shelf``; ``used.helper`` is called by ``used``.

    Both are live and neither is reported. The point of the pair is that
    resolution is per defining module, so a bare name load cannot vouch for a
    definition in a module it never imported.
    """
    assert not any(finding.name == "helper" for finding in result.symbols)


def test_a_relative_module_alias_reaches_the_symbol_it_qualifies(result: UnreachableCodeResult) -> None:
    """``from . import shelf as _shelf`` then ``_shelf.shelved()`` is a resolved use."""
    assert not any(finding.qualname == "shelved" for finding in result.symbols)


def test_shipped_data_naming_a_member_clears_it_but_never_a_top_level_symbol(
    result: UnreachableCodeResult,
) -> None:
    """Registry-style data addresses fields and enum values by name, so those are reached.

    ``data_field`` and ``DECLARED_IN_DATA`` appear only in the TOML payload and
    are cleared; their siblings that appear nowhere are still reported.
    """
    reported = {finding.qualname for finding in result.symbols}

    assert "Widget.data_field" not in reported
    assert "Config.DECLARED_IN_DATA" not in reported
    assert "Widget.hidden_field" in reported
    assert "Config.NEVER_ANYWHERE" in reported
    assert result.data_cleared == 2


def test_test_module_whose_every_shipped_subject_is_dead_is_an_orphaned_test(result: UnreachableCodeResult) -> None:
    """Code consumed only by its own tests drags those tests into the findings.

    ``test_things`` imports a test-only module, a test-only function, and a
    module inside a dead package, so it exists only to exercise dead code.
    ``test_live`` also imports the live ``run`` and is not reported, and a
    test that imports nothing shipped is not a subject of the audit at all.
    """
    by_module = {finding.module: finding for finding in result.tests}

    assert set(by_module) == {"pkg.tests.test_things"}
    orphan = by_module["pkg.tests.test_things"]
    assert orphan.path == "src/pkg/tests/test_things.py"
    assert orphan.subjects == ("pkg.dead.a", "pkg.loner", "pkg.used:orphan_fn")
    assert orphan.confidence is Confidence.EXACT
    assert orphan.id == "test:pkg.tests.test_things"


def test_findings_carry_confidence_tiers_and_stable_ids(result: UnreachableCodeResult) -> None:
    """Agents pick findings up by id and triage by how the finding was derived."""
    modules = {finding.module: finding for finding in result.modules}
    symbols = {finding.qualname: finding for finding in result.symbols}

    assert modules["pkg.dead"].confidence is Confidence.EXACT
    assert modules["pkg.dead"].id == "module:pkg.dead"
    assert symbols["orphan_fn"].confidence is Confidence.EXACT
    assert symbols["orphan_fn"].id == "symbol:pkg.used:orphan_fn"
    assert symbols["UNUSED_CONST"].confidence is Confidence.EXACT
    assert symbols["Widget.hidden"].confidence is Confidence.NAME_MATCH
    assert symbols["Color.BLUE"].confidence is Confidence.NAME_MATCH_DATA
    assert symbols["Widget.hidden_field"].confidence is Confidence.NAME_MATCH_DATA
    assert symbols["Widget.hidden"].id == "symbol:pkg.used:Widget.hidden"


def test_exact_findings_are_the_campaign_ready_subset(result: UnreachableCodeResult) -> None:
    """The exact tier collects modules, orphaned tests, and resolved top-level symbols."""
    exact = {finding.id for finding in result.exact_findings}

    assert "module:pkg.dead" in exact
    assert "test:pkg.tests.test_things" in exact
    assert "symbol:pkg.used:orphan_fn" in exact
    assert "symbol:pkg.used:Widget.hidden" not in exact
    assert all(finding.confidence is Confidence.EXACT for finding in result.exact_findings)


def test_filtering_to_one_tier_keeps_the_counts_and_drops_the_rest(result: UnreachableCodeResult) -> None:
    """A narrowed result reports only that tier but still says what the tree looks like."""
    narrowed = filter_by_confidence(result, Confidence.NAME_MATCH)

    assert narrowed.modules == ()
    assert narrowed.tests == ()
    assert {finding.qualname for finding in narrowed.symbols} == {"Widget.hidden"}
    assert narrowed.shipped_modules == result.shipped_modules
    assert narrowed.reachable_modules == result.reachable_modules


def test_iterated_enum_members_are_not_individually_reported(result: UnreachableCodeResult) -> None:
    """``for modelo in Modelo`` reaches every member, so neither M100 nor M303 is a finding."""
    assert not any(finding.qualname.startswith("Modelo.") for finding in result.symbols)


def test_clean_tree_is_green(tmp_path: Path) -> None:
    """A tree whose every module and symbol is reached lands on CLEAN."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/cli.py", "from .work import go\n\n\ndef main() -> None:\n    go()\n")
    _write(tmp_path, "src/pkg/work.py", "def go() -> None: ...\n")
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )

    outcome = scan_unreachable_code(spec)

    assert outcome.outcome is UnreachableCodeOutcome.CLEAN
    assert outcome.is_green
    assert outcome.reachable_modules == outcome.shipped_modules == 3
    assert "every shipped module and symbol is reachable" in outcome.headline()


def test_outside_relative_import_is_credited_at_every_nesting_depth(tmp_path: Path) -> None:
    """An outside file's relative import resolves from its own position, not a fake name.

    In-source tests reach their subject almost exclusively through relative
    imports, and a harness tree does the same within itself. Probing such a
    file under a synthetic flat name resolves only single-level imports, so a
    module reached by ``from ...deep import x`` is labelled as used by nobody
    and reads as dead. Both directions are asserted: the deeply-relative
    subject earns its label, and the module nothing imports keeps an empty one.
    """
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/cli.py", "def main() -> None: ...\n")
    _write(tmp_path, "src/pkg/deep.py", "def probed() -> None: ...\n")
    _write(tmp_path, "src/pkg/nobody.py", "def unprobed() -> None: ...\n")
    _write(tmp_path, "src/pkg/a/__init__.py")
    _write(tmp_path, "src/pkg/a/b/__init__.py")
    _write(tmp_path, "src/pkg/a/b/tests/__init__.py")
    _write(tmp_path, "src/pkg/a/b/tests/test_deep.py", "from ....deep import probed\n")
    _write(tmp_path, "dev/pack/__init__.py")
    _write(tmp_path, "dev/pack/inner/__init__.py")
    _write(tmp_path, "dev/pack/inner/tool.py", "from ...sibling import nothing\n")
    _write(tmp_path, "dev/sibling.py", "nothing = 1\n")
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
        outside=(
            OutsideCorpus(label="tests", root=tmp_path / "src" / "pkg", test_modules_only=True),
            OutsideCorpus(label="dev", root=tmp_path / "dev"),
        ),
    )

    outcome = scan_unreachable_code(spec)
    by_module = {finding.module: finding for finding in outcome.modules}

    assert by_module["pkg.deep"].used_by == ("tests",)
    assert by_module["pkg.nobody"].used_by == ()


def test_unparseable_shipped_module_is_an_error_not_a_verdict(tmp_path: Path) -> None:
    """A syntax error cannot be classified as clean or as findings."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/cli.py", "def main(:\n")
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )

    outcome = scan_unreachable_code(spec)

    assert outcome.outcome is UnreachableCodeOutcome.ERROR
    assert not outcome.is_green
    assert "cli.py" in outcome.reason


def test_missing_entry_point_module_is_an_error(tmp_path: Path) -> None:
    """A root the tree does not contain would silently make everything unreachable."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/present.py", "def go() -> None: ...\n")
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.absent", "main"),),
        exclude_globs=_EXCLUDES,
    )

    outcome = scan_unreachable_code(spec)

    assert outcome.outcome is UnreachableCodeOutcome.ERROR
    assert "pkg.absent" in outcome.reason


def test_console_report_and_json_carry_the_same_findings(result: UnreachableCodeResult) -> None:
    """Both renderings name every module, test, and symbol finding with its tier."""
    report = render_console_report(result, full=True)
    payload = json.loads(result_as_json(result))
    orphan_line = "src/pkg/tests/test_things.py  exercises only: pkg.dead.a, pkg.loner, pkg.used:orphan_fn"

    assert report.startswith(
        "unreachable code: 4 unreachable module(s), 3 module-exec-only, 1 type-only module(s), "
        "7 unused symbol(s) in reachable modules, 1 orphaned test module(s)"
    )
    assert "roots: pkg.cli:main" in report
    assert "2 data-shaped member(s) cleared" in report
    assert "package  src/pkg/dead/  (3 modules)  [used by: dev, tests]" in report
    assert "module   src/pkg/loner.py  [used by: tests]" in report
    assert f"{orphan_line}  [exact]" in report
    assert "method      Widget.hidden  [no use anywhere]  [name-match]" in report
    assert "enum-member Color.BLUE  [no use anywhere]  [name-match-data]" in report
    assert "function    orphan_fn  [used by: tests]  [exact]" in report
    assert payload["outcome"] == "findings"
    assert payload["data_cleared"] == 2
    assert {entry["module"] for entry in payload["modules"]} == {
        "pkg.dead",
        "pkg.loner",
        "pkg.typed",
        "pkg.tool",
        "pkg.tool.__main__",
        "pkg.tool.work",
    }
    assert {entry["qualname"] for entry in payload["symbols"]} == {f.qualname for f in result.symbols}
    assert [entry["id"] for entry in payload["tests"]] == ["test:pkg.tests.test_things"]
    assert set(payload["exact_finding_ids"]) == {f.id for f in result.exact_findings}
    assert {entry["confidence"] for entry in payload["modules"]} == {"exact"}


def test_console_report_caps_each_section_unless_full(result: UnreachableCodeResult) -> None:
    """The cap applies per section and announces what it hid."""
    capped = render_console_report(result, cap=1)

    assert "... 1 more (--full for all)" in capped
    assert "... 6 more (--full for all)" in capped
    assert "more (--full for all)" not in render_console_report(result, full=True, cap=1)


def test_repository_spec_reads_the_console_scripts_from_pyproject() -> None:
    """Roots come from ``[project.scripts]``, never from a restated list."""
    spec = ShippedTreeSpec.from_repository(REPO_ROOT)

    assert spec.package == "cadrumo"
    # `aeat` is the only console script the product declares; the full-screen
    # session is reached through `aeat --tui`, which starts the module-execution
    # surface below rather than a second console entry.
    assert "cadrumo.entrypoints._cli_main:main" in {entry.spec for entry in spec.entry_points}
    assert "cadrumo.entrypoints.tui.__main__" in spec.module_roots
    assert any(glob.endswith("tests/**") for glob in spec.exclude_globs)
    assert {corpus.label for corpus in spec.outside} == {"tests", "dev"}
    assert spec.data_globs


def test_extra_roots_join_the_declared_console_scripts() -> None:
    """A ``python -m`` surface can be admitted as a root for one run without editing packaging."""
    spec = ShippedTreeSpec.from_repository(REPO_ROOT, extra_roots=("cadrumo.entrypoints.tui.devtools.__main__:main",))

    assert spec.entry_points[-1] == EntryPoint("cadrumo.entrypoints.tui.devtools.__main__", "main")


def test_entry_point_parse_rejects_malformed_specs() -> None:
    """A console script without ``module:attribute`` shape cannot seed the walk."""
    with pytest.raises(ValueError, match="module:attribute"):
        EntryPoint.parse("cadrumo.entrypoints.main")
