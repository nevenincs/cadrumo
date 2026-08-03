"""User-profile schema coverage checks against committed modelo registry use."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from ....core.errors import BaseSeverity
from ....core.resources import resources
from .. import (
    UserProfileRegistryContractIssue,
    build_user_profile_selector_index,
    load_user_profile_schema,
    profile_binding_selectors,
    validate_user_profile_registry_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

if TYPE_CHECKING:  # pragma: no cover
    from .._schema import ProfileSchemaDefinition

_MODELO_100_ANUALIDADES_YEARS = (2021, 2022, 2023)


def test_registry_contract_issue_uses_base_severity_but_refuses_info() -> None:
    issue = UserProfileRegistryContractIssue(
        severity=BaseSeverity.WARNING,
        modelo_id="303",
        revision_id="2025",
        surface="binding",
        construct_id="binding-iva-regime",
        selector="iva.regime",
        message="profile selector needs review",
    )

    assert issue.severity is BaseSeverity.WARNING
    with pytest.raises(ValueError, match="Input should be"):
        UserProfileRegistryContractIssue.model_validate(
            {
                "severity": BaseSeverity.INFO,
                "modelo_id": "303",
                "revision_id": "2025",
                "surface": "binding",
                "construct_id": "binding-iva-regime",
                "selector": "iva.regime",
                "message": "informational findings are not part of this contract",
            },
        )


def test_schema_selector_index_contains_modelo_profile_namespaces() -> None:
    schema = load_user_profile_schema()

    index = build_user_profile_selector_index(schema)

    assert "tax.id" in index.profile_selectors
    assert "TaxResidenceProfile.ccaa" in index.profile_selectors
    assert "RentaFamilyProfile.descendants.tax_id" in index.profile_selectors
    assert "RentaFamilyProfile.ascendants.cohabiting_descendant_count" in index.profile_selectors
    assert "enrollment.large_company" in index.schedule_predicates
    assert "enrollment.public_administration_budget_gt_6000000" in index.schedule_predicates
    assert "tax.id" not in index.schedule_predicates
    assert "profile_tax_id" in index.export_headers


def test_modelo_100_anualidades_selector_is_declared_for_each_separate_escala_year() -> None:
    schema = load_user_profile_schema()
    index = build_user_profile_selector_index(schema)
    failures: list[str] = []

    for year in _MODELO_100_ANUALIDADES_YEARS:
        selector = f"renta_family.anualidades_sin_minimo_descendientes_{year}"
        if selector not in schema.field_paths:
            failures.append(f"{year}: {selector!r} missing from schema.field_paths")
            continue
        if selector not in index.profile_selectors:
            failures.append(f"{year}: {selector!r} missing from profile selectors")

    assert not failures, "\n".join(failures)


def test_missing_modelo_100_anualidades_selector_is_rejected_for_each_year() -> None:
    schema = load_user_profile_schema()
    model = resources().modelos.authority.modelo("100")
    failures: list[str] = []

    for year in _MODELO_100_ANUALIDADES_YEARS:
        selector = f"renta_family.anualidades_sin_minimo_descendientes_{year}"
        broken_schema = _schema_without_field(schema, selector)
        report = validate_user_profile_registry_contract((model,), broken_schema)
        if report.valid:
            failures.append(f"{year}: removing {selector!r} unexpectedly left the report valid")
            continue
        if not any(issue.selector == selector for issue in report.errors):
            failures.append(f"{year}: removing {selector!r} did not produce a matching error")

    assert not failures, "\n".join(failures)


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
    modelos = resources().modelos.all()

    report = validate_user_profile_registry_contract(modelos, schema)

    blocking = [
        f"{issue.modelo_id}:{issue.revision_id}:{issue.surface}:{issue.construct_id}:{issue.selector}"
        for issue in report.errors
    ]
    assert report.valid, "\n".join(blocking)
    assert all(issue.severity is not BaseSeverity.ERROR for issue in report.issues)
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
            "import cadrumo.domain.user_profile as u; "
            "import cadrumo.domain.calculations.registry as r; "
            "assert hasattr(u, 'validate_user_profile_registry_contract'); "
            "assert hasattr(r, 'RegistryValidator')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def _schema_without_field(
    schema: ProfileSchemaDefinition,
    path: str,
) -> ProfileSchemaDefinition:
    section_key, field_key = path.split(".", 1)
    sections = []
    for section in schema.sections:
        if section.key != section_key:
            sections.append(section)
            continue
        fields = tuple(field for field in section.fields if field.key != field_key)
        sections.append(section.model_copy(update={"fields": fields}))
    return schema.model_copy(update={"sections": tuple(sections)})
