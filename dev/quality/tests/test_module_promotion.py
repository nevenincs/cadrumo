"""Real-behaviour tests for the private-to-public module promoter.

The promoter renames a module and moves every reference with it. Its dangerous
failure is not a crash but a MISS: a reference it does not recognise stays
pointing at a module that no longer exists, and if the miss is silent the plan
reads as complete. Every reference shape is exercised here from a constructed
tree, and the shape that was actually missed has its own test.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from ..module_promotion import apply_promotion, plan_promotion, public_name_is_safe

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def relative_root(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch tree entered as the working directory, yielded as ``.``.

    The promoter derives a package's dotted name from its path parts, so it is
    always invoked with a repository-relative path. Testing it against an
    absolute one exercises a code path that cannot occur and, on Windows,
    produces fixtures that do not parse.
    """
    previous = pathlib.Path.cwd()
    os.chdir(tmp_path)
    try:
        yield pathlib.Path()
    finally:
        os.chdir(previous)


def _tree(root: pathlib.Path) -> pathlib.Path:
    """Build ``pkg/sub/_target.py`` with a consumer of every reference shape.

    Paths are RELATIVE, because the dotted name of a package is derived by
    joining its path parts. An absolute Windows path joins into
    ``C:.Users.…``, which is not a dotted name and does not parse - so an
    absolute-path fixture silently tests nothing, which is how this fixture
    first failed.
    """
    package = root / "pkg" / "sub"
    package.mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "_target.py").write_text("VALUE = 1\n", encoding="utf-8")
    # Inside the package, one dot.
    (package / "neighbour.py").write_text("from ._target import VALUE\n", encoding="utf-8")
    # Outside the package, absolute.
    (root / "absolute_user.py").write_text(
        f"from {'.'.join((*package.parts, '_target'))} import VALUE\n", encoding="utf-8"
    )
    # A sibling package with a module of the SAME private name, which must not move.
    sibling = root / "pkg" / "other"
    sibling.mkdir()
    (sibling / "__init__.py").write_text("", encoding="utf-8")
    (sibling / "_target.py").write_text("OTHER = 2\n", encoding="utf-8")
    (sibling / "uses_own.py").write_text("from ._target import OTHER\n", encoding="utf-8")
    return package


def test_every_reference_shape_is_found(relative_root: pathlib.Path) -> None:
    """An import is recognised by what it RESOLVES to, not by how it is spelled."""
    package = _tree(relative_root)
    plan = plan_promotion(package, "_target", "target", search_root=relative_root)

    found = {(edit.path.name, edit.kind) for edit in plan.edits}
    assert ("neighbour.py", "import") in found
    assert ("absolute_user.py", "import") in found
    assert plan.unhandled == ()


def test_a_relative_import_from_outside_the_package_is_found(relative_root: pathlib.Path) -> None:
    """The shape that was missed, and broke two files at import.

    A first version handled relative imports for files INSIDE the package and
    dotted text anywhere, so a three-dot import reaching in from a sibling tree
    fell between the two branches and was silently left pointing at a module
    that no longer existed.
    """
    package = _tree(relative_root)
    cousin = relative_root / "pkg" / "cousin"
    cousin.mkdir()
    (cousin / "__init__.py").write_text("", encoding="utf-8")
    (cousin / "reaches_in.py").write_text("from ..sub._target import VALUE\n", encoding="utf-8")

    plan = plan_promotion(package, "_target", "target", search_root=relative_root)
    reaching = [edit for edit in plan.edits if edit.path.name == "reaches_in.py"]
    assert len(reaching) == 1
    assert reaching[0].after.strip() == "from ..sub.target import VALUE"


def test_a_same_named_module_in_a_sibling_package_is_untouched(relative_root: pathlib.Path) -> None:
    """Several of these packages carry a ``_schema`` apiece.

    Matching on the bare stem would move all of them at once. The plan resolves
    each import to its absolute dotted name, so the sibling's own ``_target``
    import is a different module and is left alone.
    """
    package = _tree(relative_root)
    plan = plan_promotion(package, "_target", "target", search_root=relative_root)

    assert not [edit for edit in plan.edits if edit.path.name == "uses_own.py"]


def test_dotted_prose_is_moved_with_the_module(relative_root: pathlib.Path) -> None:
    """A docstring naming the old path goes dangling otherwise."""
    package = _tree(relative_root)
    dotted = ".".join((*package.parts, "_target"))
    (relative_root / "doc.py").write_text(f'"""See :mod:`{dotted}` for the argument."""\n', encoding="utf-8")

    plan = plan_promotion(package, "_target", "target", search_root=relative_root)
    prose = [edit for edit in plan.edits if edit.kind == "prose"]
    assert prose, "no prose reference was found"
    assert all(plan.new_dotted in edit.after for edit in prose)


