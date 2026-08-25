"""Keep the M100 2024 maternity binding value at its single domain-backed home."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REGISTRY_TESTS_ROOT = Path(__file__).parent
_BINDING_PREFIX = "renta-2024-profile-"
_BINDING_SUFFIX = "deduccion-maternidad"
_SHARED_HELPER = _REGISTRY_TESTS_ROOT / "_modelo_100_registry_support.py"

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _maternity_binding_key() -> str:
    """Construct the census target without introducing another raw literal."""
    return f"{_BINDING_PREFIX}{_BINDING_SUFFIX}"


def _binding_literal_locations(*, source_root: Path, binding_key: str) -> tuple[tuple[Path, int], ...]:
    """Return exact AST-string locations for one binding identity."""
    locations: list[tuple[Path, int]] = []
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        locations.extend(
            (path, node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value == binding_key
        )
    return tuple(sorted(locations))


def test_m100_2024_maternity_binding_literal_has_one_shared_registry_test_home() -> None:
    """The shared helper, rather than its scenario consumers, owns the literal."""
    locations = _binding_literal_locations(
        source_root=_REGISTRY_TESTS_ROOT,
        binding_key=_maternity_binding_key(),
    )

    assert tuple(path for path, _line in locations) == (_SHARED_HELPER,)


def test_m100_2024_maternity_binding_census_detects_a_raw_literal_mutation() -> None:
    """A raw scenario literal remains observable to this AST census."""
    binding_key = _maternity_binding_key()
    tree = ast.parse(f"values = {{{binding_key!r}: 0}}")

    assert [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)] == [binding_key, 0]
