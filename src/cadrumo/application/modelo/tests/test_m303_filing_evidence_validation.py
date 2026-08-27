"""Atomic validation of immutable Modelo 303 filing evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import M303RegimenSimplificadoFact, Modelo, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.deadlines import M303RegimeComposition
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
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
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoCalculationResult,
    WorkUnit,
    derive_work_unit_id,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import M303FilingEvidenceError
from .._m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e3030000-0000-4000-8000-000000000058"
_CLOCK = datetime(2026, 4, 1, tzinfo=UTC)


def _exonerado_activity_rows(
    reference: FilingEvidenceReference,
) -> tuple[M303Exonerado390ActivityRowEvidence, ...]:
    return (
        M303Exonerado390ActivityRowEvidence(
            slot=1,
            codigo_actividad="A01",
            epigrafe_iae="4191",
            evidence_reference=reference,
        ),
    )


def _general_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def _work_unit(period: Period) -> WorkUnit:
    registry_snapshot = bundled_authority().snapshot(
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
    registry_snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M130.value,
            filing_year=period.filing_year,
            period=period,
            revision_id=registry_snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M130.value,
        filing_year=period.filing_year,
        period=period,
        revision_id=registry_snapshot.revision.id,
        name="130-2026-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _evidence(period: Period) -> FilingInstanceEvidence:
    scope = _general_scope()
    registry_snapshot = bundled_authority().snapshot(
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
                dana_2024_eligibility=None,
            ),
        ),
    )


def _store_profile(
    *,
    composition: M303RegimeComposition = M303RegimeComposition.GENERAL,
    iae_epigraph: str | None = None,
) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value=composition.value),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
                *(
                    (UserProfileFact(path="activities.iae_epigraph", value=iae_epigraph),)
                    if iae_epigraph is not None
                    else ()
                ),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _simplified_evidence(period: Period) -> FilingInstanceEvidence:
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    registry_snapshot = bundled_authority().snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.code,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    )
    annual = regimen_snapshot.orden.activities[0]
    assert annual.kind == "no_agricola"
    assert annual.iae_epigrafe is not None
    reference = FilingEvidenceReference(reference="test:validation:simplified-regime")
    rows = RegimenSimplificadoFilingRows(
        ejercicio=period.filing_year,
        activities=(
            ActividadNoAgricolaSimplificado(
                orden_id=annual.orden_id,
                ejercicio=period.filing_year,
                activity_id=annual.orden_id,
                iae_epigrafe=annual.iae_epigrafe,
                auxiliary_activity_indicator=annual.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1") if index == 0 else Decimal("0"),
                        evidence_reference=reference,
                    )
                    for index, module in enumerate(annual.modulos)
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for identity in annual.applicable_fact_identities
                ),
                evidence_reference=reference,
            ),
        ),
    )
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=reference,
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=rows,
                regimen_snapshot=regimen_snapshot,
                dana_2024_eligibility=None,
            ),
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
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")

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


def test_non_m303_evidence_is_rejected_but_absent_evidence_is_accepted() -> None:
    work_unit = _non_m303_work_unit()
    registry_snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")

    assert (
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=work_unit,
            registry_snapshot=registry_snapshot,
            evidence=None,
            casilla_values={},
            observations=(),
        )
        is None
    )

    with pytest.raises(M303FilingEvidenceError) as raised_unsupported_modelo:
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=work_unit,
            registry_snapshot=registry_snapshot,
            evidence=_evidence(Period.from_year_and_code(2026, "1T")),
            casilla_values={},
            observations=(),
        )

    failure = raised_unsupported_modelo.value.precondition_failure
    assert failure is not None, "the refusal must carry its declared precondition failure"
    assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.unsupported_modelo"


def test_m303_evidence_is_required_before_profile_lookup() -> None:
    period = Period.from_year_and_code(2026, "1T")

    with pytest.raises(M303FilingEvidenceError) as raised_missing:
        validate_m303_filing_instance_evidence_for_revision(
            work_unit=_work_unit(period),
            registry_snapshot=bundled_authority().snapshot("303", filing_year=2026, period="1T"),
            evidence=None,
            casilla_values={},
            observations=(),
        )

    failure = raised_missing.value.precondition_failure
    assert failure is not None, "the refusal must carry its declared precondition failure"
    assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.missing"


@pytest.mark.parametrize(
    "composition",
    (M303RegimeComposition.SIMPLIFIED, M303RegimeComposition.MIXED),
)
def test_evidence_scope_disagreeing_with_active_censo_refuses(
    tmp_path: Path,
    composition: M303RegimeComposition,
) -> None:
    period = Period.from_year_and_code(2026, "1T")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile(composition=composition)
        with pytest.raises(M303FilingEvidenceError) as raised_regimen_scope_profile_divergence:
            validate_m303_filing_instance_evidence_for_revision(
                work_unit=_work_unit(period),
                registry_snapshot=bundled_authority().snapshot("303", filing_year=2026, period="1T"),
                evidence=_evidence(period),
                casilla_values={},
                observations=(),
            )

        failure = raised_regimen_scope_profile_divergence.value.precondition_failure
        assert failure is not None, "the refusal must carry its declared precondition failure"
        assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
        assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.regimen_scope_profile_divergence"


def test_evidence_for_another_work_period_refuses_before_persistence(tmp_path: Path) -> None:
    work_period = Period.from_year_and_code(2026, "1T")
    evidence_period = Period.from_year_and_code(2026, "2T")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile()
        with pytest.raises(M303FilingEvidenceError) as raised_period_mismatch:
            validate_m303_filing_instance_evidence_for_revision(
                work_unit=_work_unit(work_period),
                registry_snapshot=bundled_authority().snapshot("303", filing_year=2026, period="1T"),
                evidence=_evidence(evidence_period),
                casilla_values={},
                observations=(),
            )

        failure = raised_period_mismatch.value.precondition_failure
        assert failure is not None, "the refusal must carry its declared precondition failure"
        assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
        assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.period_mismatch"


def test_structurally_valid_noncanonical_simplified_result_refuses_before_persistence(tmp_path: Path) -> None:
    """The persisted result must be the calculator replay, not merely well-formed evidence."""
    period = Period.from_year_and_code(2026, "1T")
    canonical_evidence = _simplified_evidence(period)
    regimen = canonical_evidence.m303.regimen_simplificado
    canonical_result = regimen.calculation_result
    canonical_activity = canonical_result.activities[0]
    divergent_activity = M303RegimenSimplificadoActivityCalculationResult.model_validate(
        {
            **canonical_activity.model_dump(mode="python"),
            "source_refs": (*canonical_activity.source_refs, regimen.regimen_snapshot.record_design.id),
        },
    )
    divergent_result_payload = canonical_result.model_dump(mode="python", exclude={"digest"})
    divergent_result_payload["period"] = canonical_result.period
    divergent_result_payload["activities"] = (divergent_activity,)
    divergent_result = M303RegimenSimplificadoCalculationResult.calculated(**divergent_result_payload)
    divergent_regimen = regimen.model_copy(update={"calculation_result": divergent_result})
    evidence = canonical_evidence.model_copy(
        update={
            "m303": canonical_evidence.m303.model_copy(
                update={"regimen_simplificado": divergent_regimen},
            ),
        },
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        activity = regimen.rows.activities[0]
        assert isinstance(activity, ActividadNoAgricolaSimplificado)
        _store_profile(
            composition=M303RegimeComposition.SIMPLIFIED,
            iae_epigraph=activity.iae_epigrafe,
        )
        with pytest.raises(M303FilingEvidenceError) as raised_divergent_result:
            validate_m303_filing_instance_evidence_for_revision(
                work_unit=_work_unit(period),
                registry_snapshot=bundled_authority().snapshot("303", filing_year=2026, period="1T"),
                evidence=evidence,
                casilla_values={},
                observations=(),
            )

    failure = raised_divergent_result.value.precondition_failure
    assert failure is not None, "the replay refusal must carry its declared precondition failure"
    assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.simplified_calculation_result_divergence"


def test_final_period_exonerado_evidence_covers_every_a28_endpoint_and_observation(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "4T")
    work_unit = _work_unit(period)
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="4T")
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
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="4T")
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
                    activity_rows=_exonerado_activity_rows(reference),
                    operaciones_terceros_declarables=False,
                    operaciones_terceros_reference=reference,
                ),
            },
        ),
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile()
        with pytest.raises(M303FilingEvidenceError) as raised_exonerado_390_endpoint_coverage_incomplete:
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

        failure = raised_exonerado_390_endpoint_coverage_incomplete.value.precondition_failure
        assert failure is not None, "the refusal must carry its declared precondition failure"
        assert failure.verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"
        assert (
            failure.scenario_id
            == "modelo.work.calculate.m303_filing_evidence.exonerado_390_endpoint_coverage_incomplete"
        )
