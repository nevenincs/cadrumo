"""canonical_decimal_string financial alias invariant.

Asserts:
1. The old duplicate name ``canonical_decimal`` in
   ``cadrumo.adapters.inbound.financial._decimal`` no longer exists as a
   module and package facade is deleted.
"""

import ast
from pathlib import Path

import pytest

from ._inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_financial_decimal_module_is_deleted() -> None:
    """cadrumo.adapters.inbound.financial._decimal must not exist as a file."""
    decimal_module_path = SRC_CADRUMO / "adapters" / "inbound" / "financial" / "_decimal.py"
    assert not decimal_module_path.exists(), (
        f"Duplicate _decimal.py still present at {decimal_module_path}; "
        "delete the file and migrate callers to cadrumo.domain.identifiers."
    )


def _bound_names(module_path: Path) -> set[str]:
    """Return every name the module binds into its own namespace.

    Import aliases, assignments, definitions and ``__all__`` entries all count,
    because each is a way the package could hand the name back out.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
                    if target.id == "__all__":
                        bound.update(
                            element.value
                            for element in ast.walk(node.value)
                            if isinstance(element, ast.Constant) and isinstance(element.value, str)
                        )
    return bound


def test_financial_package_does_not_alias_canonical_decimal() -> None:
    """The financial package must not redeclare the domain-owned helper.

    Read structurally rather than by importing the package. The claim is about
    what the namespace DECLARES, so the declaration is the honest thing to
    inspect: an alias reintroduced behind a failing import would still be a
    reintroduced alias, and this central module stays free of adapter runtime
    ownership it has no business carrying.
    """
    package_init = SRC_CADRUMO / "adapters" / "inbound" / "financial" / "__init__.py"
    assert package_init.exists(), f"financial package __init__ missing at {package_init}"

    bound = _bound_names(package_init)

    assert "canonical_decimal" not in bound, (
        f"{package_init} rebinds 'canonical_decimal'; the helper is owned by "
        "cadrumo.domain.identifiers and must be imported from there, not aliased here."
    )


@pytest.mark.parametrize(
    "source",
    [
        "from ...domain.identifiers import canonical_decimal",
        "from ...domain.identifiers import canonical_decimal_string as canonical_decimal",
        "canonical_decimal = _something",
        '__all__ = ["canonical_decimal"]',
        "def canonical_decimal(value):\n    return value",
    ],
    ids=["import", "aliased-import", "assignment", "all-entry", "definition"],
)
def test_the_alias_detector_catches_every_reintroduction_form(tmp_path: Path, source: str) -> None:
    """Anti-tautology: a detector blind to a binding form would pass vacuously.

    The check above only means something if it fails when the alias comes back,
    so every route by which a package can hand the name out is proved caught.
    """
    module_path = tmp_path / "__init__.py"
    module_path.write_text(source, encoding="utf-8")

    assert "canonical_decimal" in _bound_names(module_path), (
        f"the detector missed a reintroduced alias declared as: {source!r}"
    )


def test_the_alias_detector_does_not_fire_on_an_unrelated_namespace(tmp_path: Path) -> None:
    """The detector must discriminate, not report the name unconditionally."""
    module_path = tmp_path / "__init__.py"
    module_path.write_text('from .providers import Provider\n__all__ = ["Provider"]', encoding="utf-8")

    assert "canonical_decimal" not in _bound_names(module_path)
