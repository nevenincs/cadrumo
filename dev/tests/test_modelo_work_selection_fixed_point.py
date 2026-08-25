"""Declarative Modelo work-selection fixed point backed by the canonical scanner."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import cadrumo.application.modelo.work_addressing as work_addressing

from ..quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    DelegatingWrapperRule,
    scan_canonical_authority,
    tracked_live_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_ROOT = Path(__file__).resolve().parents[2]
_CADRUMO = _ROOT / "src/cadrumo"
_CANONICAL = _CADRUMO / "application/modelo/work_addressing.py"
_MODULE = "cadrumo.application.modelo.work_addressing"
_MODELO_PACKAGE = ".".join(("cadrumo", "application", "modelo"))
_RETIRED = frozenset(
    f"{_MODELO_PACKAGE}.{name}" for name in ("_" + "work_addressing", "work_unit_" + "selection")
)
_DEFINED_SYMBOLS = frozenset(
    name
    for name in work_addressing.__all__
    if (inspect.isclass(value := getattr(work_addressing, name)) or inspect.isfunction(value))
    and getattr(value, "__module__", None) == _MODULE
)
_SPEC = CanonicalAuthoritySpec(
    targets=(CanonicalAuthorityTarget(_MODULE, _CANONICAL, _DEFINED_SYMBOLS),),
    retired_modules=_RETIRED,
    forbidden_text_references=_RETIRED,
    facade_modules=frozenset({"cadrumo.application.modelo"}),
    inert_modules=frozenset({"cadrumo.application.modelo"}),
    wrapper_rules=(
        DelegatingWrapperRule(
            "repository-owning selector wrapper",
            "select_modelo_work_resolution",
            collaborator_symbols=frozenset({"WorkUnitCatalogueRepository"}),
            keyword_source_methods=frozenset({("catalogue", "load"), ("catalogue", "load_revisioned")}),
        ),
        DelegatingWrapperRule(
            "catalogue preselection wrapper",
            "select_modelo_work_resolution",
            receiver_methods=frozenset({("catalogue", "get")}),
        ),
    ),
)
_MUTANT_SPEC = CanonicalAuthoritySpec(
    targets=_SPEC.targets,
    retired_modules=_SPEC.retired_modules,
    facade_modules=_SPEC.facade_modules,
    inert_modules=_SPEC.inert_modules,
    wrapper_rules=_SPEC.wrapper_rules,
)


def _tracked_live_corpus() -> tuple[Path, ...]:
    return tracked_live_files()


def test_work_selection_fixed_point_is_discovery_complete() -> None:
    assert not (_CADRUMO / "application/modelo/_work_addressing.py").exists()
    assert not (_CADRUMO / "application/modelo/work_unit_selection.py").exists()
    assert scan_canonical_authority(_SPEC, _tracked_live_corpus()) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
    ("from cadrumo.application import modelo\nmodelo.ModeloWorkResolution", "facade import/package access"),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "def outer():\n def inner():\n  WorkUnitCatalogueRepository().load(); return select_modelo_work_resolution()",
        "repository-owning selector wrapper",
    ),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "def wrapper(repo, request, bucket_id):\n"
        " catalogue = repo.load()\n"
        " return select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)",
        "repository-owning selector wrapper",
    ),
    ("def f(value: 'ModeloWorkResolution'): pass", "indirect authority symbol consumer"),
    ],
)
def test_adversarial_import_authority_mutants_are_rejected(source: str, expected: str, tmp_path: Path) -> None:
    path = tmp_path / "mutant.py"
    path.write_text(source, encoding="utf-8")
    findings = scan_canonical_authority(_MUTANT_SPEC, (_CANONICAL, path))
    assert {hit.kind for hit in findings} == {expected}
