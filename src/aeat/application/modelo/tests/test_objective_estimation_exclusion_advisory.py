from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.deadlines import IrpfEstimationRegime, IVARegime, TaxpayerProfile
from ....domain.modelos import ModeloVerificationFindingKind
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._verification_report import ModeloVerificationFindingSeverity
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from .._actions import _collect_revision_verification_findings
from .._objective_estimation_advisory import _objective_estimation_exclusion_advisory_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _work_unit(*, modelo: str = "131", filing_year: int = 2024) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, "4T" if modelo == "131" else "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="objective-estimation-advisory",
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=str(filing_year),
        ),
        bucket_id="objective-estimation-advisory",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=str(filing_year),
        name=f"{modelo}-{filing_year}-{period.registry_token}",
        created_at=_T0,
        updated_at=_T0,
    )


def _objective_profile(**overrides: object) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        **overrides,
    )


def _calculation_revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        created_at=_T0,
        updated_at=_T0,
    )


def test_objective_estimation_exclusion_advisory_fires_for_settled_year_excess() -> None:
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("125000.01"),
        objective_estimation_prior_year_purchases_eur=Decimal("250000.01"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(work_unit=_work_unit(), profile=profile)

    assert len(findings) == 3
    assert {finding.kind for finding in findings} == {ModeloVerificationFindingKind.ADVISORY}
    assert {finding.severity for finding in findings} == {ModeloVerificationFindingSeverity.WARNING}
    assert all("ley-35-2006:dt-32" in finding.legal_refs for finding in findings)
    assert {finding.message.split("field=")[1].split(" ")[0] for finding in findings} == {
        "objective_estimation_prior_year_gross_income_eur",
        "objective_estimation_prior_year_invoice_gross_income_eur",
        "objective_estimation_prior_year_purchases_eur",
    }


def test_objective_estimation_exclusion_advisory_does_not_apply_unresolved_2025_scope() -> None:
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("999999.00"),
        objective_estimation_prior_year_invoice_gross_income_eur=Decimal("999999.00"),
        objective_estimation_prior_year_purchases_eur=Decimal("999999.00"),
    )

    findings = _objective_estimation_exclusion_advisory_findings(
        work_unit=_work_unit(filing_year=2025),
        profile=profile,
    )

    assert findings == ()


def test_revision_verification_collects_objective_estimation_exclusion_advisory() -> None:
    work_unit = _work_unit(modelo="131", filing_year=2024)
    profile = _objective_profile(
        objective_estimation_prior_year_gross_income_eur=Decimal("250000.01"),
    )

    findings, _resolved, _missing = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=_calculation_revision(work_unit),
        profile=profile,
    )

    matching = [
        finding
        for finding in findings
        if "objective_estimation_prior_year_gross_income_eur" in finding.message
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
