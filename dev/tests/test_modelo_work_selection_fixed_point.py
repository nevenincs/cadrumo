"""Declarative Modelo work-selection fixed point backed by the canonical scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    DelegatingWrapperRule,
    SubstitutableWorkSelectorRule,
    definition_names,
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
_RETIRED = frozenset(f"{_MODELO_PACKAGE}.{name}" for name in ("_" + "work_addressing", "work_unit_" + "selection"))
_DEFINED_SYMBOLS = public_definition_names(_CANONICAL)
_NATURAL_SCAN_RULE = SubstitutableWorkSelectorRule(
    "parallel natural catalogue scan",
    collection_methods=frozenset({"values", "items"}),
    catalogue_types=frozenset({"WorkUnitCatalogue"}),
    repository_types=frozenset({"WorkUnitCatalogueRepository"}),
    natural_coordinates=frozenset({"modelo", "filing_year", "period"}),
    exact_coordinates=frozenset({"work_unit_id"}),
    operator_methods=frozenset({"startswith", "endswith"}),
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


def _retired_module_paths() -> tuple[Path, ...]:
    """Return the file each retired module would occupy, derived from ``_RETIRED``.

    Restating those filenames here is what broke this gate: the retired module
    carries a LEADING UNDERSCORE and the hand-written path dropped it, so the
    assertion demanded the absence of the canonical module the whole spec
    targets, and the retirement it meant to prove went unchecked in both
    directions at once. ``_RETIRED`` is the one declaration of what is retired;
    the paths follow from it rather than beside it.
    """
    return tuple(_ROOT / "src" / f"{dotted.replace('.', '/')}.py" for dotted in sorted(_RETIRED))


def test_work_selection_fixed_point_is_discovery_complete() -> None:
    # The absence claims need an anchor: were the canonical module gone, every
    # retirement below would hold over a package that no longer selects work.
    assert _CANONICAL.is_file(), f"the canonical work-selection module is missing: {_CANONICAL}"
    for retired in _retired_module_paths():
        assert not retired.exists(), f"this module is declared retired but is present: {retired}"
    assert scan_canonical_authority(_SPEC, _tracked_live_corpus()) == []


def test_canonical_module_has_no_fragmented_exact_or_operator_selector_helpers() -> None:
    names = definition_names(_CANONICAL)
    assert names.count("select_modelo_work_resolution") == 1
    assert "_select_exact_modelo_work_resolution" not in names
    assert "_select_operator_work_unit_resolution" not in names


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from cadrumo.application import modelo\nmodelo.ModeloWorkResolution", "facade import/package access"),
        (
            "from cadrumo.application.modelo.work_addressing import select_modelo_work_resolution\n"
            "def outer():\n def inner():\n  WorkUnitCatalogueRepository().load(); "
            "return select_modelo_work_resolution()",
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
            "def parallel(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
            " for unit in catalogue.values():\n"
            "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(inventory: WorkUnitCatalogue, modelo, filing_year):\n"
            " for unit in inventory.values():\n"
            "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(catalogue: WorkUnitCatalogue, holder, modelo, filing_year):\n"
            " holder.units = catalogue\n"
            " for unit in holder.units.values():\n"
            "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(inventory: WorkUnitCatalogue, wanted):\n"
            " for unit in inventory.values():\n"
            "  if unit.work_unit_id == wanted:\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(inventory: WorkUnitCatalogue, token):\n"
            " for unit in inventory.values():\n"
            "  if unit.work_unit_id.startswith(token) or unit.work_unit_id.endswith(token):\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(repo: WorkUnitCatalogueRepository):\n"
            " inventory = repo.load()\n"
            " for unit in inventory.values():\n"
            "  return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(repo: WorkUnitCatalogueRepository, wanted):\n"
            " inventory, revision = repo.load_revisioned()\n"
            " for unit in inventory.values():\n"
            "  if unit.work_unit_id == wanted:\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(repo: WorkUnitCatalogueRepository):\n return next(iter(repo.load().values()))",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(repo: WorkUnitCatalogueRepository):\n"
            " inventory = repo.load()\n"
            " return next(iter(inventory.items()))",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(inventory: WorkUnitCatalogue, wanted):\n"
            " for unit in inventory.values():\n"
            "  if unit.work_unit_id == wanted:\n"
            "   yield unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
            " units = catalogue\n"
            " for unit in units.values():\n"
            "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
            "   return unit",
            "parallel natural catalogue scan",
        ),
        (
            "def parallel(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
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
        "def project(catalogue: WorkUnitCatalogue):\n"
        " for unit in catalogue.values():\n"
        "  yield unit.modelo, unit.filing_year, unit.period\n",
        encoding="utf-8",
    )
    assert scan_canonical_authority(_MUTANT_SPEC, (_CANONICAL, path)) == []


def test_counting_comparisons_are_not_a_selector_mutant(tmp_path: Path) -> None:
    path = tmp_path / "analytics.py"
    path.write_text(
        "def count_matching(inventory: WorkUnitCatalogue, modelo, filing_year):\n"
        " return sum(\n"
        "  1 for unit in inventory.values()\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year\n"
        " )\n",
        encoding="utf-8",
    )
    assert scan_canonical_authority(_MUTANT_SPEC, (_CANONICAL, path)) == []


@pytest.mark.parametrize(
    "source",
    [
        ("def count_loaded(repo: WorkUnitCatalogueRepository):\n return len(repo.load().values())\n"),
        (
            "def project(inventory: WorkUnitCatalogue, wanted):\n"
            " for unit in inventory.values():\n"
            "  if unit.work_unit_id == wanted:\n"
            "   yield unit.modelo\n"
        ),
    ],
)
def test_repository_analytics_and_yielded_projections_are_not_selectors(source: str, tmp_path: Path) -> None:
    path = tmp_path / "non_selector.py"
    path.write_text(source, encoding="utf-8")
    assert scan_canonical_authority(_MUTANT_SPEC, (_CANONICAL, path)) == []


def test_only_exact_canonical_selector_is_exempt_from_natural_scan(tmp_path: Path) -> None:
    owner = tmp_path / "work_addressing.py"
    owner.write_text(
        "def select_modelo_work_resolution(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
        " for unit in catalogue.values():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return unit\n"
        "def extra_selector(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
        " for unit in catalogue.values():\n"
        "  if unit.modelo == modelo and unit.filing_year == filing_year:\n"
        "   return unit\n",
        encoding="utf-8",
    )
    spec = CanonicalAuthoritySpec(
        targets=(
            CanonicalAuthorityTarget("example.work_addressing", owner, frozenset({"select_modelo_work_resolution"})),
        ),
        natural_scan_rules=(_NATURAL_SCAN_RULE,),
    )
    findings = scan_canonical_authority(spec, (owner,))
    assert [(hit.kind, hit.detail) for hit in findings] == [("parallel natural catalogue scan", "extra_selector")]
