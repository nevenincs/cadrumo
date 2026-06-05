"""SensitivityClass pinning tests for the modelo catalogue repositories.

Persistence of every modelo catalogue must classify under
``SensitivityClass.FINANCIAL`` so an operator's encrypted database
backend treats the rows under the FINANCIAL key-rotation policy.
These tests read the catalogue source modules directly through ``ast``
so a future rebrand from FINANCIAL to any other class is caught at
review time, not at runtime.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_REPOSITORY_SOURCES: tuple[tuple[str, Path], ...] = (
    (
        "CalculationRevisionCatalogueRepository",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "modelos" / "_calculation_repository.py",
    ),
    (
        "ModeloRecordCatalogueRepository",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "modelos" / "_filing_repository.py",
    ),
    (
        "WorkUnitCatalogueRepository",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "modelos" / "_repository.py",
    ),
    (
        "VerificationReportCatalogueRepository",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "modelos" / "_verification_repository.py",
    ),
    (
        "BucketEventHistoryRepository",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "buckets" / "_event_repository.py",
    ),
)


def _sensitivity_attr_references(source: Path) -> set[str]:
    """Return every ``SensitivityClass.<NAME>`` attribute referenced in ``source``."""

    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "SensitivityClass":
            found.add(node.attr)
    return found


@pytest.mark.parametrize(("repository_name", "source_path"), _REPOSITORY_SOURCES)
def test_repository_classifies_every_persistence_under_financial(repository_name: str, source_path: Path) -> None:
    """Each modelo / bucket-event-history repository must use only
    ``SensitivityClass.FINANCIAL`` for its load / save calls.
    A future migration to a different class would be a deliberate
    architectural change requiring updates here and in
    ``aeat.core.classification``."""

    classes_used = _sensitivity_attr_references(source_path)
    assert classes_used == {"FINANCIAL"}, (
        f"{repository_name} ({source_path.relative_to(PROJECT_ROOT)}) "
        f"references unexpected SensitivityClass members: {sorted(classes_used)!r}"
    )


def test_every_repository_source_actually_references_sensitivity_class() -> None:
    """Guard against an accidental drop of the SensitivityClass call:
    every repository file MUST still reference the enum so the test
    above never silently passes on a repository that lost its
    classification."""

    for repository_name, source_path in _REPOSITORY_SOURCES:
        classes_used = _sensitivity_attr_references(source_path)
        assert classes_used, (
            f"{repository_name} ({source_path.relative_to(PROJECT_ROOT)}) "
            "lost all SensitivityClass references; persistence is unclassified"
        )
