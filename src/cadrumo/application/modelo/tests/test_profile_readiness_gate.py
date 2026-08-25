"""Application-level profile readiness gate coverage for modelo services."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Modelo, NoRecoveryOutcome, Period
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    FilingInstanceEvidence,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record, seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionRepository
from ...user_profile.projections import record_to_path_values
from .._action_errors import (
    ModeloProfileReadinessError,
    WorkUnitMutationRefusedError,
)
from .._calculation_actions import (
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    mark_revision_verificado_completo,
)
from .._profile_readiness_gate import (
    _profile_activity_start_date,
    modelo_applicability_refusal,
    pre_activity_period_refusal,
)
from .._work_lifecycle import create_work_unit
from ..work_addressing import ensure_modelo_work_unit_for_active_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
_M100_REVISION = "2025"
_M130_REVISION = "2019-y-siguientes"
_M200_REVISION = "2024-y-siguientes"
_M303_2025_REVISION = "2025"
_M303_2026_REVISION = "2026-y-siguientes"
_OPERATOR_PROFILE_ID = "30300000-0000-4000-8000-000000000001"
_NONRESIDENT_PROFILE_ID = "20000000-0000-4000-8000-000000000002"


def _store_incomplete_profile(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_profile_with_no_facts_whatsoever(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_profile_without_activity(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Ready"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2025, 1, 1)),
            ),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_ready_profile(
    bucket_id: str,
    *,
    activity_start_date: date,
    setup_state: ProfileSetupState = ProfileSetupState.COMPLETE,
) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=setup_state,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Ready"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="design"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
            ),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_nonresident_legal_entity_profile(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value="B66012345"),
                UserProfileFact(path="identity.legal_name", value="NordHaus GmbH"),
                UserProfileFact(path="activities.description", value="Spanish-source services"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                UserProfileFact(path="taxpayer_type.fiscal_residency", value="non_resident_irnr"),
                UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="DE"),
            ),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_nonresident_natural_person_profile(bucket_id: str) -> None:
    """Store a declared IRNR non-resident natural-person profile.

    This profile represents a non-resident who
    is a NON_RESIDENT_IRNR contribuyente, not an IRPF resident, and who
    must file Modelo 210 (IRNR) rather than Modelo 100 (the resident IRPF
    Renta).
    """
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X1234567L"),
                UserProfileFact(path="identity.name", value="Olivia"),
                UserProfileFact(path="identity.surnames", value="Whitfield"),
                UserProfileFact(path="activities.description", value="UK-source pension"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="taxpayer_type.fiscal_residency", value="non_resident_irnr"),
                UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="GB"),
                UserProfileFact(path="taxpayer_type.representante_fiscal_nif", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.representante_fiscal_nombre", value="Gestoria Madrid SL"),
            ),
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


def _store_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    modelo: Modelo = Modelo.M303,
    filing_year: int = 2025,
    period_code: str = "1T",
    revision_id: str = _M303_2025_REVISION,
) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    modelo_code = modelo.value
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo_code,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo_code),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo_code}-{filing_year}-{period.registry_token}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit


def _store_draft_revision(
    repository: CalculationRevisionCatalogueRepository,
    *,
    work_unit: WorkUnit,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
) -> str:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision_id


def test_create_work_unit_service_refuses_incomplete_profile(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID):
        _store_incomplete_profile(_OPERATOR_PROFILE_ID)

        with pytest.raises(ModeloProfileReadinessError):
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M303.value,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision_id=_M303_2025_REVISION,
                clock=_NOW,
            )


def test_create_work_unit_service_refuses_profile_missing_activity(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_profile_without_activity(_OPERATOR_PROFILE_ID)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M130.value,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision_id=_M130_REVISION,
                repository=repository,
                clock=_NOW,
            )

        from ....domain.user_profile.labels import profile_field_label
        from ....domain.user_profile.loader import load_user_profile_schema

        expected_label = profile_field_label(
            "activities",
            load_user_profile_schema().field("activities.description"),
        )
        assert excinfo.value.context == {
            "modelo": Modelo.M130.value,
            "filing_year": 2025,
            "period": "1T",
            "missing": expected_label,
        }
        assert len(repository.load()) == 0


def test_create_work_unit_service_refuses_profile_declaring_no_facts_whatsoever(tmp_path: Path) -> None:
    """A profile with zero declared facts is never reported ready, for any modelo.

    A ``UserProfileRecord`` declaring nothing must not let ``ready`` (at the
    ``ProfilePreflightService`` layer, where the per-operation axis can be
    empty for a given modelo) be misread as "nothing to check". At the
    work-creation gate, ``_FILING_BASELINE_PROFILE_PATHS`` still catches
    this: ``identity.tax_id`` is a universal baseline requirement
    independent of the per-operation axis.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_profile_with_no_facts_whatsoever(_OPERATOR_PROFILE_ID)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError):
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M130.value,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision_id=_M130_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert len(repository.load()) == 0


