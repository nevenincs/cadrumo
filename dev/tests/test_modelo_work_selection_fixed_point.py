"""Declarative S170 fixed point, backed by the canonical import-hygiene scanner."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import cadrumo.application.modelo.work_addressing as work_addressing

from ..quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    DelegatingWrapperRule,
    scan_canonical_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_ROOT = Path(__file__).resolve().parents[2]
_CADRUMO = _ROOT / "src/cadrumo"
_CANONICAL = _CADRUMO / "application/modelo/work_addressing.py"
_MODULE = "cadrumo.application.modelo.work_addressing"
_RETIRED = frozenset({"cadrumo.application.modelo._work_addressing", "cadrumo.application.modelo.work_unit_selection"})
_SPEC = CanonicalAuthoritySpec(
    targets=(CanonicalAuthorityTarget(_MODULE, _CANONICAL, frozenset(work_addressing.__all__)),),
    retired_modules=_RETIRED,
    facade_modules=frozenset({"cadrumo.application.modelo"}),
    inert_modules=frozenset({"cadrumo.application.modelo"}),
    wrapper_rules=(
        DelegatingWrapperRule(
            "repository-owning selector wrapper",
            "select_modelo_work_resolution",
            collaborator_symbols=frozenset({"WorkUnitCatalogueRepository"}),
        ),
        DelegatingWrapperRule(
            "catalogue preselection wrapper",
            "select_modelo_work_resolution",
            receiver_methods=frozenset({("catalogue", "get")}),
        ),
    ),
)


def test_work_selection_fixed_point_is_discovery_complete() -> None:
    assert not (_CADRUMO / "application/modelo/_work_addressing.py").exists()
    assert not (_CADRUMO / "application/modelo/work_unit_selection.py").exists()
    assert scan_canonical_authority(_SPEC) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
    ("from cadrumo.application import modelo\nmodelo.ModeloWorkResolution", "facade import/package access"),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "def outer():\n def inner():\n  WorkUnitCatalogueRepository().load(); return select_modelo_work_resolution()",
        "repository-owning selector wrapper",
    ),
    ("def f(value: 'ModeloWorkResolution'): pass", "indirect addressing symbol consumer"),
    ],
)
def test_adversarial_import_authority_mutants_are_rejected(source: str, expected: str, tmp_path: Path) -> None:
    path = tmp_path / "mutant.py"
    path.write_text(source, encoding="utf-8")
    assert expected in {hit.kind for hit in scan_canonical_authority(_SPEC, (path,))}


def test_rag_discovery_returns_the_canonical_owner(tmp_path: Path) -> None:
    status_dir = tmp_path / "rag-client-status"
    status_dir.mkdir()
    version = subprocess.run(
        ["vaultspec-rag", "--version"],  # noqa: S607
        cwd=_ROOT, capture_output=True, text=True, check=False, timeout=15,
    )
    assert version.returncode == 0, version.stderr
    assert "0.4.2" in version.stdout, version.stdout
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "vaultspec-rag", "--status-dir", str(status_dir), "search",
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
