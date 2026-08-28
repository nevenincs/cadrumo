from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from ....core import Period
from ....domain.deadlines import IrpfEstimationRegime, IVARegime, TaxpayerProfile
from ....domain.modelos import (
    ModeloCode,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    WorkUnit,
    derive_work_unit_id,
)
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .._objective_estimation_advisory import _objective_estimation_exclusion_advisory_findings
from .._verification_actions import _collect_revision_verification_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _work_unit(*, modelo: str = "131", filing_year: int = 2024) -> WorkUnit:
    periodo_code = "4T" if modelo == "131" else "0A"
    modelo_code = ModeloCode(modelo)
    period = Period.from_year_and_code(filing_year, periodo_code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="objective-estimation-advisory",
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=str(filing_year),
        ),
        bucket_id="objective-estimation-advisory",
        modelo=modelo_code,
        filing_year=filing_year,
        period=period,
        revision_id=str(filing_year),
        name=f"{modelo}-{filing_year}-{period.registry_token}",
        created_at=_T0,
        updated_at=_T0,
    )


def _objective_profile(**overrides: Any) -> TaxpayerProfile:
    base_data: dict[str, Any] = {
        "tax_id": "X1234567L",
        "iva_regime": IVARegime.GENERAL,
        "irpf_estimation_regime": IrpfEstimationRegime.OBJETIVA,
    }
    base_data.update(overrides)
    return TaxpayerProfile(**base_data)


def _calculation_revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_objective_estimation_exclusion_advisory_fires_for_settled_year_excess() -> None:
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("125000.01"),
        objective_estimation_prior_year_agri_livestock_forest_gross_eur=Decimal("250000.01"),
        objective_estimation_prior_year_purchases_eur=Decimal("250000.01"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(work_unit=_work_unit(), profile=profile)

    assert len(findings) == 4
    assert {finding.kind for finding in findings} == {ModeloVerificationFindingKind.ADVISORY}
    assert {finding.severity for finding in findings} == {ModeloVerificationFindingSeverity.WARNING}
    legal_refs_by_field = {
        str(finding.message_facts["profile_field_id"]): set(finding.legal_refs) for finding in findings
    }
    assert legal_refs_by_field == {
        "objective_estimation_prior_year_gross_income_eur": {"ley-35-2006:dt-32"},
        "objective_estimation_prior_year_invoice_gross_income_eur": {"ley-35-2006:dt-32"},
        "objective_estimation_prior_year_agri_livestock_forest_gross_eur": {"ley-35-2006:art-31"},
        "objective_estimation_prior_year_purchases_eur": {"ley-35-2006:dt-32"},
    }
    assert set(legal_refs_by_field) == {
        "objective_estimation_prior_year_gross_income_eur",
        "objective_estimation_prior_year_invoice_gross_income_eur",
        "objective_estimation_prior_year_agri_livestock_forest_gross_eur",
        "objective_estimation_prior_year_purchases_eur",
    }


def test_objective_estimation_exclusion_advisory_applies_to_aeat_2025_scope() -> None:
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("125000.01"),
        objective_estimation_prior_year_agri_livestock_forest_gross_eur=Decimal("250000.01"),
        objective_estimation_prior_year_purchases_eur=Decimal("250000.01"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(
        work_unit=_work_unit(filing_year=2025),
        profile=profile,
    )

    assert len(findings) == 4
    assert all(finding.message_facts["filing_year"] == 2025 for finding in findings)
    assert {finding.source_refs for finding in findings} == {("aeat-renta-2025-manual-parte1",)}


def test_objective_estimation_exclusion_advisory_applies_to_aeat_2026_scope() -> None:
    profile = _objective_profile(
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("125000.01"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(
        work_unit=_work_unit(filing_year=2026),
        profile=profile,
    )

    assert len(findings) == 1
    assert findings[0].legal_refs == ("ley-35-2006:dt-32",)
    assert findings[0].source_refs == ("aeat-renta-2025-manual-parte1",)


def test_objective_estimation_exclusion_advisory_does_not_project_beyond_official_scope() -> None:
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("999999.00"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("999999.00"),
        objective_estimation_prior_year_agri_livestock_forest_gross_eur=Decimal("999999.00"),
        objective_estimation_prior_year_purchases_eur=Decimal("999999.00"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(
        work_unit=_work_unit(filing_year=2027),
        profile=profile,
    )

    assert findings == ()


def test_revision_verification_collects_objective_estimation_exclusion_advisory() -> None:
    work_unit = _work_unit(modelo="131", filing_year=2024)
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
    )

    findings, _resolved, _missing, _failures_by_finding_id = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=_calculation_revision(work_unit),
        profile=profile,
        transaction_repository=None,
    )

    matching = [
        finding
        for finding in findings
        if finding.message_facts.get("profile_field_id") == "objective_estimation_prior_year_gross_income_eur"
    ]
    assert len(matching) == 1
    assert matching[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert matching[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-35-2006:dt-32" in matching[0].legal_refs


def test_objective_estimation_exclusion_advisory_does_not_apply_direct_estimation_profile() -> None:
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        objective_estimation_prior_year_gross_income_eur=Decimal("999999.00"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(work_unit=_work_unit(), profile=profile)

    assert findings == ()
