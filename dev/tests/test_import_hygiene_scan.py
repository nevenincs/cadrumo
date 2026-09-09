"""Real-behavior tests for the import-hygiene facade scanner.

Guards against the regression where ``discover_facades`` only recognised the
plain ``__all__ = [...]`` assignment form and silently failed to register any
``__init__.py`` using the annotated ``__all__: list[str] = [...]`` form as a
facade -- misclassifying every symbol already exported by that package as
"needs promotion" downstream.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..quality.import_hygiene_scan import (
    REPO_ROOT,
    FacadeInfo,
    discover_facades,
    dunder_all_assignment_value,
    find_underscore_in_all_violations,
    is_underscore_named,
    tracked_live_files,
    walk_module_imports,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ALLOWED_FUTURE_FEATURES: Final[frozenset[str]] = frozenset({"annotations"})


def _parse_single_statement(src: str) -> ast.stmt:
    """Parse ``src`` (one module-level statement) and return its AST node."""
    module = ast.parse(src)
    (stmt,) = module.body
    return stmt


def _future_directive_violations(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Return project future imports other than the one supported directive.

    The check reads the AST rather than matching text, so a mention in a
    docstring or a test fixture cannot masquerade as an executable future
    statement.  Explicit paths keep the detector-teeth tests isolated; the
    live-tree gate supplies the tracked project inventory below.
    """
    violations: list[str] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:  # pragma: no cover - unreadable file is its own defect
            violations.append(f"{path}: unreadable: {error}")
            continue
        try:
            tree = ast.parse(source, filename=str(path), mode="exec")
        except SyntaxError as error:
            violations.append(f"{path}:{error.lineno}: SyntaxError: {error.msg}")
            continue
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom) or statement.module != "__future__":
                continue
            forbidden = sorted(alias.name for alias in statement.names if alias.name not in _ALLOWED_FUTURE_FEATURES)
            if forbidden:
                relative = path
                if path.is_relative_to(REPO_ROOT):
                    relative = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{relative}:{statement.lineno}: unsupported future directive(s): " + ", ".join(forbidden),
                )
    return tuple(sorted(violations))


def _project_python_files() -> tuple[Path, ...]:
    """Return every tracked Python file in the live project inventory."""
    return tuple(path for path in tracked_live_files() if path.suffix == ".py")


def test_dunder_all_assignment_value_recognises_plain_form() -> None:
    """The plain ``__all__ = [...]`` assignment must yield its list value."""
    node = _parse_single_statement('__all__ = ["Foo", "Bar"]')

    value = dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_recognises_annotated_form() -> None:
    """The annotated ``__all__: list[str] = [...]`` form must also resolve."""
    node = _parse_single_statement('__all__: list[str] = ["Foo", "Bar"]')

    value = dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_ignores_unrelated_annotated_assignment() -> None:
    """An annotated assignment to a name other than ``__all__`` is not matched."""
    node = _parse_single_statement('SOME_OTHER: list[str] = ["Foo"]')

    assert dunder_all_assignment_value(node) is None


def test_dunder_all_assignment_value_ignores_bare_annotation_with_no_value() -> None:
    """A bare annotation with no assigned value (``__all__: list[str]``) is not a binding."""
    node = _parse_single_statement("__all__: list[str]")

    assert dunder_all_assignment_value(node) is None


