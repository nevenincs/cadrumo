from __future__ import annotations

import hashlib
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.modelo.calculation_helpers import external_filing_observations
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.entrypoints.justificante_composition import build_justificante_capture_service
from cadrumo.tests.inventory import FIXTURES_DIR

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
MODELO_111_RECEIPT_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_111_2026Q1.pdf"
"""The Modelo 111 receipt that prints its total a ingresar.

Modelo 111 is the bundled family whose snapshot declares a reconciliation total
casilla, so this is the receipt a filing-chain confirmation can reconcile
against. The quarterly renders under ``111/`` carry the epígrafe table and no
receipt total.
"""

_M111_EXPEDIENTE_ID = "11120260417EFGH5678IJKL9012"
"""The register expediente the 111 capture is observed under."""
_YEAR = filing_year_envelope().horizon
_EXP_130_1T = "13020260410ABCD1234EFGH5678"
_WORK_UNIT_TIMESTAMP = datetime(_YEAR, 4, 18, 8, 0, tzinfo=UTC)


@contextmanager
def isolated_justificante_backend(tmp_path: Path) -> Generator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id="11111111-1111-4111-8111-111111111111",
            overrides={"identity.tax_id": "00000000T"},
        )
        yield


def active_bucket_id() -> str:
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    bucket_id = active_bucket_id()
    filing_period = Period.from_year_and_code(filing_year, period)
    revision_id = str(
        published_authority_operation().snapshot(modelo, filing_year=filing_year, period=period).revision.id
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def persist_capture(
    *,
    pdf_bytes: bytes,
    modelo: str,
    filing_year: int,
    period: str,
    expediente_id: str = _EXP_130_1T,
    csv: str = "ABCD1234EFGH5678",
):
    """Persist one live capture of a receipt under the active profile.

    ``csv`` is the csv the cotejo redirect resolved to, and the capture gate
    compares it against the one printed in ``pdf_bytes``; a caller supplying a
    receipt from another filing must pass that receipt's own csv.
    """
    bucket_id = active_bucket_id()
    return build_justificante_capture_service(bucket_id).capture(
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        expediente_id=expediente_id,
        csv=csv,
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=datetime(_YEAR, 4, 18, 10, 0, tzinfo=UTC),
    )


def seed_unverified_filing(
    *,
    work_unit_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    member_nif: str | None = None,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
    casilla_values: Mapping[str, Decimal] | None = None,
) -> ModeloRecord:
    """Persist a coherent local filing chain with optional official confirmation.

    ``casilla_values`` are the computed values the presented revision carries.
    A receipt reconciliation compares the receipt's printed total against the
    revision's own result casilla, so a caller that wants a confirmable chain
    supplies the values its receipt was computed from; the default empty
    revision reconciles nothing.
    """
    bucket_id = active_bucket_id()
    filing_period = Period.from_year_and_code(filing_year, period)
    snapshot = published_authority_operation().snapshot(modelo, filing_year=filing_year, period=period)
    resolved_casilla_values = {
        validated_casilla_id(casilla_id): value for casilla_id, value in (casilla_values or {}).items()
    }
    # A revision carrying values must carry their typed observations, so the
    # legal and source refs of each value survive the domain boundary. The
    # snapshot is the provenance owner for a value with no in-process formula
    # entry, which is the same route an imported AEAT baseline takes.
    observations = external_filing_observations(casilla_values=resolved_casilla_values, snapshot=snapshot)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=resolved_casilla_values,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    filed_at = datetime(_YEAR, 4, 18, 9, 0, tzinfo=UTC)
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=resolved_casilla_values,
        observations=observations,
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=filed_at,
        verified_at=filed_at,
        verified_by="operator",
        filed_at=filed_at,
        filed_by="operator",
    )
    calculations = CalculationRevisionCatalogueRepository()
    calculations.save(upsert_calculation_revision(calculations.load(), revision))
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="operator",
        member_nif=member_nif,
    )
    work_units = WorkUnitCatalogueRepository()
    catalogue = work_units.load()
    work_unit = catalogue.get(work_unit_id)
    assert work_unit is not None
    work_units.save(
        upsert_work_unit(
            catalogue,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "filed_calculation_revision_id": revision_id,
                    "current_filing_record_id": filing_id,
                    "updated_at": filed_at,
                }
            ),
        )
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        member_nif=member_nif,
        filed_at=filed_at,
        filed_by="operator",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.CONFIRMADA if aeat_accepted else AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )
    repo = ModeloRecordCatalogueRepository()
    repo.save(upsert_filing_record(repo.load(), filing))
    return filing
