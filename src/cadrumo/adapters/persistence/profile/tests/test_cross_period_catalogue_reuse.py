"""Same-call catalogue reuse preserves real encrypted cross-period verdicts."""

from pathlib import Path

import pytest

from cadrumo.application.calculations.cross_period_clean_state import evaluate_cross_period_clean_state
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue
from cadrumo.domain.modelos.filing_record import ModeloRecordCatalogue
from cadrumo.domain.modelos.verification_report import VerificationReportCatalogue

from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..justificante import JustificanteRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_filing import ModeloRecordCatalogueRepository
from ..modelos_verification_reports import VerificationReportCatalogueRepository
from .cross_period_clean_state_support import BUCKET_ID, seed_official_303_source_filings, snapshot_390

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.mark.parametrize("populated", [False, True])
def test_reused_catalogue_preserves_complete_verdict_and_standalone_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    populated: bool,
) -> None:
    """Reuse avoids a decode, including for empty catalogues; later calls reload."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        observations = CalculationObservationRepository()
        if populated:
            seed_official_303_source_filings(observation_repository=observations)
        calculations = CalculationRevisionCatalogueRepository()
        filings = ModeloRecordCatalogueRepository()
        reports = VerificationReportCatalogueRepository()
        load = calculations.load
        load_filings = filings.load
        load_reports = reports.load
        reads = [0, 0, 0]

        def counted_load(*, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
            reads[0] += 1
            return load(operation=operation)

        def counted_filings() -> ModeloRecordCatalogue:
            reads[1] += 1
            return load_filings()

        def counted_reports(*, operation: PinnedAuthorityOperation | None = None) -> VerificationReportCatalogue:
            reads[2] += 1
            return load_reports(operation=operation)

        monkeypatch.setattr(calculations, "load", counted_load)
        monkeypatch.setattr(filings, "load", counted_filings)
        monkeypatch.setattr(reports, "load", counted_reports)
        with bundled_indexed_authority().operation() as operation:
            catalogue = calculations.load(operation=operation)
            filing_catalogue = filings.load()
            verification_catalogue = reports.load(operation=operation)
            assert reads == [1, 1, 1]

            def evaluate(reuse: CalculationRevisionCatalogue | None = None) -> bytes:
                return (
                    evaluate_cross_period_clean_state(
                        snapshot_390(),
                        operation=operation,
                        bucket_id=BUCKET_ID,
                        observation_repository=observations,
                        filing_repository=filings,
                        calculation_repository=calculations,
                        verification_repository=reports,
                        justificante_repository=JustificanteRepository(),
                        calculation_catalogue=reuse,
                        filing_catalogue=filing_catalogue if reuse is not None else None,
                        verification_catalogue=verification_catalogue if reuse is not None else None,
                        taxpayer_tax_id="X1234567L",
                    )
                    .model_dump_json()
                    .encode()
                )

            reused = evaluate(catalogue)
            assert reads == [1, 1, 1]
            assert evaluate() == reused
            assert reads == [2, 2, 2]
            assert evaluate() == reused
            assert reads == [3, 3, 3]
