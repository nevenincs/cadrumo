"""Shared real-repository setup for external Modelo filing import tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.modelos import (
    CalculationRevisionState,
    ExternalEvidenceKind,
    ModeloRecord,
    WorkUnit,
    derive_filing_record_id,
    upsert_calculation_revision,
    upsert_filing_record,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._calculation_actions import get_calculation_revision
from .._work_lifecycle import create_work_unit
from ..external_import_actions import import_external_filing_evidence
from .justificante_metadata import persist_justificante_metadata

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 15, 15, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_TAX_ID = "X1234567L"
_PROFILE_ID = "13000000-0000-4000-8000-000000000001"


_IMPORT_INCOME_CASILLA: CasillaId = validated_casilla_id("01")
_IMPORT_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02")
_UNKNOWN_IMPORT_CASILLA: CasillaId = validated_casilla_id("9999")
_M303_PRINTED_RESULT_TOKEN: CasillaId = validated_casilla_id("69")
_M111_AMENDMENT_CASILLA: CasillaId = validated_casilla_id("01")
_M111_EMPLOYMENT_WITHHELD_CASILLA: CasillaId = validated_casilla_id("03")
_M111_PROFESSIONAL_WITHHELD_CASILLA: CasillaId = validated_casilla_id("06")
_M111_PRIZE_WITHHELD_CASILLA: CasillaId = validated_casilla_id("09")
_M111_IMAGE_RIGHTS_WITHHELD_CASILLA: CasillaId = validated_casilla_id("12")
_M111_FORESTRY_WITHHELD_CASILLA: CasillaId = validated_casilla_id("15")
_M111_IMPUTED_INCOME_WITHHELD_CASILLA: CasillaId = validated_casilla_id("18")
_M111_ACTIVITY_COUNT_CASILLA: CasillaId = validated_casilla_id("21")
_M111_ACTIVITY_AMOUNT_CASILLA: CasillaId = validated_casilla_id("24")
_M111_ACTIVITY_WITHHELD_CASILLA: CasillaId = validated_casilla_id("27")
_M111_TOTAL_WITHHELD_CASILLA: CasillaId = validated_casilla_id("29")

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    # Modelo 111 refuses a defaulted colegio-concertado declaration: the fichero
    # carries the row as filer data, so it must be stated rather than assumed.
    # False is the truthful value for this natural-person filer.
    UserProfileFact(path="withholding.colegio_concertado", value=False),
)


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Yield the five catalogue repositories over an encrypted SQLite db."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(bucket_id=_PROFILE_ID)
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv


def _seed_ready_profile(*, bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _seed_work_unit(wu_repo: WorkUnitCatalogueRepository):
    """Create the Modelo 130 work unit used by the import-flow scenarios."""

    return create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )


@dataclass(frozen=True, slots=True)
class _ImportOutcome:
    """Bundle returned by _drive_import_persists_filing."""

    work_unit: WorkUnit
    filing: ModeloRecord


def _persist_matching_justificante(
    reference_id: str,
    work_unit: WorkUnit,
    *,
    captured_at: datetime,
    period: str | None = None,
    tax_id: str = _TAX_ID,
) -> None:
    persist_justificante_metadata(
        reference_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=period or work_unit.period.registry_token,
        captured_at=captured_at,
        tax_id=tax_id,
    )


def _import_external_filing(
    repos: _Repos,
    work_unit: WorkUnit,
    *,
    casilla_values: Mapping[Any, Decimal] | None = None,
    evidence_kind: ExternalEvidenceKind = ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
    evidence_reference_id: str,
    expected_tax_id: str | None = None,
    clock: datetime = _T1,
    actor: str = "aeat-import",
) -> ModeloRecord:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    resolved_casilla_values = {_IMPORT_INCOME_CASILLA: Decimal("1500")} if casilla_values is None else casilla_values
    return import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=resolved_casilla_values,
        evidence_kind=evidence_kind,
        evidence_reference_id=evidence_reference_id,
        actor=actor,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id=expected_tax_id,
        clock=clock,
    )


def _drive_import_persists_filing(repos: _Repos) -> _ImportOutcome:
    """Run the seed-work-unit and import-evidence scenario."""
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUST2026303Q1OPERATOR1",
        work_unit,
        captured_at=_T1,
    )
    filing = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500"), _IMPORT_EXPENSE_CASILLA: Decimal("300")},
        evidence_reference_id="JUST2026303Q1OPERATOR1",
        expected_tax_id=_TAX_ID,
    )
    return _ImportOutcome(work_unit=work_unit, filing=filing)


def _seed_local_filing_record(
    *,
    work_unit: WorkUnit,
    revision_id: str,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    filed_at: datetime,
    filed_by: str,
) -> ModeloRecord:
    revision = get_calculation_revision(revision_id, calculation_repository=calculation_repository)
    filed_revision = revision.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": filed_at,
            "filed_by": filed_by,
            "updated_at": filed_at,
        },
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), filed_revision))
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=filed_revision.calculation_revision_id,
        filed_by=filed_by,
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=filed_revision.calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=filed_at,
        filed_by=filed_by,
        external_evidence=None,
    )
    filing_repository.save(upsert_filing_record(filing_repository.load(), filing))
    return filing
