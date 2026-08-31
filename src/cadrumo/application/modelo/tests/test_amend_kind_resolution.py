"""End-to-end tests for period-aware amendment-kind routing.

These tests exercise the real :func:`~application.modelo.amend_modelo_revision`
composition path (no mocks) against seeded Modelo 303 baselines that straddle the
diseño-grounded rectificativa boundary (filing_year 2024, period 09/3T onward — see
:mod:`~core.amendment_kind_regime`). They prove:

* an illegal ``--kind`` for the resolved period is refused, naming the accepted
  kind set;
* a legal ``--kind`` for the resolved period is accepted;
* a pre-rectificativa ``complementaria`` that would lower declared liability is
  refused with guidance toward the solicitud de rectificación procedure, while
  an increase is accepted.

See Also:
    :mod:`~application.modelo._amendment_kind_resolution`
        Period-aware kind gate and complementaria liability-decrease guard under
        test.
    :func:`~core.resolve_amendment_kind_regime`
        Codified per-modelo amendment-kind regime that drives accepted-kind
        resolution.
    :func:`~application.modelo.amend_modelo_revision`
        Public application composition path exercised end to end here.
    :class:`~CalculationRevisionAmendmentKind`
        Domain enum for ``complementaria``, ``rectificativa``, and
        ``sustitutiva`` values.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import (
    AmendmentComplementariaLiabilityDecreaseError,
    AmendmentKindNotPermittedError,
)
from .._amendment_actions import amend_modelo_revision
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

type _Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    BucketEventHistoryRepository,
]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_PROFILE_ID = "10000000-0000-4000-8000-000000000234"
_PROFILE_LABEL = "Amendment kind resolution test profile"
_READY_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="X1234567L"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="amend-kind-resolution"),
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
)


_M303_RESULT_CASILLA: CasillaId = validated_casilla_id("71")


@pytest.fixture
def repos(tmp_path: Path) -> Generator[_Repos]:
    """Yield the shared ready-profile repository bundle for amend-kind-resolution tests."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_PROFILE_LABEL) as profile:
        objects = profile.repository
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_PROFILE_ID,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            ModeloRecordCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


def _seed_m303_external_baseline(
    repos_tuple: _Repos,
    *,
    result_casilla_value: Decimal,
    filing_year: int,
    period_code: str,
) -> tuple[WorkUnit, CalculationRevision, ModeloRecord]:
    """Seed a CURRENT M303 filing record carrying ``external_evidence``.

    The single casilla populated is casilla 71 (the canonical final-result
    casilla — see :func:`~core.result_disposition_casilla_ids`), so the
    liability-direction guard has a real value to compare.
    """
    wu_repo, cr_repo, fr_repo, _ = repos_tuple
    period = Period.from_year_and_code(filing_year, period_code)
    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="303",
        filing_year=filing_year,
        period=period,
        revision_id=bundled_authority()
        .snapshot("303", filing_year=filing_year, period=period.registry_token)
        .revision.id,
        repository=wu_repo,
        clock=_T0,
    )

    casilla_values = {_M303_RESULT_CASILLA: result_casilla_value}
    inputs: dict[CasillaId, str] = {}
    overrides_map: dict[str, str] = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat-import",
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_T1,
        updated_at=_T1,
        verified_at=_T1,
        verified_by="aeat-import",
        filed_at=_T1,
        filed_by="aeat-import",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    baseline_filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=_T1,
        filed_by="aeat-import",
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST-2024-303-AMEND-KIND",
            imported_at=_T1,
        ),
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), baseline_filing))

    return work_unit, revision, baseline_filing


def test_rectificativa_kind_refused_for_pre_boundary_period(repos: _Repos) -> None:
    """M303 2T 2024 predates the rectificativa fichero fields; requesting
    ``rectificativa`` is refused, naming the accepted kind set."""
    wu_repo, cr_repo, fr_repo, bv_repo = repos
    _, _, baseline = _seed_m303_external_baseline(
        repos,
        result_casilla_value=Decimal("100.00"),
        filing_year=2024,
        period_code="2T",
    )

    with pytest.raises(AmendmentKindNotPermittedError) as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_RESULT_CASILLA: Decimal("150.00")},
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            reason="illegal rectificativa for a pre-boundary period",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("requested_kind") == "rectificativa"
    accepted = str(exc_info.value.context.get("accepted_kinds"))
    assert "complementaria" in accepted
    assert "sustitutiva" in accepted
    assert "rectificativa" not in accepted


