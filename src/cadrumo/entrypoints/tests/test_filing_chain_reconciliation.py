"""Reconciliation of AEAT register entries against a period's filing chain.

Runs the service over an isolated encrypted profile with the bundled registry
and the real profile repositories, including both observation layers.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.entrypoints.tests.profile_persistence.import_flow_support import seed_ready_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.modelo.action_errors import ExternalModeloImportError
from cadrumo.application.modelo.external_import_actions import prepare_external_filing_revision
from cadrumo.application.modelo.filing_chain_reconciliation import (
    AeatRegisterEntry,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationPorts,
    reconcile_aeat_register_entry,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    AeatRegisterRef,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url

from ...core.hashing import sha256_hex

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "13000000-0000-4000-8000-0000000000c1"
_TAX_ID = "X1234567L"
_REVISION_ID = "2019-y-siguientes"
_PERIOD = Period.from_year_and_code(2026, "1T")
_T0 = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 12, 9, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 14, 9, 0, tzinfo=UTC)
_T4 = datetime(2026, 4, 16, 9, 0, tzinfo=UTC)
_C01: CasillaId = validated_casilla_id("01")
_C02: CasillaId = validated_casilla_id("02")
_M111_RESULT: CasillaId = validated_casilla_id("30")


@dataclass(frozen=True, slots=True)
class _Profile:
    ports: FilingReconciliationPorts
    work_units: WorkUnitCatalogueRepository
    revisions: CalculationRevisionCatalogueRepository
    filings: ModeloRecordCatalogueRepository
    events: BucketEventHistoryRepository
    observations: CalculationObservationRepository


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[_Profile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository
        seed_ready_profile(bucket_id=_BUCKET_ID)
        work_units = WorkUnitCatalogueRepository(objects=objects)
        revisions = CalculationRevisionCatalogueRepository(objects=objects)
        filings = ModeloRecordCatalogueRepository(objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        observations = CalculationObservationRepository()
        ports = FilingReconciliationPorts(
            filing_repository=filings,
            calculation_repository=revisions,
            work_lifecycle=WorkLifecyclePorts(work_unit_repository=work_units, bucket_event_repository=events),
            observation_repository=observations,
            justificante_repository=JustificanteRepository(),
        )
        yield _Profile(ports, work_units, revisions, filings, events, observations)


def _work_unit(profile: _Profile, operation: PinnedAuthorityOperation, *, modelo: str = "130") -> WorkUnit:
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2026,
        period=_PERIOD,
        revision_id=_REVISION_ID,
        ports=profile.ports.work_lifecycle,
        clock=_T0,
        operation=operation,
    )


def _entry(
    expediente_id: str,
    *,
    modelo: str = "130",
    values: Mapping[CasillaId, Decimal] | None = None,
    declared_kind: FilingDeclarationKind | None = None,
    evidence_kind: ExternalEvidenceKind = ExternalEvidenceKind.AEAT_CSV_REGISTER,
    justificante: Justificante | None = None,
) -> AeatRegisterEntry:
    return AeatRegisterEntry(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2026,
        period=_PERIOD,
        register=AeatRegisterRef(
            expediente_id=expediente_id,
            csv=justificante.csv if justificante is not None else None,
            presented_at=_T1,
        ),
        evidence_kind=evidence_kind,
        tax_id=_TAX_ID,
        declared_kind=declared_kind,
        justificante=justificante,
        casilla_values=values,
    )


def _justificante(csv: str, *, modelo: str, total_a_ingresar: Decimal) -> Justificante:
    pdf_digest = hashlib.sha256(f"synthetic justificante {csv}".encode()).hexdigest()
    return Justificante(
        csv=csv,
        modelo=modelo,
        period=_PERIOD,
        ejercicio="2026",
        presented_at=_T1.replace(tzinfo=None),
        tax_id=_TAX_ID,
        total_a_ingresar=total_a_ingresar,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=source_pdf_reference_path(pdf_digest),
        source_pdf_sha256=pdf_digest,
        parsed_at=_T1,
    )


def _reconcile(profile: _Profile, operation: PinnedAuthorityOperation, entry: AeatRegisterEntry, *, at: datetime):
    return reconcile_aeat_register_entry(
        entry,
        ports=profile.ports,
        operation=operation,
        actor="aeat-register",
        clock=at,
    )


def _seed_local_filing(
    profile: _Profile,
    work_unit: WorkUnit,
    values: Mapping[CasillaId, Decimal],
    *,
    at: datetime,
    kind: FilingDeclarationKind = FilingDeclarationKind.ORIGINAL,
    amends: ModeloRecord | None = None,
) -> ModeloRecord:
    """Persist a presented local revision and its pending chain entry."""
    draft = prepare_external_filing_revision(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=values,
        source_lexical_values_by_casilla_id=None,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="local-draft",
        filing_instance_evidence=None,
        expected_tax_id=None,
        actor="operator-A",
        now=at,
        work_unit_repository=profile.work_units,
        calculation_repository=profile.revisions,
        justificante_repository=profile.ports.justificante_repository,
    )
    profile.revisions.save(draft.revisions)
    profile.observations.save(
        profile.observations.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=work_unit.modelo,
                filing_year=2026,
                period=_PERIOD.registry_token,
                observations=draft.revision.observations,
            ),
            source_kind=ObservationSourceKind.APP_FILING,
            stamped_revision_id=work_unit.revision_id,
            captured_at=at,
        ),
    )
    record_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=draft.revision.calculation_revision_id,
        filed_by="operator-A",
    )
    pending = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=draft.revision.calculation_revision_id,
        bucket_id=_BUCKET_ID,
        modelo=work_unit.modelo,
        filing_year=2026,
        period=_PERIOD,
        filed_at=at,
        filed_by="operator-A",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=kind,
        amends_filing_record_id=amends.filing_record_id if amends is not None else None,
    )
    catalogue = profile.filings.load()
    if amends is not None:
        catalogue = upsert_filing_record(
            catalogue,
            catalogue.records[amends.filing_record_id].model_copy(
                update={
                    "status": ModeloRecordStatus.SUPERSEDIDO,
                    "superseded_at": at,
                    "superseded_by_filing_record_id": record_id,
                },
            ),
        )
    profile.filings.save(upsert_filing_record(catalogue, pending))
    return pending


def _reconciled_events(profile: _Profile):
    return [
        event
        for event in profile.events.load().events.values()
        if event.event_type is BucketEventType.MODELO_FILING_RECONCILED
    ]


def _codes(result) -> set[FilingReconciliationNoticeCode]:
    return {notice.code for notice in result.notices}


def test_first_register_entry_is_appended_as_confirmed_original(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation)

    result = _reconcile(
        profile, operation, _entry("EXP-1", values={_C01: Decimal("1500"), _C02: Decimal("300")}), at=_T1
    )

    assert result.outcome is FilingReconciliationOutcome.APPENDED
    record = profile.filings.load().records[result.filing_record_id]
    assert (record.origin, record.confirmation, record.declaration_kind) == (
        FilingOrigin.AEAT,
        AeatConfirmationState.CONFIRMADA,
        FilingDeclarationKind.ORIGINAL,
    )
    assert record.status is ModeloRecordStatus.VIGENTE
    assert record.aeat_register is not None and record.aeat_register.expediente_id == "EXP-1"
    assert record.amends_filing_record_id is None
    revision = profile.revisions.load().get(record.calculation_revision_id)
    assert revision is not None and revision.state is CalculationRevisionState.PRESENTADO
    assert dict(revision.casilla_values) == {_C01: Decimal("1500"), _C02: Decimal("300")}
    advanced = profile.work_units.load().get(work_unit.work_unit_id)
    assert advanced is not None and advanced.current_filing_record_id == record.filing_record_id
    [event] = _reconciled_events(profile)
    assert event.object_id == record.filing_record_id
    assert event.payload["outcome"] == "appended"


def test_re_reading_a_recorded_register_entry_changes_nothing(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    _work_unit(profile, operation)
    entry = _entry("EXP-1", values={_C01: Decimal("1500")})
    first = _reconcile(profile, operation, entry, at=_T1)
    catalogue_before = profile.filings.load()

    again = _reconcile(profile, operation, entry, at=_T2)

    assert again.outcome is FilingReconciliationOutcome.ALREADY_RECORDED
    assert again.filing_record_id == first.filing_record_id
    assert profile.filings.load() == catalogue_before
    assert len(_reconciled_events(profile)) == 1


def test_declared_correction_after_confirmed_entry_amends_it(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    _work_unit(profile, operation)
    original = _reconcile(profile, operation, _entry("EXP-1", values={_C01: Decimal("1500")}), at=_T1)

    correction = _reconcile(
        profile,
        operation,
        _entry("EXP-2", values={_C01: Decimal("1700")}, declared_kind=FilingDeclarationKind.COMPLEMENTARIA),
        at=_T2,
    )

    assert correction.outcome is FilingReconciliationOutcome.APPENDED
    assert correction.affected_filing_record_ids == (original.filing_record_id,)
    catalogue = profile.filings.load()
    new = catalogue.records[correction.filing_record_id]
    old = catalogue.records[original.filing_record_id]
    assert new.amends_filing_record_id == old.filing_record_id
    assert new.declaration_kind is FilingDeclarationKind.COMPLEMENTARIA
    assert old.status is ModeloRecordStatus.SUPERSEDIDO
    assert old.superseded_by_filing_record_id == new.filing_record_id
    assert old.confirmation is AeatConfirmationState.CONFIRMADA
    assert old.aeat_register is not None and old.aeat_register.expediente_id == "EXP-1"
    assert old.external_evidence is not None and old.external_evidence.reference_id == "EXP-1"
    assert catalogue.current_for(bucket_id=_BUCKET_ID, modelo="130", filing_year=2026, period=_PERIOD) == new
    assert catalogue.latest_confirmed_for(bucket_id=_BUCKET_ID, modelo="130", filing_year=2026, period=_PERIOD) == new
    old_revision = profile.revisions.load().get(old.calculation_revision_id)
    assert old_revision is not None and old_revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO


def test_undeclared_kind_after_confirmed_entry_is_unverifiable(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    _work_unit(profile, operation)
    original = _reconcile(profile, operation, _entry("EXP-1", values={_C01: Decimal("1500")}), at=_T1)
    catalogue_before = profile.filings.load()

    result = _reconcile(profile, operation, _entry("EXP-2", values={_C01: Decimal("1700")}), at=_T2)

    assert result.outcome is FilingReconciliationOutcome.UNVERIFIABLE
    assert _codes(result) == {FilingReconciliationNoticeCode.DECLARATION_KIND_UNDETERMINED}
    assert result.filing_record_id == original.filing_record_id
    assert profile.filings.load() == catalogue_before
    assert [event.payload["outcome"] for event in _reconciled_events(profile)].count("unverifiable") == 1


def test_matching_casillas_confirm_the_pending_entry(profile: _Profile, operation: PinnedAuthorityOperation) -> None:
    work_unit = _work_unit(profile, operation)
    pending = _seed_local_filing(profile, work_unit, {_C01: Decimal("1500"), _C02: Decimal("300")}, at=_T1)

    result = _reconcile(
        profile,
        operation,
        _entry("EXP-1", values={_C01: Decimal("1500.00"), _C02: Decimal("300")}),
        at=_T2,
    )

    assert result.outcome is FilingReconciliationOutcome.CONFIRMED
    assert result.filing_record_id == pending.filing_record_id
    assert result.evidence_basis == "casillas"
    assert result.differing_casilla_ids == ()
    catalogue = profile.filings.load()
    assert len(catalogue) == 1
    confirmed = catalogue.records[pending.filing_record_id]
    assert confirmed.origin is FilingOrigin.LOCAL
    assert confirmed.confirmation is AeatConfirmationState.CONFIRMADA
    assert confirmed.aeat_accepted is True
    assert confirmed.external_evidence is not None
    assert confirmed.external_evidence.reference_id == "EXP-1"
    assert confirmed.aeat_register is not None and confirmed.aeat_register.expediente_id == "EXP-1"
    layers = profile.observations.load_observation_layers("130", _PERIOD)
    assert layers.pending_local is None
    assert layers.official is not None
    assert layers.official.source_kind is ObservationSourceKind.AEAT_CSV_REGISTER
    assert layers.official.source_metadata["filing_record_id"] == pending.filing_record_id
    assert layers.official.observation.casilla_values[_C01] == Decimal("1500")


def test_a_register_entry_older_than_the_pending_entry_never_supersedes_it_in_the_past(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation)
    pending = _seed_local_filing(profile, work_unit, {_C01: Decimal("1500")}, at=_T3)

    result = _reconcile(profile, operation, _entry("EXP-1", values={_C01: Decimal("1700")}), at=_T1)

    assert result.outcome is FilingReconciliationOutcome.CONTRADICTED
    discrepant = profile.filings.load().records[pending.filing_record_id]
    assert discrepant.confirmation is AeatConfirmationState.DISCREPANTE
    assert discrepant.superseded_at == pending.filed_at


def test_different_casillas_contradict_the_pending_correction(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation)
    confirmed = _reconcile(profile, operation, _entry("EXP-1", values={_C01: Decimal("1500")}), at=_T1)
    baseline = profile.filings.load().records[confirmed.filing_record_id]
    pending = _seed_local_filing(
        profile,
        work_unit,
        {_C01: Decimal("1600")},
        at=_T2,
        kind=FilingDeclarationKind.COMPLEMENTARIA,
        amends=baseline,
    )

    result = _reconcile(
        profile,
        operation,
        _entry(
            "EXP-2",
            values={_C01: Decimal("1700"), _C02: Decimal("50")},
            declared_kind=FilingDeclarationKind.COMPLEMENTARIA,
        ),
        at=_T3,
    )

    assert result.outcome is FilingReconciliationOutcome.CONTRADICTED
    assert result.differing_casilla_ids == (_C01, _C02)
    assert set(result.affected_filing_record_ids) == {pending.filing_record_id, baseline.filing_record_id}
    catalogue = profile.filings.load()
    appended = catalogue.records[result.filing_record_id]
    assert appended.status is ModeloRecordStatus.VIGENTE
    assert appended.origin is FilingOrigin.AEAT
    assert appended.amends_filing_record_id == baseline.filing_record_id
    discrepant = catalogue.records[pending.filing_record_id]
    assert discrepant.confirmation is AeatConfirmationState.DISCREPANTE
    assert discrepant.status is ModeloRecordStatus.SUPERSEDIDO
    assert discrepant.superseded_by_filing_record_id == appended.filing_record_id
    assert catalogue.records[baseline.filing_record_id].superseded_by_filing_record_id == appended.filing_record_id
    assert (
        catalogue.latest_confirmed_for(bucket_id=_BUCKET_ID, modelo="130", filing_year=2026, period=_PERIOD) == appended
    )
    pending_revision = profile.revisions.load().get(pending.calculation_revision_id)
    assert pending_revision is not None
    assert pending_revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
    layers = profile.observations.load_observation_layers("130", _PERIOD)
    assert layers.pending_local is None
    assert layers.official is not None
    assert layers.official.source_metadata["filing_record_id"] == appended.filing_record_id
    assert layers.official.observation.casilla_values[_C01] == Decimal("1700")


def test_entry_without_content_leaves_the_pending_entry_unstamped(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation)
    pending = _seed_local_filing(profile, work_unit, {_C01: Decimal("1500")}, at=_T1)
    catalogue_before = profile.filings.load()

    result = _reconcile(profile, operation, _entry("EXP-1"), at=_T2)

    assert result.outcome is FilingReconciliationOutcome.UNVERIFIABLE
    assert result.filing_record_id == pending.filing_record_id
    assert _codes(result) == {FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE}
    assert profile.filings.load() == catalogue_before
    [event] = _reconciled_events(profile)
    assert event.payload["notice_count"] == "1"
    assert event.payload["notice_codes_sha256"] == sha256_hex(
        FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE.value.encode("utf-8")
    )


def test_receipt_without_a_declared_total_map_is_unverifiable(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation)
    _seed_local_filing(profile, work_unit, {_C01: Decimal("1500")}, at=_T1)
    receipt = _justificante("M130RECEIPT0001", modelo="130", total_a_ingresar=Decimal("1500"))

    result = _reconcile(
        profile,
        operation,
        _entry("EXP-1", evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF, justificante=receipt),
        at=_T2,
    )

    assert result.outcome is FilingReconciliationOutcome.UNVERIFIABLE
    assert [(notice.code, notice.context.get("reason")) for notice in result.notices] == [
        (FilingReconciliationNoticeCode.RECEIPT_TOTALS_NOT_RECONCILED, "map_not_declared"),
    ]
    assert profile.ports.justificante_repository.load(receipt.csv) == receipt


def test_matching_receipt_total_confirms_with_weaker_evidence(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation, modelo="111")
    pending = _seed_local_filing(profile, work_unit, {_M111_RESULT: Decimal("40.00")}, at=_T1)
    receipt = _justificante("M111RECEIPT0001", modelo="111", total_a_ingresar=Decimal("40.00"))

    result = _reconcile(
        profile,
        operation,
        _entry(
            "EXP-111",
            modelo="111",
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            justificante=receipt,
        ),
        at=_T4,
    )

    assert result.outcome is FilingReconciliationOutcome.CONFIRMED
    assert result.evidence_basis == "receipt_totals"
    assert _codes(result) == {FilingReconciliationNoticeCode.RECEIPT_TOTALS_ONLY}
    confirmed = profile.filings.load().records[pending.filing_record_id]
    assert confirmed.external_evidence is not None
    assert confirmed.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert confirmed.external_evidence.reference_id == receipt.csv


def test_disagreeing_receipt_total_without_casillas_is_unverifiable(
    profile: _Profile, operation: PinnedAuthorityOperation
) -> None:
    work_unit = _work_unit(profile, operation, modelo="111")
    pending = _seed_local_filing(profile, work_unit, {_M111_RESULT: Decimal("40.00")}, at=_T1)
    receipt = _justificante("M111RECEIPT0002", modelo="111", total_a_ingresar=Decimal("41.00"))

    result = _reconcile(
        profile,
        operation,
        _entry(
            "EXP-111",
            modelo="111",
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            justificante=receipt,
        ),
        at=_T4,
    )

    assert result.outcome is FilingReconciliationOutcome.UNVERIFIABLE
    assert result.evidence_basis == "receipt_totals"
    assert _codes(result) == {FilingReconciliationNoticeCode.RECEIPT_TOTALS_MISMATCH}
    unchanged = profile.filings.load().records[pending.filing_record_id]
    assert unchanged.confirmation is AeatConfirmationState.PENDIENTE
    assert unchanged.external_evidence is None


def test_register_entry_refuses_a_receipt_for_another_period(operation: PinnedAuthorityOperation) -> None:
    receipt = _justificante("M130RECEIPT0009", modelo="130", total_a_ingresar=Decimal("1"))
    with pytest.raises(ExternalModeloImportError) as refusal:
        AeatRegisterEntry(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
            register=AeatRegisterRef(expediente_id="EXP-9", csv=receipt.csv),
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            tax_id=_TAX_ID,
            justificante=receipt,
        )
    assert refusal.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"
