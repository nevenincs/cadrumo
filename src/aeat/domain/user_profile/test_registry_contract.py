"""User-profile schema coverage checks against committed modelo registry use."""

from __future__ import annotations

import pytest

from ...core.config import PROJECT_ROOT
from ..calculations.registry import load_registry_tree
from . import (
    UserProfileRegistryContractSeverity,
    build_user_profile_selector_index,
    load_user_profile_schema,
    validate_user_profile_registry_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_schema_selector_index_contains_modelo_profile_namespaces() -> None:
    schema = load_user_profile_schema()

    index = build_user_profile_selector_index(schema)

    assert "tax.id" in index.profile_selectors
    assert "TaxResidenceProfile.ccaa" in index.profile_selectors
    assert "RentaFamilyProfile.descendants.tax_id" in index.profile_selectors
    assert "RentaFamilyProfile.ascendants.cohabiting_descendant_count" in index.profile_selectors
    assert "enrollment.large_company" in index.schedule_predicates
    assert "tax.id" not in index.schedule_predicates
    assert "profile_tax_id" in index.export_headers


def test_committed_modelo_profile_selectors_are_declared_by_user_profile_schema() -> None:
    schema = load_user_profile_schema()
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")

    report = validate_user_profile_registry_contract(modelos, schema)

    blocking = [
        f"{issue.modelo_id}:{issue.revision_id}:{issue.surface}:{issue.construct_id}:{issue.selector}"
        for issue in report.errors
    ]
    assert report.valid, "\n".join(blocking)
    assert all(issue.severity is not UserProfileRegistryContractSeverity.ERROR for issue in report.issues)
    assert len(report.warnings) == 35
    assert {issue.selector for issue in report.warnings} >= {
        "colegio_concertado",
        "datos_adicionales_declaraci-n-complementaria-6",
    }
