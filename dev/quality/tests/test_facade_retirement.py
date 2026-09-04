"""Real-behaviour tests for the facade-retirement rewriter.

The rewriter edits source files, so its failure modes are expensive: a wrong
import compiles and imports the wrong symbol, and a missed one leaves a facade
that cannot be emptied. Every judgement it makes is exercised here from a
constructed package tree, never by pointing it at the live one and hoping.
"""

from __future__ import annotations

import ast
import os
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


@pytest.fixture
def relative_root(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch tree entered as the working directory, yielded as ``.``.

    A package's dotted name is derived from its path parts, so the scanners are
    always invoked with a repository-relative path.
    """
    previous = pathlib.Path.cwd()
    os.chdir(tmp_path)
    try:
        yield pathlib.Path()
    finally:
        os.chdir(previous)


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


def test_no_dev_package_initialiser_forwards_a_name() -> None:
    """The gate the retirement made landable.

    This replaces two tests that measured the live facade population - how many
    consumer sites there were, and that both underscore refusal reasons still
    occurred. Both were useful while nine initialisers forwarded 388 names
    between them; both began failing on their own "so this proves nothing"
    guards the moment the last facade came down, because the population they
    described had gone.

    That is the right way for a measurement to end. What replaces it is the
    invariant the measurements were in service of: a package initialiser under
    ``dev`` is an inert namespace marker, so no facade exists to find. A gate
    saying that could not have been written before now - it would have failed on
    nine packages.
    """
    from ..facade_retirement import facade_packages

    forwarding = facade_packages()
    assert not forwarding, "package initialiser(s) forwarding names: " + ", ".join(
        f"{package.dotted} ({len(package.exports)})" for package in forwarding
    )


def test_the_gate_detects_a_forwarding_initialiser(relative_root: pathlib.Path) -> None:
    """A gate over a clean tree proves the tree is clean, not that the gate works.

    Constructed rather than planted in the working tree: the detector is shown a
    package whose initialiser forwards a name, and must report it.
    """
    from ..facade_retirement import facade_exports, facade_packages

    package = relative_root / "widget"
    package.mkdir()
    (package / "engine.py").write_text("class Motor:" + chr(10) + "    pass" + chr(10), encoding="utf-8")
    (package / "__init__.py").write_text(
        "from .engine import Motor" + chr(10) + chr(10) + '__all__ = ["Motor"]' + chr(10), encoding="utf-8"
    )

    detected = facade_exports(package)
    assert detected.exports == {"Motor": "widget.engine"}
    assert facade_packages(relative_root), "a forwarding initialiser must be reported"

    # And an inert one is not reported, so the gate is not simply always red.
    (package / "__init__.py").write_text('"""Inert namespace marker."""' + chr(10), encoding="utf-8")
    assert not facade_packages(relative_root)


def test_every_dev_initialiser_is_fully_inert() -> None:
    """Wider than forwarding, which is only the loudest violation.

    An initialiser may not define symbols, import at module level, bind names,
    or run code at import either. A package that defines its own class in
    ``__init__.py`` forwards nothing and is still not a namespace marker, so a
    gate that only checked forwarding would pass it.

    All 63 initialisers under ``dev`` satisfy this today. The stronger gate is
    landable for the same reason the forwarding one is: the retirement made it
    true.
    """
    from ..facade_retirement import DEV_ROOT, non_inert_contents

    initialisers = [path for path in sorted(DEV_ROOT.rglob("__init__.py")) if "__pycache__" not in path.parts]
    assert len(initialisers) > 50, f"only {len(initialisers)} initialisers found; the gate is near-vacuous"

    offenders = {str(path): contents for path in initialisers if (contents := non_inert_contents(path))}
    assert not offenders, f"non-inert package initialiser(s): {offenders}"


def test_the_inertness_gate_detects_each_kind_it_names(relative_root: pathlib.Path) -> None:
    """Every kind the gate can report is shown catching a constructed instance.

    A kind with no live instance and no proof is one that stops being detected
    without anyone noticing - and none of the four has a live instance, because
    the tree is clean.
    """
    from ..facade_retirement import NON_INERT_KINDS, non_inert_contents

    package = relative_root / "widget"
    package.mkdir()
    initialiser = package / "__init__.py"

    initialiser.write_text('"""Inert."""' + chr(10), encoding="utf-8")
    assert non_inert_contents(initialiser) == {}

    # A future import alone is still inert: it is a compiler directive.
    initialiser.write_text('"""Doc."""' + chr(10) + "from __future__ import annotations" + chr(10), encoding="utf-8")
    assert non_inert_contents(initialiser) == {}

    planted = {
        "definition": "class Motor:" + chr(10) + "    pass" + chr(10),
        "import": "import os" + chr(10),
        "assignment": "VERSION = 1" + chr(10),
        "side_effect_call": "print('hello')" + chr(10),
    }
    assert set(planted) == set(NON_INERT_KINDS), "a kind is declared but has no proof"
    for kind, body in planted.items():
        initialiser.write_text('"""Doc."""' + chr(10) + body, encoding="utf-8")
        assert kind in non_inert_contents(initialiser), f"{kind} was not detected"
