"""Declarative Modelo work-selection fixed point backed by the canonical scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    DelegatingWrapperRule,
    SubstitutableNaturalScanRule,
    public_definition_names,
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
_DEFINED_SYMBOLS = public_definition_names(_CANONICAL)
_NATURAL_SCAN_RULE = SubstitutableNaturalScanRule(
    "parallel natural catalogue scan",
    collection_names=frozenset({"catalogue"}),
    collection_methods=frozenset({"values", "items"}),
    coordinate_names=frozenset({"modelo", "filing_year", "period"}),
    exempt_functions=frozenset({"select_modelo_work_resolution"}),
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
    natural_scan_rules=(_NATURAL_SCAN_RULE,),
)
_MUTANT_SPEC = CanonicalAuthoritySpec(
    targets=_SPEC.targets,
    retired_modules=_SPEC.retired_modules,
    facade_modules=_SPEC.facade_modules,
    inert_modules=_SPEC.inert_modules,
    wrapper_rules=_SPEC.wrapper_rules,
    natural_scan_rules=_SPEC.natural_scan_rules,
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
        " return select_modelo_work_resolution(request, catalogue=repo.load(), bucket_id=bucket_id)",
        "repository-owning selector wrapper",
    ),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "def wrapper(repo, request, bucket_id):\n"
        " catalogue = repo.load()\n"
        " result = select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)\n"
        " return result",
        "repository-owning selector wrapper",
    ),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "if True:\n"
        " def wrapper(repo, request, bucket_id):\n"
        "  catalogue = repo.load()\n"
        "  result = select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)\n"
        "  return result",
        "repository-owning selector wrapper",
    ),
    (
        "def parallel(catalogue, modelo, filing_year):\n"
        " for unit in catalogue.values():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return unit",
        "parallel natural catalogue scan",
    ),
    (
        "def parallel(catalogue, modelo, filing_year):\n"
        " units = catalogue\n"
        " for unit in units.values():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return unit",
        "parallel natural catalogue scan",
    ),
    (
        "def parallel(catalogue, modelo, filing_year):\n"
        " for key, unit in catalogue.items():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return key, unit",
        "parallel natural catalogue scan",
    ),
    (
        "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
        "def wrapper(repo, request, bucket_id):\n"
        " loaded = repo.load()\n"
        " catalogue = loaded\n"
        " return select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)",
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


def test_projection_loop_is_not_a_selector_mutant(tmp_path: Path) -> None:
    path = tmp_path / "projection.py"
    path.write_text(
        "def project(catalogue):\n"
        " for unit in catalogue.values():\n"
        "  yield unit.modelo, unit.filing_year, unit.period\n",
        encoding="utf-8",
    )
    assert scan_canonical_authority(_MUTANT_SPEC, (_CANONICAL, path)) == []


def test_only_exact_canonical_selector_is_exempt_from_natural_scan(tmp_path: Path) -> None:
    owner = tmp_path / "work_addressing.py"
    owner.write_text(
        "def select_modelo_work_resolution(catalogue, modelo, filing_year):\n"
        " for unit in catalogue.values():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return unit\n"
        "def extra_selector(catalogue, modelo, filing_year):\n"
        " for unit in catalogue.values():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return unit\n",
        encoding="utf-8",
    )
    spec = CanonicalAuthoritySpec(
        targets=(
            CanonicalAuthorityTarget(
                "example.work_addressing", owner, frozenset({"select_modelo_work_resolution"})
            ),
        ),
        natural_scan_rules=(_NATURAL_SCAN_RULE,),
    )
    findings = scan_canonical_authority(spec, (owner,))
    assert [(hit.kind, hit.detail) for hit in findings] == [
        ("parallel natural catalogue scan", "extra_selector")
    ]
