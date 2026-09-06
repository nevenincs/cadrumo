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

    unreached = {item.dotted for item in unreached_modules(relative_root)}

    assert "pkg.lonely" in unreached, (
        "the report named nothing untested, so the claim below would hold because the walk found no modules at all"
    )
    assert "pkg.reached" not in unreached


def test_a_package_initialiser_is_never_reported(relative_root: pathlib.Path) -> None:
    """They are inert namespace markers here, so "no test imports it" says nothing.

    This tree carries no test at all, so both real modules are untested and
    must be reported. Pinning that set is what stops the claim below being
    satisfied by a walk that reported nothing: an empty report contains no
    initialiser either.
    """
    _tree(relative_root)

    reported = {item.dotted for item in unreached_modules(relative_root)}

    assert reported == {"pkg.reached", "pkg.lonely"}, (
        f"the walk must report both untested modules for the absence below to mean anything, "
        f"but reported {sorted(reported)}"
    )
    assert not [name for name in reported if name.endswith("__init__")]


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

    Not a second implementation of the detector: it calls the same predicate
    over a freshly parsed tree and asks whether the evidence is still there, so
    a disagreement means a capability was attributed to a module whose source
    does not carry it. Re-stating the predicate here instead is what made this
    read only one of the two branches that rank a write, so a module ranked by
    a bare ``*write_text`` helper would have been reported as evidence-free by
    the very check meant to confirm it.
    """
    from ..module_test_reach import is_write_call

    if capability == "writes":
        return [node for node in ast.walk(tree) if is_write_call(node)]
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

    # A capability with no live member is not a failure: this package's standing
    # rule is that a condition emptied by a correction keeps its proof rather
    # than being deleted. ``applies`` emptied exactly that way - both modules
    # declaring an apply flag were tested, and the category that ranked first
    # when this report was built is now empty. What must hold is that every
    # capability is reachable from SOMETHING, live or constructed.
    constructed = {
        "writes": ast.parse("target.write_text('x')" + chr(10)),
        "applies": ast.parse("parser.add_argument('--apply')" + chr(10)),
        "operator": ast.parse("def main() -> int:" + chr(10) + "    return 0" + chr(10)),
    }
    for capability in CAPABILITIES:
        assert checked[capability] or _evidence_for(capability, constructed[capability]), (
            f"{capability} has no live member and no constructed proof, so it proves nothing"
        )


def test_the_evidence_check_can_report_an_absence() -> None:
    """A checker that always finds evidence proves nothing about the report.

    Each capability is asked of a tree that carries none of it, so the assertion
    above is known to be capable of failing rather than merely observed to pass.
    """
    barren = ast.parse("value = other.read_text()\n")

    assert _evidence_for("writes", barren) == []
    assert _evidence_for("applies", barren) == []
    assert _evidence_for("operator", barren) == []

    assert _evidence_for("writes", ast.parse("target.write_text('x')\n"))
    assert _evidence_for("applies", ast.parse("parser.add_argument('--apply')\n"))
    assert _evidence_for("operator", ast.parse("def main() -> int:\n    return 0\n"))


def test_an_unreadable_test_is_announced_as_inflating_the_list(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A skipped test contributes no imports, so what it covers looks unreached.

    This list is used to choose work, so a false entry costs an iteration spent
    testing something already tested. The skip stays - a concurrently edited
    tree can present a half-written file - but it is no longer silent.
    """
    (tmp_path / "subject.py").write_text("VALUE = 1" + chr(10), encoding="utf-8")
    (tmp_path / "test_broken.py").write_text("def (:" + chr(10), encoding="utf-8")

    unreached_modules(tmp_path)

    error = capsys.readouterr().err
    assert "test module(s) could not be read" in error
    assert "test_broken.py" in error


def test_an_unreadable_module_is_announced_as_absent_from_the_report(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The opposite direction: the finding disappears rather than being false.

    A module that cannot be parsed is dropped from the result, so a genuinely
    unreached module becomes invisible - the report shrinks by exactly the file
    nobody could read.
    """
    (tmp_path / "broken.py").write_text("def (:" + chr(10), encoding="utf-8")

    reported = unreached_modules(tmp_path)

    assert "broken" not in {item.dotted.rsplit(".", 1)[-1] for item in reported}
    assert "absent from this report entirely" in capsys.readouterr().err


def test_a_readable_tree_announces_nothing(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A notice that fires for every run would carry no information."""
    (tmp_path / "subject.py").write_text("VALUE = 1" + chr(10), encoding="utf-8")

    unreached_modules(tmp_path)

    assert capsys.readouterr().err == ""
