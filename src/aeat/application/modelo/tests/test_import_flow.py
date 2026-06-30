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
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import (
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.calculations.registry import CasillaId
from ....domain.modelos._calculation_revision import (
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
)
from ....domain.modelos._filing_record import (
    ExternalEvidenceKind,
    ModeloRecordStatus,
)
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
from ._import_flow_support import (
    _IMPORT_EXPENSE_CASILLA,
    _IMPORT_INCOME_CASILLA,
    _M111_ACTIVITY_AMOUNT_CASILLA,
    _M111_ACTIVITY_COUNT_CASILLA,
    _M111_ACTIVITY_WITHHELD_CASILLA,
    _M111_AMENDMENT_CASILLA,
    _M111_EMPLOYMENT_WITHHELD_CASILLA,
    _M111_FORESTRY_WITHHELD_CASILLA,
    _M111_IMAGE_RIGHTS_WITHHELD_CASILLA,
    _M111_IMPUTED_INCOME_WITHHELD_CASILLA,
    _M111_PRIZE_WITHHELD_CASILLA,
    _M111_PROFESSIONAL_WITHHELD_CASILLA,
    _M111_TOTAL_WITHHELD_CASILLA,
    _M303_PRINTED_RESULT_TOKEN,
    _PROFILE_ID,
    _T0,
    _T1,
    _T2,
    _T3,
    _T4,
    _TAX_ID,
    _UNKNOWN_IMPORT_CASILLA,
    _drive_import_persists_filing,
    _import_external_filing,
    _persist_matching_justificante,
    _Repos,
    _repos,
    _seed_local_filing_record,
    _seed_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    yield from _repos(tmp_path)


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
    (_IMPORT_INCOME_CASILLA, Decimal("1500")),
    (_IMPORT_EXPENSE_CASILLA, Decimal("300")),
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

    assert set(observations) == {_IMPORT_INCOME_CASILLA, _IMPORT_EXPENSE_CASILLA}
    assert observations[_IMPORT_INCOME_CASILLA].value == Decimal("1500")
    assert observations[_IMPORT_INCOME_CASILLA].formula_id is None
    assert observations[_IMPORT_INCOME_CASILLA].operand_refs == ()
    assert observations[_IMPORT_INCOME_CASILLA].operand_casilla_refs == ()
    assert observations[_IMPORT_INCOME_CASILLA].legal_refs
    assert observations[_IMPORT_INCOME_CASILLA].source_refs
    assert observations[_IMPORT_EXPENSE_CASILLA].legal_refs
    assert observations[_IMPORT_EXPENSE_CASILLA].source_refs


@pytest.mark.parametrize(("casilla_id", "expected"), _IMPORTED_REVISION_CASILLAS)
def test_import_persists_casilla_value(repos: _Repos, casilla_id: CasillaId, expected: Decimal) -> None:
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
    _persist_matching_justificante(
        "JUST-FIRST",
        work_unit,
        captured_at=_T1,
    )
    first = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
        evidence_reference_id="JUST-FIRST",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )

    _persist_matching_justificante(
        "CSV-SECOND",
        work_unit,
        captured_at=_T2,
    )
    second = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1600")},
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="CSV-SECOND",
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
    _persist_matching_justificante(
        "JUST-BASELINE",
        work_unit,
        captured_at=_T1,
    )

    imported = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500"), _IMPORT_EXPENSE_CASILLA: Decimal("300")},
        evidence_reference_id="JUST-BASELINE",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )
    assert imported.external_evidence is not None

    amended = amend_modelo_revision(
        from_filing_record_id=imported.filing_record_id,
        overrides={_IMPORT_INCOME_CASILLA: Decimal("1650")},
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

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_UNKNOWN_IMPORT_CASILLA: Decimal("100")},
            evidence_reference_id="JUST-FABRICATED",
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert _UNKNOWN_IMPORT_CASILLA in casillas_obj


def test_import_refuses_printed_number_metadata_token(repos: _Repos) -> None:
    """External imports must not treat a printed number as a casilla reference."""

    wu_repo, _, _, _, _ = repos
    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id="2023-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    with pytest.raises(ExternalModeloImportError, match="non-canonical reference tokens") as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_M303_PRINTED_RESULT_TOKEN: Decimal("100")},
            evidence_reference_id="JUST-PRINTED-NUMBER",
            clock=_T1,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == [_M303_PRINTED_RESULT_TOKEN]
    assert "iva.resultado" in str(exc_info.value)


def test_import_refuses_non_string_casilla_keys_without_coercion(repos: _Repos) -> None:
    """Malformed external casilla keys fail before registry membership checks."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={1: Decimal("100")},
            evidence_reference_id="JUST-MALFORMED",
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == ["1"]


def test_import_refuses_empty_casilla_values(repos: _Repos) -> None:
    """The import path requires at least one casilla value — a
    zero-value mapping doesn't represent any real receipt."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={},
            evidence_reference_id="JUST-WHATEVER",
            clock=_T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_no_casilla_values"


def test_import_refuses_empty_evidence_reference(repos: _Repos) -> None:
    """The import path requires a non-empty evidence reference id —
    without it the baseline can't be traced back to the receipt."""

    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
            evidence_reference_id="   ",
            clock=_T1,
        )
    assert raised.value.translated_message == "application.modelo.errors.external_filing_evidence_reference_blank"


def test_import_refuses_justificante_evidence_without_persisted_artifact(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-MISSING",
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_missing"


def test_import_refuses_justificante_evidence_without_expected_tax_id(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUST-NO-TAX-ID",
        work_unit,
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-NO-TAX-ID",
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_tax_id_missing"


def test_import_refuses_justificante_evidence_for_different_period(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUST-MISMATCH",
        work_unit,
        period="2T",
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-MISMATCH",
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_refuses_justificante_evidence_for_different_taxpayer(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUST-WRONG-TAXPAYER",
        work_unit,
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-WRONG-TAXPAYER",
            expected_tax_id="B12345678",
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_justificante_taxpayer_match_is_case_insensitive(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUST-CASE-TAXPAYER",
        work_unit,
        captured_at=_T1,
        tax_id="X1234567L",
    )

    filing = _import_external_filing(
        repos,
        work_unit,
        evidence_reference_id="JUST-CASE-TAXPAYER",
        expected_tax_id="x1234567l",
        clock=_T1,
    )

    assert filing.aeat_accepted is True
    assert filing.external_evidence is not None
    assert filing.external_evidence.reference_id == "JUST-CASE-TAXPAYER"


def test_import_csv_register_refuses_without_enrolled_justificante(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="CSV-MISSING-JUSTIFICANTE",
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_justificante_missing"


def test_import_refuses_discarded_work_unit(repos: _Repos) -> None:
    """A discarded work unit cannot accept new imports."""

    wu_repo, _, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    with pytest.raises(WorkUnitMutationRefusedError):
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-LATE",
            clock=_T2,
        )


def test_import_refuses_unknown_work_unit(repos: _Repos) -> None:
    """A work_unit_id absent from the catalogue is rejected."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        import_external_filing_evidence(
            work_unit_id="0" * 64,
            casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
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
        bucket_id=_PROFILE_ID,
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
            _M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            _M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            _M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            _M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            _M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            _M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            _M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            _M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            _M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            _M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
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
            overrides={_M111_AMENDMENT_CASILLA: Decimal("1700")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="needed to amend",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
