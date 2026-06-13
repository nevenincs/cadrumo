"""End-to-end tests for the external-filing import path.

The import path is the production source of ``ModeloRecord``
records that carry ``external_evidence``. Operators (or import
adapters: justificante PDF reader, AEAT CSV register importer,
AEAT live capture) call ``import_external_filing_evidence`` with
the casilla values they read from the official receipt, plus a
reference id pointing at the evidence source. The amend path then
consumes these records as its baseline.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
)
from ....domain.modelos._filing_record import (
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos._filing_repository import (
    ModeloRecordCatalogueRepository,
    upsert_filing_record,
)
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)
from ....domain.modelos._work_unit import WorkUnit
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    AmendmentEvidenceMissingError,
    ExternalModeloImportError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    get_calculation_revision,
    get_filing_record,
    get_work_unit,
    import_external_filing_evidence,
    mark_revision_verificado_completo,
)
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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
_T5 = datetime(2026, 4, 17, 13, 0, 0, tzinfo=UTC)
_TAX_ID = "X1234567L"


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Yield the five catalogue repositories over an encrypted SQLite db."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        fr = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, fr, vr, bv


def _seed_work_unit(wu_repo: WorkUnitCatalogueRepository):
    """Modelo 130 1T 2026 — registry-resolvable for the
    ``calculate_modelo_revision`` formula-engine path used by the
    locally-filed regression test."""

    return create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )


_DEFAULT_130_BINDING_VALUES = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
}


@dataclass(frozen=True, slots=True)
class _ImportOutcome:
    """Bundle returned by _drive_import_persists_filing.

    Holds every state slice the focused tests inspect:
    work_unit + the new filing record produced by
    ``import_external_filing_evidence``.
    """

    work_unit: WorkUnit
    filing: ModeloRecord


def _drive_import_persists_filing(repos: _Repos) -> _ImportOutcome:
    """Run the seed-work-unit + import-evidence scenario and bundle the observable state."""
    wu_repo, cr_repo, fr_repo, _evidence_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-2026-303-Q1-OPERATOR1",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
    )
    filing = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500"), "02": Decimal("300")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-2026-303-Q1-OPERATOR1",
        actor="aeat-import",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id=_TAX_ID,
        clock=_T1,
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
        filed_at=filed_at,
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


def test_import_filing_is_current_and_accepted(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    assert outcome.filing.status is ModeloRecordStatus.VIGENTE
    assert outcome.filing.aeat_accepted is True


def test_import_filing_carries_external_evidence_metadata(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    evidence = outcome.filing.external_evidence
    assert evidence is not None
    assert evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert evidence.reference_id == "JUST-2026-303-Q1-OPERATOR1"
    assert evidence.imported_at == _T1


def test_import_filing_records_no_amendment_link(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    assert outcome.filing.amends_filing_record_id is None
    assert outcome.filing.filed_at == _T1


_IMPORTED_REVISION_CASILLAS = (
    ("01", Decimal("1500")),
    ("02", Decimal("300")),
)


def test_import_persists_filed_calculation_revision(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    _, cr_repo, _, _, _ = repos
    revision = get_calculation_revision(outcome.filing.calculation_revision_id, calculation_repository=cr_repo)
    assert revision.state is CalculationRevisionState.PRESENTADO
    assert revision.amendment_kind is None  # import is not an amendment


def test_import_persists_registry_grounded_casilla_observations(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    _, cr_repo, _, _, _ = repos
    revision = get_calculation_revision(outcome.filing.calculation_revision_id, calculation_repository=cr_repo)
    observations = {obs.casilla_id: obs for obs in revision.observations}

    assert set(observations) == {"01", "02"}
    assert observations["01"].value == Decimal("1500")
    assert observations["01"].formula_id is None
    assert observations["01"].operand_refs == ()
    assert observations["01"].legal_refs
    assert observations["01"].source_refs
    assert observations["02"].legal_refs
    assert observations["02"].source_refs


@pytest.mark.parametrize(("casilla_id", "expected"), _IMPORTED_REVISION_CASILLAS)
def test_import_persists_casilla_value(repos: _Repos, casilla_id: str, expected: Decimal) -> None:
    outcome = _drive_import_persists_filing(repos)
    _, cr_repo, _, _, _ = repos
    revision = get_calculation_revision(outcome.filing.calculation_revision_id, calculation_repository=cr_repo)
    assert revision.casilla_values[casilla_id] == expected


def test_import_work_unit_pointers_advance_to_new_filing(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    wu_repo, _, _, _, _ = repos
    refreshed_wu = get_work_unit(outcome.work_unit.work_unit_id, repository=wu_repo)
    assert refreshed_wu.filed_calculation_revision_id == outcome.filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == outcome.filing.filing_record_id


def test_import_emits_single_modelo_filing_imported_event(repos: _Repos) -> None:
    outcome = _drive_import_persists_filing(repos)
    _, _, _, _, bv_repo = repos
    events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_IMPORTED,),
    )
    assert len(events) == 1
    assert events[0].object_type is BucketEventObjectType.FILING_RECORD
    assert events[0].object_id == outcome.filing.filing_record_id


_IMPORTED_EVENT_PAYLOAD_EXPECTATIONS = (
    ("evidence_kind", "aeat_justificante_pdf"),
    ("evidence_reference_id", "JUST-2026-303-Q1-OPERATOR1"),
    ("supersedes_filing_record_id", ""),
    ("casilla_count", "2"),
)


@pytest.mark.parametrize(("payload_key", "expected"), _IMPORTED_EVENT_PAYLOAD_EXPECTATIONS)
def test_import_event_payload_records_field(repos: _Repos, payload_key: str, expected: str) -> None:
    outcome = _drive_import_persists_filing(repos)
    _, _, _, _, bv_repo = repos
    events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_IMPORTED,),
    )
    assert events[0].payload[payload_key] == expected


def test_import_supersedes_prior_current_filing(repos: _Repos) -> None:
    """A second import for the same (bucket, modelo, year, period)
    supersedes the prior current filing. The supersession metadata
    is captured; the new filing's bucket-event references the prior
    via ``supersedes_filing_record_id``."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-FIRST",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
    )

    first = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-FIRST",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )

    persist_justificante_metadata(
        "CSV-SECOND",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T2,
    )
    second = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1600")},
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="CSV-SECOND",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id=_TAX_ID,
        clock=_T2,
    )

    refreshed_first = get_filing_record(first.filing_record_id, filing_repository=fr_repo)
    assert refreshed_first.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_first.superseded_by_filing_record_id == second.filing_record_id

    refreshed_first_revision = get_calculation_revision(first.calculation_revision_id, calculation_repository=cr_repo)
    assert refreshed_first_revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO

    assert second.status is ModeloRecordStatus.VIGENTE
    assert second.external_evidence is not None
    assert second.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER

    catalogue = bv_repo.load()
    imports = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_IMPORTED,),
    )
    assert len(imports) == 2
    assert imports[0].payload["supersedes_filing_record_id"] == ""
    assert imports[1].payload["supersedes_filing_record_id"] == first.filing_record_id