def test_create_work_unit_service_refuses_period_year_mismatch_with_typed_error(tmp_path: Path) -> None:
    """A mismatched Period/year pair refuses through the modelo error hierarchy."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(WorkUnitMutationRefusedError) as excinfo:
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M303.value,
                filing_year=2025,
                period=Period.from_year_and_code(2026, "1T"),
                revision_id=_M303_2025_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert excinfo.value.translated_message == "application.modelo.errors.work_unit_filing_year_period_mismatch"
        assert excinfo.value.context == {
            "modelo": Modelo.M303.value,
            "filing_year": 2025,
            "period_year": 2026,
            "period": "1T",
            "revision_id": _M303_2025_REVISION,
            "filing_year_matches_period": False,
        }
        failure = excinfo.value.precondition_failure
        assert failure is not None
        assert failure.identity == (
            "modelo.work.create",
            "modelo.work.create.period.filing_year.matches",
            "modelo.work.create.period.filing_year.mismatch",
        )
        assert failure.verdict.action is None
        assert failure.verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
        assert len(repository.load()) == 0


def test_create_work_unit_service_refuses_nonresident_legal_entity_m200(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_NONRESIDENT_PROFILE_ID) as profile:
        _store_nonresident_legal_entity_profile(_NONRESIDENT_PROFILE_ID)
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id=_NONRESIDENT_PROFILE_ID,
                modelo=Modelo.M200.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "0A"),
                revision_id=_M200_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert "NON_RESIDENT_IRNR" in str(excinfo.value)
        assert "establecimiento permanente" in str(excinfo.value)
        assert excinfo.value.context == {
            "bucket_id": _NONRESIDENT_PROFILE_ID,
            "modelo": Modelo.M200.value,
            "applicability_verdict": "not_applicable",
            "legal_refs": ("ley-27-2014:art-124, trlirnr-rdleg-5-2004:art-2, trlirnr-rdleg-5-2004:art-24"),
        }
        assert len(repository.load()) == 0


def test_mark_verified_service_refuses_existing_work_unit_with_incomplete_profile(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID):
        _store_incomplete_profile(_OPERATOR_PROFILE_ID)
        work_repository = WorkUnitCatalogueRepository()
        calculation_repository = CalculationRevisionCatalogueRepository()
        work_unit = _store_work_unit(work_repository, bucket_id=_OPERATOR_PROFILE_ID)
        revision_id = _store_draft_revision(
            calculation_repository,
            work_unit=work_unit,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period,
                reference="test:profile-readiness:verification-refusal",
            ),
        )

        with pytest.raises(ModeloProfileReadinessError):
            mark_revision_verificado_completo(
                revision_id,
                actor="operator",
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )


def test_calculate_service_refuses_existing_work_unit_with_incomplete_profile(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID):
        _store_incomplete_profile(_OPERATOR_PROFILE_ID)
        repository = WorkUnitCatalogueRepository()
        work_unit = _store_work_unit(repository, bucket_id=_OPERATOR_PROFILE_ID)

        with pytest.raises(ModeloProfileReadinessError):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("100.00")},
                work_unit_repository=repository,
                clock=_NOW,
            )


def test_calculate_service_refusal_carries_grounded_legal_refs_for_missing_tax_id(tmp_path: Path) -> None:
    """The blocking gate's refusal carries real legal grounding.

    ``require_profile_ready_for_modelo_work`` (invoked here via
    ``calculate_modelo_revision`` re-checking an existing work unit) threads
    the live registry authority through both
    ``_require_profile_filing_ready`` and the full preflight report, so a
    profile missing ``identity.tax_id`` for a Modelo 100 work unit refuses
    with the field's grounded ``legal_refs`` rendered inline - not a bare
    label. ``identity.tax_id`` is grounded by a real Modelo 100 registry
    binding, so this is a genuine registry fact, not an invented expectation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID):
        _store_profile_with_no_facts_whatsoever(_OPERATOR_PROFILE_ID)
        repository = WorkUnitCatalogueRepository()
        work_unit = _store_work_unit(
            repository,
            bucket_id=_OPERATOR_PROFILE_ID,
            modelo=Modelo.M100,
            filing_year=2025,
            period_code="0A",
            revision_id=_M100_REVISION,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=repository,
                clock=_NOW,
            )

        assert excinfo.value.context is not None
        missing_text = excinfo.value.context["missing"]
        assert isinstance(missing_text, str)
        assert "orden-hac-242-2025:art-3" in missing_text or "orden-hac-277-2026:art-3" in missing_text


