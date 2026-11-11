"""The period gate asks the canonical selector and reports a period it cannot place or choose."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ..casilla_lineage_seed_paths import MODELOS_ROOT, REGISTRY_ROOT
from ..period_edition_coverage import period_coverage_findings

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

SUPPORT = load_shared_catalogues(REGISTRY_ROOT).require_supported_filing_years()


@pytest.fixture(scope="module")
def modelo() -> ModeloDefinition:
    return load_modelo_directory(MODELOS_ROOT / "130")


def test_modelo_with_one_edition_per_period_is_clean(modelo: ModeloDefinition) -> None:
    assert period_coverage_findings([modelo], SUPPORT) == ()


def test_two_editions_covering_the_same_period_are_reported_as_overlap(modelo: ModeloDefinition) -> None:
    (only,) = ordered_revisions(modelo)
    twin = only.model_copy(update={"id": f"{only.id}-twin"})
    doubled = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})
    findings = period_coverage_findings([doubled], SUPPORT)
    assert findings
    assert {finding.outcome for finding in findings} == {"overlap"}
    assert {finding.year for finding in findings} <= set(SUPPORT.years)