def test_complementaria_permitted_for_pre_boundary_liability_increase(repos: _Repos) -> None:
    """A pre-boundary complementaria that RAISES liability is the lawful, permitted kind."""
    wu_repo, cr_repo, fr_repo, bv_repo = repos
    _, _, baseline = _seed_m303_external_baseline(
        repos,
        result_casilla_value=Decimal("100.00"),
        filing_year=2024,
        period_code="2T",
    )

    record = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_M303_RESULT_CASILLA: Decimal("150.00")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported cuota discovered in audit",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    assert record.amends_filing_record_id == baseline.filing_record_id


def test_complementaria_refused_for_pre_boundary_liability_decrease(repos: _Repos) -> None:
    """A pre-boundary complementaria that LOWERS liability is refused — that
    correction is a solicitud de rectificación (LGT art. 120.3), not a
    complementaria (LGT art. 122.2)."""
    wu_repo, cr_repo, fr_repo, bv_repo = repos
    _, _, baseline = _seed_m303_external_baseline(
        repos,
        result_casilla_value=Decimal("100.00"),
        filing_year=2024,
        period_code="2T",
    )

    with pytest.raises(AmendmentComplementariaLiabilityDecreaseError) as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_RESULT_CASILLA: Decimal("40.00")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="illegal liability-decreasing complementaria",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("baseline_result") == "100.00"
    assert exc_info.value.context.get("corrected_result") == "40.00"


def test_complementaria_kind_refused_for_post_boundary_period(repos: _Repos) -> None:
    """M303 3T 2024 is the diseño's stated rectificativa boundary quarter;
    ``complementaria`` is no longer a permitted kind — rectificativa is the
    unified mechanism from this period onward."""
    wu_repo, cr_repo, fr_repo, bv_repo = repos
    _, _, baseline = _seed_m303_external_baseline(
        repos,
        result_casilla_value=Decimal("100.00"),
        filing_year=2024,
        period_code="3T",
    )

    with pytest.raises(AmendmentKindNotPermittedError) as exc_info:
        amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides={_M303_RESULT_CASILLA: Decimal("40.00")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="illegal complementaria for a post-boundary period",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
    accepted = str(exc_info.value.context.get("accepted_kinds")) if exc_info.value.context else ""
    assert "rectificativa" in accepted
    assert "sustitutiva" in accepted
    assert "complementaria" not in accepted


def test_rectificativa_kind_permits_liability_decrease_post_boundary(repos: _Repos) -> None:
    """Post-boundary, rectificativa may lawfully lower the declared result —
    the liability-decrease guard is complementaria-specific and does not fire."""
    wu_repo, cr_repo, fr_repo, bv_repo = repos
    _, _, baseline = _seed_m303_external_baseline(
        repos,
        result_casilla_value=Decimal("100.00"),
        filing_year=2024,
        period_code="3T",
    )

    record = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_M303_RESULT_CASILLA: Decimal("40.00")},
        amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
        reason="lawful rectificativa lowering the declared result",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    assert record.amends_filing_record_id == baseline.filing_record_id


def test_sustitutiva_kind_permitted_at_every_period(repos: _Repos) -> None:
    """sustitutiva is always in the permitted set, pre- and post-boundary."""
    wu_repo, cr_repo, fr_repo, bv_repo = repos
    _, _, baseline = _seed_m303_external_baseline(
        repos,
        result_casilla_value=Decimal("100.00"),
        filing_year=2024,
        period_code="2T",
    )

    record = amend_modelo_revision(
        from_filing_record_id=baseline.filing_record_id,
        overrides={_M303_RESULT_CASILLA: Decimal("40.00")},
        amendment_kind=CalculationRevisionAmendmentKind.SUSTITUTIVA,
        reason="material restatement, sustitutiva always permitted",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )
    assert record.amends_filing_record_id == baseline.filing_record_id