def test_grounding_index_lookup_stays_bounded_across_repeated_readiness_checks(tmp_path: Path) -> None:
    """``build_profile_grounding_index`` is memoised per authority.

    The blocking gate calls it on every filing-grade mutation
    (``require_profile_ready_for_modelo_work``), so an unmemoised
    registry-wide binding walk on every call would scale linearly with call
    count. This proves a large batch of calls costs close to one walk, not N
    walks: the first call pays the full registry walk, and a generous
    multiple of that cost bounds the remaining 199.
    """
    import time

    from ....core.resources import resources
    from ....domain.calculations.registry import build_profile_grounding_index

    authority = resources().modelos.authority

    first_start = time.perf_counter()
    first_index = build_profile_grounding_index(authority)
    first_duration = time.perf_counter() - first_start
    assert first_index

    repeat_start = time.perf_counter()
    for _ in range(199):
        repeated_index = build_profile_grounding_index(authority)
        assert repeated_index is first_index
    repeat_duration = time.perf_counter() - repeat_start

    # 199 cached lookups must cost a small fraction of one uncached walk, not
    # 199x it - a generous 0.5x ceiling leaves ample margin over dict-lookup
    # cost while still failing hard if memoisation regresses to a re-walk.
    assert repeat_duration < max(first_duration * 0.5, 0.05)


def test_calculate_service_refuses_existing_nonresident_legal_entity_m200(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_NONRESIDENT_PROFILE_ID) as profile:
        _store_nonresident_legal_entity_profile(_NONRESIDENT_PROFILE_ID)
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id=_NONRESIDENT_PROFILE_ID,
            modelo=Modelo.M200,
            filing_year=2026,
            period_code="0A",
            revision_id=_M200_REVISION,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )

        assert "NON_RESIDENT_IRNR" in str(excinfo.value)
        assert "establecimiento permanente" in str(excinfo.value)
        assert len(calculation_repository.load()) == 0


