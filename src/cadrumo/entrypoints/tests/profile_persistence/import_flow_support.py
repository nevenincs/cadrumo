"""Shared real-repository setup for external Modelo filing import tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from cadrumo.adapters.persistence.profile.tests.ready_profile_support import (
    WITHHOLDING_PAYER_PERSONA,
    seed_persona_profile,
    seed_ready_profile,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculation_revision_queries import get_calculation_revision
from cadrumo.application.modelo.external_import_actions import import_external_filing_evidence
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision

_YEAR = filing_year_envelope().horizon


Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

T0 = datetime(_YEAR, 1, 15, 12, 0, 0, tzinfo=UTC)
T1 = datetime(_YEAR, 1, 15, 13, 0, 0, tzinfo=UTC)
T2 = datetime(_YEAR, 1, 15, 14, 0, 0, tzinfo=UTC)
T3 = datetime(_YEAR, 4, 15, 15, 0, 0, tzinfo=UTC)
T4 = datetime(_YEAR, 4, 16, 12, 0, 0, tzinfo=UTC)
TAX_ID = "X0001500M"
PROFILE_ID = "13000000-0000-4000-8000-000000000001"


IMPORT_INCOME_CASILLA: CasillaId = validated_casilla_id("01")
IMPORT_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02")
#: What an imported Modelo 130 never records and a correction of box 01 reaches: the estimación directa modality
#: (the RIRPF art. 30.2.4a provision on box 02), the expenses of the earlier quarters that box 02 accumulates, the
#: earlier year's net income and the agrarian figures that boxes 03 to 19 read; the filer has no agrarian activity.
IMPORT_UNRECORDED_BINDINGS: Mapping[str, str] = {
    "modelo-130-estimacion-directa-modalidad": "directa_normal",
    "modelo-130-actividad-economica-gastos-cumulative": "300",
    "irpf.previous_year_economic_activity_net_income": "0",
    "modelo-130-retenciones-agrarias": "0",
    "modelo-130-volumen-ingresos-agrario": "0",
}
UNKNOWN_IMPORT_CASILLA: CasillaId = validated_casilla_id("9999")
M303_PRINTED_RESULT_TOKEN: CasillaId = validated_casilla_id("69")
M111_AMENDMENT_CASILLA: CasillaId = validated_casilla_id("01")
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


def _catalogue_repositories(tmp_path: Path, seed: Callable[[], None]) -> Iterator[Repos]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=PROFILE_ID) as profile:
        objects = profile.repository
        seed()
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[Repos]:
    """Yield the five catalogue repositories over an encrypted SQLite db."""

    yield from _catalogue_repositories(tmp_path, lambda: seed_ready_profile(bucket_id=PROFILE_ID, at=T0))


@pytest.fixture
def withholding_payer_repos(tmp_path: Path) -> Iterator[Repos]:
    """Yield the repositories over a profile whose taxpayer pays withheld income, so Modelo 111 applies."""

    yield from _catalogue_repositories(
        tmp_path, lambda: seed_persona_profile(WITHHOLDING_PAYER_PERSONA, bucket_id=PROFILE_ID, at=T0)
    )


def seed_work_unit(
    wu_repo: WorkUnitCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    *,
    operation: PinnedAuthorityOperation,
):
    """Create the Modelo 130 work unit used by the import-flow scenarios."""

    return create_work_unit(
        bucket_id=PROFILE_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=open_ended_revision("130").id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bucket_event_repository),
        clock=T0,
        operation=operation,
    )


@dataclass(frozen=True, slots=True)
class _ImportOutcome:
    """Bundle returned by drive_import_persists_filing."""

    work_unit: WorkUnit
    filing: ModeloRecord


def persist_matching_justificante(
    reference_id: str,
    work_unit: WorkUnit,
    *,
    captured_at: datetime,
    period: str | None = None,
    tax_id: str = TAX_ID,
) -> None:
    persist_justificante_metadata(
        reference_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=period or work_unit.period.registry_token,
        captured_at=captured_at,
        tax_id=tax_id,
    )


def import_external_filing(
    repos: Repos,
    work_unit: WorkUnit,
    *,
    casilla_values: Mapping[Any, Decimal] | None = None,
    evidence_kind: ExternalEvidenceKind = ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
    evidence_reference_id: str,
    expected_tax_id: str | None = None,
    clock: datetime = T1,
    actor: str = "aeat-import",
    declared_kind: FilingDeclarationKind | None = None,
) -> ModeloRecord:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    resolved_casilla_values = {IMPORT_INCOME_CASILLA: Decimal("1500")} if casilla_values is None else casilla_values
    return import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=resolved_casilla_values,
        evidence_kind=evidence_kind,
        evidence_reference_id=evidence_reference_id,
        declared_kind=declared_kind,
        actor=actor,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        observation_repository=CalculationObservationRepository(),
        expected_tax_id=expected_tax_id,
        clock=clock,
    ).filing_record


def drive_import_persists_filing(repos: Repos, *, operation: PinnedAuthorityOperation) -> _ImportOutcome:
    """Run the seed-work-unit and import-evidence scenario."""
    wu_repo, _, _, _, _ = repos
    work_unit = seed_work_unit(wu_repo, repos[-1], operation=operation)
    persist_matching_justificante(
        "JUST2026303Q1OPERATOR1",
        work_unit,
        captured_at=T1,
    )
    filing = import_external_filing(
        repos,
        work_unit,
        casilla_values={IMPORT_INCOME_CASILLA: Decimal("1500"), IMPORT_EXPENSE_CASILLA: Decimal("300")},
        evidence_reference_id="JUST2026303Q1OPERATOR1",
        expected_tax_id=TAX_ID,
    )
    return _ImportOutcome(work_unit=work_unit, filing=filing)


def seed_local_filing_record(
    *,
    work_unit: WorkUnit,
    revision_id: str,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    filed_at: datetime,
    filed_by: str,
) -> ModeloRecord:
    with bundled_indexed_authority().operation() as operation:
        calculation_ports = replace(
            build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            calculation_repository=calculation_repository,
        )
        revision = get_calculation_revision(revision_id, ports=calculation_ports)
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
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    filing_repository.save(upsert_filing_record(filing_repository.load(), filing))
    return filing