def test_import_then_amend_unlocks_amendment_path(repos: _Repos) -> None:
    """The import path produces a baseline the amend path accepts.
    This is the canonical production flow for correcting an
    externally-filed return: import official evidence, then amend
    locally with the corrected casilla values."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-BASELINE",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
    )

    imported = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500"), "02": Decimal("300")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-BASELINE",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )
    assert imported.external_evidence is not None

    amended = amend_modelo_revision(
        from_filing_record_id=imported.filing_record_id,
        overrides={"01": Decimal("1650")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="under-reported revenue discovered in subsequent audit",
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert amended.amends_filing_record_id == imported.filing_record_id
    refreshed_baseline = get_filing_record(imported.filing_record_id, filing_repository=fr_repo)
    assert refreshed_baseline.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_baseline.superseded_by_filing_record_id == amended.filing_record_id

    # Chronological import/amend event chain. Work-unit creation is
    # also persisted in this catalogue by the shared runtime path.
    catalogue = bv_repo.load()
    chain = tuple(
        e.event_type
        for e in catalogue.for_bucket(work_unit.bucket_id)
        if e.event_type in {BucketEventType.MODELO_FILING_IMPORTED, BucketEventType.MODELO_AMENDED}
    )
    assert chain == (
        BucketEventType.MODELO_FILING_IMPORTED,
        BucketEventType.MODELO_AMENDED,
    )


def test_import_refuses_casilla_ids_not_in_registry(repos: _Repos) -> None:
    """The import path refuses casilla ids the registry does not
    declare for the work unit's modelo / filing_year / period.
    Imported baselines are the legal source of truth for amend
    paths — fabricated casilla ids cannot be silently accepted."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"9999": Decimal("100")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-FABRICATED",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert "9999" in casillas_obj


