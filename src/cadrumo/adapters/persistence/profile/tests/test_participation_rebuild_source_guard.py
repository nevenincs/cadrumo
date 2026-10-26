"""A stale participation rebuild cannot replace a newer co-committed index."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.participation_index_rebuild import rebuild_participation_index
from cadrumo.application.modelo.participation_index_rebuild_ports import (
    ParticipationIndexRebuildPorts,
    ParticipationRebuildSourceRevisions,
)
from cadrumo.application.modelo.revision_persistence import persist_filed_revision
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.filing_record import ModeloRecordCatalogue
from cadrumo.domain.modelos.participation_index import TransactionRevisionParticipationIndex

from .filing_report_support import seed_filing_gate_report
from .test_participation_co_emission import (
    _BUCKET_ID,
    _T0,
    _TAXPAYER_NIF,
    _TX_A,
    _TX_B,
    _seed_borrador,
    _seed_verified_participation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _source_revisions(
    *,
    calculations: CalculationRevisionCatalogueRepository,
    work_units: WorkUnitCatalogueRepository,
    filings: ModeloRecordCatalogueRepository,
    operation: PinnedAuthorityOperation,
) -> ParticipationRebuildSourceRevisions:
    """Capture the exact encrypted singleton revisions a rebuild opened."""
    _, calculation_revision = calculations.load_revisioned(operation=operation)
    _, work_unit_revision = work_units.load_revisioned()
    _, filing_revision = filings.load_revisioned()
    return ParticipationRebuildSourceRevisions(
        calculation=calculation_revision,
        work_units=work_unit_revision,
        filings=filing_revision,
    )


def test_stale_rebuild_conflicts_after_canonical_filing_co_commit_and_fresh_rebuild_is_read_only(
    tmp_path: Path,
) -> None:
    """A file co-commit wins over an older rebuild snapshot and survives its prune."""
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
    ):
        calculations = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_units = WorkUnitCatalogueRepository(objects=profile.repository)
        filings = ModeloRecordCatalogueRepository(objects=profile.repository)
        participation = TransactionParticipationIndexRepository(objects=profile.repository)

        # Reuse the authority-grounded revision and genuine verification/index
        # co-write exercised by the existing participation persistence test.
        draft, work_unit = _seed_borrador(cr_repo=calculations, wu_repo=work_units)
        _seed_verified_participation(
            target=draft,
            work_unit=work_unit,
            calculation_repository=calculations,
            participation_index_repository=participation,
            actor="aeat.cli.modelo.verify",
            now=_T0.replace(hour=12),
        )
        stale_source_revisions = _source_revisions(
            calculations=calculations,
            work_units=work_units,
            filings=filings,
            operation=operation,
        )
        assert stale_source_revisions.filings == ABSENT_SECURE_OBJECT_REVISION_ID

        verified_revision = calculations.load(operation=operation).get(draft.calculation_revision_id)
        assert verified_revision is not None
        verification_reports = VerificationReportCatalogueRepository(objects=profile.repository)
        report_id = seed_filing_gate_report(verified_revision, verification_reports)
        _, filing_baseline_revision = filings.load_revisioned()
        filed = persist_filed_revision(
            target=verified_revision,
            approved_verification_report_id=report_id,
            filing_baseline_revision_id=filing_baseline_revision,
            work_unit=work_unit,
            work_units=work_units.load(),
            notes=None,
            actor="aeat.cli.modelo.file",
            now=_T0.replace(hour=13),
            calculation_repository=calculations,
            filing_repository=filings,
            verification_repository=verification_reports,
            work_unit_repository=work_units,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
            calculation_observation_repository=CalculationObservationRepository(objects=profile.repository),
            iva_compensation_history_repository=IvaCompensationHistoryRepository(objects=profile.repository),
            participation_index_repository=participation,
            prorrata_register_repository=ProrrataRegisterRepository(objects=profile.repository),
            result_disposition=ResultDisposition.INGRESO,
            taxpayer_nif=_TAXPAYER_NIF,
            operation=operation,
        )

        expected_a = participation.load(_TX_A)
        expected_b = participation.load(_TX_B)
        assert expected_a.participations[0].revision_state == "presentado"
        assert expected_a.participations[0].filing_record_id == filed.filing_record_id
        assert expected_b.participations[0].filing_record_id == filed.filing_record_id

        current_source_revisions = _source_revisions(
            calculations=calculations,
            work_units=work_units,
            filings=filings,
            operation=operation,
        )
        assert current_source_revisions.calculation != stale_source_revisions.calculation
        assert current_source_revisions.work_units != stale_source_revisions.work_units
        assert current_source_revisions.filings != stale_source_revisions.filings

        # An empty replacement would delete both freshly co-emitted rows if
        # the stale source assertions did not abort the same SQL batch.
        with pytest.raises(SecureObjectRevisionConflictError) as raised:
            participation.replace_all((), source_revisions=stale_source_revisions)

        assert raised.value.context is not None
        assert raised.value.context["namespace"] == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace
        assert participation.load(_TX_A) == expected_a
        assert participation.load(_TX_B) == expected_b

        ports = ParticipationIndexRebuildPorts(
            calculation_repository=calculations,
            work_unit_repository=work_units,
            filing_repository=filings,
            participation_index_repository=participation,
        )
        before_fresh_rebuild = _source_revisions(
            calculations=calculations,
            work_units=work_units,
            filings=filings,
            operation=operation,
        )
        stats = rebuild_participation_index(ports=ports, operation=operation)
        after_fresh_rebuild = _source_revisions(
            calculations=calculations,
            work_units=work_units,
            filings=filings,
            operation=operation,
        )

        assert stats.transaction_count == 2
        assert stats.participation_count == 2
        assert stats.revision_count == 1
        assert stats.stale_removed_count == 0
        assert after_fresh_rebuild == before_fresh_rebuild
        assert participation.load(_TX_A) == expected_a
        assert participation.load(_TX_B) == expected_b


def test_first_filing_catalogue_insert_invalidates_an_absent_source_snapshot(tmp_path: Path) -> None:
    """An observed absent singleton is asserted, so its first insertion blocks replacement."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        calculations = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_units = WorkUnitCatalogueRepository(objects=profile.repository)
        filings = ModeloRecordCatalogueRepository(objects=profile.repository)
        participation = TransactionParticipationIndexRepository(objects=profile.repository)

        with bundled_indexed_authority().operation() as operation:
            absent_source_revisions = _source_revisions(
                calculations=calculations,
                work_units=work_units,
                filings=filings,
                operation=operation,
            )
            assert absent_source_revisions.filings == ABSENT_SECURE_OBJECT_REVISION_ID

        filings.save(ModeloRecordCatalogue())
        _, inserted_filing_revision = filings.load_revisioned()
        assert inserted_filing_revision != ABSENT_SECURE_OBJECT_REVISION_ID

        preserved_index = TransactionRevisionParticipationIndex(transaction_id=_TX_A)
        participation.save(preserved_index)
        with pytest.raises(SecureObjectRevisionConflictError) as raised:
            participation.replace_all((), source_revisions=absent_source_revisions)

        assert raised.value.context is not None
        assert raised.value.context["namespace"] == MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.namespace
        assert participation.load(_TX_A) == preserved_index
