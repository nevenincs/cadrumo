"""Atomic validation of immutable Modelo 303 filing evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos import (
    FilingInstanceEvidence,
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
    ModeloError,
    WorkUnit,
    derive_work_unit_id,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .._m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e3030000-0000-4000-8000-000000000058"
_CLOCK = datetime(2026, 4, 1, tzinfo=UTC)


def _general_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def _work_unit(period: Period) -> WorkUnit:
    registry_snapshot = resources().modelos.authority.snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.code,
    )
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            revision_id=registry_snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=period.filing_year,
        period=period,
        revision_id=registry_snapshot.revision.id,
        name=f"303-{period.filing_year}-{period.code}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _evidence(period: Period) -> FilingInstanceEvidence:
    scope = _general_scope()
    registry_snapshot = resources().modelos.authority.snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.code,
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference="test:validation:exonerado-390"),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=M303RegimenSimplificadoFilingEvidence(
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=resolve_m303_regimen_simplificado_snapshot(
                    registry_snapshot=registry_snapshot,
                    scope_decision=scope,
                ),
            ),
        ),
    )


def _store_profile() -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="M303 filing evidence validation",
            facts=(
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _activity_rows(reference: FilingEvidenceReference) -> tuple[M303Exonerado390ActivityRowEvidence, ...]:
    return (
        M303Exonerado390ActivityRowEvidence(
            slot=1, codigo_actividad="A01", epigrafe_iae="4101", evidence_reference=reference
        ),
        M303Exonerado390ActivityRowEvidence(
            slot=2, codigo_actividad="A02", epigrafe_iae="4102", evidence_reference=reference
        ),
        M303Exonerado390ActivityRowEvidence(
            slot=3, codigo_actividad="A03", epigrafe_iae="4103", evidence_reference=reference
        ),
        M303Exonerado390ActivityRowEvidence(
            slot=4, codigo_actividad="A04", epigrafe_iae="4104", evidence_reference=reference
        ),
        M303Exonerado390ActivityRowEvidence(
            slot=5, codigo_actividad="A05", epigrafe_iae="4105", evidence_reference=reference
        ),
        M303Exonerado390ActivityRowEvidence(
            slot=6, codigo_actividad="A06", epigrafe_iae="4106", evidence_reference=reference
        ),
    )


def test_complete_evidence_matches_work_unit_registry_and_active_censo(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "1T")
    work_unit = _work_unit(period)
    evidence = _evidence(period)
    registry_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile()
        validated = validate_m303_filing_instance_evidence_for_revision(
            work_unit=work_unit,
            registry_snapshot=registry_snapshot,
            evidence=evidence,
            casilla_values={},
            observations=(),
        )

    assert validated == evidence


def test_evidence_for_another_work_period_refuses_before_persistence(tmp_path: Path) -> None:
    work_period = Period.from_year_and_code(2026, "1T")
    evidence_period = Period.from_year_and_code(2026, "2T")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile()
        with pytest.raises(ModeloError, match="period must match its work unit"):
            validate_m303_filing_instance_evidence_for_revision(
                work_unit=_work_unit(work_period),
                registry_snapshot=resources().modelos.authority.snapshot("303", filing_year=2026, period="1T"),
                evidence=_evidence(evidence_period),
                casilla_values={},
                observations=(),
            )


def test_final_period_exonerado_evidence_covers_every_a28_endpoint_and_observation(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "4T")
    work_unit = _work_unit(period)
    registry_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="4T")
    endpoint_ids = tuple(
        casilla.id
        for casilla in registry_snapshot.revision.casillas
        if tuple(casilla.section)[:2] == ("iva", "exonerado_390")
    )
    values = {casilla_id: Decimal("0") for casilla_id in endpoint_ids}
    reference = FilingEvidenceReference(reference="test:validation:all-a28-endpoints")
    base = _evidence(period)
    evidence = FilingInstanceEvidence(
        m303=base.m303.model_copy(
            update={
                "exonerado_390": M303Exonerado390FilingEvidence(
                    applicable=True,
                    applicability_reference=reference,
                    endpoints=tuple(
                        M303Exonerado390EndpointEvidence(
                            casilla_id=casilla_id,
                            value=value,
                            evidence_reference=reference,
                        )
                        for casilla_id, value in values.items()
                    ),
                    activity_rows=_activity_rows(reference),
                    operaciones_terceros_declarables=False,
                    operaciones_terceros_reference=reference,
                ),
            },
        ),
    )
    observations = registry_grounded_observations(
        modelo="303",
        filing_year=2026,
        period="4T",
        casilla_values=values,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile()
        validated = validate_m303_filing_instance_evidence_for_revision(
            work_unit=work_unit,
            registry_snapshot=registry_snapshot,
            evidence=evidence,
            casilla_values=values,
            observations=observations,
        )

    assert validated == evidence


def test_incomplete_a28_endpoint_population_refuses_before_persistence(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "4T")
    registry_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="4T")
    endpoint = next(
        casilla
        for casilla in registry_snapshot.revision.casillas
        if tuple(casilla.section)[:2] == ("iva", "exonerado_390")
    )
    reference = FilingEvidenceReference(reference="test:validation:incomplete-a28")
    base = _evidence(period)
    evidence = FilingInstanceEvidence(
        m303=base.m303.model_copy(
            update={
                "exonerado_390": M303Exonerado390FilingEvidence(
                    applicable=True,
                    applicability_reference=reference,
                    endpoints=(
                        M303Exonerado390EndpointEvidence(
                            casilla_id=endpoint.id,
                            value=Decimal("0"),
                            evidence_reference=reference,
                        ),
                    ),
                    activity_rows=_activity_rows(reference),
                    operaciones_terceros_declarables=False,
                    operaciones_terceros_reference=reference,
                ),
            },
        ),
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile()
        with pytest.raises(ModeloError, match="cover every canonical A28 endpoint"):
            validate_m303_filing_instance_evidence_for_revision(
                work_unit=_work_unit(period),
                registry_snapshot=registry_snapshot,
                evidence=evidence,
                casilla_values={endpoint.id: Decimal("0")},
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=2026,
                    period="4T",
                    casilla_values={endpoint.id: Decimal("0")},
                ),
            )
