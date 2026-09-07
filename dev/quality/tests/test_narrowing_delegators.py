"""Gate: no shipped function is an unreached bare narrowing of a sibling.

The teeth are the real shape. ``is_active_censo_modelo`` was the fifth function
removed for returning one field of a record its caller needed whole -- here it
returned ``active_work_unit_allowed`` and dropped ``superseded_by``, the pointer
saying WHICH modelo replaced the historical one. The fixtures below reproduce
that body rather than inventing a simpler one.

Two of the tests exist because the detector was wrong before it was right, and
both false positives were caller-search scoping. They are regression tests for
the reader, not illustrations of the rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..narrowing_delegators import CALLER_ROOTS, SHIPPED_ROOT, unreached_narrowings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The body of the removed ``is_active_censo_modelo``, spelled as it shipped.
_REMOVED_SHAPE = '''
def censo_modelo_ownership(modelo: str) -> object:
    return _record(modelo)


def is_active_censo_modelo(modelo: str) -> bool:
    """Return whether a censo modelo may create active work units."""
    return censo_modelo_ownership(modelo).active_work_unit_allowed
'''


def _tree(root: Path, **files: str) -> Path:
    for name, text in files.items():
        path = root / f"{name}.py"
        path.write_text(text, encoding="utf-8")
    return root


def test_the_shipped_tree_has_no_unreached_narrowing() -> None:
    """The direction the gate exists for."""
    offences = unreached_narrowings(SHIPPED_ROOT, CALLER_ROOTS)

    assert offences == [], (
        "these functions return one field of a sibling's result and nothing calls "
        "them; the record's other fields -- a refusal, a coverage manifest, a "
        f"superseded_by pointer -- are dropped with no caller to want them: {offences}"
    )


def test_the_shipped_tree_still_has_functions_to_check(tmp_path: Path) -> None:
    """A vacuity floor: a scan that parses nothing is not a passing scan."""
    modules = [p for p in SHIPPED_ROOT.rglob("*.py") if "tests" not in p.parts]

    assert len(modules) >= 500, (
        f"the scan covered only {len(modules)} shipped module(s); the root has moved "
        "or the exclusion has widened, and the gate is inert rather than satisfied"
    )


def test_the_gate_catches_the_shape_that_was_removed_five_times(tmp_path: Path) -> None:
    """Detector teeth: the exact body ``is_active_censo_modelo`` carried."""
    _tree(tmp_path, censo=_REMOVED_SHAPE)

    assert unreached_narrowings(tmp_path) == [
        "censo.py::is_active_censo_modelo -> censo_modelo_ownership(...)",
    ]


def test_a_subscript_narrowing_is_caught_too(tmp_path: Path) -> None:
    """``result[0]`` discards as surely as ``result.field``."""
    _tree(
        tmp_path,
        manifest="def _both() -> tuple[int, int]:\n    return (1, 2)\n\n\ndef first() -> int:\n    return _both()[0]\n",
    )

    assert unreached_narrowings(tmp_path) == ["manifest.py::first -> _both(...)"]


def test_a_narrowing_its_own_module_calls_is_left_alone(tmp_path: Path) -> None:
    """Regression: the owner module must be searched, never skipped.

    The detector's first run claimed ``generate_m303_annual_orden_manifest`` was
    unreached while the sibling four lines below calls it, and said the same of
    ``read_total_system_memory_bytes``, whose caller is the next function in the
    file. A same-module caller is a real caller.
    """
    _tree(
        tmp_path,
        manifest=(
            "def _both() -> tuple[int, int]:\n    return (1, 2)\n\n\n"
            "def first() -> int:\n    return _both()[0]\n\n\n"
            "def rendered() -> str:\n    return str(first())\n"
        ),
    )

    assert unreached_narrowings(tmp_path) == []


def test_a_narrowing_a_design_time_tool_calls_is_left_alone(tmp_path: Path) -> None:
    """Regression: a ``dev/`` consumer is a real consumer.

    Scoping the caller search to the tree that ships the DEFINITIONS reported
    ``check_m303_annual_orden_manifest`` unreached while
    ``dev/registry/analysis/m303_orden_anual.py`` imports and calls it.
    """
    shipped = tmp_path / "src"
    shipped.mkdir()
    _tree(
        shipped,
        manifest=(
            "def _both() -> tuple[int, int]:\n    return (1, 2)\n\n\n"
            "def checked() -> int:\n    return _both()[0]\n"
        ),
    )
    tool = tmp_path / "dev"
    tool.mkdir()
    (tool / "analysis.py").write_text("from manifest import checked\n\nchecked()\n", encoding="utf-8")

    assert unreached_narrowings(shipped) == ["manifest.py::checked -> _both(...)"]
    assert unreached_narrowings(shipped, (shipped, tool)) == []


def test_a_function_that_does_more_than_narrow_is_left_alone(tmp_path: Path) -> None:
    """A guard before the return makes it a real function, not a field read."""
    _tree(
        tmp_path,
        guarded=(
            "def record(modelo: str) -> object:\n    return modelo\n\n\n"
            "def narrowed(modelo: str) -> object:\n"
            "    if not modelo:\n        raise ValueError(modelo)\n"
            "    return record(modelo).field\n"
        ),
    )

    assert unreached_narrowings(tmp_path) == []


def test_a_full_delegation_is_left_alone(tmp_path: Path) -> None:
    """Returning the whole record discards nothing; only the field read does."""
    _tree(
        tmp_path,
        full=(
            "def record(modelo: str) -> object:\n    return modelo\n\n\n"
            "def aliased(modelo: str) -> object:\n    return record(modelo)\n"
        ),
    )

    assert unreached_narrowings(tmp_path) == []