def test_calculate_service_refuses_existing_nonresident_natural_person_m100(tmp_path: Path) -> None:
    """A non-resident natural person is refused an M100 calculate.

    A NON_RESIDENT_IRNR contribuyente owns an existing Modelo 100 work unit
    (created while resident, or bypassed at create). The calculate service
    must re-check applicability against
    the current profile and refuse — never silently produce a resident
    IRPF Renta calculation for a non-resident. The refusal names the IRNR
    route and the Modelo 210 path, and persists no revision.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_NONRESIDENT_PROFILE_ID) as profile:
        _store_nonresident_natural_person_profile(_NONRESIDENT_PROFILE_ID)
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id=_NONRESIDENT_PROFILE_ID,
            modelo=Modelo.M100,
            filing_year=2025,
            period_code="0A",
            revision_id=_M100_REVISION,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )

        assert "NON_RESIDENT_IRNR" in str(excinfo.value)
        assert "Modelo 210" in str(excinfo.value)
        assert excinfo.value.context is not None
        assert excinfo.value.context["applicability_verdict"] == "not_applicable"
        assert len(calculation_repository.load()) == 0


def test_m100_applicability_gate_distinguishes_resident_from_nonresident_natural_person() -> None:
    """The shared readiness gate refuses M100 for a non-resident,
    yet accepts it for a resident — the distinction is the authoritative
    ``fiscal_residency`` signal, not a blanket refusal.

    The same ``modelo_applicability_refusal`` function the calculate,
    verify, file, and export paths consult: it returns a refusal naming
    the IRNR / Modelo 210 route for a NON_RESIDENT_IRNR natural person and
    returns ``None`` (applicable, no refusal) for a resident IRPF natural
    person whose only differing fact is the residency axis.
    """
    nonresident = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_NONRESIDENT_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="X1234567L"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="taxpayer_type.fiscal_residency", value="non_resident_irnr"),
            UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="FR"),
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )
    resident = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_OPERATOR_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="taxpayer_type.fiscal_residency", value="resident_irpf"),
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )

    refusal = modelo_applicability_refusal(
        record=nonresident,
        bucket_id=_NONRESIDENT_PROFILE_ID,
        modelo=Modelo.M100.value,
    )
    assert refusal is not None
    message, context = refusal
    assert "NON_RESIDENT_IRNR" in message
    assert "Modelo 210" in message
    assert context["applicability_verdict"] == "not_applicable"

    assert (
        modelo_applicability_refusal(
            record=resident,
            bucket_id=_OPERATOR_PROFILE_ID,
            modelo=Modelo.M100.value,
        )
        is None
    )


def test_create_work_unit_service_refuses_pre_activity_m303_and_persists_no_work_unit(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_ready_profile(_OPERATOR_PROFILE_ID, activity_start_date=date(2026, 5, 1))
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M303.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision_id=_M303_2026_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert "pre-activity period" in str(excinfo.value)
        assert excinfo.value.context == {
            "bucket_id": _OPERATOR_PROFILE_ID,
            "modelo": "303",
            "filing_year": 2026,
            "period": "1T",
            "activity_start_date": "2026-05-01",
            "period_end_date": "2026-03-31",
        }
        assert len(repository.load()) == 0


def test_create_work_unit_service_refuses_pre_activity_m130_and_persists_no_work_unit(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_ready_profile(_OPERATOR_PROFILE_ID, activity_start_date=date(2026, 7, 15))
        repository = WorkUnitCatalogueRepository(objects=profile.repository)

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M130.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "2T"),
                revision_id=_M130_REVISION,
                repository=repository,
                clock=_NOW,
            )

        assert "Modelo 130 2026 2T is before" in str(excinfo.value)
        assert "pre-activity period" in str(excinfo.value)
        assert excinfo.value.context == {
            "bucket_id": _OPERATOR_PROFILE_ID,
            "modelo": Modelo.M130.value,
            "filing_year": 2026,
            "period": "2T",
            "activity_start_date": "2026-07-15",
            "period_end_date": "2026-06-30",
        }
        assert len(repository.load()) == 0


def test_stale_pre_activity_m303_calculate_refuses_before_wallet_or_revision(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_ready_profile(_OPERATOR_PROFILE_ID, activity_start_date=date(2026, 5, 1))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        wallet_repository = IvaWalletDecisionRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id=_OPERATOR_PROFILE_ID,
            filing_year=2026,
            period_code="1T",
            revision_id=_M303_2026_REVISION,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                iva_compensation_decision_repository=wallet_repository,
                clock=_NOW,
            )

        assert "Modelo 303 2026 1T is before" in str(excinfo.value)
        assert len(calculation_repository.load()) == 0
        assert wallet_repository.list_decisions() == ()


def test_stale_pre_activity_m130_calculate_and_verify_refuse_before_revision_mutation(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_ready_profile(_OPERATOR_PROFILE_ID, activity_start_date=date(2026, 7, 15))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id=_OPERATOR_PROFILE_ID,
            modelo=Modelo.M130,
            filing_year=2026,
            period_code="2T",
            revision_id=_M130_REVISION,
        )
        revision_id = _store_draft_revision(calculation_repository, work_unit=work_unit)

        with pytest.raises(ModeloProfileReadinessError) as calculate_exc:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )

        assert "Modelo 130 2026 2T is before" in str(calculate_exc.value)
        assert len(calculation_repository.load()) == 1

        with pytest.raises(ModeloProfileReadinessError) as verify_exc:
            mark_revision_verificado_completo(
                revision_id,
                actor="operator",
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                clock=_NOW,
            )

        assert "Modelo 130 2026 2T is before" in str(verify_exc.value)
        persisted_revision = calculation_repository.load().get(revision_id)
        assert persisted_revision is not None
        assert persisted_revision.state is CalculationRevisionState.BORRADOR


def test_first_active_m303_period_allows_create_and_calculate(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "2T")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_ready_profile(_OPERATOR_PROFILE_ID, activity_start_date=date(2026, 5, 1))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        wallet_repository = IvaWalletDecisionRepository(objects=profile.repository)

        work_unit = create_work_unit(
            bucket_id=_OPERATOR_PROFILE_ID,
            modelo=Modelo.M303.value,
            filing_year=2026,
            period=period,
            revision_id=_M303_2026_REVISION,
            repository=work_repository,
            clock=_NOW,
        )
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator",
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            iva_compensation_decision_repository=wallet_repository,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period,
                reference="test:profile-readiness:first-active-m303",
            ),
            clock=_NOW,
        )

        assert result.revision.work_unit_id == work_unit.work_unit_id
        assert tuple(calculation_repository.load().values()) == (result.revision,)
        decisions = wallet_repository.list_decisions()
        assert len(decisions) == 1
        assert decisions[0].target_period == period


def test_visible_target_ensure_refuses_reused_pre_activity_m303_before_rename(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID) as profile:
        _store_ready_profile(_OPERATOR_PROFILE_ID, activity_start_date=date(2026, 5, 1))
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        work_unit = _store_work_unit(
            work_repository,
            bucket_id=_OPERATOR_PROFILE_ID,
            filing_year=2026,
            period_code="1T",
            revision_id=_M303_2026_REVISION,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            ensure_modelo_work_unit_for_active_target(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M303.value,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                registry_revision_id=_M303_2026_REVISION,
                name="renamed stale work",
                actor="operator",
                catalogue=work_repository.load(),
            )

        assert "pre-activity period" in str(excinfo.value)
        assert tuple(work_repository.load().values()) == (work_unit,)


def test_create_work_unit_service_refuses_a_setup_incomplete_profile(tmp_path: Path) -> None:
    """A mid-setup profile failing only the flow's cross-field rule keeps the generic wording.

    ``_store_ready_profile`` populates every schema-required fact, so the
    ``SETUP_INCOMPLETE`` status here can only reflect a cross-field failure
    (the flow's final validation), never an empty required field -
    ``missing_required_field_paths`` enumerates nothing for this record, and
    the refusal correctly falls back to the generic key rather than claiming
    "missing: nothing".
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID):
        _store_ready_profile(
            _OPERATOR_PROFILE_ID,
            activity_start_date=date(2025, 1, 1),
            setup_state=ProfileSetupState.INCOMPLETE,
        )

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            create_work_unit(
                bucket_id=_OPERATOR_PROFILE_ID,
                modelo=Modelo.M303.value,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision_id=_M303_2025_REVISION,
                clock=_NOW,
            )
        assert excinfo.value.translated_message == "application.modelo.errors.profile_readiness_setup_incomplete"


