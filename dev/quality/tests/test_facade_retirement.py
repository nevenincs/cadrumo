"""Real-behaviour tests for the facade-retirement rewriter.

The rewriter edits source files, so its failure modes are expensive: a wrong
import compiles and imports the wrong symbol, and a missed one leaves a facade
that cannot be emptied. Every judgement it makes is exercised here from a
constructed package tree, never by pointing it at the live one and hoping.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ..facade_retirement import (
    FacadePackage,
    ImportSite,
    facade_exports,
    facade_import_sites,
    relative_spelling,
    resolve_relative,
    submodule_names,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _package(tmp_path: pathlib.Path) -> pathlib.Path:
    """Build a package whose initialiser forwards two names from one module."""
    package = tmp_path / "widget"
    package.mkdir()
    (package / "__init__.py").write_text(
        'from __future__ import annotations\n\nfrom .engine import Motor, Spring\n\n__all__ = ["Motor", "Spring"]\n',
        encoding="utf-8",
    )
    (package / "engine.py").write_text("class Motor:\n    pass\n\n\nclass Spring:\n    pass\n", encoding="utf-8")
    (package / "errors.py").write_text("class WidgetError(Exception):\n    pass\n", encoding="utf-8")
    return package


def test_the_forwarding_map_is_read_from_the_initialiser_itself(tmp_path: pathlib.Path) -> None:
    """The mapping is already written down; a second copy would go stale."""
    package = facade_exports(_package(tmp_path))
    assert package.exports == {
        "Motor": ".".join((*tmp_path.parts, "widget", "engine")),
        "Spring": ".".join((*tmp_path.parts, "widget", "engine")),
    }


def test_a_future_import_is_not_counted_as_a_re_export(tmp_path: pathlib.Path) -> None:
    """A compiler directive is not a forwarded name.

    Counting it inflated every facade by exactly one, and a constant offset
    reads as two definitions disagreeing rather than as a defect: the live count
    came out at 397 against an independent 388 and the gap looked like a
    question of what to count.
    """
    package = facade_exports(_package(tmp_path))
    assert "annotations" not in package.exports
    assert len(package.exports) == 2


def test_submodules_are_distinguished_from_forwarded_names(tmp_path: pathlib.Path) -> None:
    """A submodule survives the retirement and must not be repointed."""
    directory = _package(tmp_path)
    assert submodule_names(directory) == frozenset({"engine", "errors"})
    assert "errors" not in facade_exports(directory).exports


def test_a_relative_import_in_a_module_resolves_to_its_containing_package() -> None:
    """The bug that reported every facade as having no consumers at all.

    Reading a module's own dotted name as its package makes ``from . import x``
    resolve one level too deep, so no import ever matches a package root. The
    live answer came out as zero consumers, and the true figure is 77 statements
    across 70 files. A resolver that silently reports nothing is worse than one
    that raises, so this pins the depth in both shapes.
    """
    module = ast.parse("from . import errors").body[0]
    assert isinstance(module, ast.ImportFrom)
    assert resolve_relative(module, pathlib.Path("dev/locales/cli.py")) == "dev.locales"

    initialiser = ast.parse("from .engine import Motor").body[0]
    assert isinstance(initialiser, ast.ImportFrom)
    assert resolve_relative(initialiser, pathlib.Path("dev/widget/__init__.py")) == "dev.widget.engine"

    deeper = ast.parse("from ..apidocs import Thing").body[0]
    assert isinstance(deeper, ast.ImportFrom)
    assert resolve_relative(deeper, pathlib.Path("dev/docs/tests/test_x.py")) == "dev.docs.apidocs"

    absolute = ast.parse("from dev.locales.manager import LocaleManager").body[0]
    assert isinstance(absolute, ast.ImportFrom)
    assert resolve_relative(absolute, pathlib.Path("anywhere.py")) == "dev.locales.manager"


def test_a_relative_consumer_keeps_its_relative_spelling() -> None:
    """An absolute import lands in the wrong isort group and lints as an error.

    The rewrite would look applied and leave the tree red, which is the worst of
    the available outcomes: the work appears done.
    """
    assert relative_spelling("dev.docs.apidocs.manager", consumer_package="dev.docs") == ".apidocs.manager"
    assert relative_spelling("dev.docs.apidocs.manager", consumer_package="dev.docs.tests") == "..apidocs.manager"
    assert relative_spelling("dev.locales.manager", consumer_package="dev.locales") == ".manager"
    assert relative_spelling("other.tree.thing", consumer_package="dev.docs") is None


def _site(names: tuple[tuple[str, str | None], ...], *, level: int = 0, package: str = "consumer") -> ImportSite:
    return ImportSite(
        path=pathlib.Path("consumer.py"),
        package="widget",
        lineno=1,
        end_lineno=1,
        names=names,
        indent="",
        level=level,
        consumer_package=package,
    )


_FACADE = FacadePackage(
    dotted="widget",
    exports={"Motor": "widget.engine", "Spring": "widget.engine", "Dial": "widget.panel"},
    submodules=frozenset({"engine", "panel", "errors"}),
)


def test_names_are_grouped_by_the_module_that_defines_them() -> None:
    """Six names from one facade become as many statements as there are owners."""
    from ..facade_retirement import rewrite_statement

    lines = rewrite_statement(_site((("Motor", None), ("Dial", None), ("Spring", None))), _FACADE)
    assert lines == ("from widget.engine import Motor, Spring", "from widget.panel import Dial")


def test_an_alias_is_preserved() -> None:
    """Dropping it renames a symbol in the consumer's body, and still compiles."""
    from ..facade_retirement import rewrite_statement

    assert rewrite_statement(_site((("Motor", "Engine"),)), _FACADE) == ("from widget.engine import Motor as Engine",)


