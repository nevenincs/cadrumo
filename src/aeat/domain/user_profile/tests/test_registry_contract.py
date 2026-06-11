"""User-profile schema coverage checks against committed modelo registry use."""

from __future__ import annotations

import subprocess
import sys

import pytest

from ....core.resources import bundled_path
from ...calculations.registry import load_registry_tree
from .. import (
    UserProfileRegistryContractSeverity,
    build_user_profile_selector_index,
    load_user_profile_schema,
    profile_binding_selectors,
    validate_user_profile_registry_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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


def test_profile_binding_selectors_is_public_and_deduplicates_supported_selector_forms() -> None:
    selectors = profile_binding_selectors(
        {
            "profile_key": "tax.id",
            "profile_keys": ("tax.id", "tax.residence.ccaa"),
            "required_when_profile_key": "enrollment.large_company",
            "profile_model": "TaxResidenceProfile",
            "field": "ccaa",
        },
    )

    assert selectors == (
        "tax.id",
        "tax.residence.ccaa",
        "enrollment.large_company",
        "TaxResidenceProfile.ccaa",
    )


def test_committed_modelo_profile_selectors_are_declared_by_user_profile_schema() -> None:
    schema = load_user_profile_schema()
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    report = validate_user_profile_registry_contract(modelos, schema)

    blocking = [
        f"{issue.modelo_id}:{issue.revision_id}:{issue.surface}:{issue.construct_id}:{issue.selector}"
        for issue in report.errors
    ]
    assert report.valid, "\n".join(blocking)
    assert all(issue.severity is not UserProfileRegistryContractSeverity.ERROR for issue in report.issues)
    # Every WARNING must be the tolerated "export header not yet
    # classified" kind: committed layouts carry header fields whose
    # selectors are per-filing flags (e.g. declaracion_complementaria),
    # not stable taxpayer-profile attributes, so the user-profile schema
    # deliberately does not classify them. The exact warning count
    # drifts as schema-hardening lands new export layouts; what must
    # hold is that no warning is a different, unexpected kind — a real
    # classification gap would surface as a non-"export header" message
    # or an ERROR, both still caught above.
    assert report.warnings, "expected the tolerated export-header warnings to be present"
    assert all(
        issue.message == "export header is not yet classified by user-profile schema" for issue in report.warnings
    ), "an unexpected non-export-header warning kind appeared"
    assert {issue.selector for issue in report.warnings} >= {
        "colegio_concertado",
        "datos_adicionales_declaraci-n-complementaria-6",
        "declaracion_complementaria",
    }


def test_user_profile_imports_before_registry_barrel() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import aeat.domain.user_profile as u; "
            "import aeat.domain.calculations.registry as r; "
            "assert hasattr(u, 'validate_user_profile_registry_contract'); "
            "assert hasattr(r, 'RegistryValidator')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
