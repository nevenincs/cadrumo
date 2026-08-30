"""Real-behavior tests for the encrypted reconciliation-record store.

The reconciliation detail no longer rides in the ``MODELO_RECONCILED``
bucket-event payload. It is persisted as a
:class:`~application.modelo.ModeloReconciliationRecord` in the
``AUDIT``-class profile-scoped
:data:`~adapters.persistence.storage.MODELO_RECONCILIATION_RECORDS_NAMESPACE`
namespace, co-written with the slim event in one SQL unit of work.

Two properties of that store are correctness risks in encrypted storage rather
than matters of effort, so each carries a gate here rather than a review:

* The object key must admit N reconciliations per work unit without collapsing
  them, and must admit the runs that carry no persisted calculation revision at
  all. A key that silently collapsed runs would destroy exactly the history the
  store exists to preserve.
* The record and the event must land together. A crash between them would
  desynchronise the event log from the detail store.

Every test drives the real stack: real
:class:`~tests.master_key.EphemeralMasterKeyProvider`, real per-bucket SQLite,
real serializer, real production write and read paths. No doubles.
"""

from __future__ import annotations

import json
import textwrap
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....application.modelo.reconciliation import (
    ModeloReconciliationCommand,
    _reconcile_parsed_justificante,
    modelo_reconcile,
)
from .....application.modelo.reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)
from .....application.workflow.persistence import workflow_state_repository
from .....core import ABSENT_SECURE_OBJECT_REVISION_ID, Period
from .....domain.buckets.event import BucketEventType
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.repository import upsert_work_unit
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .....tests import FIXTURES_DIR
from .....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....inbound.justificante import parse_justificante
from ...storage import (
    MODELO_RECONCILIATION_RECORDS_NAMESPACE,
    SecureObjectRevisionConflictError,
)
from ..buckets import BucketEventHistoryRepository
from ..modelo_reconciliation import ModeloReconciliationRecordRepository, modelo_reconciliation_record_key
from ..modelos_work_units import WorkUnitCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_WORK_UNIT_TIMESTAMP = datetime(2026, 5, 28, 13, 30, 0, tzinfo=UTC)
_RECONCILED_AT = datetime(2026, 6, 1, 9, 15, 30, tzinfo=UTC)


# Seeded through a detached WorkflowState, never a repository read: the
# capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
# which a workflow-state repository construction would otherwise materialise
# first and collide with.
_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_PROFILE_ID,
    profile_overrides={"identity.tax_id": "00000000T"},
)


def _active_bucket_id() -> str:
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_work_unit(*, modelo: str = "130", filing_year: int = 2026, period: str = "1T") -> str:
    bucket_id = _active_bucket_id()
    typed_period = Period.from_year_and_code(filing_year, period)
    # The law-determined revision id, never a fabricated pin: the snapshot
    # resolver asserts the work unit's stored revision equals the one the law
    # selects, so a fabricated pin diverts reconcile into a snapshot_unavailable
    # advisory instead of reaching the branch under test.
    revision_id = (
        bundled_authority().snapshot(modelo, filing_year=filing_year, period=typed_period.registry_token).revision.id
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _reconcile(work_unit_id: str) -> None:
    modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
            actor="tester",
        ),
    )