def test_discover_facades_walks_the_live_tree_and_finds_core_inert() -> None:
    """The live-tree walk still runs, and ``cadrumo.core`` is correctly NOT a facade.

    This asserted the opposite until now: that ``cadrumo.core`` carries a real
    ``__all__`` exporting ``Modelo`` and ``CasillaId``. That was true when it was
    written and is now forbidden -- the initialiser was emptied deliberately
    (``cadrumo/core has none left``), and the architecture rule requires package
    initialisers to be inert namespace markers whose consumers import from the
    defining module. So the old assertion could only pass while the facade it
    demanded still existed: its green depended on the very state the project set
    out to remove, and it went red the moment that work landed rather than when
    anything broke.

    Inverted rather than deleted, because the live-tree exercise is the part
    worth keeping: the annotated ``__all__`` FORM is already proven on
    constructed input by the two ``dunder_all_assignment_value`` cases above,
    but nothing else walks the real ``src/cadrumo`` tree. The floor keeps that
    walk honest -- a collapsed walk would satisfy an emptiness check about
    ``cadrumo.core`` without having looked at anything.
    """
    facades = discover_facades()

    assert len(facades) > 100, f"the facade walk reached only {len(facades)} initialisers; it collapsed"
    assert any(info.has_real_all for info in facades.values()), (
        "no initialiser anywhere carries a real __all__, so this walk cannot tell an inert "
        "package from one it failed to parse"
    )
    core_facade = facades["cadrumo.core"]
    assert core_facade.has_real_all is False, (
        "cadrumo.core declares a non-empty __all__ again; package initialisers are inert "
        "namespace markers and consumers import from the defining module: {core_facade.all_names}"
    )


def test_walk_module_imports_tolerates_file_removed_after_discovery(tmp_path: Path) -> None:
    """A generated module removed after discovery is not a scanner failure."""
    generated = tmp_path / "generated_test_module.py"
    generated.write_text("from pathlib import Path\n", encoding="utf-8")
    generated.unlink()

    assert walk_module_imports(generated) == []


def test_is_underscore_named_flags_leading_underscore_but_not_dunders() -> None:
    """A leading-underscore identifier is private-convention; a dunder is not."""
    assert is_underscore_named("_private_helper") is True
    assert is_underscore_named("__all__") is False
    assert is_underscore_named("__init__") is False
    assert is_underscore_named("public_name") is False


def test_find_underscore_in_all_violations_flags_a_private_named_export() -> None:
    """A facade whose ``__all__`` contains a leading-underscore name is flagged.

    Real-behavior fixture: a synthetic :class:`FacadeInfo` standing in for a
    parsed ``__init__.py`` (the detector operates purely on the already-parsed
    facade inventory ``discover_facades`` produces, so no file I/O is needed to
    exercise the finder's own logic).
    """
    facades = {
        "cadrumo.fixture_pkg": FacadeInfo(
            package="cadrumo.fixture_pkg",
            path=REPO_ROOT / "src" / "cadrumo" / "fixture_pkg" / "__init__.py",
            all_names=["PublicThing", "_private_helper", "__all__"],
            has_real_all=True,
        ),
        "cadrumo.clean_pkg": FacadeInfo(
            package="cadrumo.clean_pkg",
            path=REPO_ROOT / "src" / "cadrumo" / "clean_pkg" / "__init__.py",
            all_names=["PublicOnly"],
            has_real_all=True,
        ),
    }

    violations = find_underscore_in_all_violations(facades)

    assert [(v.package, v.name) for v in violations] == [("cadrumo.fixture_pkg", "_private_helper")]


def test_find_underscore_in_all_violations_ignores_facades_without_real_all() -> None:
    """A facade with no real ``__all__`` (empty / absent) yields no violations, even if named."""
    facades = {
        "cadrumo.no_all_pkg": FacadeInfo(
            package="cadrumo.no_all_pkg",
            path=REPO_ROOT / "src" / "cadrumo" / "no_all_pkg" / "__init__.py",
            all_names=["_would_be_flagged_if_real"],
            has_real_all=False,
        ),
    }

    assert find_underscore_in_all_violations(facades) == []


def test_live_tree_has_zero_underscore_in_all_violations() -> None:
    """The live ``src/cadrumo`` tree must carry zero underscore-named ``__all__`` entries.

    Real-behavior regression pinning the disposal outcome: every previously
    private-named facade export was either promoted to a public name and its
    consumers swept, or dropped from ``__all__``.
    """
    facades = discover_facades()

    violations = find_underscore_in_all_violations(facades)

    assert violations == [], (
        f"underscore-named __all__ entries found (public facade exporting a private-named "
        f"symbol): {[(v.package, v.name) for v in violations]}"
    )