def test_import_refuses_empty_casilla_values(repos: _Repos) -> None:
    """The import path requires at least one casilla value — a
    zero-value mapping doesn't represent any real receipt."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WHATEVER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_no_casilla_values"


def test_import_refuses_empty_evidence_reference(repos: _Repos) -> None:
    """The import path requires a non-empty evidence reference id —
    without it the baseline can't be traced back to the receipt."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="   ",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_evidence_reference_blank"


def test_import_refuses_justificante_evidence_without_persisted_artifact(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-MISSING",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_missing"


def test_import_refuses_justificante_evidence_without_expected_tax_id(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-NO-TAX-ID",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-NO-TAX-ID",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_tax_id_missing"


def test_import_refuses_justificante_evidence_for_different_period(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-MISMATCH",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period="2T",
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-MISMATCH",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_refuses_justificante_evidence_for_different_taxpayer(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-WRONG-TAXPAYER",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WRONG-TAXPAYER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            expected_tax_id="B12345678",
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_justificante_taxpayer_match_is_case_insensitive(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    persist_justificante_metadata(
        "JUST-CASE-TAXPAYER",
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
        tax_id="X1234567L",
    )

    filing = import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={"01": Decimal("1500")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-CASE-TAXPAYER",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        expected_tax_id="x1234567l",
        clock=_T1,
    )

    assert filing.aeat_accepted is True
    assert filing.external_evidence is not None
    assert filing.external_evidence.reference_id == "JUST-CASE-TAXPAYER"


def test_import_csv_register_refuses_without_enrolled_justificante(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="CSV-MISSING-JUSTIFICANTE",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_justificante_missing"


def test_import_refuses_discarded_work_unit(repos: _Repos) -> None:
    """A discarded work unit cannot accept new imports."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    with pytest.raises(WorkUnitMutationRefusedError):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-LATE",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_import_refuses_unknown_work_unit(repos: _Repos) -> None:
    """A work_unit_id absent from the catalogue is rejected."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        import_external_filing_evidence(
            work_unit_id="0" * 64,
            casilla_values={"01": Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WHATEVER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_amend_locally_filed_still_refused_after_import_path_exists(repos: _Repos) -> None:
    """Adding the import path does NOT loosen the amend evidence
    gate — a locally-filed record still has no ``external_evidence``
    and the amend path still refuses it."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="111",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={
            "03": Decimal("180.25"),
            "06": Decimal("12.10"),
            "09": Decimal("300.00"),
            "12": Decimal("14.40"),
            "15": Decimal("25.00"),
            "18": Decimal("0.50"),
            "21": Decimal("7.00"),
            "24": Decimal("8.00"),
            "27": Decimal("9.00"),
            "29": Decimal("40.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    verified_revision = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    locally_filed = _seed_local_filing_record(
        work_unit=work_unit,
        revision_id=verified_revision.calculation_revision_id,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        filed_at=_T3,
        filed_by="operator-A",
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError, match=r"external_evidence|imported|baseline"):
        amend_modelo_revision(
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={"01": Decimal("1700")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="needed to amend",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
