"""Declarative S170 fixed point, backed by the canonical import-hygiene scanner."""
from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import find_addressing_boundary_violations

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_ROOT = Path(__file__).resolve().parents[2]
_CADRUMO = _ROOT / "src/cadrumo"
_CANONICAL = _CADRUMO / "application/modelo/work_addressing.py"
_MODULE = "cadrumo.application.modelo.work_addressing"
_RETIRED = frozenset({"cadrumo.application.modelo._work_addressing", "cadrumo.application.modelo.work_unit_selection"})


def _sources() -> list[Path]:
    roots = (_ROOT / "src/cadrumo", _ROOT / "src/cadrumo-harness", _ROOT / "dev", _ROOT / "packaging")
    return sorted({path for root in roots if root.exists() for path in root.rglob("*.py")} | set(_ROOT.glob("*.py")))


def _symbols() -> frozenset[str]:
    tree = ast.parse(_CANONICAL.read_text(encoding="utf-8"))
    return frozenset(
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
    )


def _scan(paths: list[Path]):
    return find_addressing_boundary_violations(
        paths,
        canonical_path=_CANONICAL,
        canonical_module=_MODULE,
        facade_module="cadrumo.application.modelo",
        retired_modules=_RETIRED,
        addressing_symbols=_symbols(),
    )


def test_work_selection_fixed_point_is_discovery_complete() -> None:
    assert not (_CADRUMO / "application/modelo/_work_addressing.py").exists()
    assert not (_CADRUMO / "application/modelo/work_unit_selection.py").exists()
    assert _scan(_sources()) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
    ("from cadrumo.application import modelo\nmodelo.ModeloWorkResolution", "facade import/package access"),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "def outer():\n def inner():\n  WorkUnitCatalogueRepository().load(); select_modelo_work_resolution()",
        "repository-owning selector wrapper",
    ),
    ("def f(value: 'ModeloWorkResolution'): pass", "indirect addressing symbol consumer"),
    ],
)
def test_adversarial_import_authority_mutants_are_rejected(source: str, expected: str, tmp_path: Path) -> None:
    path = tmp_path / "mutant.py"
    path.write_text(source, encoding="utf-8")
    assert expected in {hit.kind for hit in _scan([path])}


def test_modelo_package_is_inert() -> None:
    tree = ast.parse((_CADRUMO / "application/modelo/__init__.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Import)
        or (isinstance(node, ast.ImportFrom) and node.module != "__future__")
        for node in tree.body
    )
    assert "ModeloWorkResolution" not in {
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


def test_rag_discovery_returns_the_canonical_owner() -> None:
    result = subprocess.run(
        [  # noqa: S607
            "uv", "run", "--no-sync", "vaultspec-rag", "search",
            "Modelo work-unit selector repository wrapper natural catalogue scan facade import",
            "--type", "code", "--port", "8766", "--timeout", "45.0", "--json",
        ],
        cwd=_ROOT, capture_output=True, text=True, check=False, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response.get("ok") is True, response
    assert any(
        "application/modelo/work_addressing.py" in str(hit.get("path", "")).replace("\\", "/")
        for hit in response.get("data", {}).get("results", [])
    )