def _fully_populated_record(
    *,
    work_unit_id: str,
    bucket_event_id: str,
    reconciled_at: datetime = _RECONCILED_AT,
) -> ModeloReconciliationRecord:
    """Build a record with EVERY defaultable field set to a non-default value.

    A save-drops-field regression is invisible when the fixture leaves a
    defaultable field at its default, because the reload re-defaults it and the
    equality still holds. So every default here is displaced: ``source_ref`` is
    non-empty, both containers carry real entries, the diff's ``diff_kind`` is
    the non-default ``CASILLA``, both of its value strings and both of its
    grounding tuples are populated, and the advisory's ``context`` mapping is
    non-empty.
    """
    return ModeloReconciliationRecord(
        bucket_event_id=bucket_event_id,
        bucket_id=_active_bucket_id(),
        work_unit_id=work_unit_id,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_ref="/operator/evidence/modelo-100-2024-declaracion.pdf",
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diffs=(
            ModeloReconciliationDiff(
                field_name="0604",
                work_unit_value=f"{Decimal('1234.56'):.2f}",
                evidence_value=f"{Decimal('1200.00'):.2f}",
                kind="casilla_value_mismatch",
                diff_kind=ModeloReconciliationDiffKind.CASILLA,
                legal_refs=("ley-35-2006:art-79", "ley-35-2006:art-80"),
                source_refs=("aeat-dr-100-2024-dictionary",),
            ),
            ModeloReconciliationDiff(
                field_name="total_ingresar",
                work_unit_value=f"{Decimal('500.00'):.2f}",
                evidence_value=f"{Decimal('999.99'):.2f}",
                kind="total_ingresar_mismatch",
                diff_kind=ModeloReconciliationDiffKind.TOTAL,
                legal_refs=("rd-439-2007:art-110",),
                source_refs=("aeat-dr-131-2024",),
            ),
        ),
        advisories=(
            ModeloReconciliationAdvisory(
                code="totals_not_reconciled",
                message="filed totals were not reconciled against the computed result",
                context={"reason": "no_persisted_revision", "modelo": "100"},
            ),
        ),
        actor="operator",
        reconciled_at=reconciled_at,
    )


def test_record_roundtrips_with_every_defaultable_field_populated_non_default() -> None:
    """A fully populated record survives save -> load with strict equality.

    Real encryption, real SQLite, real serializer. Strict equality across the
    boundary is the assertion: a field silently dropped on write, or re-defaulted
    on read, breaks it.
    """
    work_unit_id = _seed_work_unit()
    record = _fully_populated_record(work_unit_id=work_unit_id, bucket_event_id="e" * 64)
    repository = ModeloReconciliationRecordRepository()

    repository.save(record)
    loaded = repository.load(
        modelo_reconciliation_record_key(work_unit_id=work_unit_id, bucket_event_id="e" * 64),
    )

    assert loaded == record
    assert loaded is not None
    # Spelled out so a wholesale-equality pass over two identically-defaulted
    # models could not be mistaken for evidence that the containers survived.
    assert len(loaded.diffs) == 2
    assert loaded.diffs[0].legal_refs == ("ley-35-2006:art-79", "ley-35-2006:art-80")
    assert loaded.diffs[0].diff_kind is ModeloReconciliationDiffKind.CASILLA
    assert len(loaded.advisories) == 1
    assert loaded.advisories[0].context == {"reason": "no_persisted_revision", "modelo": "100"}
    assert loaded.source_ref.endswith("modelo-100-2024-declaracion.pdf")


def test_anti_tautology_stored_payload_with_a_deleted_field_refuses_on_load() -> None:
    """Deleting a field from the stored payload makes the read refuse.

    The proof that the roundtrip above is not tautological. The record is
    re-persisted through the production encryption path with one required field
    removed from the envelope's payload; the strict model must refuse it. The
    positive control re-persists the SAME bytes unmodified and loads cleanly, so
    a refusal caused by the mutation procedure itself rather than by the missing
    field could not be mistaken for the property under test.
    """
    work_unit_id = _seed_work_unit()
    record = _fully_populated_record(work_unit_id=work_unit_id, bucket_event_id="f" * 64)
    repository = ModeloReconciliationRecordRepository()
    objects = repository.secure_object_repository
    prepared = repository.to_secure_object_write(record)
    key = prepared.object_key

    def _persist(envelope_bytes: bytes) -> None:
        objects.save(
            namespace=MODELO_RECONCILIATION_RECORDS_NAMESPACE.namespace,
            object_key=key,
            classification=MODELO_RECONCILIATION_RECORDS_NAMESPACE.sensitivity,
            schema_version=MODELO_RECONCILIATION_RECORDS_NAMESPACE.schema_version,
            written_at=prepared.written_at,
            payload=envelope_bytes,
        )

    # Positive control: the untouched bytes load back to the same record.
    _persist(prepared.payload)
    assert repository.load(key) == record

    envelope = json.loads(prepared.payload.decode("utf-8"))
    del envelope["payload"]["verdict"]
    _persist(json.dumps(envelope).encode("utf-8"))

    with pytest.raises(ValidationError):
        repository.load(key)