def test_calculate_service_names_missing_fields_for_a_setup_incomplete_profile(tmp_path: Path) -> None:
    """A mid-setup profile missing real required fields names them instead of refusing vaguely.

    Per the per-operation-axis-and-silent-defaults audit's open item: the
    setup-incomplete refusal used to name a lifecycle STATUS rather than a
    field gap, sending the operator back into the wizard to hunt for what
    was actually missing.

    ``create_work_unit`` cannot exercise this branch: its early registry-free
    gate (``require_existing_profile_baseline_ready_for_modelo_work``) runs
    ``ProfileValidationService`` first and already refuses with the generic
    ``profile_readiness_missing`` message for ANY missing required field,
    before the status-aware gate below ever runs - so the two gates would
    always agree on "missing", never reach the SETUP_INCOMPLETE branch with a
    gap to report. This exercises the readiness re-check on an EXISTING work
    unit instead (``calculate_modelo_revision``), whose only gate is
    ``require_profile_ready_for_work_unit`` -> the status-aware
    ``require_profile_ready_for_modelo_work`` directly.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OPERATOR_PROFILE_ID):
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_OPERATOR_PROFILE_ID,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="activities.description", value="design"),
                ),
                created_at=_NOW,
                updated_at=_NOW,
            ),
        )
        repository = WorkUnitCatalogueRepository()
        work_unit = _store_work_unit(
            repository,
            bucket_id=_OPERATOR_PROFILE_ID,
            modelo=Modelo.M303,
            filing_year=2025,
            period_code="1T",
            revision_id=_M303_2025_REVISION,
        )
        record = load_test_profile_record(_OPERATOR_PROFILE_ID)
        replace_test_profile_record(record.model_copy(update={"setup_state": ProfileSetupState.INCOMPLETE}))

        with pytest.raises(ModeloProfileReadinessError) as excinfo:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=repository,
                clock=_NOW,
            )

        assert (
            excinfo.value.translated_message == "application.modelo.errors.profile_readiness_setup_incomplete_missing"
        )
        assert excinfo.value.context is not None
        missing_text = excinfo.value.context["missing"]
        assert isinstance(missing_text, str)
        assert missing_text
        # Never a raw dotted path once a catalogue label is available.
        assert "identity." not in missing_text


def _reversed_declaration_order_record() -> UserProfileRecord:
    """A record whose later effective window is declared FIRST.

    Both facts are live at one effective-dated path, so declaration order and
    ``valid_from`` order disagree and the two readers can be told apart.
    """
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_OPERATOR_PROFILE_ID,
        facts=(
            UserProfileFact(
                path="censo.activity_start_date",
                value=date(2026, 1, 1),
                valid_from=date(2026, 1, 1),
            ),
            UserProfileFact(
                path="censo.activity_start_date",
                value=date(2020, 1, 1),
                valid_from=date(2020, 1, 1),
            ),
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_activity_start_reader_agrees_with_the_canonical_effective_projection() -> None:
    """The readiness reader resolves the same effective fact as the canonical projection.

    Two readers of one effective-dated path must not disagree about which fact
    is in force. Declaration order is not the effective order: here the later
    window is declared first, so a reverse scan returns the 2020 fact while
    ``valid_from`` ordering returns the 2026 one.
    """
    record = _reversed_declaration_order_record()

    canonical = record_to_path_values(record)["censo.activity_start_date"]
    resolved = _profile_activity_start_date(record)

    assert resolved == date(2026, 1, 1)
    assert resolved is not None
    assert resolved.isoformat() == canonical


def test_pre_activity_refusal_uses_the_effective_window_not_declaration_order() -> None:
    """A period before the effective activity start is refused, not admitted.

    The reader decides whether a target period is pre-activity, so resolving the
    wrong fact fails open: reading the superseded 2020 window would admit a 2021
    period that the effective 2026 start puts before the activity ever began.
    """
    record = _reversed_declaration_order_record()

    refusal = pre_activity_period_refusal(
        record=record,
        bucket_id=_OPERATOR_PROFILE_ID,
        modelo=Modelo.M303.value,
        filing_year=2021,
        period=Period.from_year_and_code(2021, "1T"),
    )

    assert refusal is not None
    message, context = refusal
    assert "pre-activity period" in message
    assert context["activity_start_date"] == "2026-01-01"
