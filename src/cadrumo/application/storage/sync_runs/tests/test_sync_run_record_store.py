"""Real-behavior tests for the encrypted sync-run provenance store.

Every test drives the real stack: real ephemeral master-key provider, real
per-bucket SQLite, real serializer, real production write and read paths. No
doubles, because a double returning what the test expects is the canonical
false-positive signal for a persistence boundary.

Four properties are correctness risks rather than matters of effort, so each
carries a gate here rather than a review:

* Every defaultable field must survive the round trip carrying a NON-default
  value. A fixture that leaves defaults in place cannot distinguish a field that
  round-tripped from one the save dropped and the load re-defaulted.
* A corrupted on-disk payload must be REFUSED rather than silently repaired.
  Without that proof the round trip above could pass with the boundary broken.
* The key must admit N runs per surface without collapsing them. A key that
  collapsed runs would make the last sync the only sync, destroying exactly the
  provenance this store exists to carry.
* The record and its bucket event must land together, because the record is
  keyed on the event's own id -- an identity that means nothing if either can
  land alone.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from .....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from .....adapters.persistence.storage.secure_object_namespaces import SYNC_RUN_RECORDS_NAMESPACE
from .....core.directory_scan import scan_directory
from .....core.sync_surface import SyncSurface
from .....domain.buckets.event import BucketEventType
from .....tests.profile_capsule import open_test_profile_session
from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_minimal_profile
from ....workflow.persistence import workflow_state_repository
from .._persist import record_sync_run
from .._records import (
    SyncRunCoverage,
    SyncRunRecord,
    bounded_scope_description,
    coverage_of,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_COMPLETED_AT = datetime(2026, 8, 10, 9, 30, tzinfo=UTC)

#: A scope long enough to exercise the summariser rather than the pass-through
#: arm. Proving the bound with a short value would prove nothing: the field
#: refuses past 256 characters, and the default filed sweep resolves to every
#: bundled modelo, so the summariser is on the ORDINARY path rather than an
#: edge one.
_WIDE_SCOPE_MODELOS = tuple(f"{100 + index}" for index in range(120))


@pytest.fixture
def active_profile(tmp_path: Path) -> Iterator[str]:
    """Bind a real isolated encrypted profile bucket for one test."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(profile_id=_BUCKET_ID)
        bucket_id = workflow_state_repository().load().active_profile_bucket_id()
        assert bucket_id is not None
        yield bucket_id


def test_every_defaultable_field_survives_the_round_trip_carrying_a_non_default_value(
    active_profile: str,
) -> None:
    """A strict round trip through the real encrypted store, no field left at its default.

    ``resolved_scope``, ``unit_count`` and ``divergence_count`` all carry
    defaults, so each is populated with a value the default could not produce.
    A save that dropped one and a load that re-defaulted it would be invisible
    against a fixture that used the defaults.
    """
    record = SyncRunRecord(
        bucket_event_id="a" * 64,
        bucket_id=active_profile,
        surface=SyncSurface.CALC_SHEETS_EXPORT,
        resolved_scope="303 2026-1T",
        succeeded=False,
        unit_count=17,
        divergence_count=5,
        completed_at=_COMPLETED_AT,
    )
    repository = SyncRunRecordRepository()
    repository.save(record)

    loaded = repository.load(repository.extract_identifier(record))

    assert loaded == record, "the record must survive the encrypted boundary under strict equality"
    assert loaded is not None
    assert loaded.resolved_scope == "303 2026-1T"
    assert loaded.unit_count == 17
    assert loaded.divergence_count == 5
    assert loaded.succeeded is False


def test_a_payload_with_a_deleted_field_is_refused_rather_than_re_defaulted(
    active_profile: str,
) -> None:
    """Anti-tautology proof: corrupt the stored payload and require a refusal.

    Without this, the round trip above could pass while the boundary silently
    reconstructed missing fields from defaults -- which is precisely how a
    save-drops / load-re-defaults regression hides.
    """
    record = SyncRunRecord(
        bucket_event_id="b" * 64,
        bucket_id=active_profile,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope="130 2025-2026",
        succeeded=True,
        unit_count=9,
        divergence_count=2,
        completed_at=_COMPLETED_AT,
    )
    repository = SyncRunRecordRepository()
    repository.save(record)
    identifier = repository.extract_identifier(record)

    objects = repository.secure_object_repository
    stored = objects.load(
        SYNC_RUN_RECORDS_NAMESPACE.namespace,
        identifier,
        expected_class=SYNC_RUN_RECORDS_NAMESPACE.sensitivity,
        max_supported_version=SYNC_RUN_RECORDS_NAMESPACE.schema_version,
    )
    assert stored is not None
    document = json.loads(stored.payload)
    del document["payload"]["completed_at"]
    objects.save(
        namespace=SYNC_RUN_RECORDS_NAMESPACE.namespace,
        object_key=identifier,
        classification=SYNC_RUN_RECORDS_NAMESPACE.sensitivity,
        schema_version=SYNC_RUN_RECORDS_NAMESPACE.schema_version,
        written_at=_COMPLETED_AT,
        payload=json.dumps(document).encode("utf-8"),
        expected_revision_id=stored.revision_id,
    )

    with pytest.raises(ValidationError):
        repository.load(identifier)