def test_n_records_for_one_work_unit_persist_distinctly_and_all_read_back() -> None:
    """Several reconciliations of ONE work unit keep separate rows.

    The key derives from the co-written bucket event id, so distinct runs key
    distinctly. A key that collapsed them (a work-unit-only key, or one derived
    from a revision) would leave one row here.
    """
    work_unit_id = _seed_work_unit()
    repository = ModeloReconciliationRecordRepository()
    event_ids = ["a" * 64, "b" * 64, "c" * 64]

    for offset, event_id in enumerate(event_ids):
        repository.save(
            _fully_populated_record(
                work_unit_id=work_unit_id,
                bucket_event_id=event_id,
                reconciled_at=_RECONCILED_AT + timedelta(minutes=offset),
            ),
        )

    keys = {modelo_reconciliation_record_key(work_unit_id=work_unit_id, bucket_event_id=e) for e in event_ids}
    assert len(keys) == 3
    stored = tuple(repository.iter_records())
    assert {record.bucket_event_id for record in stored} == set(event_ids)

    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)
    assert [entry.event_id for entry in entries] == event_ids


def test_repeated_reconciliation_of_one_work_unit_records_every_run() -> None:
    """End-to-end: three real reconciliations of one work unit list as three.

    Drives the production verb rather than the repository, so it gates the key
    as the write path actually composes it.
    """
    work_unit_id = _seed_work_unit()

    _reconcile(work_unit_id)
    _reconcile(work_unit_id)
    _reconcile(work_unit_id)

    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)

    assert len(entries) == 3
    assert len({entry.event_id for entry in entries}) == 3
    assert [entry.reconciled_at for entry in entries] == sorted(entry.reconciled_at for entry in entries)


def test_reconciliation_with_no_persisted_revision_still_persists_and_reads_back() -> None:
    """A run that has no calculation revision at all is storable.

    Modelo 131 declares a ``reconciliation_total_casilla_ids`` map, so with no
    persisted revision the receipt-total reconcile emits exactly
    ``no_persisted_revision`` and still produces a report. The store must hold
    that run: this is the case a revision-derived key could not have stored,
    which is why the key derives from none.
    """
    work_unit_id = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    receipt = parse_justificante(MODELO_130_FIXTURE).model_copy(
        update={
            "modelo": "131",
            "ejercicio": "2024",
            "period": Period.from_year_and_code(2024, "1T"),
            "tax_id": "00000000T",
            "total_a_ingresar": Decimal("500.00"),
            "total_a_devolver": None,
        },
    )

    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    assert work_unit is not None
    report = _reconcile_parsed_justificante(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref="test://m131-no-revision",
        actor="operator",
        justificante=receipt,
    )

    assert "no_persisted_revision" in {
        advisory.context.get("reason") for advisory in report.advisories if advisory.code == "totals_not_reconciled"
    }
    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)
    assert len(entries) == 1
    stored = tuple(ModeloReconciliationRecordRepository().iter_records())
    assert len(stored) == 1
    advisory_reasons = {advisory.context.get("reason") for advisory in stored[0].advisories}
    assert "no_persisted_revision" in advisory_reasons


def test_grounded_diffs_survive_the_persist_and_read_back_cycle() -> None:
    """Stored grounding reaches the read API, never re-derived from the registry."""
    work_unit_id = _seed_work_unit()
    record = _fully_populated_record(work_unit_id=work_unit_id, bucket_event_id="d" * 64)
    ModeloReconciliationRecordRepository().save(record)

    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.diff_count == 2
    assert entry.diffs == record.diffs
    assert "ley-35-2006:art-79" in entry.diffs[0].legal_refs
    assert entry.diffs[0].source_refs == ("aeat-dr-100-2024-dictionary",)


