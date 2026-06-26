"""Real-behavior coverage for cross-period clean-state dependency proof."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, Modelo202Modality
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.justificante import Justificante, JustificanteRepository
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepository,
    ModeloRecordStatus,
    VerificationReportCatalogueRepository,
    WorkUnit,
    derive_calculation_revision_id,
    derive_filing_record_id,
)
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.registry_observations import registry_grounded_modelo_observation, registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo import (
    create_work_unit,
    import_external_filing_evidence,
)
from .. import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodExpectedMemberSet,
    NoPriorObligationProvenanceKind,
    cross_period_dependency_inventory,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
    partition_cross_period_requirements_by_activity_start,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "default"
_M390_YEAR = 2025
_M390_PERIOD = "0A"
_M390_FIRST_QUARTER = Period.from_year_and_code(_M390_YEAR, "1T")
_M390_REVISION = "2010-y-siguientes"
_M303_REVISION = "2023-y-siguientes"
_M353_YEAR = 2026
_M353_PERIOD = "12"
_CLOCK = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_GROUP_MEMBER_A = "A00000000"
_GROUP_MEMBER_B = "B00000001"
_GROUP_MEMBER_C = "C00000002"


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _snapshot_390():
    return resources().modelos.authority.snapshot("390", filing_year=_M390_YEAR, period=_M390_PERIOD)


def _m390_first_quarter_evidence(verdict: CrossPeriodCleanStateVerdict) -> CrossPeriodDependencyEvidence:
    return next(evidence for evidence in verdict.dependencies if evidence.requirement.period == _M390_FIRST_QUARTER)


def _source_values(period: str, source_casilla_ids: tuple[CasillaId, ...]) -> dict[CasillaId, Decimal]:
    period_ordinal = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}[period]
    return {casilla_id: Decimal(period_ordinal * (index + 1)) for index, casilla_id in enumerate(source_casilla_ids)}


def _save_source_observation(
    repository: CalculationObservationRepository,
    *,
    period: str,
    source_values: dict[CasillaId, Decimal],
    source_kind: str = "aeat_sede_justificante",
    source_metadata: dict[str, str] | None = None,
) -> None:
    repository.save_observation(
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=_M390_YEAR,
            period=period,
            casilla_values=source_values,
        ),
        source_kind=source_kind,
        captured_at=_CLOCK,
        source_metadata=source_metadata,
    )


def _snapshot_353():
    return resources().modelos.authority.snapshot("353", filing_year=_M353_YEAR, period=_M353_PERIOD)


def _member_fan_in_requirement():
    return next(
        requirement
        for requirement in cross_period_dependency_requirements(_snapshot_353())
        if requirement.requires_member_fan_in
    )


def _member_source_values(member_nif: str, source_casilla_ids: tuple[CasillaId, ...]) -> dict[CasillaId, Decimal]:
    member_ordinal = {
        _GROUP_MEMBER_A: Decimal("1"),
        _GROUP_MEMBER_B: Decimal("10"),
        _GROUP_MEMBER_C: Decimal("100"),
    }[member_nif]
    return {casilla_id: member_ordinal * Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)}


def _save_member_322_observation(
    repository: CalculationObservationRepository,
    *,
    member_nif: str,
    source_casilla_ids: tuple[CasillaId, ...],
    source_metadata: dict[str, str] | None = None,
) -> None:
    repository.save_observation(
        registry_grounded_modelo_observation(
            modelo="322",
            filing_year=_M353_YEAR,
            period=_M353_PERIOD,
            casilla_values=_member_source_values(member_nif, source_casilla_ids),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CLOCK,
        member_nif=member_nif,
        source_metadata=source_metadata,
    )


def _seed_member_322_filing(
    observation_repository: CalculationObservationRepository,
    *,
    member_nif: str,
    source_casilla_ids: tuple[CasillaId, ...],
    justificante_tax_id: str | None = None,
    source_metadata: dict[str, str] | None = None,
) -> None:
    if source_metadata is None:
        source_metadata = {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": f"EXP-322-{_M353_YEAR}-{_M353_PERIOD}-{member_nif}",
            "authenticated_identity": member_nif,
            "aeat_justificante_csv": f"JUST-322-{member_nif}",
        }
    values = _member_source_values(member_nif, source_casilla_ids)
    work_unit_id = hashlib.sha256(f"322:{_M353_YEAR}:{_M353_PERIOD}:{member_nif}".encode()).hexdigest()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=values,
        observations=registry_grounded_modelo_observation(
            modelo="322",
            filing_year=_M353_YEAR,
            period=_M353_PERIOD,
            casilla_values=values,
        ).observations,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="aeat-import-test",
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
    )
    calculation_repository = CalculationRevisionCatalogueRepository()
    calculation_catalogue = calculation_repository.load()
    calculation_repository.save(
        CalculationRevisionCatalogue(revisions={**dict(calculation_catalogue.revisions), revision_id: revision}),
    )

    evidence_reference_id = f"JUST-322-{member_nif}"
    _persist_justificante_metadata(
        evidence_reference_id,
        modelo="322",
        period=_M353_PERIOD,
        filing_year=_M353_YEAR,
        tax_id=justificante_tax_id or member_nif,
    )
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
        member_nif=member_nif,
    )
    filing_repository = ModeloRecordCatalogueRepository()
    filing_catalogue = filing_repository.load()
    filing_repository.save(
        ModeloRecordCatalogue(
            records={
                **dict(filing_catalogue.records),
                filing_id: ModeloRecord(
                    filing_record_id=filing_id,
                    work_unit_id=work_unit_id,
                    calculation_revision_id=revision_id,
                    bucket_id=_BUCKET_ID,
                    modelo=ModeloCode("322"),
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nif=member_nif,
                    filed_at=_CLOCK,
                    filed_by="aeat-import-test",
                    aeat_accepted=True,
                    external_evidence=ExternalEvidence(
                        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                        reference_id=evidence_reference_id,
                        imported_at=_CLOCK,
                    ),
                ),
            },
        ),
    )
    _save_member_322_observation(
        observation_repository,
        member_nif=member_nif,
        source_casilla_ids=source_casilla_ids,
        source_metadata=source_metadata,
    )


def _persist_justificante_metadata(
    csv: str,
    *,
    modelo: str,
    period: str,
    filing_year: int,
    tax_id: str = "X1234567L",
    presentation_id: str | None = None,
) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=Period.from_year_and_code(filing_year, period),
            ejercicio=str(filing_year),
            presentation_id=presentation_id,
            presented_at=_CLOCK,
            tax_id=tax_id,
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            parsed_at=_CLOCK,
        ),
    )


def _live_capture_filing(*, csv: str, kind: ExternalEvidenceKind) -> ModeloRecord:
    work_unit_id = hashlib.sha256(f"130:2026:1T:{csv}".encode()).hexdigest()
    revision_id = hashlib.sha256(f"rev:{csv}".encode()).hexdigest()
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CLOCK,
        filed_by="aeat-live-capture-test",
    )
    return ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=_CLOCK,
        filed_by="aeat-live-capture-test",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(kind=kind, reference_id=csv, imported_at=_CLOCK),
    )


def test_live_capture_evidence_clears_justificante_verification(tmp_path: Path) -> None:
    """A filing stamped with AEAT_LIVE_CAPTURE evidence clears the justificante gate."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130ABCD01"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "app_filing",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION not in blockers
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD not in blockers
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_live_capture_evidence_requires_expected_taxpayer_identity(tmp_path: Path) -> None:
    """A matching receipt cannot clear the gate unless the taxpayer axis is known."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130NOIDENT"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "app_filing",
            JustificanteRepository(),
            None,
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_taxpayer_match_is_case_insensitive(tmp_path: Path) -> None:
    """Taxpayer comparison is canonicalized while still requiring the same identity."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130CASE01"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "app_filing",
            JustificanteRepository(),
            "x1234567l",
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_live_capture_evidence_rejects_mismatched_typed_justificante_period(tmp_path: Path) -> None:
    """A matching ejercicio label cannot override a mismatched typed Period value."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130MISMATCH"
        pdf_bytes = b"%PDF-1.4\n% mismatched period justificante\n%%EOF\n"
        JustificanteRepository().save(
            Justificante(
                csv=csv,
                modelo="130",
                period=Period.from_year_and_code(2025, "1T"),
                ejercicio="2026",
                presentation_id=None,
                presented_at=_CLOCK,
                tax_id="X1234567L",
                total_a_ingresar=None,
                total_a_devolver=None,
                verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
                source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
                source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                parsed_at=_CLOCK,
            ),
        )
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "app_filing",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_evidence_rejects_mismatched_filed_history_justificante_csv(
    tmp_path: Path,
) -> None:
    """Filed-history metadata cannot point at a different justificante than the filing record."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130CSVLOCK"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            JustificanteRepository(),
            "X1234567L",
            {"aeat_register_status": "ALTA", "authenticated_identity": "X1234567L", "aeat_justificante_csv": "OTHER"},
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_evidence_accepts_matching_plural_filed_history_justificante_csv(
    tmp_path: Path,
) -> None:
    """Plural filed-history CSV metadata clears only when it contains the filing receipt."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130CSVSET"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            JustificanteRepository(),
            "X1234567L",
            {
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_justificante_csvs": f"OTHER,{csv}",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_live_capture_evidence_rejects_plural_filed_history_justificante_csv_without_match(
    tmp_path: Path,
) -> None:
    """Plural filed-history CSV metadata must not bypass reference reconciliation."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130CSVSETMISS"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            JustificanteRepository(),
            "X1234567L",
            {
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_justificante_csvs": "OTHER-ONE,OTHER-TWO",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_evidence_rejects_mismatched_filed_history_presentation_id(
    tmp_path: Path,
) -> None:
    """When AEAT exposes both references, expediente and justificante presentation id must agree."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130PRESID"
        period = Period.from_year_and_code(2026, "1T")
        _persist_justificante_metadata(
            csv,
            modelo="130",
            period=period.registry_token,
            filing_year=period.year,
            presentation_id=f"PRES-130-{period.year}-{period.registry_token}",
        )
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            JustificanteRepository(),
            "X1234567L",
            {
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_expediente_id": "DIFFERENT-PRESENTATION-ID",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_evidence_rejects_expediente_only_metadata_without_comparable_receipt_reference(
    tmp_path: Path,
) -> None:
    """Expediente-only filed history cannot verify a receipt lacking presentation id."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130EXPONLY"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026, presentation_id=None)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            JustificanteRepository(),
            "X1234567L",
            {
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_expediente_id": "EXPEDIENTE-WITHOUT-CSV-REFERENCE",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_csv_register_evidence_clears_with_matching_justificante_metadata(tmp_path: Path) -> None:
    """A CSV-register reference clears the gate only when its justificante is enrolled."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "CSVREG130ABCD01"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_CSV_REGISTER)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_csv_register",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION not in blockers
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD not in blockers
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_csv_register_evidence_without_enrolled_justificante_still_blocks(tmp_path: Path) -> None:
    """A CSV-register reference without its parsed receipt cannot clear clean-state."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        filing = _live_capture_filing(csv="CSVREG130NOJUST", kind=ExternalEvidenceKind.AEAT_CSV_REGISTER)

        blockers = _filing_external_evidence_blockers(
            filing,
            "aeat_csv_register",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in blockers


def test_bare_aeat_acceptance_without_external_evidence_does_not_clear_cross_period_gate(tmp_path: Path) -> None:
    """A bare acceptance bit is not enough without an AEAT evidence reference."""
    from ....domain.justificante import JustificanteRepository
    from .._cross_period_clean_state import _filing_external_evidence_blockers

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        base = _live_capture_filing(csv="LIVECAP130BARE01", kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)
        legacy_payload = base.model_dump(mode="python")
        legacy_payload["external_evidence"] = None
        filing = ModeloRecord.model_construct(**legacy_payload)

        blockers = _filing_external_evidence_blockers(
            filing,
            "app_filing",
            JustificanteRepository(),
            "X1234567L",
        )

        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE in blockers
        assert CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE in blockers


def _seed_official_303_source_filings(
    *,
    observation_repository: CalculationObservationRepository,
    evidence_kind_by_period: dict[str, ExternalEvidenceKind] | None = None,
    skip_justificante_metadata_periods: set[str] | None = None,
    source_kind_by_period: dict[str, str] | None = None,
    source_metadata_by_period: dict[str, dict[str, str] | None] | None = None,
) -> None:
    evidence_kind_by_period = evidence_kind_by_period or {}
    skip_justificante_metadata_periods = skip_justificante_metadata_periods or set()
    source_kind_by_period = source_kind_by_period or {}
    source_metadata_by_period = source_metadata_by_period or {}
    source_casilla_ids_by_period: dict[str, set[CasillaId]] = {}
    for requirement in cross_period_dependency_requirements(_snapshot_390()):
        source_casilla_ids_by_period.setdefault(
            requirement.period.registry_token,
            set(),
        ).update(requirement.source_casilla_ids)

    for period, source_casilla_ids in sorted(source_casilla_ids_by_period.items()):
        evidence_kind = evidence_kind_by_period.get(period, ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF)
        evidence_reference_id = f"JUST-{period}"
        if (
            evidence_kind
            in {
                ExternalEvidenceKind.AEAT_CSV_REGISTER,
                ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
            }
            and period not in skip_justificante_metadata_periods
        ):
            _persist_justificante_metadata(evidence_reference_id, modelo="303", period=period, filing_year=_M390_YEAR)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, period),
            revision_id=_M303_REVISION,
            clock=_CLOCK,
        )
        values = _source_values(period, tuple(sorted(source_casilla_ids)))
        if (
            evidence_kind
            in {
                ExternalEvidenceKind.AEAT_CSV_REGISTER,
                ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
            }
            and period in skip_justificante_metadata_periods
        ):
            _seed_legacy_source_filing_record(
                work_unit=work_unit,
                casilla_values=values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
            )
        else:
            import_external_filing_evidence(
                work_unit_id=work_unit.work_unit_id,
                casilla_values=values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
                actor="aeat-import-test",
                expected_tax_id="X1234567L",
                clock=_CLOCK,
            )
        default_source_metadata = {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": f"EXP-303-{_M390_YEAR}-{period}",
            "authenticated_identity": "X1234567L",
        }
        if (
            evidence_kind
            in {
                ExternalEvidenceKind.AEAT_CSV_REGISTER,
                ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
            }
            and period not in skip_justificante_metadata_periods
        ):
            default_source_metadata["aeat_justificante_csv"] = evidence_reference_id
        _save_source_observation(
            observation_repository,
            period=period,
            source_values=values,
            source_kind=source_kind_by_period.get(period, "aeat_sede_justificante"),
            source_metadata=source_metadata_by_period.get(period, default_source_metadata),
        )