def test_two_runs_over_one_surface_do_not_collapse(active_profile: str) -> None:
    """N records per surface. A collapsing key would make the last sync the only sync.

    This is the store's whole reason for existing: the phase it serves is
    last-sync PROVENANCE, and a key scoped to the surface alone would overwrite
    the history rather than extend it.
    """
    first = record_sync_run(
        bucket_id=active_profile,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope="303 2025-2025",
        succeeded=True,
        coverage=SyncRunCoverage(unit_count=3, divergence_count=0),
        completed_at=_COMPLETED_AT,
        repository=SyncRunRecordRepository(),
    )
    second = record_sync_run(
        bucket_id=active_profile,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope="303 2026-2026",
        succeeded=False,
        coverage=SyncRunCoverage(unit_count=1, divergence_count=1),
        completed_at=_COMPLETED_AT + timedelta(hours=1),
        repository=SyncRunRecordRepository(),
    )

    assert first.bucket_event_id != second.bucket_event_id
    repository = SyncRunRecordRepository()
    stored_ids = set(repository.iter_ids())
    assert repository.extract_identifier(first) in stored_ids
    assert repository.extract_identifier(second) in stored_ids, "the second run must not overwrite the first"


def test_the_record_and_its_bucket_event_land_together(active_profile: str) -> None:
    """The pair is co-written, and the record is keyed on the event's own id.

    That identity is what joins the two surfaces without a cross-reference field
    that could drift, and it only means anything if neither can land alone.
    """
    record = record_sync_run(
        bucket_id=active_profile,
        surface=SyncSurface.CALC_SHEETS_EXPORT,
        resolved_scope="100 2026-0A",
        succeeded=True,
        coverage=SyncRunCoverage(unit_count=42, divergence_count=1),
        completed_at=_COMPLETED_AT,
        repository=SyncRunRecordRepository(),
    )

    # `.events` is a Mapping keyed by event id, not a sequence of events, so the
    # record's own id is a direct lookup rather than a scan.
    events = BucketEventHistoryRepository().load().events
    assert record.bucket_event_id in events, "the event the record names must exist in the history"
    event = events[record.bucket_event_id]
    assert event.event_type is BucketEventType.SYNC_RUN_CALC_SHEETS_EXPORT_COMPLETED
    assert event.payload["divergence_count"] == "1"

    loaded = SyncRunRecordRepository().load(SyncRunRecordRepository().extract_identifier(record))
    assert loaded is not None, "the record must be present alongside the event it names"


def test_a_scope_too_wide_to_enumerate_is_summarised_rather_than_truncated() -> None:
    """A truncated enumeration reads as a COMPLETE list of a smaller set.

    That is the same lie a partial sweep tells when it reads as a full one, and
    stopping that lie is the entire reason this store exists -- so an oversized
    scope collapses to a count and a range instead of to a prefix. The wide case
    is the ORDINARY one: a filed sweep with no explicit modelo list resolves to
    every bundled modelo.
    """
    enumerated = ",".join(_WIDE_SCOPE_MODELOS)
    assert len(enumerated) > 256, "the fixture must actually exceed the field bound"

    described = bounded_scope_description(_WIDE_SCOPE_MODELOS, suffix="2023-2025")

    assert len(described) <= 256
    assert described.startswith(f"{len(_WIDE_SCOPE_MODELOS)} modelos")
    assert not described.startswith(_WIDE_SCOPE_MODELOS[0] + ","), "a prefix would read as a complete short list"
    # The summary must survive the field it was built for.
    record = SyncRunRecord(
        bucket_event_id="c" * 64,
        bucket_id=_BUCKET_ID,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope=described,
        succeeded=True,
        unit_count=len(_WIDE_SCOPE_MODELOS),
        divergence_count=0,
        completed_at=_COMPLETED_AT,
    )
    assert record.resolved_scope == described


