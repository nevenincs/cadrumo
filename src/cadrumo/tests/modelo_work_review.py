"""Public real-storage construction support for canonical modelo-work review tests.

Entrypoint tests consume this defining test-support module directly.  It is not
an application-layer test helper or a package facade.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..application.modelo.work_review_projection import ModeloWorkReview, build_modelo_work_review
from ..core import Period
from ..domain.calculations.registry import CasillaObservation, bundled_authority, select_revision
from ..domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    WorkUnit,
    derive_calculation_revision_id,
    derive_verification_report_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_verification_report,
    upsert_work_unit,
)
from .secure_sql import isolated_runtime_profile

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=UTC)


def build_real_modelo_work_review(
    tmp_path: Path,
    *,
    modelo: str,
    filing_year: int,
    period_code: str,
    blocked: bool = False,
    materialised: bool = False,
) -> ModeloWorkReview:
    """Build the public review record from genuine encrypted repositories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository
        work_repository = WorkUnitCatalogueRepository(objects=objects)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
        verification_repository = VerificationReportCatalogueRepository(objects=objects)
        modelo_code = ModeloCode(modelo)
        period = Period.from_year_and_code(filing_year, period_code)
        authority = bundled_authority()
        selected_revision = select_revision(
            authority.validate_modelo(modelo_code),
            filing_year=filing_year,
            period=period.registry_token,
        )
        snapshot = authority.snapshot(
            modelo_code,
            filing_year=filing_year,
            period=period.registry_token,
            revision_id=selected_revision.id,
            grade=selected_revision.effective_authority_grade,
        )
        work_unit_id = derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        )
        casilla_values: dict[str, Decimal] = {}
        binding_overrides: dict[str, str] = {}
        observations: tuple[CasillaObservation, ...] = ()
        if materialised:
            materialised_values = {
                "01": Decimal("10000"),
                "02": Decimal("5000"),
                "03": Decimal("5000"),
                "06": Decimal("0"),
            }
            definitions = {str(casilla.id): casilla for casilla in snapshot.revision.casillas}
            casilla_values = dict(materialised_values)
            binding_overrides = {
                "modelo-130-actividad-economica-ingresos-cumulative": "9000",
                "modelo-130-actividad-economica-gastos-cumulative": "5000",
            }
            observations = tuple(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=value,
                    legal_refs=tuple(definitions[casilla_id].legal_refs),
                    source_refs=tuple(definitions[casilla_id].source_refs),
                )
                for casilla_id, value in materialised_values.items()
            )
        calculation_revision_id = (
            derive_calculation_revision_id(
                work_unit_id=work_unit_id,
                input_values_by_casilla_id={},
                binding_overrides=binding_overrides,
                casilla_values=casilla_values,
                filing_instance_evidence=None,
                source_provenance=(),
            )
            if blocked or materialised
            else None
        )
        work_unit = WorkUnit(
            work_unit_id=work_unit_id,
            bucket_id=_BUCKET_ID,
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
            name=f"{modelo}-{filing_year}-{period_code}",
            current_calculation_revision_id=calculation_revision_id,
            created_at=_NOW,
            updated_at=_NOW,
        )
        work_repository.save(upsert_work_unit(work_repository.load(), work_unit))

        if calculation_revision_id is not None:
            calculation = CalculationRevision(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                state=CalculationRevisionState.BORRADOR,
                binding_overrides=binding_overrides,
                casilla_values=casilla_values,
                observations=observations,
                created_at=_NOW,
                updated_at=_NOW,
                filing_instance_evidence=None,
                source_provenance=(),
            )
            calculation_repository.save(
                upsert_calculation_revision(calculation_repository.load(), calculation),
            )
            affected = next(casilla for casilla in snapshot.revision.casillas if casilla.legal_refs)
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id=affected.id,
                expectation_id="review-screen-expectation",
                message_locale_key="application.modelo.findings.blocking_rule",
                message_facts={"casilla_id": str(affected.id)},
                legal_refs=tuple(affected.legal_refs),
                source_refs=tuple(affected.source_refs),
            )
            findings = (finding,)
            if materialised:
                findings = (
                    finding,
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
                        severity=ModeloVerificationFindingSeverity.WARNING,
                        message_locale_key="application.modelo.findings.m303_m349_intracom_reconciliation_mismatch",
                        message_facts={
                            "period_code": period.registry_token,
                            "filing_year": filing_year,
                            "m303_total": Decimal("100"),
                            "m349_total": Decimal("80"),
                            "gap": Decimal("20"),
                        },
                        legal_refs=tuple(affected.legal_refs),
                        source_refs=tuple(affected.source_refs),
                    ),
                )
            report = VerificationReport(
                verification_report_id=derive_verification_report_id(
                    calculation_revision_id=calculation_revision_id,
                    completeness_status=VerificationCompletenessStatus.BLOCKED,
                    findings=findings,
                    verified_by="modelo-review-tui-test",
                ),
                calculation_revision_id=calculation_revision_id,
                completeness_status=VerificationCompletenessStatus.BLOCKED,
                findings=findings,
                run_at=_NOW,
                verified_by="modelo-review-tui-test",
                granted_verificado_completo=False,
            )
            verification_repository.save(
                upsert_verification_report(verification_repository.load(), report),
            )

        return build_modelo_work_review(
            _BUCKET_ID,
            modelo_code,
            filing_year,
            period,
            authority=authority,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
        )


__all__ = ["build_real_modelo_work_review"]