def _seed_legacy_source_filing_record(
    *,
    work_unit: WorkUnit,
    casilla_values: dict[CasillaId, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
) -> None:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="aeat-import-test",
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
    )
    calculation_repository = CalculationRevisionCatalogueRepository()
    calculation_catalogue = calculation_repository.load()
    calculation_repository.save(
        CalculationRevisionCatalogue(revisions={**dict(calculation_catalogue.revisions), revision_id: revision}),
    )

    filing_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CLOCK,
        filed_by="aeat-import-test",
    )
    filing_repository = ModeloRecordCatalogueRepository()
    filing_catalogue = filing_repository.load()
    filing_repository.save(
        ModeloRecordCatalogue(
            records={
                **dict(filing_catalogue.records),
                filing_id: ModeloRecord(
                    filing_record_id=filing_id,
                    work_unit_id=work_unit.work_unit_id,
                    calculation_revision_id=revision_id,
                    bucket_id=work_unit.bucket_id,
                    modelo=ModeloCode(str(work_unit.modelo)),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period,
                    filed_at=_CLOCK,
                    filed_by="aeat-import-test",
                    aeat_accepted=True,
                    status=ModeloRecordStatus.VIGENTE,
                    external_evidence=ExternalEvidence(
                        kind=evidence_kind,
                        reference_id=evidence_reference_id,
                        imported_at=_CLOCK,
                    ),
                ),
            },
        ),
    )