def test_a_submodule_keeps_its_import_from_the_package() -> None:
    """The package still holds it, so the traversal must survive untouched."""
    from ..facade_retirement import rewrite_statement

    lines = rewrite_statement(_site((("errors", None), ("Motor", None))), _FACADE)
    assert lines == ("from widget import errors", "from widget.engine import Motor")


def test_a_name_the_facade_does_not_forward_is_refused() -> None:
    """No evidence about where it lives means no rewrite, rather than a guess."""
    from ..facade_retirement import rewrite_statement

    assert rewrite_statement(_site((("Unknown", None),)), _FACADE) == ()


def test_indentation_is_preserved_for_a_type_checking_block() -> None:
    """An import inside ``if TYPE_CHECKING:`` is rewritten where it stands."""
    from ..facade_retirement import rewrite_statement

    site = ImportSite(
        path=pathlib.Path("consumer.py"),
        package="widget",
        lineno=3,
        end_lineno=3,
        names=(("Motor", None),),
        indent="    ",
        level=0,
        consumer_package="consumer",
    )
    assert rewrite_statement(site, _FACADE) == ("    from widget.engine import Motor",)


def test_a_multi_line_parenthesised_import_is_replaced_by_its_whole_span(tmp_path: pathlib.Path) -> None:
    """A line-oriented rewrite defeats a parenthesised import in both directions.

    The statement spans four lines and its replacement spans one, so replacing
    by pattern leaves the closing parenthesis behind and the file stops parsing.
    Held by rewriting a real file and re-parsing the result.
    """
    from ..facade_retirement import apply_rewrites

    directory = _package(tmp_path)
    consumer = tmp_path / "uses.py"
    consumer.write_text(
        "from widget import (\n    Motor,\n    Spring,\n)\n\nvalue = Motor\n",
        encoding="utf-8",
    )
    package = FacadePackage(
        dotted="widget",
        exports={"Motor": "widget.engine", "Spring": "widget.engine"},
        submodules=submodule_names(directory),
    )
    sites = facade_import_sites((package,), search_root=tmp_path)
    assert len(sites) == 1, "the parenthesised statement was not found"
    assert sites[0].end_lineno - sites[0].lineno == 3

    files, rewritten = apply_rewrites(sites, (package,))
    assert (files, rewritten) == (1, 1)
    rewritten_text = consumer.read_text(encoding="utf-8")
    ast.parse(rewritten_text)
    assert rewritten_text.startswith("from widget.engine import Motor, Spring\n")
    assert ")" not in rewritten_text.splitlines()[0]


def test_the_live_report_never_names_a_submodule_or_an_unforwarded_name() -> None:
    """What the live tree offers is checked against the two exclusions.

    A site listing a submodule would put a legitimate traversal into a worklist
    that must not touch it; a site listing an unforwarded name would be a
    rewrite this module has no evidence for.
    """
    from ..facade_retirement import facade_packages

    packages = facade_packages()
    assert packages, "no dev facade was found, so this proves nothing"
    by_dotted = {package.dotted: package for package in packages}
    sites = facade_import_sites(packages)
    assert sites, "no consumer was found, so this proves nothing"
    for site in sites:
        package = by_dotted[site.package]
        forwarded = [name for name, _ in site.names if name not in package.submodules]
        assert forwarded, "a site was reported that asks the facade for nothing"
        assert all(name in package.exports for name in forwarded)


def test_a_private_target_reached_from_another_package_is_refused() -> None:
    """Retiring the facade must not create the worse violation in its place.

    A facade forwarding out of ``_residual_identity`` is the only public home
    that symbol has. Repointing an outside consumer straight at the private
    module satisfies the inert-initialiser rule and breaks module privacy in the
    same edit, and 33 of the corpus's 75 sites are in exactly that position.
    """
    from ..facade_retirement import refusal_reason, rewrite_statement

    private = FacadePackage(dotted="widget", exports={"Motor": "widget._engine"}, submodules=frozenset({"_engine"}))
    outsider = _site((("Motor", None),), package="other.package")
    assert refusal_reason(outsider, private) == "cross_package_private_target"
    assert rewrite_statement(outsider, private) == ()


