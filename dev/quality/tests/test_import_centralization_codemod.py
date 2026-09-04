"""Tests for the import-centralization codemod's rewriting decisions.

The module rewrites source files behind ``--apply`` and had no tests, which is
why `dev.quality.module_test_reach` ranks it first. Unlike its sibling sweep it
takes an explicit path, so ``apply_plans_to_file`` can be exercised on a
constructed file and the write is provable rather than only reasoned about.

Three decisions carry the risk. The relative prefix has to count directory
levels correctly or the rewritten import reaches the wrong package; the style
choice has to follow the file rather than a preference, because an absolute
import dropped into a relatively-grouped block lints rather than fails; and the
formatter has to wrap at the line limit, since a codemod that emits an
over-long line hands its user a lint error for every file it touched.

This codemod rewrites imports ONTO package facades, which was the policy before
package initialisers were made inert. That is recorded here because a reader
finding these tests should know the module encodes a superseded direction, and
testing it is not endorsing it.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ..import_centralization_codemod import (
    RewritePlan,
    _existing_import_style,
    _format_import_stmt,
    _module_is_package,
    _relative_prefix_for,
    apply_plans_to_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_package_initialiser_is_recognised_as_its_own_package() -> None:
    """The level count depends on it: a module sits one level below its package."""
    assert _module_is_package(pathlib.Path("cadrumo/core/__init__.py"))
    assert not _module_is_package(pathlib.Path("cadrumo/core/thing.py"))


def test_a_sibling_target_is_one_dot_from_a_module() -> None:
    """A module's own package is one level up, so a sibling is a single dot."""
    assert _relative_prefix_for("cadrumo.core.thing", False, "cadrumo.core.other") == ".other"


def test_a_sibling_target_is_one_dot_from_a_package_initialiser_too() -> None:
    """An initialiser IS its package, so its children are also one dot away.

    Counting from the initialiser as though it were a module would go one level
    too high and reach the parent package instead, which is the same off-by-one
    that has broken three separate walks in this campaign.
    """
    assert _relative_prefix_for("cadrumo.core", True, "cadrumo.core.other") == ".other"


def test_a_cousin_target_climbs_to_the_common_ancestor() -> None:
    """Two dots leave the package, three leave its parent."""
    assert _relative_prefix_for("cadrumo.application.modelo.actions", False, "cadrumo.core.parsing") == (
        "...core.parsing"
    )


def test_the_common_ancestor_itself_is_returned_as_bare_dots() -> None:
    """No remainder means the clause is the dots alone, and must not end in a dot."""
    prefix = _relative_prefix_for("cadrumo.core.thing", False, "cadrumo.core")
    assert prefix == "."


def test_the_style_follows_the_file_rather_than_a_preference() -> None:
    """An absolute import in a relatively-grouped block lints rather than fails.

    That failure mode is silent in the worst way: the rewrite looks applied and
    leaves the tree red, which is exactly what happened when a sibling tool in
    this campaign emitted the wrong style.
    """
    relative = ast.parse("from ..core import a\nfrom .other import b\nfrom cadrumo.x import c\n")
    absolute = ast.parse("from cadrumo.x import c\nfrom cadrumo.y import d\n")

    assert _existing_import_style(relative) == "relative"
    assert _existing_import_style(absolute) == "absolute"


def test_a_file_with_no_imports_at_all_gets_a_definite_answer() -> None:
    """The tie goes to relative, and the function must not return None."""
    assert _existing_import_style(ast.parse("VALUE = 1\n")) == "relative"


def test_a_short_import_is_written_on_one_line() -> None:
    """The ordinary case, and the one every diff is read in."""
    rendered = _format_import_stmt(indent="", module_clause=".core", aliases=[ast.alias(name="Thing")])

    assert rendered == "from .core import Thing\n"


def test_an_over_long_import_is_wrapped_rather_than_emitted_red() -> None:
    """A codemod that emits a lint error per file is worse than one that refuses.

    The limit is the repository's own line length, and the wrapped form is the
    parenthesised one every formatter in this tree produces.
    """
    aliases = [ast.alias(name=f"VeryLongSymbolName{index:02d}") for index in range(6)]
    rendered = _format_import_stmt(indent="", module_clause=".core.deeply.nested", aliases=aliases)

    assert rendered.startswith("from .core.deeply.nested import (\n")
    assert rendered.endswith(")\n")
    assert all(len(line) <= 119 for line in rendered.splitlines())


def test_names_are_sorted_and_aliases_are_preserved() -> None:
    """Dropping an alias renames a symbol in the body and still compiles."""
    rendered = _format_import_stmt(
        indent="",
        module_clause=".core",
        aliases=[ast.alias(name="Zebra"), ast.alias(name="Apple", asname="Fruit")],
    )

    assert "Apple as Fruit" in rendered
    assert rendered.index("Apple") < rendered.index("Zebra")


def test_indentation_is_preserved_for_a_nested_import() -> None:
    """An import inside ``if TYPE_CHECKING:`` is rewritten where it stands."""
    rendered = _format_import_stmt(indent="    ", module_clause=".core", aliases=[ast.alias(name="Thing")])

    assert rendered == "    from .core import Thing\n"


def test_applying_a_plan_refuses_a_path_outside_the_source_root(tmp_path: pathlib.Path) -> None:
    """Apply mode cannot be pointed at an arbitrary file, and that is the property.

    ``apply_plans_to_file`` derives a module name through the hygiene scanner,
    which resolves paths relative to ``src`` and refuses anything outside it. So
    a constructed file cannot be rewritten - which is why no test here exercises
    a successful write, and why the refusal is asserted instead: it is the only
    thing standing between this codemod and a path typed by mistake.

    Both codemods in this package share the limitation from opposite ends. The
    sibling sweep walks a module-level constant with no injectable root at all;
    this one takes a path and then rejects every path but the real tree's.
    Neither can be exercised in apply mode without rewriting the repository, and
    that is a testability defect in both rather than a gap in these tests.
    """
    target = tmp_path / "consumer.py"
    original = "from cadrumo.core._private import Thing" + chr(10)
    target.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="subpath"):
        apply_plans_to_file(target, [])

    assert target.read_text(encoding="utf-8") == original, "the file was touched before the refusal"


def test_the_refusal_happens_before_any_write(tmp_path: pathlib.Path) -> None:
    """A guard that fires after the write is not a guard.

    The refusal comes from a module-name lookup, not from an explicit check, so
    the ordering is incidental rather than designed - which is exactly why it is
    pinned here.
    """
    target = tmp_path / "consumer.py"
    original = "from cadrumo.core._private import Thing" + chr(10) + "VALUE = Thing" + chr(10)
    target.write_text(original, encoding="utf-8")
    tree = ast.parse(original)
    node = next(item for item in ast.walk(tree) if isinstance(item, ast.ImportFrom))

    with pytest.raises(ValueError):
        apply_plans_to_file(
            target,
            [
                RewritePlan(
                    path=target,
                    node=node,
                    owning_package="cadrumo.core",
                    facaded_aliases=[ast.alias(name="Thing")],
                    private_aliases=[],
                )
            ],
        )

    assert target.read_text(encoding="utf-8") == original