def test_cross_period_clean_state_blocks_missing_required_prior_filings(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISSING_OBSERVATION in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


def test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced(tmp_path: Path) -> None:
    """M100 suffered-retencion deps scope out; self-filed deps still block.

    The grounded payee/payer distinction (``taxpayer_files_source = false`` on the suffered
    classifications) lets a salaried taxpayer reach export, while pagos-fraccionados the taxpayer
    DOES file stay enforced. Classification-driven, not schedule-driven (the reverted Option 1).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            resources().modelos.authority.snapshot("100", filing_year=2024, period="0A"),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    suffered = {"111", "115", "123", "193"}
    scoped_out = {
        item.requirement.source_modelo for item in verdict.dependencies if item.modelo_not_applicable_advisory
    }
    assert suffered <= scoped_out, f"suffered deps must be scoped out, got {scoped_out}"
    assert verdict.has_modelo_not_applicable_advisory is True
    assert all(item.clean for item in verdict.dependencies if item.modelo_not_applicable_advisory)
    assert scoped_out.isdisjoint({"130", "131"}), "self-filed pagos fraccionados must NOT be scoped out"


def test_m100_pagos_fraccionados_conditional_on_economic_activity(tmp_path: Path) -> None:
    """130/131 scope out for a declared employee and stay enforced otherwise."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snap = resources().modelos.authority.snapshot("100", filing_year=2024, period="0A")

        def evaluate_activity_state(
            taxpayer_files_economic_activity: bool | None,
        ) -> CrossPeriodCleanStateVerdict:
            return evaluate_cross_period_clean_state(
                snap,
                bucket_id=_BUCKET_ID,
                observation_repository=CalculationObservationRepository(),
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                taxpayer_tax_id="X1234567L",
                taxpayer_files_economic_activity=taxpayer_files_economic_activity,
            )

        employee = evaluate_activity_state(False)
        autonomo = evaluate_activity_state(True)
        undeclared = evaluate_activity_state(None)

    def scoped(verdict: CrossPeriodCleanStateVerdict) -> set[str]:
        return {item.requirement.source_modelo for item in verdict.dependencies if item.modelo_not_applicable_advisory}

    def blocking(verdict: CrossPeriodCleanStateVerdict) -> set[str]:
        return {item.requirement.source_modelo for item in verdict.dependencies if not item.clean}

    # Declared employee (no actividad económica): 130/131 scope out as not-applicable.
    assert {"130", "131"} <= scoped(employee)
    # Autónomo (declares actividad económica): 130/131 stay enforced (still block, never scoped).
    assert scoped(autonomo).isdisjoint({"130", "131"})
    assert {"130", "131"} & blocking(autonomo)
    # Undeclared income categories: fail-closed — 130/131 stay enforced.
    assert scoped(undeclared).isdisjoint({"130", "131"})


def test_cross_period_requirements_include_relation_rollups(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")

    requirements = cross_period_dependency_requirements(snapshot)

    assert any(
        requirement.origin is CrossPeriodDependencyOrigin.REGISTRY_RELATION
        and requirement.source_modelo == "115"
        and requirement.period == Period.from_year_and_code(2026, "1T")
        for requirement in requirements
    )


def test_cross_period_dependency_inventory_covers_declared_2026_target_modelos(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventory = cross_period_dependency_inventory(
            resources().modelos.authority,
            filing_year=2026,
        )

    assert inventory.target_modelos == (
        "130",
        "131",
        "180",
        "190",
        "193",
        "200",
        "202",
        "303",
        "353",
        "390",
    )
    assert all(item.dependencies for item in inventory.items)
    assert any(
        item.target_modelo == "390"
        and item.target_period == Period.from_year_and_code(2026, "0A")
        and item.source_modelos == ("303",)
        for item in inventory.items
    )
    assert any(
        item.target_modelo == "353"
        and item.target_period == Period.from_year_and_code(2026, "12")
        and item.source_modelos == ("322",)
        for item in inventory.items
    )


def test_cross_period_dependency_inventory_covers_renta_2025_target_modelo(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventory = cross_period_dependency_inventory(
            resources().modelos.authority,
            filing_year=2025,
            modelos=("100",),
        )

    assert inventory.target_modelos == ("100",)
    assert len(inventory.items) == 1
    assert inventory.items[0].target_period == Period.from_year_and_code(2025, "0A")
    assert set(inventory.items[0].source_modelos) >= {
        "111",
        "115",
        "123",
        "130",
        "131",
        "180",
        "184",
        "190",
        "193",
    }


def test_cross_period_dependency_inventory_documents_patrimonio_foreign_asset_scope(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventories = tuple(
            cross_period_dependency_inventory(
                resources().modelos.authority,
                filing_year=filing_year,
            )
            for filing_year in (2025, 2026)
        )

    assert all("714" not in inventory.target_modelos for inventory in inventories)
    assert all("720" not in inventory.target_modelos for inventory in inventories)
    assert all("721" not in inventory.target_modelos for inventory in inventories)
    assert all("714" not in inventory.source_modelos for inventory in inventories)
    assert all("720" not in inventory.source_modelos for inventory in inventories)
    assert all("721" not in inventory.source_modelos for inventory in inventories)


def test_cross_period_clean_state_blocks_missing_group_member_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = _snapshot_353()

        verdict = evaluate_cross_period_clean_state(
            snapshot,
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    assert verdict.requires_clean_state is True
    assert any(evidence.requirement.requires_member_fan_in for evidence in verdict.dependencies)
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in verdict.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in verdict.blockers


def test_cross_period_clean_state_blocks_group_member_fan_in_without_expected_roster(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _save_member_322_observation(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            source_casilla_ids=requirement.source_casilla_ids,
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A,)
    assert member_evidence.expected_member_nifs == ()
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in member_evidence.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in member_evidence.blockers


def test_cross_period_clean_state_blocks_incomplete_expected_group_member_fan_in(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _save_member_322_observation(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            source_casilla_ids=requirement.source_casilla_ids,
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A,)
    assert member_evidence.expected_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B)
    assert member_evidence.missing_member_nifs == (_GROUP_MEMBER_B,)
    assert member_evidence.unexpected_member_nifs == ()
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER not in member_evidence.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in member_evidence.blockers


def test_cross_period_clean_state_blocks_unexpected_group_member_fan_in(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        for member_nif in (_GROUP_MEMBER_A, _GROUP_MEMBER_B, _GROUP_MEMBER_C):
            _save_member_322_observation(
                observation_repository,
                member_nif=member_nif,
                source_casilla_ids=requirement.source_casilla_ids,
            )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B, _GROUP_MEMBER_C)
    assert member_evidence.expected_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B)
    assert member_evidence.missing_member_nifs == ()
    assert member_evidence.unexpected_member_nifs == (_GROUP_MEMBER_C,)
    assert CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE in member_evidence.blockers


def test_cross_period_clean_state_accepts_member_scoped_group_filing_records(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        for member_nif in (_GROUP_MEMBER_A, _GROUP_MEMBER_B):
            _seed_member_322_filing(
                observation_repository,
                member_nif=member_nif,
                source_casilla_ids=requirement.source_casilla_ids,
            )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert member_evidence.clean is True
    assert member_evidence.member_filing_record_ids
    assert len(member_evidence.member_filing_record_ids) == 2
    assert member_evidence.member_calculation_revision_ids
    assert len(member_evidence.member_calculation_revision_ids) == 2


def test_cross_period_clean_state_blocks_member_filing_with_wrong_tax_id_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _seed_member_322_filing(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            justificante_tax_id=_GROUP_MEMBER_B,
            source_casilla_ids=requirement.source_casilla_ids,
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_353(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A,),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in member_evidence.blockers


def test_cross_period_clean_state_blocks_taxpayer_filing_with_wrong_tax_id_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            skip_justificante_metadata_periods={"1T"},
        )
        _persist_justificante_metadata(
            "JUST-1T",
            modelo="303",
            period="1T",
            filing_year=_M390_YEAR,
            tax_id="B12345678",
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_superseded_upstream_filing(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(observation_repository=observation_repository)
        filing_repository = ModeloRecordCatalogueRepository()
        catalogue = filing_repository.load()
        source_record = catalogue.current_for(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, "1T"),
        )
        assert source_record is not None
        superseded_record = source_record.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": _CLOCK,
                "superseded_by_filing_record_id": "f" * 64,
            },
        )
        filing_repository.save(
            ModeloRecordCatalogue(
                records={
                    **dict(catalogue.records),
                    source_record.filing_record_id: superseded_record,
                },
            ),
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=filing_repository,
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


def test_cross_period_clean_state_accepts_aeat_attested_reconciled_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(observation_repository=observation_repository)

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert verdict.blockers == ()


def test_cross_period_clean_state_accepts_matching_aeat_register_observation_provenance(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            source_metadata_by_period={
                "1T": {
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-303-2025-1T",
                    "authenticated_identity": "X1234567L",
                    "aeat_justificante_csv": "JUST-1T",
                },
            },
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is True
    assert first_quarter.blockers == ()


def test_cross_period_clean_state_accepts_matching_filed_history_justificante_csv_provenance(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            source_metadata_by_period={
                "1T": {
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-303-2025-1T",
                    "authenticated_identity": "X1234567L",
                    "aeat_justificante_csv": "JUST-1T",
                },
            },
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is True
    assert first_quarter.blockers == ()


def test_cross_period_clean_state_blocks_filed_history_justificante_csv_mismatch(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            source_metadata_by_period={
                "1T": {
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-303-2025-1T",
                    "authenticated_identity": "X1234567L",
                    "aeat_justificante_csv": "DIFFERENT-JUSTIFICANTE-CSV",
                },
            },
        )

        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=observation_repository,
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_empty_pre_activity_span_produces_no_cross_period_blocker_for_genuine_first_filer(
    tmp_path: Path,
) -> None:
    """A genuine first filer with no prior obligations verifies clean.

    The M390/2025 target depends on the four 2025 M303 quarters. An activity-start
    date of 2026-01-01 places every dependency strictly before activity start, so
    each is scoped out as no-prior-obligation (absent-by-design). No observation is
    seeded for any quarter; the verdict is fully clean on current-period merits and
    every suppressed dependency carries the typed provenance facet rather than a
    silent omission.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
            activity_start_date=date(2026, 1, 1),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert verdict.blockers == ()
    suppressed = verdict.suppressed_pre_activity_dependencies
    assert len(suppressed) == len(verdict.dependencies)
    assert all(evidence.blockers == () for evidence in suppressed)
    assert all(evidence.no_prior_obligation is not None for evidence in suppressed)
    assert all(
        evidence.no_prior_obligation is not None
        and evidence.no_prior_obligation.activity_start_date == date(2026, 1, 1)
        and evidence.no_prior_obligation.provenance_kind is NoPriorObligationProvenanceKind.OPERATOR_DECLARED
        for evidence in suppressed
    )
    assert verdict.has_operator_declared_suppression_advisory is True


def test_alta_containing_period_stays_in_scope_as_first_obligation(tmp_path: Path) -> None:
    """At the ratified boundary, the alta-CONTAINING period is in scope.

    With activity start on 2025-10-01 (the first day of 4T), the M390/2025
    dependency graph suppresses 1T/2T/3T (strictly prior) but keeps 4T - the
    period that contains the alta - in scope as the first obligation. The
    in-scope 4T dependency is NOT marked suppressed and still demands its filing
    (here unevidenced, so it blocks), proving the alta-period is treated as a real
    obligation rather than scoped away.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
            activity_start_date=date(2025, 10, 1),
        )

    fourth_quarter = Period.from_year_and_code(_M390_YEAR, "4T")
    fourth = next(e for e in verdict.dependencies if e.requirement.period == fourth_quarter)
    assert fourth.suppressed_pre_activity is False
    assert fourth.no_prior_obligation is None
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in fourth.blockers
    suppressed_periods = {e.requirement.period.registry_token for e in verdict.suppressed_pre_activity_dependencies}
    assert suppressed_periods == {"1T", "2T", "3T"}


def test_activity_start_scoping_applies_to_both_requirement_origins(tmp_path: Path) -> None:
    """Scoping is uniform across previous_filing and relation origins.

    M180/0A derives its prior-quarter dependencies via registry RELATIONS over
    M115; M303/4T derives its prior-quarter dependency via a PREVIOUS_FILING
    binding over M303/3T. Both origins suppress their strictly-prior quarters under
    the same activity-start date, so a first filer is not unblocked on one origin
    while trapped on the other.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        relation_snapshot = resources().modelos.authority.snapshot("180", filing_year=2026, period="0A")
        previous_filing_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="4T")

        relation_verdict = evaluate_cross_period_clean_state(
            relation_snapshot,
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
            activity_start_date=date(2026, 7, 1),
        )
        previous_filing_verdict = evaluate_cross_period_clean_state(
            previous_filing_snapshot,
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
            activity_start_date=date(2026, 10, 15),
        )

    relation_suppressed = relation_verdict.suppressed_pre_activity_dependencies
    assert relation_suppressed
    assert all(e.requirement.origin is CrossPeriodDependencyOrigin.REGISTRY_RELATION for e in relation_suppressed)
    assert {e.requirement.period.registry_token for e in relation_suppressed} == {"1T", "2T"}

    # M303/4T depends on M303/3T (Jul-Sep) via BOTH a previous_filing binding and a
    # self-compensacion registry relation; an alta of 2026-10-15 places 3T strictly
    # before activity start, so BOTH origins suppress it. This proves the scoping is
    # uniform across the two requirement origins on the very same period.
    previous_filing_suppressed = previous_filing_verdict.suppressed_pre_activity_dependencies
    assert previous_filing_suppressed
    assert {e.requirement.period.registry_token for e in previous_filing_suppressed} == {"3T"}
    suppressed_origins = {e.requirement.origin for e in previous_filing_suppressed}
    assert CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING in suppressed_origins
    assert CrossPeriodDependencyOrigin.REGISTRY_RELATION in suppressed_origins


def test_real_prior_filing_post_dating_alta_still_blocks_anti_tautology(tmp_path: Path) -> None:
    """Anti-tautology: a real prior obligation after the alta still blocks.

    The scoping is NOT a vacuous open: a dependency whose period is on or after the
    declared activity-start date stays in scope and still demands official AEAT
    evidence. With activity start on 2025-01-01, every 2025 M303 quarter is in
    scope (none strictly prior); with no AEAT evidence seeded, the gate blocks
    exactly as it does without any activity-start date - proving an operator cannot
    scope away a real obligation that fell on or after the claimed start.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_390(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="X1234567L",
            activity_start_date=date(2025, 1, 1),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert verdict.suppressed_pre_activity_dependencies == ()
    assert CrossPeriodCleanStateBlocker.MISSING_OBSERVATION in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


def _snapshot_202():
    return resources().modelos.authority.snapshot("202", filing_year=2026, period="2P")


def test_first_year_modalidad_cuota_suppresses_m202_dependency_through_evaluator(tmp_path: Path) -> None:
    """A first-year modalidad-cuota IS filer clears the M202 cross-period gate.

    The M202/2026/2P snapshot derives a self-prior M202 pago-fraccionado
    dependency. With the derived modality ART_40_2_OPTIONAL and an activity-start
    date inside the target year (first IS year), the source-202 dependencies are
    scoped out as first-year no-fractional-payment obligations: no observation is
    seeded, yet every 202-source dependency is clean and carries the typed facet,
    and the verdict reports the advisory.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_202(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="B12345678",
            activity_start_date=date(2026, 2, 1),
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
        )

    m202_dependencies = [e for e in verdict.dependencies if e.requirement.source_modelo == "202"]
    assert m202_dependencies, "expected at least one M202-source cross-period dependency"
    assert all(e.suppressed_first_year_fractional for e in m202_dependencies)
    assert all(e.clean for e in m202_dependencies)
    assert all(
        e.no_prior_obligation is not None
        and e.no_prior_obligation.facet_kind
        is NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR
        for e in m202_dependencies
    )
    assert verdict.has_first_year_fractional_suppression_advisory is True
    suppressed_periods = {
        e.requirement.period.registry_token for e in verdict.suppressed_first_year_fractional_dependencies
    }
    assert suppressed_periods


def test_mandatory_modalidad_base_keeps_m202_dependency_in_scope_through_evaluator(tmp_path: Path) -> None:
    """ART_40_3_MANDATORY keeps the M202 dependency in scope and blocking (fail-closed).

    Under modalidad base the pago fraccionado is owed in the first year, so the
    self-prior M202 dependency is NOT suppressed; with no AEAT evidence seeded it
    blocks exactly as it would without the modality, proving the suppression is
    refused for the mandatory modality.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_202(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="B12345678",
            activity_start_date=date(2026, 2, 1),
            modelo_202_modality=Modelo202Modality.ART_40_3_MANDATORY,
        )

    m202_dependencies = [e for e in verdict.dependencies if e.requirement.source_modelo == "202"]
    assert m202_dependencies
    assert verdict.suppressed_first_year_fractional_dependencies == ()
    assert verdict.has_first_year_fractional_suppression_advisory is False
    assert any(not e.clean for e in m202_dependencies)


def test_incomplete_modality_keeps_m202_dependency_in_scope_through_evaluator(tmp_path: Path) -> None:
    """INCOMPLETE / unthreaded modality never suppresses the M202 dependency (fail-closed).

    When the modality cannot be derived (or is not threaded), the self-prior M202
    dependency stays in scope and blocks with no evidence seeded — a missing
    modality is never read as 'no obligation'.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        for modality in (Modelo202Modality.INCOMPLETE, None):
            verdict = evaluate_cross_period_clean_state(
                _snapshot_202(),
                bucket_id=_BUCKET_ID,
                observation_repository=CalculationObservationRepository(),
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                taxpayer_tax_id="B12345678",
                activity_start_date=date(2026, 2, 1),
                modelo_202_modality=modality,
            )
            assert verdict.suppressed_first_year_fractional_dependencies == ()
            assert verdict.has_first_year_fractional_suppression_advisory is False
            assert verdict.clean is False


def test_non_first_year_keeps_m202_dependency_in_scope_through_evaluator(tmp_path: Path) -> None:
    """An activity-start year before the target year keeps the M202 dependency in scope.

    With activity start in 2025 (a prior IS year exists to provide the cuota
    basis), the modalidad-cuota M202 dependency is NOT suppressed and blocks on
    missing evidence — an operator cannot scope away a real prior obligation by
    declaring modalidad cuota.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = evaluate_cross_period_clean_state(
            _snapshot_202(),
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            filing_repository=ModeloRecordCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            taxpayer_tax_id="B12345678",
            activity_start_date=date(2025, 6, 1),
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
        )

    assert verdict.suppressed_first_year_fractional_dependencies == ()
    assert verdict.has_first_year_fractional_suppression_advisory is False
    assert verdict.clean is False


def test_partition_keeps_non_calendar_anchors_in_scope(tmp_path: Path) -> None:
    """A dependency with no calendar span is never silently dropped.

    The strictly-before predicate is guarded by Period.has_date_span(); a period
    that cannot be positioned against a date (e.g. an instalment clave) stays in
    scope rather than being silently suppressed. This proves the scoping never
    drops an anchor it cannot legitimately position.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        requirements = cross_period_dependency_requirements(_snapshot_390())

    instalment_period = Period.from_year_and_code(_M390_YEAR, "1P")
    assert instalment_period.has_date_span() is False
    forged = tuple(requirement.model_copy(update={"period": instalment_period}) for requirement in requirements[:1])
    partition = partition_cross_period_requirements_by_activity_start(
        forged,
        activity_start_date=date(2099, 1, 1),
    )
    assert partition.suppressed == ()
    assert partition.in_scope == forged