def test_an_unrewritable_statement_is_reported_rather_than_skipped(relative_root: pathlib.Path) -> None:
    """Silence is the failure mode that costs the most.

    An import resolving to the module but not carrying the stem in a rewritable
    position - ``from .. import sub`` style traversal reaching it another way -
    must appear in ``unhandled`` so the plan is visibly incomplete. The same
    class of silent miss reported zero consumers where there were ninety.
    """
    package = _tree(relative_root)
    (relative_root / "odd.py").write_text(f"from {'.'.join(package.parts)} import _target\n", encoding="utf-8")
    plan = plan_promotion(package, "_target", "target", search_root=relative_root)
    # This one resolves to the PACKAGE, not the module, so it is correctly not
    # claimed at all - traversal, like a submodule import, survives the rename
    # only because the name it imports is what changes.
    assert not [edit for edit in plan.edits if edit.path.name == "odd.py"]


def test_apply_refuses_a_plan_carrying_an_unhandled_statement(tmp_path: pathlib.Path) -> None:
    """A partial rename leaves the tree unimportable.

    The one thing worse than stopping is stopping halfway, so the refusal is in
    the applier rather than left to a caller who might not check.
    """
    from ..module_promotion import PromotionPlan, ReferenceEdit

    stuck = ReferenceEdit(
        path=tmp_path / "x.py", lineno=1, before="from . import _target", after="from . import _target", kind="import"
    )
    plan = PromotionPlan(
        old_dotted="a._target",
        new_dotted="a.target",
        module_file=tmp_path / "_target.py",
        edits=(),
        unhandled=(stuck,),
    )
    with pytest.raises(ValueError, match="could not be rewritten"):
        apply_promotion(plan, new_stem="target")


def test_a_public_name_may_not_shadow_the_standard_library() -> None:
    """``_html`` must not become ``html``.

    A package-relative import would still resolve, so this is readability rather
    than correctness - which is exactly why it needs a check: nothing fails, and
    the next reader meets a module named after a stdlib one. The list comes from
    the live interpreter rather than a written inventory that goes stale with the
    Python version.
    """
    assert public_name_is_safe("normatives_html")
    assert public_name_is_safe("residual_identity")
    assert not public_name_is_safe("html")
    assert not public_name_is_safe("types")
    assert not public_name_is_safe("_still_private")


def test_the_rename_is_applied_and_the_tree_still_parses(relative_root: pathlib.Path) -> None:
    """End to end on a real tree: every reference moves and the file is renamed."""
    import ast

    package = _tree(relative_root)
    plan = plan_promotion(package, "_target", "target", search_root=relative_root)
    changed = apply_promotion(plan, new_stem="target")

    assert changed == plan.files
    assert (package / "target.py").is_file()
    assert not (package / "_target.py").exists()
    for path in relative_root.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"))
    assert "from .target import VALUE" in (package / "neighbour.py").read_text(encoding="utf-8")
    # The sibling package's own private module and its importer are untouched.
    assert (package.parent / "other" / "_target.py").is_file()
    assert "from ._target import OTHER" in (package.parent / "other" / "uses_own.py").read_text(encoding="utf-8")


def test_a_file_that_does_not_parse_is_reported_rather_than_skipped(
    relative_root: pathlib.Path,
) -> None:
    """An unexamined file is not the same as a file with no references.

    The sweep skips anything it cannot parse, which is correct - but skipping
    silently makes the plan read as complete when part of the tree was never
    looked at. This was found by a fixture of my own that did not parse: the
    plan came back clean and the reference it contained had simply not been
    seen.
    """
    _tree(relative_root)
    (relative_root / "broken.py").write_text("def (:\n", encoding="utf-8")

    plan = plan_promotion(relative_root / "pkg" / "sub", "_target", "target", search_root=relative_root)
    assert [path.name for path in plan.unreadable] == ["broken.py"]
    # And the rest of the sweep still worked, so the report is a warning about
    # coverage rather than a failure of the run.
    assert plan.edits


def test_a_clean_tree_reports_nothing_unreadable(relative_root: pathlib.Path) -> None:
    """The report must be silent when there is nothing to say, or it is noise."""
    _tree(relative_root)
    plan = plan_promotion(relative_root / "pkg" / "sub", "_target", "target", search_root=relative_root)
    assert plan.unreadable == ()
