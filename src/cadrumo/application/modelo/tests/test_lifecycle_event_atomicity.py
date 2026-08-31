"""Modelo state transitions commit their promised lifecycle event atomically.

A modelo mutation persists several encrypted catalogues -- the calculation
revision, the filing record, the advanced work-unit pointer -- and promises a
``BucketEvent`` recording the transition. Written as independent saves, the
state lands durably while an event-storage failure leaves the history with no
matching entry and no retryable marker naming the gap: the revision is
``PRESENTADO``, the filed pointer has advanced, and nothing in the audit trail
accounts for it.

These tests pin each transition to one SQL unit of work using real adapters
throughout: a real encrypted-SQLite
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`, the
production catalogue repositories, and the production serializers. Nothing is
stubbed. The failure injected in the rollback cases is the same compare-and-swap
revision guard production uses.

Each single-transaction assertion is paired with an anti-tautology case: the
same catalogues persisted through independent saves must be observed as more
than one transaction, or a recorder that could never report a seam would make
the primary assertion vacuous.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.buckets import BucketEventObjectType, BucketEventType
from ....domain.modelos import ExternalEvidenceKind, WorkUnit
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.write_unit_recorder import WriteUnitRecorder
from .._work_lifecycle import (
    create_work_unit,
    discard_work_unit,
    get_work_unit,
    rename_work_unit,
)
from ..external_import_actions import import_external_filing_evidence
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "13a00000-0000-4000-8000-0000000000a1"
_TAX_ID = "X1234567L"
_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_STALE_REVISION_ID = "0" * 64
#: Doubles as the justificante CSV, which AEAT prints as an unbroken
#: alphanumeric run -- the model enforces ^[A-Z0-9]{8,32}$, so the
#: hyphenated form this used to carry could never be a real CSV.
_EVIDENCE_REFERENCE = "JUST2026130Q1ATOMIC"

_INCOME_CASILLA: CasillaId = validated_casilla_id("01", surface="test casilla id")
_EXPENSE_CASILLA: CasillaId = validated_casilla_id("02", surface="test casilla id")

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value=_TAX_ID),
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
)


@dataclass(frozen=True, slots=True)
class _Fixture:
    """The live engine plus the four catalogue repositories sharing it."""

    engine: Engine
    work_units: WorkUnitCatalogueRepository
    calculations: CalculationRevisionCatalogueRepository
    filings: ModeloRecordCatalogueRepository
    events: BucketEventHistoryRepository


@pytest.fixture
def fixture(tmp_path: Path) -> Iterator[_Fixture]:
    """Yield real catalogue repositories over one encrypted SQLite database."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        objects = profile.repository
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_PROFILE_ID,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        yield _Fixture(
            engine=profile.repository.engine,
            work_units=WorkUnitCatalogueRepository(objects=objects),
            calculations=CalculationRevisionCatalogueRepository(objects=objects),
            filings=ModeloRecordCatalogueRepository(objects=objects),
            events=BucketEventHistoryRepository(objects=objects),
        )


def _seed_work_unit(fixture: _Fixture) -> WorkUnit:
    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=fixture.work_units,
        clock=_T0,
    )
    persist_justificante_metadata(
        _EVIDENCE_REFERENCE,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        captured_at=_T1,
        tax_id=_TAX_ID,
    )
    return work_unit


def _import(fixture: _Fixture, work_unit: WorkUnit):
    return import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values={_INCOME_CASILLA: Decimal("1500"), _EXPENSE_CASILLA: Decimal("300")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=_EVIDENCE_REFERENCE,
        actor="aeat-import",
        work_unit_repository=fixture.work_units,
        calculation_repository=fixture.calculations,
        filing_repository=fixture.filings,
        bucket_event_repository=fixture.events,
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )


def test_external_import_commits_state_and_event_in_one_transaction(fixture: _Fixture) -> None:
    """The import's revision, filing, pointer, and event share one transaction.

    A commit falling between them is the seam the finding names: the imported
    filing and the advanced filed-revision pointer would survive an
    event-storage failure with the history left at its pre-import count.
    """
    work_unit = _seed_work_unit(fixture)
    recorder = WriteUnitRecorder(fixture.engine)

    with recorder.recording():
        _import(fixture, work_unit)

    assert recorder.commits_between_writes() == 0


def test_split_import_write_shape_commits_between_catalogues(fixture: _Fixture) -> None:
    """Anti-tautology: the recorder does report a seam when one exists.

    Persisting the same four catalogues through independent saves -- the shape
    the import replaced -- must be observed as more than one transaction.
    """
    work_unit = _seed_work_unit(fixture)
    _import(fixture, work_unit)
    revisions = fixture.calculations.load()
    filings = fixture.filings.load()
    work_units = fixture.work_units.load()
    events = fixture.events.load()
    recorder = WriteUnitRecorder(fixture.engine)

    with recorder.recording():
        fixture.calculations.save(revisions)
        fixture.filings.save(filings)
        fixture.work_units.save(work_units)
        fixture.events.save(events)

    assert recorder.commits_between_writes() >= 1


