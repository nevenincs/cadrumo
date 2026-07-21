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

import pytest

from ..import_hygiene_scan import (
    REPO_ROOT,
    FacadeInfo,
    _dunder_all_assignment_value,
    discover_facades,
    find_shim_modules,
    find_underscore_in_all_violations,
    is_underscore_named,
    walk_module_imports,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _parse_single_statement(src: str) -> ast.stmt:
    """Parse ``src`` (one module-level statement) and return its AST node."""
    module = ast.parse(src)
    (stmt,) = module.body
    return stmt


def test_dunder_all_assignment_value_recognises_plain_form() -> None:
    """The plain ``__all__ = [...]`` assignment must yield its list value."""
    node = _parse_single_statement('__all__ = ["Foo", "Bar"]')

    value = _dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_recognises_annotated_form() -> None:
    """The annotated ``__all__: list[str] = [...]`` form must also resolve."""
    node = _parse_single_statement('__all__: list[str] = ["Foo", "Bar"]')

    value = _dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_ignores_unrelated_annotated_assignment() -> None:
    """An annotated assignment to a name other than ``__all__`` is not matched."""
    node = _parse_single_statement('SOME_OTHER: list[str] = ["Foo"]')

    assert _dunder_all_assignment_value(node) is None


def test_dunder_all_assignment_value_ignores_bare_annotation_with_no_value() -> None:
    """A bare annotation with no assigned value (``__all__: list[str]``) is not a binding."""
    node = _parse_single_statement("__all__: list[str]")

    assert _dunder_all_assignment_value(node) is None


def test_discover_facades_registers_annotated_all_init_as_a_facade() -> None:
    """``cadrumo.core`` declares ``__all__`` in the annotated form and must be discovered.

    Exercises the real ``discover_facades`` walk over the actual ``src/cadrumo``
    tree (no fixtures, no mocks) so the regression -- ``cadrumo.core`` silently
    absent from the facade set -- is caught against the live source tree.
    """
    facades = discover_facades()

    assert "cadrumo.core" in facades
    core_facade = facades["cadrumo.core"]
    assert core_facade.has_real_all is True
    assert "Modelo" in core_facade.all_names
    assert "CasillaId" in core_facade.all_names


def test_find_shim_modules_excludes_dunder_main_entrypoint_modules() -> None:
    """A standard ``__main__.py`` entrypoint module must never be classified as a shim.

    Exercises the real classifier against ``src/cadrumo/locales/__main__.py`` --
    the live module whose ``from .cli import app`` plus
    ``if __name__ == "__main__": app()`` shape previously false-positived as a
    shim (zero real defs, one import statement) before the classifier learned
    to skip ``__main__.py`` modules as the standard entry-point pattern.
    """
    main_path = REPO_ROOT / "src" / "cadrumo" / "locales" / "__main__.py"
    assert main_path.is_file()

    shims = find_shim_modules([main_path], facades={})

    assert shims == []


def test_find_shim_modules_still_flags_a_non_main_pure_reexport_module() -> None:
    """A genuine pure-reexport module (not named ``__main__.py``) is still flagged.

    Guards against the exclusion in the prior test over-broadening to skip
    every import-only module rather than only the ``__main__.py`` entrypoint
    shape.
    """
    reexport_path = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli" / "_schemas.py"
    assert reexport_path.is_file()

    shims = find_shim_modules([reexport_path], facades={})

    assert any(shim.reason == "pure_reexport_shape" for shim in shims)


def test_walk_module_imports_tolerates_file_removed_after_discovery(tmp_path: Path) -> None:
    """A generated module removed after discovery is not a scanner failure."""
    generated = tmp_path / "generated_test_module.py"
    generated.write_text("from pathlib import Path\n", encoding="utf-8")
    generated.unlink()

    assert walk_module_imports(generated) == []


def test_find_shim_modules_tolerates_file_removed_after_discovery(tmp_path: Path) -> None:
    """Shim classification ignores only a path that genuinely vanished."""
    generated = tmp_path / "generated_test_module.py"
    generated.write_text("from pathlib import Path\n", encoding="utf-8")
    generated.unlink()

    assert find_shim_modules([generated], facades={}) == []


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
    consumers swept, or dropped from ``__all__``. This is the scanner-level
    proof that closes the underscore-in-``__all__`` finding; the pytest gate
    (``src/cadrumo/tests/test_import_hygiene_gate.py``) is the CI-wired
    counterpart.
    """
    facades = discover_facades()

    violations = find_underscore_in_all_violations(facades)

    assert violations == [], (
        f"underscore-named __all__ entries found (public facade exporting a private-named "
        f"symbol): {[(v.package, v.name) for v in violations]}"
    )
