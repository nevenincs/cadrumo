"""Resident-service discovery gate for the canonical Modelo work-addressing owner."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ....quality.import_hygiene_scan import (
    SubstitutableWorkSelectorRule,
    source_contains_substitutable_work_selector,
)

_ROOT = Path(__file__).resolve().parents[4]
_CANONICAL_OWNER = "src/cadrumo/application/modelo/work_addressing.py"
_OWNER_SYMBOLS = frozenset({"ModeloWorkResolution", "ModeloWorkSelectorRequest", "select_modelo_work_resolution"})
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


@dataclass(frozen=True, slots=True)
class ModeloAddressingSearchClassification:
    canonical_owners: frozenset[str]
    parallel_owners: frozenset[str]


def _classify_modelo_addressing_results(results: list[dict[str, Any]]) -> ModeloAddressingSearchClassification:
    """Classify defining-owner hits while ignoring tests, docs, and ordinary consumers."""
    canonical: set[str] = set()
    parallel: set[str] = set()
    for hit in results:
        path = str(hit.get("path", "")).replace("\\", "/")
        if path == _CANONICAL_OWNER:
            canonical.add(path)
        is_production = path.startswith("src/cadrumo/") and "/tests/" not in path
        declared_name = str(hit.get("function_name") or hit.get("class_name") or "")
        snippet = str(hit.get("snippet") or "")
        declares_owner = any(
            declaration in snippet
            for declaration in (
                "class ModeloWorkResolution",
                "class ModeloWorkSelectorRequest",
                "def select_modelo_work_resolution(",
            )
        )
        wraps_repository = (
            "def " in snippet
            and "select_modelo_work_resolution(" in snippet
            and any(read in snippet for read in (".load(", ".load_revisioned(", "catalogue.get("))
        )
        natural_scan = source_contains_substitutable_work_selector(snippet, _NATURAL_SCAN_RULE)
        if is_production and (declared_name in _OWNER_SYMBOLS or declares_owner or wraps_repository or natural_scan):
            parallel.add(path)
    return ModeloAddressingSearchClassification(frozenset(canonical), frozenset(parallel))


@pytest.mark.unit
@pytest.mark.hex_core
def test_result_classification_rejects_mixed_canonical_and_parallel_owners() -> None:
    results = [
        {"path": _CANONICAL_OWNER, "function_name": "select_modelo_work_resolution"},
        {
            "path": _CANONICAL_OWNER,
            "snippet": (
                "def extra_selector(inventory: WorkUnitCatalogue, wanted):\n"
                "    for unit in inventory.values():\n"
                "        if unit.work_unit_id == wanted:\n"
                "            return unit"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/parallel_selector.py",
            "snippet": "def select_modelo_work_resolution(request, *, catalogue, bucket_id): ...",
        },
        {
            "path": "src/cadrumo/application/modelo/aliased_items_scan.py",
            "snippet": (
                "def resolve(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
                "    units = catalogue\n"
                "    for key, unit in units.items():\n"
                "        if unit.modelo == modelo and unit.filing_year == filing_year:\n"
                "            return key, unit"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/projection.py",
            "snippet": (
                "def project(catalogue: WorkUnitCatalogue):\n"
                "    for unit in catalogue.values():\n"
                "        yield unit.modelo, unit.filing_year, unit.period"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/analytics.py",
            "snippet": (
                "def count_matching(inventory: WorkUnitCatalogue, modelo, filing_year):\n"
                "    return sum(\n"
                "        1 for unit in inventory.values()\n"
                "        if unit.modelo == modelo and unit.filing_year == filing_year\n"
                "    )"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/revisioned_scan.py",
            "snippet": (
                "def resolve(repo: WorkUnitCatalogueRepository, wanted):\n"
                "    inventory, revision = repo.load_revisioned()\n"
                "    for unit in inventory.values():\n"
                "        if unit.work_unit_id == wanted:\n"
                "            return unit"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/direct_first.py",
            "snippet": ("def resolve(repo: WorkUnitCatalogueRepository):\n    return next(iter(repo.load().values()))"),
        },
        {
            "path": "src/cadrumo/application/modelo/yield_selector.py",
            "snippet": (
                "def resolve(inventory: WorkUnitCatalogue, wanted):\n"
                "    for unit in inventory.values():\n"
                "        if unit.work_unit_id == wanted:\n"
                "            yield unit"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/yield_projection.py",
            "snippet": (
                "def project(inventory: WorkUnitCatalogue, wanted):\n"
                "    for unit in inventory.values():\n"
                "        if unit.work_unit_id == wanted:\n"
                "            yield unit.modelo"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/natural_scan.py",
            "snippet": (
                "def resolve(catalogue: WorkUnitCatalogue, modelo, filing_year):\n"
                "    for unit in catalogue.values():\n"
                "        if unit.modelo == modelo and unit.filing_year == filing_year:\n"
                "            return unit"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/repository_wrapper.py",
            "snippet": (
                "def resolve(repo, request, bucket_id):\n"
                "    catalogue = repo.load()\n"
                "    return select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)"
            ),
        },
        {
            "path": "src/cadrumo/application/modelo/tests/test_work_addressing.py",
            "function_name": "select_modelo_work_resolution",
        },
    ]
    classification = _classify_modelo_addressing_results(results)
    assert classification.canonical_owners == {_CANONICAL_OWNER}
    assert classification.parallel_owners == {
        "src/cadrumo/application/modelo/parallel_selector.py",
        "src/cadrumo/application/modelo/repository_wrapper.py",
        "src/cadrumo/application/modelo/natural_scan.py",
        "src/cadrumo/application/modelo/aliased_items_scan.py",
        _CANONICAL_OWNER,
        "src/cadrumo/application/modelo/revisioned_scan.py",
        "src/cadrumo/application/modelo/direct_first.py",
        "src/cadrumo/application/modelo/yield_selector.py",
    }


@pytest.mark.integration
@pytest.mark.hex_core
@pytest.mark.resident_service
def test_rag_discovery_returns_the_canonical_owner() -> None:
    status_dir = Path(os.environ["_VAULTSPEC_RAG_PYTEST_SINGLETON_ROOT"]) / "modelo-addressing-client"
    status_dir.mkdir()
    command = ("uv", "tool", "run", "--from", "vaultspec-rag==0.4.2", "vaultspec-rag")
    version = subprocess.run(  # noqa: S603
        (*command, "--version"),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert version.returncode == 0, version.stderr
    assert "0.4.2" in version.stdout, version.stdout
    result = subprocess.run(  # noqa: S603
        (
            *command,
            "--status-dir",
            str(status_dir),
            "search",
            "Modelo work-unit selector repository wrapper natural catalogue scan facade import",
            "--type",
            "code",
            "--port",
            "8766",
            "--timeout",
            "45.0",
            "--json",
        ),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response.get("ok") is True, response
    classification = _classify_modelo_addressing_results(response.get("data", {}).get("results", []))
    assert classification.canonical_owners == {_CANONICAL_OWNER}, classification
    assert classification.parallel_owners == frozenset(), classification