def test_external_import_persists_its_filing_imported_event(fixture: _Fixture) -> None:
    """A valid import leaves coherent state and exactly one matching event.

    The parity case the atomicity assertions rest on: co-committing the event
    must not change what a successful import records.
    """
    work_unit = _seed_work_unit(fixture)
    filing = _import(fixture, work_unit)

    revision = fixture.calculations.load().get(filing.calculation_revision_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.PRESENTADO
    refreshed = get_work_unit(work_unit.work_unit_id, repository=fixture.work_units)
    assert refreshed.filed_calculation_revision_id == filing.calculation_revision_id
    assert refreshed.current_filing_record_id == filing.filing_record_id

    imported = [
        event
        for event in fixture.events.load().events.values()
        if event.event_type is BucketEventType.MODELO_FILING_IMPORTED
    ]
    assert len(imported) == 1
    assert imported[0].object_type is BucketEventObjectType.FILING_RECORD
    assert imported[0].object_id == filing.filing_record_id
    assert imported[0].bucket_id == work_unit.bucket_id
    assert imported[0].payload["calculation_revision_id"] == filing.calculation_revision_id


def test_event_write_failure_rolls_back_every_import_catalogue(fixture: _Fixture) -> None:
    """A conflict on the event write leaves no revision, filing, or pointer.

    The fault is the production compare-and-swap guard: the event-history write
    carries a revision id that no longer matches the stored row, so the conflict
    is raised inside the same unit of work carrying the import's three state
    catalogues. Nothing may survive it -- which is exactly what an
    event-emitted-afterwards shape could not guarantee.
    """
    work_unit = _seed_work_unit(fixture)
    _import(fixture, work_unit)
    baseline_revisions = fixture.calculations.load()
    baseline_filings = fixture.filings.load()
    baseline_work_units = fixture.work_units.load()
    baseline_events = fixture.events.load()

    conflicting_event_write = fixture.events.to_secure_object_write(
        baseline_events,
        expected_revision_id=_STALE_REVISION_ID,
    )

    with pytest.raises(SecureObjectRevisionConflictError):
        fixture.filings.save_with_secure_object_writes(
            baseline_filings,
            (
                fixture.calculations.to_secure_object_write(baseline_revisions),
                fixture.work_units.to_secure_object_write(baseline_work_units),
                conflicting_event_write,
            ),
        )

    assert fixture.calculations.load() == baseline_revisions
    assert fixture.filings.load() == baseline_filings
    assert fixture.work_units.load() == baseline_work_units
    assert fixture.events.load() == baseline_events


def test_work_unit_creation_commits_state_and_event_in_one_transaction(fixture: _Fixture) -> None:
    """Creating a work unit commits the unit and its CREATED event together.

    The lifecycle transitions saved the work-unit catalogue and emitted the
    event through a separate write, so an event-storage failure left the unit
    durable while the history had no record it was ever created — the same
    durable-but-unrecorded shape as the import path, on the transition that
    brings the work unit into existence.
    """
    recorder = WriteUnitRecorder(fixture.engine)

    with recorder.recording():
        create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2019-y-siguientes",
            repository=fixture.work_units,
            clock=_T0,
        )

    assert recorder.commits_between_writes() == 0


def test_split_work_unit_creation_write_shape_commits_between_catalogues(fixture: _Fixture) -> None:
    """Anti-tautology: the recorder reports a seam on the shape this replaced.

    Persisting the same two catalogues through independent saves — the pre-fix
    shape — must be observed as more than one transaction, or the assertion
    above could not fail.
    """
    _seed_work_unit(fixture)
    work_units = fixture.work_units.load()
    events = fixture.events.load()
    recorder = WriteUnitRecorder(fixture.engine)

    with recorder.recording():
        fixture.work_units.save(work_units)
        fixture.events.save(events)

    assert recorder.commits_between_writes() >= 1


def test_work_unit_creation_persists_its_created_event(fixture: _Fixture) -> None:
    """The positive control: the event is really written, not merely co-committed.

    A single-transaction assertion says nothing about whether the event exists;
    without this, dropping the event write entirely would still report zero
    commits between writes.
    """
    work_unit = _seed_work_unit(fixture)

    events = fixture.events.load()
    created = [
        event
        for event in events
        if event.event_type is BucketEventType.MODELO_WORK_UNIT_CREATED and event.object_id == work_unit.work_unit_id
    ]

    assert len(created) == 1
    assert created[0].object_type is BucketEventObjectType.WORK_UNIT


def test_work_unit_rename_and_discard_commit_their_events_in_one_transaction(fixture: _Fixture) -> None:
    """Rename and discard each commit their state and event together.

    Both carried the same separate-write shape as creation, so each is pinned
    here rather than assuming the creation fix covers the whole module.
    """
    work_unit = _seed_work_unit(fixture)

    rename_recorder = WriteUnitRecorder(fixture.engine)
    with rename_recorder.recording():
        rename_work_unit(
            work_unit_id=work_unit.work_unit_id,
            new_name="Renamed unit",
            actor="operator",
            repository=fixture.work_units,
            clock=_T1,
        )
    assert rename_recorder.commits_between_writes() == 0

    discard_recorder = WriteUnitRecorder(fixture.engine)
    with discard_recorder.recording():
        discard_work_unit(
            work_unit_id=work_unit.work_unit_id,
            actor="operator",
            reason="superseded",
            repository=fixture.work_units,
            clock=_T1,
        )
    assert discard_recorder.commits_between_writes() == 0

    events = fixture.events.load()
    emitted = {event.event_type for event in events if event.object_id == work_unit.work_unit_id}
    assert BucketEventType.MODELO_WORK_UNIT_RENAMED in emitted
    assert BucketEventType.MODELO_WORK_UNIT_DISCARDED in emitted