def test_future_directive_scan_detects_legacy_directives(tmp_path: Path) -> None:
    """A removed future feature cannot re-enter the project unnoticed."""
    source = tmp_path / "legacy_future.py"
    source.write_text(
        "from __future__ import annotations, division\nvalue = 1 / 2\n",
        encoding="utf-8",
    )

    violations = _future_directive_violations((source,))

    assert len(violations) == 1
    assert "unsupported future directive(s): division" in violations[0]


def test_future_directive_scan_accepts_annotations_and_plain_modules(tmp_path: Path) -> None:
    """The established directive and modules without one are both valid."""
    annotated = tmp_path / "annotated.py"
    annotated.write_text("from __future__ import annotations\nvalue: Missing = None\n", encoding="utf-8")
    plain = tmp_path / "plain.py"
    plain.write_text("value = 1\n", encoding="utf-8")

    assert _future_directive_violations((annotated, plain)) == ()


def test_live_project_uses_annotations_as_its_only_future_directive() -> None:
    """Every tracked project module must share the one annotation model."""
    violations = _future_directive_violations(_project_python_files())

    assert violations == ()


def test_the_two_path_factory_vocabularies_have_not_drifted_apart() -> None:
    """Two scanners carry the same path-construction vocabulary; nothing joined them.

    ``governance_corpus_scan`` and ``import_hygiene_scan`` each declare their own
    ``_PATH_FACTORY_CALLABLES`` and ``_SEGMENT_JOIN_CALLABLES``, with the same
    members and near-identical comments, and each uses them the same way -- a
    ``not in`` test that decides whether a call assembles a path. Nothing reads
    either constant from a test, so a name added to one and not the other would
    leave one scanner quietly blind to a construct the other recognises, in the
    direction that reports clean.

    The two are compared rather than merged: extracting a shared module would
    relocate a private symbol across a package boundary for a seven-name tuple,
    and the copies are deliberate -- each scanner stays importable on its own.
    Comparing them costs nothing and makes the divergence loud.
    """
    from ..quality.governance_corpus_scan import _PATH_FACTORY_CALLABLES as GOVERNANCE_FACTORIES
    from ..quality.governance_corpus_scan import _SEGMENT_JOIN_CALLABLES as GOVERNANCE_JOINS
    from ..quality.import_hygiene_scan import _PATH_FACTORY_CALLABLES as HYGIENE_FACTORIES
    from ..quality.import_hygiene_scan import _SEGMENT_JOIN_CALLABLES as HYGIENE_JOINS

    assert GOVERNANCE_FACTORIES, (
        "the governance scanner's path vocabulary is empty, so its check reads every call as a non-factory"
    )
    assert HYGIENE_FACTORIES, (
        "the hygiene scanner's path vocabulary is empty, so its check reads every call as a non-factory"
    )
    assert GOVERNANCE_FACTORIES == HYGIENE_FACTORIES, (
        "the two scanners' path-factory vocabularies have drifted, so one recognises a construct the "
        f"other does not: governance-only={sorted(GOVERNANCE_FACTORIES - HYGIENE_FACTORIES)} "
        f"hygiene-only={sorted(HYGIENE_FACTORIES - GOVERNANCE_FACTORIES)}"
    )
    assert GOVERNANCE_JOINS == HYGIENE_JOINS, (
        "the two scanners' segment-join vocabularies have drifted: "
        f"governance-only={sorted(GOVERNANCE_JOINS - HYGIENE_JOINS)} "
        f"hygiene-only={sorted(HYGIENE_JOINS - GOVERNANCE_JOINS)}"
    )