def test_finalise_reconciliation_issues_exactly_one_batched_save() -> None:
    """The write path hands BOTH writes to a single ``save_many`` call.

    The companion runtime test below proves that a batch rolls back as a unit.
    That property only protects the reconcile write if the reconcile write
    actually is one batch, and no runtime observation distinguishes one batched
    save from two sequential ones on the success path — the rows look identical
    either way. So the composition is gated structurally, by reading the source
    of the function that performs it: exactly one ``save_many``, carrying a
    two-element tuple. Splitting it into two sequential saves reopens the
    desynchronisation window and reds this test, which a rollback test alone
    does not.
    """
    import ast
    import inspect
    from importlib import import_module

    reconcile_module = import_module("cadrumo.application.modelo.reconciliation")

    source = inspect.getsource(reconcile_module._finalise_reconciliation)
    tree = ast.parse(textwrap.dedent(source))
    batched_saves = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "save_many"
    ]

    assert len(batched_saves) == 1, "the record and the event must be committed in ONE batched save, not two"
    (batched,) = batched_saves
    assert len(batched.args) == 1
    written = batched.args[0]
    assert isinstance(written, ast.Tuple)
    assert len(written.elts) == 2, "the one batch must carry both the event-catalogue write and the record write"
    # Nothing else may commit inside this function: a stray single-row save
    # would be a second transaction wearing a different name.
    stray_saves = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "save"
    ]
    assert stray_saves == []


def test_a_failed_write_in_the_batch_rolls_the_whole_batch_back() -> None:
    """A failure on the record write rolls the co-written event write back.

    The runtime half of the atomicity proof: because both writes go to one
    :meth:`~adapters.persistence.storage.SecureObjectRepository.save_many` they
    share a single session scope. Here the record write carries an absent-row
    compare-and-swap guard against a key that already exists, which fails INSIDE
    that session; the event-catalogue write queued ahead of it must not survive.
    """
    work_unit_id = _seed_work_unit()
    _reconcile(work_unit_id)

    catalogue_repo = BucketEventHistoryRepository()
    objects = catalogue_repo.secure_object_repository
    record_repo = ModeloReconciliationRecordRepository(objects=objects)
    stored = tuple(record_repo.iter_records())
    assert len(stored) == 1
    existing = stored[0]

    catalogue = catalogue_repo.load()
    events_before = catalogue.for_bucket(
        _active_bucket_id(),
        event_types=(BucketEventType.MODELO_RECONCILED,),
    )
    assert len(events_before) == 1

    from .....domain.buckets.event import BucketEvent, BucketEventObjectType, derive_bucket_event_id
    from .....domain.buckets.event_repository import append_bucket_event

    second_at = _RECONCILED_AT + timedelta(hours=1)
    payload = {"work_unit_id": work_unit_id, "verdict": ModeloReconciliationVerdict.MATCHES.value, "diffs": "0"}
    second_event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=_active_bucket_id(),
            event_type=BucketEventType.MODELO_RECONCILED,
            occurred_at=second_at,
            actor="tester",
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id=work_unit_id,
            payload=payload,
        ),
        bucket_id=_active_bucket_id(),
        event_type=BucketEventType.MODELO_RECONCILED,
        occurred_at=second_at,
        actor="tester",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=work_unit_id,
        payload_version=1,
        payload=payload,
    )
    advanced_catalogue = append_bucket_event(catalogue, second_event)

    # The record write addresses the row that already exists while asserting it
    # is absent, so it raises after the catalogue write has been applied in the
    # same session.
    doomed_record_write = record_repo.to_secure_object_write(
        existing,
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )

    with pytest.raises(SecureObjectRevisionConflictError):
        objects.save_many(
            (
                catalogue_repo.to_secure_object_write(advanced_catalogue),
                doomed_record_write,
            ),
        )

    events_after = (
        BucketEventHistoryRepository()
        .load()
        .for_bucket(
            _active_bucket_id(),
            event_types=(BucketEventType.MODELO_RECONCILED,),
        )
    )
    assert len(events_after) == 1
    assert {event.event_id for event in events_after} == {event.event_id for event in events_before}


def test_repository_binds_the_registered_namespace_contract() -> None:
    """The repository restates no namespace constant of its own.

    Sensitivity, schema version and namespace all read off the registered
    definition, so the registry-wide schema-lineage gate (which binds every
    registered namespace to the from-birth durability floor and a complete
    upgrade chain) governs this store too rather than being sidestepped by a
    local literal.
    """
    definition = MODELO_RECONCILIATION_RECORDS_NAMESPACE

    assert ModeloReconciliationRecordRepository.namespace == definition.namespace
    assert ModeloReconciliationRecordRepository.schema_version == definition.schema_version
    assert ModeloReconciliationRecordRepository.sensitivity is definition.sensitivity
    assert ModeloReconciliationRecordRepository.payload_type is ModeloReconciliationRecord