def test_more_divergences_than_units_reached_is_refused() -> None:
    """A unit the run never reached cannot have been found to diverge.

    The refusal fires at construction because the only way to produce the state
    is a caller counting one of the two against the wrong population -- which is
    exactly the error a truncated sweep invites.
    """
    with pytest.raises(ValidationError, match="cannot have diverged"):
        SyncRunRecord(
            bucket_event_id="d" * 64,
            bucket_id=_BUCKET_ID,
            surface=SyncSurface.FILED_DECLARATIONS,
            resolved_scope="303 2026-1T",
            succeeded=True,
            unit_count=2,
            divergence_count=3,
            completed_at=_COMPLETED_AT,
        )


class _Run:
    """A real coverage source: one object that answers for one population.

    Not a stand-in for a collaborator the code under test would otherwise call.
    The protocol IS "an object that knows both numbers", so an object knowing
    both numbers is the genuine article rather than a double of one.
    """

    def __init__(self, *, reached: int, divergences: tuple[str, ...]) -> None:
        self._reached = reached
        self._divergences = divergences

    @property
    def reached_count(self) -> int:
        return self._reached

    @property
    def divergences(self) -> tuple[str, ...]:
        return self._divergences


def test_coverage_reads_both_counts_off_one_source() -> None:
    """The derivation is the guarantee: two numbers, one object, no second read."""
    coverage = coverage_of(_Run(reached=4, divergences=("303-1T", "303-2T")))

    assert coverage.unit_count == 4
    assert coverage.divergence_count == 2


def test_a_source_claiming_more_divergences_than_it_reached_is_refused() -> None:
    """The backstop still bites when a source lies about its own population.

    Deriving from one object is what stops a CALLER pairing two populations. It
    cannot stop an object that misreports itself, so the bound survives on the
    coverage model as well -- and this is the half that proves it is not
    decorative.
    """
    with pytest.raises(ValidationError, match="cannot have diverged"):
        coverage_of(_Run(reached=1, divergences=("303-1T", "303-2T")))


def test_every_production_run_record_derives_its_coverage_from_a_source() -> None:
    """The floor: nothing in production hand-pairs the two counts.

    Making the invalid pair unrepresentable protects the path THROUGH
    ``coverage_of``. It says nothing about a future call site that builds a
    coverage from two literals, or constructs a record directly. So this walks
    production and requires every ``record_sync_run`` call to pass a ``coverage``
    argument that is a ``coverage_of(...)`` call.

    A structural assertion pinned to the one call site we know about would go
    green the moment a second writer appeared -- which is precisely how the
    original defect arrived. This asserts a property of the whole tree instead.

    The non-empty floor below is load-bearing: a walk that resolved no call
    sites at all would pass this test while proving nothing, which is the
    failure mode that makes a green gate worse than no gate.
    """
    package_root = Path(__file__).resolve().parents[4]
    offenders: list[str] = []
    call_sites: list[str] = []

    for module in scan_directory(package_root, pattern="*.py", recursive=True):
        if "tests" in module.parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "record_sync_run":
                continue
            where = f"{module.relative_to(package_root).as_posix()}:{node.lineno}"
            call_sites.append(where)
            passed = {keyword.arg for keyword in node.keywords}
            if "unit_count" in passed or "divergence_count" in passed:
                offenders.append(f"{where} passes raw counts instead of a derived coverage")
                continue
            derived = next(
                (keyword.value for keyword in node.keywords if keyword.arg == "coverage"),
                None,
            )
            is_derived = (
                isinstance(derived, ast.Call)
                and getattr(derived.func, "id", getattr(derived.func, "attr", None)) == "coverage_of"
            )
            if not is_derived:
                offenders.append(f"{where} builds its coverage without coverage_of")

    assert call_sites, (
        "no production record_sync_run call site was found, so this gate proved nothing; "
        "the walk or the verb name has drifted"
    )
    assert not offenders, "coverage must be derived from one source at every production writer: " + "; ".join(offenders)


def test_a_naive_completion_instant_is_refused() -> None:
    """Two runs over one surface must be orderable against each other.

    A bare ``datetime`` would accept a naive or ``+01:00`` value, and a
    Madrid-local instant read back as UTC in a store whose entire purpose is
    answering when something last happened.
    """
    with pytest.raises(ValidationError):
        SyncRunRecord(
            bucket_event_id="e" * 64,
            bucket_id=_BUCKET_ID,
            surface=SyncSurface.FILED_DECLARATIONS,
            resolved_scope="303 2026-1T",
            succeeded=True,
            unit_count=1,
            divergence_count=0,
            completed_at=datetime(2026, 8, 10, 9, 30),
        )
