"""Shared helpers for Modelo work UX CLI tests."""

from __future__ import annotations

import json

# Importing the wizard catalogue + persistence modules triggers
# register_wizard_catalogue() at import time, exactly as the production CLI
# startup does.
import cadrumo.application.wizard.catalogue as _wizard_catalogue
import cadrumo.application.wizard.persistence as _wizard_persistence
from cadrumo.domain.calculations.registry.temporal import select_revision

from ....core.aggregation import BindingSourceKind
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_PROFILE_LABEL = "operator"
#: The seeded profile's machine identity. A profile id is a UUID; the
#: readable "operator" above is the operator-chosen LABEL, and the two are
#: different concepts that must not share one constant.
_PROFILE_ID = "6f1d2c3a-4b5e-4f60-8a71-9c2d3e4f5a6b"


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile(*, activity_start_date: str | None = None) -> None:
    """Register the operator profile through the shared CLI registration door.

    Creation is a precondition here, not the subject: these tests exercise the
    modelo work UX against a profile that already exists.
    """
    facts = {
        "identity.tax_id": "12345678Z",
        "identity.name": "Operator",
        "identity.surnames": "Readiness",
        "activities.description": "design",
    }
    if activity_start_date is not None:
        facts["censo.activity_start_date"] = activity_start_date
    register_cli_profile(label=_PROFILE_LABEL, facts=facts)


def _create_gb_non_resident_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "Spanish-source rent",
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "GB",
            "taxpayer_type.representante_fiscal_nif": "12345678Z",
            "taxpayer_type.representante_fiscal_nombre": "Test Representative",
        },
    )


def _create_de_nonresident_legal_entity_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B66012345",
            "identity.legal_name": "NordHaus GmbH",
            "activities.description": "Spanish-source services",
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "DE",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def _create_attribution_entity_intracom_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "attribution_entity",
            "identity.tax_id": "E12345674",
            "identity.name": "M349 Readiness CB",
            "activities.description": "intracommunity operations",
            "iva.does_intracomunitario": "true",
        },
    )


def _create_m130_work_unit(*, period: str = "1T") -> str:
    return create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2025,
        period=period,
        revision="2019-y-siguientes",
    )


def _create_m303_work_unit() -> str:
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "303")
    return create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=2025,
        period="1T",
        revision=str(select_revision(modelo, filing_year=2025, period="1T").id),
    )


def _seed_m111_retencion_observation() -> None:
    """Seed one work-income retención percepción so a Modelo 111 work unit's
    ``work calculate`` resolves the ``retenciones_aggregation`` source.

    Modelo 111 calculation requires per-perceptor retención evidence: the
    source resolver refuses an all-blank quarter rather than silently filing
    a zero return. One real ``rendimientos_trabajo`` percepción is the
    minimum that makes the 2025 1T quarter calculable.
    """
    observation = json.dumps(
        {
            "source_kind": BindingSourceKind.LEDGER_TRANSACTION.value,
            "source_object_id": "m111-work-income-row-001",
            "perceptor_nif": "A12345678",
            "perceptor_name": "Empresa Pagadora SL",
            "scheme": "rendimientos_trabajo",
            "taxable_base": "1000.00",
            "retencion_amount": "190.00",
            "accrued_on": "2025-01-15",
        },
    )
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--retencion-observation", observation,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_calculable_work_unit() -> str:
    """Create a modelo 111 work unit whose `work calculate` succeeds.

    Seeds one real work-income retención percepción so the
    ``retenciones_aggregation`` source resolves the quarter; the calc path
    then needs no further operator-supplied casilla inputs.
    """
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="111",
        filing_year=2025,
        period="1T",
        revision="2019-y-siguientes",
    )
    _seed_m111_retencion_observation()
    return work_unit_id
