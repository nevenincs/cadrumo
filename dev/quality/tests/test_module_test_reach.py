"""Real-behaviour tests for the module-reach report.

Its subject is which modules nobody tests, so the first thing it must be right
about is what counts as being reached - a question this campaign got wrong three
times in hand-written walks. The report asks the shared resolver instead, and
these tests pin the two halves that make its output mean something: reach, and
the capability ranking that decides which unreached module matters.
"""

from __future__ import annotations

import ast
import collections
import os
import pathlib

import pytest

from ..module_test_reach import CAPABILITIES, UnreachedModule, module_capabilities, unreached_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def relative_root(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch tree entered as the working directory, yielded as ``.``.

    A module's dotted name is derived from its path parts, so the report is
    always invoked with a repository-relative path.
    """
    previous = pathlib.Path.cwd()
    os.chdir(tmp_path)
    try:
        yield pathlib.Path()
    finally:
        os.chdir(previous)


def _tree(root: pathlib.Path) -> pathlib.Path:
    package = root / "pkg"
    (package / "tests").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (package / "reached.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "lonely.py").write_text("VALUE = 2\n", encoding="utf-8")
    return package


def test_a_module_a_test_imports_is_reached(relative_root: pathlib.Path) -> None:
    """The ordinary case, and the baseline for every other assertion here."""
    package = _tree(relative_root)
    (package / "tests" / "test_reached.py").write_text("from ..reached import VALUE\n", encoding="utf-8")

    unreached = {item.dotted for item in unreached_modules(relative_root)}
    assert "pkg.reached" not in unreached
    assert "pkg.lonely" in unreached


def test_a_module_imported_by_name_from_its_package_is_reached(
    relative_root: pathlib.Path,
) -> None:
    """The shape a hand-written version of this report got wrong.

    ``from .. import reached`` resolves to the PACKAGE, so a walk that credits
    only the resolved target calls the module untested while its test sits
    beside it. That mistake reported six tested modules as untested here.
    """
    package = _tree(relative_root)
    (package / "tests" / "test_reached.py").write_text("from .. import reached\n", encoding="utf-8")

    assert "pkg.reached" not in {item.dotted for item in unreached_modules(relative_root)}


def test_a_package_initialiser_is_never_reported(relative_root: pathlib.Path) -> None:
    """They are inert namespace markers here, so "no test imports it" says nothing."""
    _tree(relative_root)
    assert not [item for item in unreached_modules(relative_root) if item.dotted.endswith("__init__")]


def test_a_writing_module_is_ranked_above_a_reporting_one() -> None:
    """ "Untested" means something different for a codemod than for a census."""
    writer = UnreachedModule(dotted="a", path="a.py", capabilities=("writes", "operator"))
    reporter = UnreachedModule(dotted="b", path="b.py", capabilities=("operator",))
    silent = UnreachedModule(dotted="c", path="c.py", capabilities=())

    assert writer.rank < reporter.rank < silent.rank


def test_every_capability_is_read_from_the_syntax(relative_root: pathlib.Path) -> None:
    """Importing a module to ask what it does acquires the side effects measured.

    Each capability is detected from a constructed source rather than from the
    live tree, so a kind that stops being attributed fails here rather than
    quietly emptying.
    """
    writes = ast.parse("import pathlib\npathlib.Path('x').write_text('y')\n")
    applies = ast.parse("parser.add_argument('--apply', action='store_true')\n")
    operator = ast.parse("def main() -> int:\n    return 0\n")

    assert module_capabilities(writes) == ("writes",)
    assert module_capabilities(applies) == ("applies",)
    assert module_capabilities(operator) == ("operator",)
    assert set(CAPABILITIES) == {"writes", "applies", "operator"}


def test_capabilities_are_reported_worst_first() -> None:
    """The order is the ranking, so it is asserted rather than assumed."""
    tree = ast.parse(
        "def main() -> int:\n    parser.add_argument('--apply')\n    pathlib.Path('x').write_text('y')\n    return 0\n"
    )
    assert module_capabilities(tree) == ("writes", "applies", "operator")


def test_a_module_that_only_reads_carries_no_capability() -> None:
    """Absence is a real answer here: some unreached modules can do nothing."""
    assert module_capabilities(ast.parse("VALUE = pathlib.Path('x').read_text()\n")) == ()


def test_the_live_tree_reports_a_ranked_population() -> None:
    """The report must discriminate on the real tree, or its ordering means nothing."""
    unreached = unreached_modules()
    assert unreached, "no unreached module found, so this proves nothing"

    ranks = [item.rank for item in unreached]
    assert ranks == sorted(ranks), "the report is not ordered by capability"
    assert any("writes" in item.capabilities for item in unreached)
    assert any(not item.capabilities for item in unreached)


def test_this_report_is_itself_reached_by_a_test() -> None:
    """The measurement includes its own module, and this is why it does not appear.

    Before these tests existed the report counted 43 modules, itself among them.
    A tool that reports on the tree it lives in should be subject to what it
    reports, and the honest way to leave that list is to be tested.
    """
    assert "dev.quality.module_test_reach" not in {item.dotted for item in unreached_modules()}


def test_a_string_replace_is_not_a_write() -> None:
    """``str.replace`` is far commoner than ``Path.replace`` and must not rank.

    The write-call set matched ``replace`` on the attribute name, and no
    attribute-name test can tell the two apart. It attributed ``writes`` to two
    modules whose only offence was normalising a path separator - putting a
    string method in the same rank as a codemod, which is the costliest failure
    a ranking report can make. The live figure fell from fourteen writing
    modules to nine when it was removed.
    """
    normalising = ast.parse("forward = path.replace(chr(92), '/')\n")
    assert module_capabilities(normalising) == ()


def test_the_unambiguous_write_calls_still_rank() -> None:
    """Removing one ambiguous name must not quietly empty the category.

    Each survivor is a call no common string or collection method shares, so an
    attribute-name match is sound for them in a way it was not for ``replace``.
    """
    for call in ("write_text", "write_bytes", "rename", "unlink", "mkdir", "rmdir"):
        tree = ast.parse(f"target.{call}()\n")
        assert module_capabilities(tree) == ("writes",), f"{call} stopped counting as a write"


def _evidence_for(capability: str, tree: ast.Module) -> list[ast.AST]:
    """Return the syntax the report must be able to point at for ``capability``.

    Deliberately not a second implementation of the detector: it reads the same
    trees back and asks whether the evidence exists, so a disagreement means a
    capability was attributed from somewhere invisible rather than that two
    detectors happen to differ.
    """
    from ..module_test_reach import _WRITE_CALLS

    if capability == "writes":
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _WRITE_CALLS
        ]
    if capability == "applies":
        return [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value == "--apply"]
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "main"]


def test_every_live_attribution_has_evidence_the_report_can_point_at() -> None:
    """Each ranked module is checked against the syntax that ranked it.

    Two false positives were found by noticing an implausible module name, which
    is not a method: it does not scale past the modules a reader happens to
    know. This asks the question of every attribution of every capability
    instead.

    Asked of all three deliberately. Checking only ``writes`` would leave the
    asymmetry this campaign keeps finding - one category with a proof and two
    without - inside the module that exists to rank them.
    """
    from ..module_test_reach import CAPABILITIES, unreached_modules

    unreached = unreached_modules()
    assert unreached, "nothing was reported, so this proves nothing"

    checked: collections.Counter[str] = collections.Counter()
    for item in unreached:
        tree = ast.parse(pathlib.Path(item.path).read_text(encoding="utf-8"))
        for capability in item.capabilities:
            assert _evidence_for(capability, tree), f"{item.path} is ranked {capability} with nothing to show"
            checked[capability] += 1

    for capability in CAPABILITIES:
        assert checked[capability], f"no live module carries {capability}, so it proves nothing"
