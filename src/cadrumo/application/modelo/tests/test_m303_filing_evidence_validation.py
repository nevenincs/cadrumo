"""Application-policy validation tests for immutable Modelo 303 filing evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_snapshot,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision_m303_evidence import M303Exonerado390FilingEvidence
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence, M303FilingInstanceEvidence
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...calculations.tests.filing_evidence import regimen_simplificado_filing_evidence
from ..action_errors import M303FilingEvidenceError
from ..m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e3030000-0000-4000-8000-000000000058"
_CLOCK = datetime(2026, 4, 1, tzinfo=UTC)


def _general_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=m303_regime_composition_simplified_scope("general", authority=PublishedGovernedFactSource()),
    )


def _work_unit(period: Period) -> WorkUnit:
    registry_snapshot = published_snapshot(
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


def _non_m303_work_unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    registry_snapshot = published_snapshot("130", filing_year=2026, period="1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=Modelo("130").value,
            filing_year=period.filing_year,
            period=period,
            revision_id=registry_snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=Modelo("130").value,
        filing_year=period.filing_year,
        period=period,
        revision_id=registry_snapshot.revision.id,
        name="130-2026-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _evidence(period: Period, *, operation: PinnedAuthorityOperation) -> FilingInstanceEvidence:
    scope = _general_scope()
    registry_snapshot = published_snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.code,
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference="test:validation:exonerado-390"),
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=resolve_m303_regimen_simplificado_snapshot(
                    registry_snapshot=registry_snapshot,
                    scope_decision=scope,
                ),
                dana_eligibility=None,
                operation=operation,
            ),
        ),
    )


def test_non_m303_evidence_is_rejected_but_absent_evidence_is_accepted(*, operation: PinnedAuthorityOperation) -> None:
    work_unit = _non_m303_work_unit()
    registry_snapshot = published_snapshot("130", filing_year=2026, period="1T")

    assert (
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=work_unit,
            registry_snapshot=registry_snapshot,
            evidence=None,
            casilla_values={},
            observations=(),
            operation=operation,
        )
        is None
    )

    with pytest.raises(M303FilingEvidenceError) as raised_unsupported_modelo:
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=work_unit,
            registry_snapshot=registry_snapshot,
            evidence=_evidence(Period.from_year_and_code(2026, "1T"), operation=operation),
            casilla_values={},
            observations=(),
            operation=operation,
        )

    failure = raised_unsupported_modelo.value.precondition_failure
    assert failure is not None, "the refusal must carry its declared precondition failure"
    assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.unsupported_modelo"


def test_m303_evidence_is_required_before_profile_lookup(*, operation: PinnedAuthorityOperation) -> None:
    period = Period.from_year_and_code(2026, "1T")

    with pytest.raises(M303FilingEvidenceError) as raised_missing:
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=_work_unit(period),
            registry_snapshot=published_snapshot("303", filing_year=2026, period="1T"),
            evidence=None,
            casilla_values={},
            observations=(),
            operation=operation,
        )

    failure = raised_missing.value.precondition_failure
    assert failure is not None, "the refusal must carry its declared precondition failure"
    assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.missing"


def test_evidence_for_another_work_period_refuses_before_persistence(*, operation: PinnedAuthorityOperation) -> None:
    work_period = Period.from_year_and_code(2026, "1T")
    evidence_period = Period.from_year_and_code(2026, "2T")

    with pytest.raises(M303FilingEvidenceError) as raised_period_mismatch:
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=_work_unit(work_period),
            registry_snapshot=published_snapshot("303", filing_year=2026, period="1T"),
            evidence=_evidence(evidence_period, operation=operation),
            casilla_values={},
            observations=(),
            operation=operation,
        )

    failure = raised_period_mismatch.value.precondition_failure
    assert failure is not None, "the refusal must carry its declared precondition failure"
    assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.period_mismatch"
