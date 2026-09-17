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

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.tests.import_flow_support import (
    _IMPORT_EXPENSE_CASILLA,
    _IMPORT_INCOME_CASILLA,
    _PROFILE_ID,
    _T1,
    _T2,
    _TAX_ID,
    _drive_import_persists_filing,
    _import_external_filing,
    _persist_matching_justificante,
    _Repos,
    _seed_work_unit,
    repos,
)
from cadrumo.application.modelo.action_errors import ExternalModeloImportError
from cadrumo.application.modelo.amendment_actions import amend_modelo_revision
from cadrumo.application.modelo.calculation_actions import get_calculation_revision
from cadrumo.application.modelo.filing_actions import get_filing_record
from cadrumo.application.modelo.work_lifecycle import get_work_unit
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind, ModeloRecordStatus
from cadrumo.entrypoints.adapter_composition import (
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_filing_action_ports,
    build_work_lifecycle_ports,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def test_import_filing_is_current_and_accepted(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    assert outcome.filing.status is ModeloRecordStatus.VIGENTE
    assert outcome.filing.aeat_accepted is True


def test_import_filing_carries_external_evidence_metadata(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    evidence = outcome.filing.external_evidence
    assert evidence is not None
    assert evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert evidence.reference_id == "JUST2026303Q1OPERATOR1"
    assert evidence.imported_at == _T1


def test_import_filing_records_no_amendment_link(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    assert outcome.filing.amends_filing_record_id is None
    assert outcome.filing.filed_at == _T1


_IMPORTED_REVISION_CASILLAS = (
    (_IMPORT_INCOME_CASILLA, Decimal("1500")),
    (_IMPORT_EXPENSE_CASILLA, Decimal("300")),
)


def test_import_persists_filed_calculation_revision(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        revision = get_calculation_revision(
            outcome.filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
    assert revision.state is CalculationRevisionState.PRESENTADO
    assert revision.amendment_identity is None  # import is not an amendment


def test_import_persists_registry_grounded_casilla_observations(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        revision = get_calculation_revision(
            outcome.filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
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
def test_import_persists_casilla_value(
    repos: _Repos, casilla_id: CasillaId, expected: Decimal, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        revision = get_calculation_revision(
            outcome.filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
    assert revision.casilla_values[casilla_id] == expected


def test_import_work_unit_pointers_advance_to_new_filing(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    _wu_repo, _, _, _, _ = repos
    refreshed_wu = get_work_unit(
        outcome.work_unit.work_unit_id,
        ports=build_work_lifecycle_ports(bucket_id=outcome.work_unit.bucket_id),
    )
    assert refreshed_wu.filed_calculation_revision_id == outcome.filing.calculation_revision_id
    assert refreshed_wu.current_filing_record_id == outcome.filing.filing_record_id


def test_import_emits_single_modelo_filing_reconciled_event(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_RECONCILED,),
    )
    assert len(events) == 1
    assert events[0].object_type is BucketEventObjectType.FILING_RECORD
    assert events[0].object_id == outcome.filing.filing_record_id


_IMPORTED_EVENT_PAYLOAD_EXPECTATIONS = (
    ("outcome", "appended"),
    ("evidence_kind", "aeat_justificante_pdf"),
    # A receipt import knows the CSV, never the register expediente.
    ("aeat_expediente_id", ""),
    ("affected_filing_record_count", "0"),
)


@pytest.mark.parametrize(("payload_key", "expected"), _IMPORTED_EVENT_PAYLOAD_EXPECTATIONS)
def test_import_event_payload_records_field(
    repos: _Repos, payload_key: str, expected: str, *, operation: PinnedAuthorityOperation
) -> None:
    outcome = _drive_import_persists_filing(repos, operation=operation)
    _, _, _, _, bv_repo = repos
    events = bv_repo.load().for_bucket(
        outcome.work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_RECONCILED,),
    )
    assert events[0].payload[payload_key] == expected


def test_import_of_a_declared_correction_amends_the_prior_filing(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A second import for the same (bucket, modelo, year, period), declared as
    a correction, supersedes and amends the prior confirmed filing. The
    reconciliation event names the prior entry it affected."""

    wu_repo, _cr_repo, _fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, bv_repo, operation=operation)
    _persist_matching_justificante(
        "JUSTFIRST01",
        work_unit,
        captured_at=_T1,
    )
    first = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
        evidence_reference_id="JUSTFIRST01",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )

    _persist_matching_justificante(
        "CSVSECOND01",
        work_unit,
        captured_at=_T2,
    )
    second = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1600")},
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="CSVSECOND01",
        expected_tax_id=_TAX_ID,
        clock=_T2,
        declared_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )

    refreshed_first = get_filing_record(
        first.filing_record_id,
        ports=build_filing_action_ports(bucket_id=work_unit.bucket_id),
    )
    assert refreshed_first.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_first.superseded_by_filing_record_id == second.filing_record_id

    with bundled_indexed_authority().operation() as operation:
        refreshed_first_revision = get_calculation_revision(
            first.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
        )
    assert refreshed_first_revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO

    assert second.status is ModeloRecordStatus.VIGENTE
    assert second.external_evidence is not None
    assert second.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER
    assert second.amends_filing_record_id == first.filing_record_id

    catalogue = bv_repo.load()
    reconciled = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILING_RECONCILED,),
    )
    assert len(reconciled) == 2
    assert reconciled[0].payload["affected_filing_record_count"] == "0"
    assert reconciled[1].payload["affected_filing_record_count"] == "1"
    assert reconciled[1].payload["affected_filing_record_ids_sha256"] == sha256_hex(
        first.filing_record_id.encode("utf-8")
    )


def test_import_after_a_confirmed_filing_without_a_declared_kind_is_refused(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, bv_repo, operation=operation)
    _persist_matching_justificante("JUSTFIRST02", work_unit, captured_at=_T1)
    _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
        evidence_reference_id="JUSTFIRST02",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )
    before = fr_repo.load()

    with pytest.raises(ExternalModeloImportError) as refusal:
        _import_external_filing(
            repos,
            work_unit,
            casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1600")},
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="CSVSECOND02",
            clock=_T2,
        )

    assert refusal.value.translated_message == "application.modelo.errors.external_import_unverifiable"
    assert fr_repo.load() == before


def test_import_then_amend_unlocks_amendment_path(repos: _Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The import path produces a baseline the amend path accepts.
    This is the canonical production flow for correcting an
    externally-filed return: import official evidence, then amend
    locally with the corrected casilla values."""

    wu_repo, _cr_repo, _fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, bv_repo, operation=operation)
    _persist_matching_justificante(
        "JUSTBASELINE1",
        work_unit,
        captured_at=_T1,
    )

    imported = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500"), _IMPORT_EXPENSE_CASILLA: Decimal("300")},
        evidence_reference_id="JUSTBASELINE1",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )
    assert imported.external_evidence is not None

    with bundled_indexed_authority().operation() as operation:
        amended = amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            from_filing_record_id=imported.filing_record_id,
            overrides={_IMPORT_INCOME_CASILLA: Decimal("1650")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="under-reported revenue discovered in subsequent audit",
            actor="operator-A",
            clock=_T2,
        )

    assert amended.amends_filing_record_id == imported.filing_record_id
    refreshed_baseline = get_filing_record(
        imported.filing_record_id,
        ports=build_filing_action_ports(bucket_id=work_unit.bucket_id),
    )
    assert refreshed_baseline.status is ModeloRecordStatus.SUPERSEDIDO
    assert refreshed_baseline.superseded_by_filing_record_id == amended.filing_record_id

    # Chronological import/amend event chain. Work-unit creation is
    # also persisted in this catalogue by the shared runtime path.
    catalogue = bv_repo.load()
    chain = tuple(
        e.event_type
        for e in catalogue.for_bucket(work_unit.bucket_id)
        if e.event_type in {BucketEventType.MODELO_FILING_RECONCILED, BucketEventType.MODELO_AMENDED}
    )
    assert chain == (
        BucketEventType.MODELO_FILING_RECONCILED,
        BucketEventType.MODELO_AMENDED,
    )