def test_a_private_target_inside_the_owning_package_is_allowed() -> None:
    """A private module is private to its own package, so its tests may reach it.

    Refusing these too would leave every one of the 42 safe sites unrewritable
    and the retirement blocked everywhere rather than in the 33 places it is
    genuinely blocked.
    """
    from ..facade_retirement import refusal_reason, rewrite_statement

    private = FacadePackage(dotted="widget", exports={"Motor": "widget._engine"}, submodules=frozenset({"_engine"}))
    for package in ("widget", "widget.tests"):
        inside = _site((("Motor", None),), package=package)
        assert refusal_reason(inside, private) is None
        assert rewrite_statement(inside, private) == ("from widget._engine import Motor",)


def test_a_public_target_is_never_refused_for_privacy() -> None:
    """The refusal is about the underscore, not about crossing a package."""
    from ..facade_retirement import refusal_reason

    assert refusal_reason(_site((("Motor", None),), package="other.package"), _FACADE) is None


def test_documentation_references_move_with_the_same_map() -> None:
    """A docstring path that only the facade makes true goes dangling without this."""
    from ..facade_retirement import reference_rewrites

    package = FacadePackage(
        dotted="dev.harness",
        exports={"Scored": "dev.harness._scoring", "score": "dev.harness._scoring"},
        submodules=frozenset({"_scoring"}),
    )
    text = "See :class:`~dev.harness.Scored` and :func:`~dev.harness.score`.\n"
    rewritten, count = reference_rewrites(text, package)
    assert count == 2
    assert "dev.harness._scoring.Scored" in rewritten
    assert "dev.harness._scoring.score" in rewritten


def test_a_reference_to_a_submodule_is_not_rewritten_into_itself() -> None:
    """``dev.harness._scoring`` is a module path, not a forwarded name."""
    from ..facade_retirement import reference_rewrites

    package = FacadePackage(
        dotted="dev.harness",
        exports={"Scored": "dev.harness._scoring"},
        submodules=frozenset({"_scoring"}),
    )
    text = "Defined in :mod:`~dev.harness._scoring`.\n"
    assert reference_rewrites(text, package) == (text, 0)


def test_a_reference_does_not_claim_a_longer_name_that_starts_with_it() -> None:
    """``Scored`` must not eat the text of ``ScoredField``.

    Longest-first ordering alone does not prevent it: the shorter name is still
    tried, and without a delimiter check it matches the prefix of the longer one
    and produces a path that names nothing.
    """
    from ..facade_retirement import reference_rewrites

    package = FacadePackage(
        dotted="dev.harness",
        exports={"Scored": "dev.harness._scoring", "ScoredField": "dev.harness._fields"},
        submodules=frozenset({"_scoring", "_fields"}),
    )
    text = "Both :class:`~dev.harness.ScoredField` and :class:`~dev.harness.Scored` exist.\n"
    rewritten, count = reference_rewrites(text, package)
    assert count == 2
    assert "dev.harness._fields.ScoredField" in rewritten
    assert "dev.harness._scoring.Scored" in rewritten
    assert "_scoring.ScoredField" not in rewritten


def test_an_entry_point_target_is_refused_under_its_own_reason() -> None:
    """``__main__`` is not a privacy problem and must not be reported as one.

    It matches the underscore test, so the privacy rule would claim it and send
    a reader to make ``__main__`` public - which is not the fix and is not a
    thing anyone should do. A module run as ``python -m package`` is an entry
    point; a facade forwarding a library symbol out of one means the library
    lives inside the entry point.
    """
    from ..facade_retirement import refusal_reason, rewrite_statement

    entry = FacadePackage(dotted="widget", exports={"run": "widget.__main__"}, submodules=frozenset({"__main__"}))
    outsider = _site((("run", None),), package="other.package")
    assert refusal_reason(outsider, entry) == "entry_point_target"
    assert rewrite_statement(outsider, entry) == ()


def test_an_entry_point_target_is_refused_inside_the_owning_package_too() -> None:
    """Unlike privacy, this refusal does not soften within the package.

    A private module may legitimately be reached by its own tests. An entry
    point holding library code is wrong for everyone, including its own package,
    so the exemption that applies to the first must not apply to the second.
    """
    from ..facade_retirement import refusal_reason

    entry = FacadePackage(dotted="widget", exports={"run": "widget.__main__"}, submodules=frozenset({"__main__"}))
    assert refusal_reason(_site((("run", None),), package="widget"), entry) == "entry_point_target"
    assert refusal_reason(_site((("run", None),), package="widget.tests"), entry) == "entry_point_target"


def test_the_two_underscore_refusals_are_reported_separately_on_the_live_tree() -> None:
    """Both reasons occur live, and neither is folded into the other.

    Collapsing them would report the repository as having 33 sites needing a
    public module, when 31 need one and 2 need a library moved out of an entry
    point - different work with a different owner.
    """
    from ..facade_retirement import REFUSALS, facade_import_sites, facade_packages, refusal_reason

    packages = facade_packages()
    by_dotted = {package.dotted: package for package in packages}
    reasons = [refusal_reason(site, by_dotted[site.package]) for site in facade_import_sites(packages)]
    seen = {reason for reason in reasons if reason is not None}
    assert seen <= set(REFUSALS)
    assert "cross_package_private_target" in seen, "no private target found, so this proves nothing"
    assert "entry_point_target" in seen, "no entry-point target found, so this proves nothing"
